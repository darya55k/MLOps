# MLOps

<details>
<summary>
Цели и особенности проекта
</summary>

## 1. Цели проектируемой антифрод-системы:

1. **Снижение уровня мошеннических транзакций**
2. **Поддержжание конкурентноспособности компании**  (фиксация не более 2 мошеннических транзакций, приводящих к потере денежных средств + общий ущерб клиентов за месяц не должен привышать 500 тысяч рублей.)
3. **Достижение первых результатов в течение 3 месяцев** для оценки эффективности и целесообразности дальнейшего развития проекта
4. **Реализация проекта в рамках выделенного бюджета** (не более 10 млн руб.) и в установленный срок (не более 6 месяцев).
5. **Обеспечение высокой производительности и масштабируемости** (для обработки 50 транзакций в секунду на постоянной основе и до 400 транзакций в период праздников).
6. **Снижение процента ложных определений корректных транзакций как мошеннических** до уровня не более 5% от общего числа транзакций, чтобы избежать недовольства клиентов и предотвратить отток клиентов.
7. **Обеспечение конфиденциальности и безопасности данных**
8. **Обеспечение интеграции с существующей инфраструктурой**
  
## 2. Метрика для проектируемой антифрод-системы:
В рамках данной задачи важно:
1.	Минимизировать количество мошеннических транзакций (Recall)
2.	Минимизировать вероятность ошибочного определения транзакции как мошеннической (Precision)

Для данной задачи Recall является более предпочтительной метрикой:
* Пропущенные мошеннические транзакции (False Negatives) могут привести к значительным финансовым потерям. Высокий Recall минимизирует этот риск.
* Ложные срабатывания могут быть частично компенсированы дополнительными проверками и верификацией подозрительных транзакций.
  
Также в дополнение к Recall можно использовать ROC-AUC для более полной оценки производительности модели.

## 3. Особенности проекта:
https://miro.com/welcomeonboard/OVMxZDM2bW4zU0VtV0ludHZqRzVVemppNkJqaTVxNnZBTWFMclZQUG8wbGRiU0g1dWJieXVveVgzRHVwY1phanwzNDU4NzY0NTIzODQ4OTMwMjkxfDI=?share_link_id=384743824398

## 4. Основные функциональные части системы:
1. Сбор и подготовка данных
2. Модуль машинного обучения
3. Реализация и интеграция
4. Мониторинг и логирование
5. Безопасность и конфиденциальность
6. Масштабируемость и отказоустойчивость

## 5. Задачи:
Размещены на Kanban-доске

</details>
<details>
<summary>
Настройка облачной инфраструктуры
</summary>
  
## 1. Создание bucket в Yandex Cloud Object Storage с использованием terraform:
  
```
  resource "yandex_storage_bucket" "test" {
    bucket = "mlops-daria-bucket"
    folder_id = "b1gi1i2cfgl8sb9tnjig"

    anonymous_access_flags {
       read = true
       list = true
       config_read = true
     }

    default_storage_class = "COLD"
    max_size = 150323855360
}
```
## 2. Дочка доступа к бакету:
   s3://mlops-daria-bucket/

