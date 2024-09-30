import uuid
from datetime import datetime, timedelta
from airflow import DAG, settings
from airflow.models import Connection, Variable
from airflow.utils.trigger_rule import TriggerRule
from airflow.operators.python import PythonOperator
from airflow.providers.yandex.operators.yandexcloud_dataproc import (
    DataprocCreateClusterOperator,
    DataprocCreatePysparkJobOperator,
    DataprocDeleteClusterOperator,

)


# Common settings for your environment
YC_DP_FOLDER_ID = 'b1gi1i2cfgl8sb9tnjig'
YC_DP_SUBNET_ID = 'e2lhllitsg0u9khnd5u7'
YC_DP_SA_ID = 'ajeqslt3me74kubhltpk'
YC_DP_AZ = 'ru-central1-b'
YC_DP_SSH_PUBLIC_KEY = Variable.get("SSH_PUBLIC")
YC_DP_GROUP_ID = 'enpe1i84pncj2in8iull'
AWS_ACCESS_KEY = Variable.get("S3_KEY_ID")
AWS_SECRET_KEY = Variable.get("S3_SECRET_KEY")


# Settings for S3 buckets
YC_INPUT_DATA_BUCKET = 'airflow-dz4/airflow/'  # YC S3 bucket for input data
YC_SOURCE_BUCKET = 'airflow-dz4'     # YC S3 bucket for pyspark source files
YC_DP_LOGS_BUCKET = 'airflow-dz4/airflow_logs/'      # YC S3 bucket for Data Proc cluster logs



# Создание подключения для Object Storage
session = settings.Session()
ycS3_connection = Connection(
    conn_id='yc-s3',
    conn_type='s3',
    host='https://storage.yandexcloud.net/',
    extra={
        "aws_access_key_id": AWS_ACCESS_KEY,
        "aws_secret_access_key": AWS_SECRET_KEY,
        "host": "https://storage.yandexcloud.net/"
    }
)


if not session.query(Connection).filter(Connection.conn_id == ycS3_connection.conn_id).first():
    session.add(ycS3_connection)
    session.commit()

ycSA_connection = Connection(
    conn_id='yc-SA',
    conn_type='yandexcloud',
    extra={
        "extra__yandexcloud__public_ssh_key": Variable.get("DP_PUBLIC_SSH_KEY"),
        "extra__yandexcloud__service_account_json_path": Variable.get("DP_SA_PATH") # путь к вашему файлу с секретками сервисного аккаунта
    }
)

if not session.query(Connection).filter(Connection.conn_id == ycSA_connection.conn_id).first():
    session.add(ycSA_connection)
    session.commit()


# Настройки DAG
with DAG(
        dag_id = 'DATA_PREPROCESS_2',
        #schedule_interval='@hourly',
        start_date=datetime(year = 2024,month = 1,day = 20),
        schedule_interval = timedelta(minutes=16),
        catchup=False,
        max_active_runs=1
) as ingest_dag:

    create_spark_cluster = DataprocCreateClusterOperator(
        task_id='dp-cluster-create-task',
        folder_id=YC_DP_FOLDER_ID,
        cluster_name=f'tmp-dp-{uuid.uuid4()}',
        cluster_description='Temporary cluster for Spark processing under Airflow orchestration',
        subnet_id=YC_DP_SUBNET_ID,
        s3_bucket=YC_DP_LOGS_BUCKET,
        service_account_id=YC_DP_SA_ID,
        ssh_public_keys=YC_DP_SSH_PUBLIC_KEY,
        zone=YC_DP_AZ,
        cluster_image_version='2.0.43',
        masternode_resource_preset='s3-c2-m8',
        masternode_disk_type='network-ssd',
        masternode_disk_size=40,
        datanode_resource_preset='s3-c4-m16',
        datanode_disk_type='network-ssd',
        datanode_disk_size=128,
        datanode_count=3,
        services=['YARN', 'SPARK', 'HDFS', 'MAPREDUCE'],  
        computenode_count=0,           
        connection_id=ycSA_connection.conn_id,
        dag=ingest_dag
    )

    # 2 этап: запуск задания PySpark
    poke_spark_processing = DataprocCreatePysparkJobOperator(
        task_id='dp-cluster-pyspark-task',
        main_python_file_uri=f's3a://{YC_SOURCE_BUCKET}/scripts/pyspark_script.py', # ваш скрипт, выполняющий очистку данных
        connection_id = ycSA_connection.conn_id,
        dag=ingest_dag,
        properties={
            "spark.yarn.appMasterEnv.AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY,
            "spark.yarn.appMasterEnv.AWS_SECRET_ACCESS_KEY": AWS_SECRET_KEY
        }
    )

    delete_spark_cluster = DataprocDeleteClusterOperator(
        task_id='dp-cluster-delete-task',
        trigger_rule=TriggerRule.ALL_DONE,
        dag=ingest_dag
    )
    # Формирование DAG из указанных выше этапов
    create_spark_cluster >> poke_spark_processing >> delete_spark_cluster
