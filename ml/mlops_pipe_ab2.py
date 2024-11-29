from datetime import datetime
import os
import logging
import mlflow
from mlflow.tracking import MlflowClient
from pyspark.ml import Pipeline
from pyspark.ml.classification import LogisticRegression
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.feature import StandardScaler, VectorAssembler, StringIndexer, OneHotEncoder
from pyspark.ml.tuning import ParamGridBuilder, TrainValidationSplit
from pyspark.sql import DataFrame
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, hour, udf
from pyspark.sql.types import IntegerType
from scipy.stats import ttest_ind
from typing import Tuple


BUCKET = "s3a://mlops-daria-bucket/"
DATASET_NAME = "cleaned_dataset_sample.parquet"
RANDOM_STATE = 29
BOOTSTRAP_ITERATIONS = 10
REGISTRY_SERVER_HOST = "89.169.175.116"
TRACKING_SERVER_HOST = "89.169.175.116"

logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logger = logging.getLogger()


def time_bin(hour):
    if 6 <= hour < 12:
        return 1  # Утро
    elif 12 <= hour < 18:
        return 2  # День
    elif 18 <= hour < 24:
        return 3  # Вечер
    else:
        return 4  # Ночь

def transform_data(df_cleaned: DataFrame, is_train: bool) -> DataFrame:

    if is_train:
        # Downsample the data, because there is a substantial imbalance in target column values
        df_majority = df_cleaned.filter(col("tx_fraud") == 0)
        df_minority = df_cleaned.filter(col("tx_fraud") == 1)

        df_majority_downsampled = df_majority.sample(withReplacement=False,
                                                     fraction=df_minority.count() / df_majority.count())
        df_cleaned = df_majority_downsampled.union(df_minority)

    # EDA showed obvious difference in target variable between samples with major value terminal_id=0 and others,
    # so it's a valuable feature
    # df.where(col("is_zero_terminal") == 0).agg({"tx_fraud": "avg"}).show() # this equals 0.0577
    # df.where(col("is_zero_terminal") == 1).agg({"tx_fraud": "avg"}).show() # this equals 0.0927
    transformed_df = df_cleaned.withColumn("is_zero_terminal", when(col("terminal_id") == "0", 1).otherwise(0))

    # Using time from timestamp column in bins as a new attribute
    time_bin_udf = udf(time_bin, IntegerType())
    transformed_df = transformed_df.withColumn("time_of_day", time_bin_udf(hour(col("tx_datetime"))))

    return transformed_df


def stratified_train_test_split(df: DataFrame, test_size=0.2) -> Tuple[DataFrame, DataFrame]:
    zeros = df.filter(df["tx_fraud"] == 0)
    ones = df.filter(df["tx_fraud"] == 1)

    train_0, test_0 = zeros.randomSplit([1 - test_size, test_size], seed=RANDOM_STATE)
    train_1, test_1 = ones.randomSplit([1 - test_size, test_size], seed=RANDOM_STATE)

    train = train_0.union(train_1)
    test = test_0.union(test_1)

    return train, test


def get_pipeline() -> Pipeline:
    num_features = ["tx_amount", "tx_time_seconds", "is_zero_terminal"]
    cat_feature = "time_of_day"

    indexer = StringIndexer(inputCol=cat_feature, outputCol=cat_feature + "_index")
    oh_encoder = OneHotEncoder(inputCol=cat_feature + "_index", outputCol=cat_feature + "_encoded")

    all_features = num_features + [cat_feature + "_encoded"]

    assembler = VectorAssembler(inputCols=all_features, outputCol="features")
    scaler = StandardScaler(withMean=True, inputCol="features", outputCol="scaled_features")
    lr = LogisticRegression(featuresCol="scaled_features", labelCol="tx_fraud")
    pipeline = Pipeline(stages=[indexer, oh_encoder, assembler, scaler, lr])

    return pipeline


def main():
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = "https://storage.yandexcloud.net"
    os.environ["AWS_ACCESS_KEY_ID"] = "mykey"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "mykey"

    mlflow.set_tracking_uri(f"http://{TRACKING_SERVER_HOST}:5000")
    mlflow.set_registry_uri(f"http://{REGISTRY_SERVER_HOST}:5000")
    logger.info("tracking URI: %s", {mlflow.get_tracking_uri()})

    logger.info("Creating Spark Session ...")
    spark = (
        SparkSession
        .builder
        .appName("Otus-hometask")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    client = MlflowClient()

    df = spark.read.parquet(BUCKET + DATASET_NAME)
    df_train, df_test = stratified_train_test_split(df, test_size=0.2)
    
    df_train = transform_data(df_train, is_train=True)
    df_test = transform_data(df_test, is_train=False)

    experiment = mlflow.set_experiment("mlops_experiment_2")
    experiment_id = experiment.experiment_id
    run_name = f"run_{datetime.now()}"

    if len(client.search_runs(experiment_id, max_results=1)) < 1:
        is_first = True
    else:
        is_first = False
        best_run = client.search_runs(experiment_id, order_by=["metrics.roc_auc_mean DESC"], max_results=1)[0]

    with mlflow.start_run(run_name=run_name, experiment_id=experiment_id):

        pipeline = get_pipeline()
        lr = pipeline.getStages()[-1]

        param_grid = (
            ParamGridBuilder()
            .addGrid(lr.regParam, [0, 0.1, 0.5])
            .addGrid(lr.maxIter, [100, 500, 1000])
            .build()
        )

        evaluator = BinaryClassificationEvaluator(labelCol="tx_fraud")
        
        tvs = TrainValidationSplit(
            estimator=pipeline,
            estimatorParamMaps=param_grid,
            evaluator=evaluator,
            trainRatio=0.8,
            parallelism=3,
            seed=RANDOM_STATE
        )

        model = tvs.fit(df_train)
        
        best_regParam = model.bestModel.stages[-1].getRegParam()
        best_maxIter = model.bestModel.stages[-1].getMaxIter()

        mlflow.log_param('optimal_regParam', best_regParam)
        mlflow.log_param('optimal_maxIter', best_maxIter)

        predictions = model.transform(df_test)
        current_metrics = []

        # Running bootstrap samples evaluation
        for _ in range(BOOTSTRAP_ITERATIONS):
            sample = predictions.sample(withReplacement=True, fraction=0.2, seed=RANDOM_STATE)
            roc_auc = evaluator.evaluate(sample)

            mlflow.log_metric("roc_auc", roc_auc)
            current_metrics.append(roc_auc)
        
        # Mean of metrics
        roc_auc_mean = sum(current_metrics) / len(current_metrics)
        mlflow.log_metric("roc_auc_mean", roc_auc_mean)

        # If it's the first run then just save the model
        if is_first:
            mlflow.spark.log_model(model, "mlflow_data_experiment_2")
        # If it's not, and the mean is higher than in the best run so far, then do 2-samples independent t-test
        # to check if the change is significant 
        else:
            if roc_auc_mean > best_run.data.metrics.get("roc_auc_mean", 0):
                best_run_id = best_run.info.run_id
                best_metrics = []

                for best_metric in client.get_metric_history(best_run_id, "roc_auc"):
                    best_metrics.append(best_metric.value)

                pvalue = ttest_ind(best_metrics, current_metrics).pvalue
                mlflow.log_metric("p-value", pvalue)

                # If the new mean is significantly higher than the previous one, save the model
                alpha = 0.05
                if pvalue < alpha:
                    mlflow.spark.log_model(model, "mlflow_model_experiment_2")

    spark.stop()


if __name__ == "__main__":
    main()
