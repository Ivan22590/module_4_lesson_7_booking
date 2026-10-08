"""CRUD-функции для моделей мини-системы бронирования.

Функции работают поверх драйвера :class:`db_driver.Database` и dataclass-моделей
из пакета ``models``. Для каждой таблицы — ``users``, ``tables`` и ``bookings`` —
есть функции создания, чтения, обновления и удаления записей. Каждая функция
открывает собственное соединение, выполняет одну операцию и возвращает результат
в том же виде, что и методы драйвера: словарь или список словарей.

Пример использования::

    from backend import create_user, get_user, update_user, delete_user
    from models.user import User

    user = create_user(User(username="ivan", email="ivan@example.com"))
    print(get_user(user["id"]))
    update_user(user["id"], {"phone": "+7 900 000-00-00"})
    delete_user(user["id"])
"""

from __future__ import annotations

import dataclasses
from datetime import date, time, timedelta
from typing import Any, Iterable, Mapping

from psycopg2 import sql

from db_driver import Database
from models.booking import Booking
from models.tables import Table
from models.user import User

__all__ = [
    "create_user",
    "get_users",
    "get_user",
    "update_user",
    "delete_user",
    "create_table",
    "get_tables",
    "get_table",
    "update_table",
    "delete_table",
    "create_booking",
    "get_bookings",
    "get_booking",
    "update_booking",
    "delete_booking",
    "check_table_availability",
    "BookingConflictError",
    "clear_table",
    "seed_test_data",
]

# Условие отбора строк: словарь или список пар ``(колонка, значение)``.
Where = Mapping[str, Any] | Iterable[tuple[str, Any]] | None

#: Статусы броней, которые не занимают стол при проверке доступности.
INACTIVE_BOOKING_STATUSES = ("cancelled",)


class BookingConflictError(ValueError):
    """Стол занят: новая бронь пересекается по времени с существующей.

    Наследуется от :class:`ValueError`, поэтому обрабатывается вызывающим кодом
    (в том числе графическим интерфейсом) как ошибка входных данных.
    """


def _to_row(model: Any) -> dict[str, Any]:
    """Преобразует модель в словарь, опуская поля со значением ``None``.

    Используется при вставке: так база сама заполнит ``id`` и ``created_at``,
    а неуказанные поля получат значения по умолчанию.
    """
    return {
        field.name: getattr(model, field.name)
        for field in dataclasses.fields(model)
        if getattr(model, field.name) is not None
    }


# --- users ----------------------------------------------------------------------


def create_user(user: User) -> dict | None:
    """Добавляет пользователя и возвращает созданную запись."""
    with Database() as db:
        return db.create(User.TABLE, _to_row(user))


