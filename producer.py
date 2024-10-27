from datetime import datetime
import os
import time

from kafka import KafkaProducer
import mlflow


REGISTRY_SERVER_HOST = "89.169.175.116"
TRACKING_SERVER_HOST = "89.169.175.116"
FILE_TO_SEND = "2019-08-22.txt"
BOOTSTRAP_SERVERS = [
    'rc1a-9912bk99ei6nptmg.mdb.yandexcloud.net:9091',
    'rc1b-8bgoe5q76dij6dhh.mdb.yandexcloud.net:9091',
    'rc1d-98kkqdi64ek3d44h.mdb.yandexcloud.net:9091'
]

def send_to_kafka(producer, topic, chunk):
    for line in chunk:
        producer.send(topic, value=line.encode("utf-8"))
    producer.flush()


def process_file_in_chunks(file_path, producer, topic, chunk_size=50000):
    experiment = mlflow.set_experiment("mlops_experiment_2")
    experiment_id = experiment.experiment_id
    run_name = f"run_{datetime.now()}"
    with mlflow.start_run(run_name=run_name, experiment_id=experiment_id):
        with open(file_path, 'r') as file:
            chunk = []
            start_time = time.time()
            for i, line in enumerate(file):
                chunk.append(line.strip())
                if (i + 1) % chunk_size == 0:
                    send_to_kafka(producer, topic, chunk)
                    
                    # log tps to mlflow
                    end_time = time.time()
                    transactions_per_second = len(chunk) / (end_time - start_time)
                    mlflow.log_metric("transactions_per_second_sent_to_kafka", transactions_per_second)
                    start_time = end_time

                    chunk.clear()

            if chunk:
                send_to_kafka(producer, topic, chunk)


def main():
    producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP_SERVERS,
    security_protocol="SASL_SSL",
    sasl_mechanism="SCRAM-SHA-512",
    sasl_plain_username='producer',
    sasl_plain_password='mypass',
    ssl_cafile="/usr/local/share/ca-certificates/Yandex/YandexInternalRootCA.crt")

    topic = 'input'

    os.environ["MLFLOW_S3_ENDPOINT_URL"] = "https://storage.yandexcloud.net"
    mlflow.set_tracking_uri(f"http://{TRACKING_SERVER_HOST}:5000")
    mlflow.set_registry_uri(f"http://{REGISTRY_SERVER_HOST}:5000")

    process_file_in_chunks(FILE_TO_SEND, producer, topic)


if __name__ == "__main__":
    main()
