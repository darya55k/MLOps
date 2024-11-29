import os
import time
import logging

from kafka import KafkaConsumer, KafkaProducer
import mlflow
import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, when, hour, udf, floor
from pyspark.sql.types import (StructType, StructField, LongType,
                               IntegerType, FloatType, TimestampType)

# Настраиваем логирование для лучшего отслеживания
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRACKING_SERVER_HOST = "89.169.175.116"
MLFLOW_MODEL_RUN_ID = "8dfe495ee17348e1b9ae718477beed36"
PRODUCER_METRIC_RUN_ID = "d4330af6cb094be98b645c3ebb2fa057"
MODEL_URI = "s3://airflow-dz4/mlflow-artifacts/2/8dfe495ee17348e1b9ae718477beed36/artifacts/mlflow_data_model"
BOOTSTRAP_SERVERS = [
    'rc1a-9912bk99ei6nptmg.mdb.yandexcloud.net:9091',
    'rc1b-8bgoe5q76dij6dhh.mdb.yandexcloud.net:9091',
    'rc1d-98kkqdi64ek3d44h.mdb.yandexcloud.net:9091'
]

# Проверка подключения к Kafka
def check_kafka_connection(consumer):
    try:
        partitions = consumer.partitions_for_topic('input')
        if partitions:
            logger.info("Successfully connected to Kafka topic 'input' with partitions: %s", partitions)
        else:
            logger.warning("Connected to Kafka but no partitions found for topic 'input'.")
    except Exception as e:
        logger.error("Failed to connect to Kafka topic 'input': %s", e)


def time_bin(hour):
    
    if 6 <= hour < 12:
        return 1  # Утро
    elif 12 <= hour < 18:
        return 2  # День
    elif 18 <= hour < 24:
        return 3  # Вечер
    else:
        return 4  # Ночь


def clean_dataset(df):
    df = df.dropDuplicates(["transaction_id"])
    df = df.withColumn("customer_id", when(col("customer_id") < 0, col("customer_id") * -1).otherwise(col("customer_id")))
    df = df.withColumn("tx_time_days", when(floor(col("tx_time_seconds") / 86400) != col("tx_time_days"),
                                            floor(col("tx_time_seconds") / 86400)).otherwise(col("tx_time_days")))
    return df


def transform_data(df_cleaned: DataFrame, is_train: bool) -> DataFrame:

    if is_train:
        # Downsample the data, because there is a substantial imbalance in target column values
        df_majority = df_cleaned.filter(col("tx_fraud") == 0)
        df_minority = df_cleaned.filter(col("tx_fraud") == 1)

        df_majority_downsampled = df_majority.sample(withReplacement=False,
                                                     fraction=df_minority.count() / df_majority.count())
        df_cleaned = df_majority_downsampled.union(df_minority)

    transformed_df = df_cleaned.withColumn("is_zero_terminal", when(col("terminal_id") == "0", 1).otherwise(0))

    # Using time from timestamp column in bins as a new attribute
    time_bin_udf = udf(time_bin, IntegerType())
    transformed_df = transformed_df.withColumn("time_of_day", time_bin_udf(hour(col("tx_datetime"))))

    return transformed_df


