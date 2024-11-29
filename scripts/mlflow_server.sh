export MLFLOW_S3_ENDPOINT_URL=https://storage.yandexcloud.net
export AWS_ACCESS_KEY_ID=mykey
export AWS_SECRET_ACCESS_KEY=mykey


mlflow server \
    --host 0.0.0.0 \
    --backend-store-uri postgresql://otus_mlflow_database_user:otus_mlflow_database_password@89.169.169.94:5432/mlflow_database \
    --registry-store-uri postgresql://otus_mlflow_database_user:otus_mlflow_database_password@89.169.169.94:5432/mlflow_database \
    --default-artifact-root s3://airflow-dz4/mlflow-artifacts \
