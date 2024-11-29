from datetime import datetime
import os
import logging
import mlflow
from pyspark.ml import Pipeline
from pyspark.ml.classification import LogisticRegression
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.feature import StandardScaler, VectorAssembler, StringIndexer, OneHotEncoder
from pyspark.ml.tuning import ParamGridBuilder, TrainValidationSplit
from pyspark.sql import DataFrame
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, hour, udf
from pyspark.sql.types import IntegerType


BUCKET = "s3a://mlops-daria-bucket/"
DATASET_NAME = "cleaned_dataset_sample.parquet"
RANDOM_STATE = 29
REGISTRY_SERVER_HOST = "89.169.175.116"
TRACKING_SERVER_HOST = "89.169.175.116"

logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logger = logging.getLogger()

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

    df = spark.read.parquet(BUCKET + DATASET_NAME)
  
    experiment = mlflow.set_experiment("mlflow_data_experiment")
    experiment_id = experiment.experiment_id
    run_name = f"run_{datetime.now()}"

    with mlflow.start_run(run_name=run_name, experiment_id=experiment_id):

        pipeline = get_pipeline()
        lr = pipeline.getStages()[-1]

        train, test = df.randomSplit([0.8, 0.2], seed=RANDOM_STATE)

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

        logger.info("Fitting new inference pipeline ...")

        model = tvs.fit(train)

        run_id = mlflow.active_run().info.run_id
        logger.info(f"Logging optimal parameters to MLflow run {run_id} ...")
        
        best_regParam = model.bestModel.stages[-1].getRegParam()
        best_maxIter = model.bestModel.stages[-1].getMaxIter()

        mlflow.log_param('optimal_regParam', best_regParam)
        mlflow.log_param('optimal_maxIter', best_maxIter)

        logger.info("Scoring the model ...")

        predictions = model.transform(test)
        roc_auc = evaluator.evaluate(predictions)

        logger.info(f"Logging metrics to MLflow run {run_id} ...")

        mlflow.log_metric("roc_auc", roc_auc)

        mlflow.spark.save_model(model, "mlflow_data_model")
        logger.info("Exporting/logging pipline ...")
        mlflow.spark.log_model(model, "mlflow_data_model")
    
    spark.stop()

if __name__ == "__main__":
    main()