## 3. Создание Spark-кластера с использованием terraform:
```
resource "yandex_dataproc_cluster" "foo" {

 depends_on = [yandex_resourcemanager_folder_iam_binding.dataproc]
 bucket      = yandex_storage_bucket.test.bucket
 description = "Dataproc Cluster created by Terraform"
 name        = "daria-mlops-dataproc-cluster"

 labels = {
   created_by = "terraform"
 }

 service_account_id = yandex_iam_service_account.dataproc.id
 zone_id            = "ru-central1-b"

 cluster_config {

   hadoop {
     services = ["HDFS", "HIVE", "YARN", "SPARK", "TEZ", "MAPREDUCE"]
     ssh_public_keys = [
     file("~/.ssh/id_rsa.pub")]
   }

   subcluster_spec {
    name = "main"
    role = "MASTERNODE"
    resources {
        resource_preset_id = "s3-c2-m8"
        disk_type_id       = "network-hdd"
        disk_size          = 40
     }

    assign_public_ip  = true
        subnet_id   = data.yandex_vpc_subnet.subnet_b.id
        hosts_count = 1
   }


   subcluster_spec {
     name = "data"
     role = "DATANODE"
     resources {
       resource_preset_id = "s3-c4-m16"
       disk_type_id       = "network-hdd"
       disk_size          = 128
     }
     subnet_id   = data.yandex_vpc_subnet.subnet_b.id
     hosts_count = 3
   }
}

security_group_ids = [data.yandex_vpc_security_group.dataproc_ex.id]
}

data "yandex_vpc_subnet" "subnet_b" {
 subnet_id = "e2lhllitsg0u9khnd5u7"
}

data "yandex_vpc_security_group" "dataproc_ex" {
 security_group_id  = "enpe1i84pncj2in8iull"
}

resource "yandex_iam_service_account" "dataproc" {
 name        = "dataproc"
 description = "service account to manage Dataproc Cluster"
}

data "yandex_resourcemanager_folder" "foo" {
 folder_id = "b1gi1i2cfgl8sb9tnjig"
}

resource "yandex_resourcemanager_folder_iam_binding" "dataproc" {
 folder_id = data.yandex_resourcemanager_folder.foo.id
 role      = "mdb.dataproc.agent"
 members = [
   "serviceAccount:${yandex_iam_service_account.dataproc.id}",
 ]
}

```
## 4. Соединение по SSH с мастер-узлом и копирование содержимого хранилища в файловую систему HDFS с использованием инструмента hadoop distcp.
![image](https://github.com/user-attachments/assets/606c4093-0096-4e3c-8eda-8678b12dba7a)

</details>


<details>
<summary>
Анализ качества и очистка датасета мошеннических финансовых операций
</summary>
  В результате анализа данных были выделены следующие проблемы:
  
  - Удаление дубликатов
  - Преобразование типов данных (например, tx_amount к типу Float)
  - Удаление строк с пропущенными значениями
  
  Для очистки данных использовался Spark:
  
  ```
    df = df.withColumn("tx_amount", col("tx_amount").cast(FloatType()))
    df = df.na.drop("any")
    df = df.dropDuplicates(['transaction_id'])

  ```

После очистки данных и их преобразования в формат .parquet, данные были загружены в следующий бакет:

 ```
s3://mlops-data-ready/
 ```
</details>


<details>
<summary>
Периодический запуск процедуры очистки датасета мошеннических финансовых транзакций
</summary>
  
  В ходе выполенения задания были выполнены следующие действия:
  
  **1. Была запущена система Apache Airflow на отдельной виртуальной машине Yandex cloud.**
  
  **2. Создан DAG для ежедневного автоматизированного создания и удаления Spark-кластера и запуска скрипта очистки датасета.**
  
  **3. Выполнена проверка загрузки DAG в систему:**
  ![image](https://github.com/user-attachments/assets/bba1f844-b26c-4df3-9370-8293ca3f9e8c)
  
  Файл, в котором привен код с DAG:
  https://github.com/darya55k/MLOps/blob/main/data_proc_webinar.py

  **4. Выполнена проверка работоспособности DAG:**
  Скриншот с запусками процедуры очистки датасета по расписанию:
  ![image](https://github.com/user-attachments/assets/2f6e9f8e-c02b-4ef5-9d75-4ac615af1010)

</details>


<details>
<summary>
Регулярное переобучение модели обнаружения мошенничества
</summary>
  
  В ходе выполенения задания были выполнены следующие действия:

  ## 1. Создание и запуск виртуальных машин
В Яндкс.Клауд были созданы три виртуальные машины со следующими характеристиками:
1. MLflow
2. Postgres
3. Airflow
![image](https://github.com/user-attachments/assets/b3f9c588-a749-4eec-9721-a24c1f6caa71)

  ## 2. Установка зависимостей
  1. Для Airflow све необходимые зависимости были установлены в прошлом домашнем задании.
  2. Для MLflow были устновлены:
     * mlflow
     * psycopg2-binary
     * boto3
  Файл с кодом для запуска mlflow-сервера:
  https://github.com/darya55k/MLOps/blob/main/mlflow_server.sh
   3. Для Postgres был создан Dockerfile. База данных запускалась в докер-контейнере.
      https://github.com/darya55k/MLOps/blob/main/Dockerfile
## 3. Создание скриптов
1. Для MLflow использовался следующий скрипт:
   https://github.com/darya55k/MLOps/blob/main/mlops_pipe_final.py
2. Для Airflow был доработан даг:
   https://github.com/darya55k/MLOps/blob/main/data_proc_webinar1.py

## 4. Результаты
Так выглядит даг, если новых данных не было обнаружено:
![image](https://github.com/user-attachments/assets/40d044d3-8ddf-4af2-a2c1-d0817955a031)

И так, если новые данные присутсвуют:
![image](https://github.com/user-attachments/assets/ae82aa3d-1fe0-46c1-b2c2-5181de88c0c1)

Результаты, записанные в MLflow:
![image](https://github.com/user-attachments/assets/9ef0395d-f746-4fc8-9d6a-08d0ab3daeda)

![image](https://github.com/user-attachments/assets/7ae5e291-9148-4911-bd92-b7ee37f71af9)

Запись данных а бакет:
![image](https://github.com/user-attachments/assets/3898c4c2-4bc6-418e-ad73-dad96e34c573)


</details>


<details>
<summary>
Валидация модели обнаружения мошенничества
</summary>
  
  В ходе выполенения задания были выполнены следующие действия:

  ## 1. Виртуальные машины
Для выполенения работы были использованы виртуальные машины, созданные в рамках выполенния предыдуших домашних заданий:
1. MLflow
2. Postgres
3. Airflow
![image](https://github.com/user-attachments/assets/b3f9c588-a749-4eec-9721-a24c1f6caa71)

 ## 2. Оценка модели
Прогнозы модели на тестовых данных оцениваются по метрике ROC-AUC.
В цикле проводится бутстрап-оценка: создаются подвыборки тестовых данных, и на каждой из них вычисляется ROC-AUC.
Среднее значение ROC-AUC логируется в MLflow.

## 3. Сравнение моделей
Если это первый запуск, модель сохраняется.
Если это не первый запуск, то проверяется, лучше ли новая модель предыдущей по метрике ROC-AUC. Если да, проводится t-тест для проверки статистической значимости улучшения. Если p-значение меньше 0.05, новая модель сохраняется как улучшенная версия.


## 4. Результаты
Файл с обновленным скриптом:
https://github.com/darya55k/MLOps/blob/main/mlops_pipe_ab2.py

Поскольку новые метрики оказались выше, был проведен t-тест, который показал практически нулевое значение p-value. Это позволяет отвергнуть нулевую гипотезу о равенстве средних метрик выборок. 
![image](https://github.com/user-attachments/assets/9635ec6f-bccd-417c-a7db-f6eb927c8e35)

Новая модель была сохранена в MLflow, который подключен к S3-хранилищу.

![image](https://github.com/user-attachments/assets/e199f7de-5f68-417c-ad83-e2efa1027287)

</details>


<details>
<summary>
Инференс на потоке
</summary>
  
  В ходе выполенения задания были выполнены следующие действия:

  ## 1. Виртуальные машины
Для выполенения работы были использованы виртуальные машины, созданные в рамках выполенния предыдуших домашних заданий:
1. MLflow
2. Postgres
3. Airflow
![image](https://github.com/user-attachments/assets/b3f9c588-a749-4eec-9721-a24c1f6caa71)

## 2. Создание кластера с Kafka
Для выполнения ДЗ необходимо было запустить систему Apache Kafka на отдельной виртуальной машине Yandex cloud.
![image](https://github.com/user-attachments/assets/9dc15d80-4bc9-451d-8144-38e6b5faf843)

## 3. Настройка Kafka
1. Создала топики input и predictions
   ![image](https://github.com/user-attachments/assets/ca9e60da-8342-4724-a5f1-4c82919d99af)

2. Создала пользователей:
   ![image](https://github.com/user-attachments/assets/73b02bca-6857-4fd9-aa36-6fc56ffabbdb)
К Kafka UI подключалась через admin, так как у него есть все досупы и права.

## 4. Подключение к Kafka UI
Для подключения к Kafka UI необходимо было установить:
1. Сертификат:
 ```
mkdir -p /usr/local/share/ca-certificates/Yandex && \
wget "https://storage.yandexcloud.net/cloud-certs/CA.pem" \
     --output-document /usr/local/share/ca-certificates/Yandex/YandexInternalRootCA.crt && \
chmod 0655 /usr/local/share/ca-certificates/Yandex/YandexInternalRootCA.crt
 ```
2. Зависимости:
 ```
sudo apt update && sudo apt install --yes python3 python3-pip libsnappy-dev && \
pip3 install kafka-python lz4 python-snappy crc32c
 ```

3. Также в переменных указала свои данные для подключения
 ```
KAFKA_UI_STOREPASS=111111
KAFKA_CLUSTERS_NAME=kafka693
KAFKA_CLUSTERS_BOOTSTRAPSERVERS=rc1a-9912bk99ei6nptmg.mdb.yandexcloud.net:9091,rc1b-8bgoe5q76dij6dhh.mdb.yandexcloud.net:9091,rc1d-98kkqdi64ek3d44h.mdb.yandexcloud.net:9091
KAFKA_USER_LOGIN=mylogin
KAFKA_USER_PASSWORD=mypass
KSQLDB_STOREPASS=kuCxDPVj0mh4
STOREPASS=111111
 ```
4. Приложение запустилось по адресу http://158.160.79.228:8282

Из интерсейса можно налюдать за сообщениями

![image](https://github.com/user-attachments/assets/7db99b21-35e8-4a1d-a5d5-fbc6821b4eef)

## 5. Доработка скриптов
1. Продюсер для отправки данных в Kafka:
   
https://github.com/darya55k/MLOps/blob/main/producer.py

* Скрипт читает строки из файла 2019-08-22.txt, делит их на чанки и отправляет в топик input.
* Во время отправки метрика скорости передачи (transactions_per_second_sent_to_kafka) логируется в MLflow, чтобы отслеживать производительность загрузки данных.

2. Потребитель для обработки данных:
   
https://github.com/darya55k/MLOps/blob/main/consumer.py

* Cкрипт подключается к Kafka и прослушивает топик inputs, куда скрипт продюсера отправляет данные.
* Потребитель обрабатывает каждое сообщение: очищает его, трансформирует и применяет модель для предсказания.
* Затем результаты предсказания отправляются в топик predictions.
* В процессе метрики производительности также логируются в MLflow.

## 6. Графики в MLflow
В результате получился следующий гафик
![image](https://github.com/user-attachments/assets/a6a90723-0c47-4bed-860e-fa694a188c10)

По графику можно следать вывод, что кластер обрабатывает около 4 тысяч транзакций в секунду, а источник генерировал около 25 тысяч транзакций. 

</details>

<details>
<summary>
Обновление моделей
</summary>
  
В ходе выполенения задания были выполнены следующие действия:

## 1. REST API для модели
Для выполенения работы был написан fast api сервис: https://github.com/darya55k/MLOps/blob/main/app.py
## 2. Настройка Github actions:

Были добавлены следующие секреты:
![image](https://github.com/user-attachments/assets/50e2c193-da73-47da-b9e9-7bb3d6243fea)

Создан конфигрурационный файл github actions для сборки, тестирования и публикации контейнера: https://github.com/darya55k/MLOps/blob/main/main.yml

![image](https://github.com/user-attachments/assets/1963d39e-10f6-41f6-9ab3-8c2c8a3ea02b)

Публикация в DockerHub:
![image](https://github.com/user-attachments/assets/866860a8-159f-4623-9868-8dfcca588465)

## 3. Настройка k8s
k8s был развернут с помощью Docker Desktop
![image](https://github.com/user-attachments/assets/bf60eb35-fcfc-49ee-a070-ad459d48e50f)

Конфигурационные файлы kubernetes для запуска сервиса в kubernetes-кластере:

https://github.com/darya55k/MLOps/blob/main/service.yaml

https://github.com/darya55k/MLOps/blob/main/ingress.yaml

https://github.com/darya55k/MLOps/blob/main/deployment.yaml

Работа сервиса:
![image](https://github.com/user-attachments/assets/8699b422-87f7-48cd-b3a1-1aca6a6d8cb7)

</details>




