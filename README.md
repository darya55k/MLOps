# MLOps
## 1. Цели проектируемой антифрод-системы:

1. **Снижение уровня мошеннических транзакций**
2. **Поддержжание конкурентноспособности компании**  (фиксация не более 2 мошеннических транзакций, приводящих к потере денежных средств + общий ущерб клиентов за месяц не должен привышать 500 тасяч рублей.)
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