def get_users(
    where: Where = None,
    order_by: Any = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    """Возвращает пользователей, удовлетворяющих условию."""
    with Database() as db:
        return db.read(User.TABLE, where=where, order_by=order_by, limit=limit, offset=offset)


def get_user(user_id: int) -> dict | None:
    """Возвращает пользователя по ``id`` или ``None``."""
    with Database() as db:
        return db.read_one(User.TABLE, where={"id": user_id})


def update_user(user_id: int, data: Mapping[str, Any]) -> list[dict]:
    """Обновляет пользователя с указанным ``id`` и возвращает обновлённые записи."""
    with Database() as db:
        return db.update(User.TABLE, data, where={"id": user_id})


def delete_user(user_id: int) -> list[dict]:
    """Удаляет пользователя с указанным ``id`` и возвращает удалённые записи."""
    with Database() as db:
        return db.delete(User.TABLE, where={"id": user_id})


# --- tables ---------------------------------------------------------------------


def create_table(table: Table) -> dict | None:
    """Добавляет стол и возвращает созданную запись."""
    with Database() as db:
        return db.create(Table.TABLE, _to_row(table))


def get_tables(
    where: Where = None,
    order_by: Any = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    """Возвращает столы, удовлетворяющие условию."""
    with Database() as db:
        return db.read(Table.TABLE, where=where, order_by=order_by, limit=limit, offset=offset)


def get_table(table_id: int) -> dict | None:
    """Возвращает стол по ``id`` или ``None``."""
    with Database() as db:
        return db.read_one(Table.TABLE, where={"id": table_id})


def update_table(table_id: int, data: Mapping[str, Any]) -> list[dict]:
    """Обновляет стол с указанным ``id`` и возвращает обновлённые записи."""
    with Database() as db:
        return db.update(Table.TABLE, data, where={"id": table_id})


def delete_table(table_id: int) -> list[dict]:
    """Удаляет стол с указанным ``id`` и возвращает удалённые записи."""
    with Database() as db:
        return db.delete(Table.TABLE, where={"id": table_id})


# --- bookings -------------------------------------------------------------------


def check_table_availability(
    table_id: int,
    booking_date: date,
    start_time: time,
    end_time: time,
    exclude_booking_id: int | None = None,
) -> bool:
    """Проверяет, свободен ли стол в указанном интервале времени.

    Возвращает ``True``, если на выбранные дату и время у стола нет активных
    броней, пересекающихся с интервалом ``[start_time, end_time)``, и ``False``
    иначе. Брони со статусом из :data:`INACTIVE_BOOKING_STATUSES` (например,
    ``cancelled``) стол не занимают и не учитываются.

    Интервалы считаются пересекающимися, если начало одного раньше окончания
    другого и наоборот (``start < other_end and other_start < end``).

    :param table_id: идентификатор стола.
    :param booking_date: дата бронирования.
    :param start_time: время начала интервала.
    :param end_time: время окончания интервала (не включается).
    :param exclude_booking_id: бронь, которую нужно исключить из проверки —
        используется при обновлении существующей записи.
    :raises ValueError: если ``start_time`` не раньше ``end_time``.
    """
    if start_time >= end_time:
        raise ValueError("Время начала должно быть раньше времени окончания.")

    rows = get_bookings(where={"table_id": table_id, "booking_date": booking_date})
    for row in rows:
        if row.get("status") in INACTIVE_BOOKING_STATUSES:
            continue
        if exclude_booking_id is not None and row.get("id") == exclude_booking_id:
            continue
        existing_start = row.get("start_time")
        existing_end = row.get("end_time")
        if existing_start is None or existing_end is None:
            continue
        if existing_start < end_time and start_time < existing_end:
            return False
    return True


def _ensure_booking_available(
    table_id: Any,
    booking_date: Any,
    start_time: Any,
    end_time: Any,
    exclude_booking_id: int | None = None,
) -> None:
    """Проверяет доступность стола и выбрасывает :class:`BookingConflictError`.

    Если данных для проверки не хватает (какое-то из значений ``None``),
    проверка пропускается — интервал определить невозможно.
    """
    if None in (table_id, booking_date, start_time, end_time):
        return
    if check_table_availability(
        table_id, booking_date, start_time, end_time, exclude_booking_id
    ):
        return
    raise BookingConflictError(
        f"Стол {table_id} занят {booking_date} "
        f"в интервале {start_time:%H:%M}–{end_time:%H:%M}: "
        "есть пересекающаяся бронь."
    )


def create_booking(booking: Booking) -> dict | None:
    """Добавляет бронь и возвращает созданную запись.

    Перед вставкой проверяет, что стол свободен в указанное время
    (см. :func:`check_table_availability`). При пересечении с другой бронью
    того же стола выбрасывает :class:`BookingConflictError`.
    """
    _ensure_booking_available(
        booking.table_id,
        booking.booking_date,
        booking.start_time,
        booking.end_time,
    )
    with Database() as db:
        return db.create(Booking.TABLE, _to_row(booking))


def get_bookings(
    where: Where = None,
    order_by: Any = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    """Возвращает брони, удовлетворяющие условию."""
    with Database() as db:
        return db.read(Booking.TABLE, where=where, order_by=order_by, limit=limit, offset=offset)


def get_booking(booking_id: int) -> dict | None:
    """Возвращает бронь по ``id`` или ``None``."""
    with Database() as db:
        return db.read_one(Booking.TABLE, where={"id": booking_id})


def update_booking(booking_id: int, data: Mapping[str, Any]) -> list[dict]:
    """Обновляет бронь с указанным ``id`` и возвращает обновлённые записи.

    Проверяет доступность стола для итоговых значений: текущая запись
    объединяется с изменениями ``data``, а сама обновляемая бронь исключается
    из проверки. При пересечении с другой бронью выбрасывает
    :class:`BookingConflictError`.
    """
    current = get_booking(booking_id)
    if current is not None:
        merged = {**current, **data}
        _ensure_booking_available(
            merged.get("table_id"),
            merged.get("booking_date"),
            merged.get("start_time"),
            merged.get("end_time"),
            exclude_booking_id=booking_id,
        )
    with Database() as db:
        return db.update(Booking.TABLE, data, where={"id": booking_id})


def delete_booking(booking_id: int) -> list[dict]:
    """Удаляет бронь с указанным ``id`` и возвращает удалённые записи."""
    with Database() as db:
        return db.delete(Booking.TABLE, where={"id": booking_id})


# --- служебные операции ---------------------------------------------------------


def clear_table(table: str) -> None:
    """Полностью очищает таблицу, сбрасывая счётчик ``id``.

    Выполняет ``TRUNCATE ... RESTART IDENTITY CASCADE``: удаляются все строки,
    автоинкрементные идентификаторы начинаются заново, а связанные записи
    (например, брони, ссылающиеся на пользователей и столы) удаляются каскадно.

    :param table: имя таблицы (``users``, ``tables`` или ``bookings``).
    """
    with Database() as db:
        db.execute(
            sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                sql.Identifier(table)
            )
        )


def seed_test_data() -> dict[str, int]:
    """Заполняет таблицы тестовыми данными.

    Создаёт несколько пользователей, столов и броней, связывая брони с уже
    созданными пользователями и столами. Возвращает словарь с количеством
    добавленных записей по каждой таблице.

    Предполагается, что таблицы уже созданы (см. ``create_tables``).
    """
    users = [
        User(
            username="ivan",
            email="ivan@example.com",
            password_hash="hash_ivan",
            full_name="Иван Петров",
            phone="+7 900 111-22-33",
            role="client",
        ),
        User(
            username="maria",
            email="maria@example.com",
            password_hash="hash_maria",
            full_name="Мария Смирнова",
            phone="+7 900 222-33-44",
            role="client",
        ),
        User(
            username="admin",
            email="admin@example.com",
            password_hash="hash_admin",
            full_name="Администратор",
            role="admin",
        ),
    ]
    tables = [
        Table(number=1, seats=2, location="main_hall", description="У окна"),
        Table(number=2, seats=4, location="main_hall"),
        Table(number=3, seats=6, location="terrace", description="Летняя веранда"),
        Table(number=4, seats=2, location="vip", description="VIP-зал"),
    ]

    created_users = [row for row in (create_user(user) for user in users) if row]
    created_tables = [row for row in (create_table(table) for table in tables) if row]
    user_ids = [row["id"] for row in created_users]
    table_ids = [row["id"] for row in created_tables]

    today = date.today()
    bookings = [
        Booking(
            user_id=user_ids[0],
            table_id=table_ids[0],
            booking_date=today,
            start_time=time(18, 0),
            end_time=time(20, 0),
            guests=2,
            status="confirmed",
            comment="Годовщина",
        ),
        Booking(
            user_id=user_ids[1],
            table_id=table_ids[2],
            booking_date=today + timedelta(days=1),
            start_time=time(13, 0),
            end_time=time(15, 0),
            guests=6,
            status="pending",
            comment="Семейный обед",
        ),
        Booking(
            user_id=user_ids[0],
            table_id=table_ids[3],
            booking_date=today + timedelta(days=2),
            start_time=time(20, 0),
            end_time=time(22, 0),
            guests=2,
            status="pending",
        ),
        Booking(
            user_id=user_ids[2],
            table_id=table_ids[1],
            booking_date=today - timedelta(days=1),
            start_time=time(19, 0),
            end_time=time(21, 0),
            guests=4,
            status="completed",
        ),
    ]
    created_bookings = [
        row for row in (create_booking(booking) for booking in bookings) if row
    ]

    return {
        User.TABLE: len(created_users),
        Table.TABLE: len(created_tables),
        Booking.TABLE: len(created_bookings),
    }
