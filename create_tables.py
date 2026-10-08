"""Скрипт инициализации схемы базы данных мини-системы бронирования.

Создаёт таблицы ``users``, ``tables`` и ``bookings`` на основе dataclass-моделей
из пакета ``models`` с помощью драйвера :class:`db_driver.Database`.

Порядок создания важен: сначала ``users`` и ``tables``, затем ``bookings``,
потому что таблица броней ссылается на них через внешние ключи.

Запуск::

    python backend.py
"""

from __future__ import annotations

from db_driver import Database, DatabaseError
from models.booking import Booking
from models.tables import Table
from models.user import User

# Модели в порядке создания: сначала таблицы-справочники, затем брони.
MODELS = (User, Table, Booking)


def create_tables() -> None:
    """Создаёт все таблицы системы, если они ещё не существуют."""
    with Database() as db:
        for model in MODELS:
            db.create_table(model)
            print(f"Таблица {model.TABLE!r} готова.")


def main() -> None:
    """Точка входа: создаёт таблицы и сообщает о результате."""
    try:
        create_tables()
    except DatabaseError as exc:
        print("Ошибка базы данных:", exc)
        raise SystemExit(1) from exc
    print("Схема базы данных успешно инициализирована.")


if __name__ == "__main__":
    main()
