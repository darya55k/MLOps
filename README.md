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



