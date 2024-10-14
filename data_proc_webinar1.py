import uuid
import os
import boto3

from datetime import datetime, timedelta
from airflow import DAG, settings
from airflow.models import Connection, Variable
from airflow.operators.python import BranchPythonOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.operators.python import PythonOperator
from airflow.providers.yandex.operators.yandexcloud_dataproc import (
    DataprocCreateClusterOperator,
    DataprocCreatePysparkJobOperator,
    DataprocDeleteClusterOperator,

)

os.environ["MLFLOW_S3_ENDPOINT_URL"] = "https://storage.yandexcloud.net"
os.environ["AWS_ACCESS_KEY_ID"] = "key"
os.environ["AWS_SECRET_ACCESS_KEY"] = "key"

NEW_DATA_PROCESSED_LOG = "data_cleaning_status.log"
DAG_FOLDER = "/home/airflow/dags"
LOG_PATH = os.path.join(DAG_FOLDER, NEW_DATA_PROCESSED_LOG)

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
YC_SOURCE_BUCKET1 = "mlops-daria-bucket"
YC_DP_LOGS_BUCKET = 'airflow-dz4/airflow_logs/'      # YC S3 bucket for Data Proc cluster logs

# Checking if data cleaning script found new data and processed it, if not, then model retraining should not start
def check_new_data_exists():
    for key in s3.list_objects(Bucket=YC_SOURCE_BUCKET1)['Contents']:
        if key['Key'] == NEW_DATA_PROCESSED_LOG:
            s3.download_file(Bucket=YC_SOURCE_BUCKET1, Key=NEW_DATA_PROCESSED_LOG, Filename=LOG_PATH)
            break
    
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r") as f:
            status = f.read().strip()
        if status == "new data exists":
            return "dp-cluster-modeltraining-task"
        else:
            return "dp-cluster-delete-task"
    else:
        return "dp-cluster-delete-task"

boto3_session = boto3.session.Session()
s3 = boto3_session.client(
    service_name="s3",
    endpoint_url="https://storage.yandexcloud.net",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name="ru-central1"
)


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
ддwith DAG(
        dag_id = 'DATA_PREPROCESS_2',
        #schedule_interval='@hourly',
        start_date=datetime(year = 2024,month = 1,day = 20),
        schedule_interval = timedelta(minutes=2),
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
        cluster_image_version='2.0',
        masternode_resource_preset='s3-c2-m8',
        masternode_disk_type='network-ssd',
        masternode_disk_size=40,
        datanode_resource_preset='s3-c4-m16',
        datanode_disk_type='network-hdd',
        datanode_disk_size=128,
        datanode_count=2,
        services=['YARN', 'SPARK', 'HDFS', 'MAPREDUCE'],  
        computenode_count=0,           
        connection_id=ycSA_connection.conn_id,
        dag=ingest_dag
    )

    # 2 этап: запуск задания PySpark
    poke_spark_processing = DataprocCreatePysparkJobOperator(
        task_id='dp-cluster-pyspark-task',
        main_python_file_uri=f's3a://{YC_SOURCE_BUCKET}/scripts/data_cleaning_new.py', # ваш скрипт, выполняющий очистку данных
        connection_id = ycSA_connection.conn_id,
        dag=ingest_dag,
        properties={
            "spark.yarn.appMasterEnv.AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY,
            "spark.yarn.appMasterEnv.AWS_SECRET_ACCESS_KEY": AWS_SECRET_KEY
        }
    )
    

    check_status = BranchPythonOperator(
        task_id="check_new_data_exists",
        python_callable=check_new_data_exists,
        provide_context=True
    ) 

    model_training = DataprocCreatePysparkJobOperator(
        task_id='dp-cluster-modeltraining-task',
        main_python_file_uri=f's3a://{YC_SOURCE_BUCKET}/scripts/mlops_pipe_final.py',
        connection_id=ycSA_connection.conn_id,
        dag=ingest_dag,
        properties={
            "spark.yarn.appMasterEnv.AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY,
            "spark.yarn.appMasterEnv.AWS_SECRET_ACCESS_KEY": AWS_SECRET_KEY,
            "spark.executorEnv.AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY,
            "spark.executorEnv.AWS_SECRET_ACCESS_KEY": AWS_SECRET_KEY,
            "spark.yarn.appMasterEnv.PYSPARK_DRIVER_PYTHON": "./mlflow-venv-pap/mlflow-venv-try/bin/python",
            "spark.submit.deployMode": "cluster",
            "spark.yarn.dist.archives": "s3a://mlops-daria-bucket/envs/mlflow-venv-try.tar#mlflow-venv-pap"
        }
    )

    delete_spark_cluster = DataprocDeleteClusterOperator(
        task_id='dp-cluster-delete-task',
        trigger_rule=TriggerRule.ALL_DONE,
        dag=ingest_dag
    )   
    # Формирование DAG из указанных выше этапов      create_spark_cluster >> poke_spark_processing  >> model_training >> delete_spark_cluster
    create_spark_cluster >> poke_spark_processing >> check_status >> [model_training, delete_spark_cluster]
    model_training >> delete_spark_cluster