def main():
    restart = False  
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = "https://storage.yandexcloud.net"
    

    mlflow.set_tracking_uri(f"http://{TRACKING_SERVER_HOST}:5000")

    spark = (
        SparkSession
        .builder
        .appName("Otus-hometask")
        .config("spark.hadoop.fs.s3a.endpoint", "https://storage.yandexcloud.net")
        .config("spark.hadoop.fs.s3a.access.key", os.environ["AWS_ACCESS_KEY_ID"])
        .config("spark.hadoop.fs.s3a.secret.key", os.environ["AWS_SECRET_ACCESS_KEY"])
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )

    consumer = KafkaConsumer(
        'input',
        bootstrap_servers=BOOTSTRAP_SERVERS,
        security_protocol="SASL_SSL",
        sasl_mechanism="SCRAM-SHA-512",
        sasl_plain_username='consumer',
        sasl_plain_password='dak201455',
        ssl_cafile="/usr/local/share/ca-certificates/Yandex/YandexInternalRootCA.crt",
        fetch_min_bytes=100000,
        fetch_max_wait_ms=3000,
        session_timeout_ms=30000,
        group_id='consume-to-predict',
        auto_offset_reset='earliest',  # Читает с самого начала, если нет смещения
        enable_auto_commit=True
    )

    # Проверка подключения к Kafka
    check_kafka_connection(consumer)

    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        security_protocol="SASL_SSL",
        sasl_mechanism="SCRAM-SHA-512",
        sasl_plain_username='producer',
        sasl_plain_password='dak201455',
        ssl_cafile="/usr/local/share/ca-certificates/Yandex/YandexInternalRootCA.crt",
        request_timeout_ms=120000,
        max_block_ms=120000
    )

    # Типы данных и схема
    type_mapping = {
        "transaction_id": int,
        "tx_datetime": 'datetime64[ns]',
        "customer_id": int,
        "terminal_id": int,
        "tx_amount": float,
        "tx_time_seconds": int,
        "tx_time_days": int,
        "tx_fraud": int,
        "tx_fraud_scenario": int,
    }

    column_names = ["transaction_id", "tx_datetime", "customer_id", "terminal_id",
                    "tx_amount", "tx_time_seconds", "tx_time_days", "tx_fraud", "tx_fraud_scenario"]

    schema = StructType([
        StructField("transaction_id", IntegerType(), True),
        StructField("tx_datetime", TimestampType(), True),
        StructField("customer_id", IntegerType(), True),
        StructField("terminal_id", LongType(), True),
        StructField("tx_amount", FloatType(), True),
        StructField("tx_time_seconds", IntegerType(), True),
        StructField("tx_time_days", IntegerType(), True),
        StructField("tx_fraud", IntegerType(), True),
        StructField("tx_fraud_scenario", IntegerType(), True),
    ])

    model = mlflow.spark.load_model(MODEL_URI)

    while True:
        msg_pack = consumer.poll(1000, max_records=30000)
        logger.info("Проверка новых сообщений в Kafka...")

        if len(msg_pack) == 0:
            logger.info("Новых сообщений нет.")
            time.sleep(5)  # Ожидание перед следующей проверкой
            continue

        start_time = time.time()

        data = []
        for tp, lines in msg_pack.items():
            for line in lines:
                data.append(line.value.decode("utf-8").split(","))

        pandas_df = pd.DataFrame(data, columns=column_names)
        # Очистка данных
        pandas_df["terminal_id"] = pandas_df["terminal_id"].fillna("0")
        pandas_df.dropna(subset="tx_datetime", inplace=True)

        # Преобразование типов
        for column, dtype in type_mapping.items():
            try:
                pandas_df[column] = pandas_df[column].astype(dtype)
            except ValueError:
                pandas_df[column] = pandas_df[column].str.replace("", "0")
                try:
                    pandas_df[column] = pandas_df[column].astype(dtype)
                except ValueError:
                    restart = True
                    break
        if restart:
            continue    

        spark_df = spark.createDataFrame(pandas_df, schema=schema)
        spark_df = clean_dataset(spark_df)
        spark_df = transform_data(spark_df, is_train=False)
        predictions = model.transform(spark_df)
        
        predictions_list = predictions.select("prediction").rdd.flatMap(lambda x: x).collect()
        predictions_str = "\n".join(map(str, predictions_list))
        
        producer.send('predictions', predictions_str.encode("utf-8"))
        producer.flush()
        
        end_time = time.time()
        transactions_per_second = len(data) / (end_time - start_time)
        mlflow.log_metric("transactions_per_second_processed_and_returned_2", transactions_per_second, run_id=PRODUCER_METRIC_RUN_ID)
    

if __name__ == "__main__":
    main()
