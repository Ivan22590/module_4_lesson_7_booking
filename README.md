# module_4_lesson_6_postgres

Учебный проект: подключение к PostgreSQL на Python с помощью `psycopg2` и
модуль-драйвер `db_driver` с готовыми CRUD-методами.

## Состав проекта

| Файл | Назначение |
|---|---|
| `db_driver.py` | Модуль-драйвер: класс `Database` с CRUD-методами |
| `main.py` | Пример подключения и чтения таблицы `users` |
| `.env.example` | Шаблон параметров подключения (скопируйте в `.env`) |
| `requirements.txt` | Зависимости проекта |

## Требования

- Python 3.10+
- Запущенный сервер PostgreSQL

## Установка

1. Создайте и активируйте виртуальное окружение:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

2. Установите зависимости:

   ```powershell
   pip install -r requirements.txt
   ```

3. Создайте файл `.env` из шаблона и укажите свои параметры подключения:

   ```powershell
   Copy-Item .env.example .env
   ```

   Содержимое `.env`:

   ```
   PGHOST=localhost
   PGPORT=5432
   PGDATABASE=postgres
   PGUSER=postgres
   PGPASSWORD=your_password
   ```

## Запуск

Запуск примера (`main.py` читает таблицу `users`):

```powershell
python main.py
```

Запуск через интерпретатор из `.venv` без активации окружения:

```powershell
.venv\Scripts\python.exe main.py
```

## Использование драйвера

```python
from db_driver import Database, DatabaseError

try:
    with Database() as db:
        user = db.create("users", {"name": "Ivan", "age": 30})
        adults = db.read("users", where={"age": 30}, order_by=("id", "DESC"))
        one = db.read_one("users", where={"id": user["id"]})
        db.update("users", {"age": 31}, where={"id": user["id"]})
        db.delete("users", where={"id": user["id"]})
except DatabaseError as exc:
    print("Ошибка БД:", exc)
```

Параметры подключения можно передать напрямую, минуя `.env`:

```python
db = Database(host="localhost", dbname="test", user="user", password="12345")
```

### Методы класса `Database`

| Метод | Описание |
|---|---|
| `create(table, data)` | Вставка строки, возвращает её |
| `read(table, columns, where, order_by, limit, offset)` | Выборка строк |
| `read_one(table, columns, where, order_by)` | Одна строка или `None` |
| `update(table, data, where)` | Обновление строк |
| `delete(table, where)` | Удаление строк |
| `fetchall(query, params)` | Произвольный SELECT |
| `fetchone(query, params)` | Первая строка SELECT |
| `execute(query, params)` | Произвольный запрос, число затронутых строк |
| `connect()` / `close()` | Открыть / закрыть соединение |

> Имена таблиц и колонок экранируются, значения передаются параметрами —
> запросы защищены от SQL-инъекций. `update` и `delete` требуют непустой `where`.
