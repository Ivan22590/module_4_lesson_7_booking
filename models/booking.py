"""Модель данных бронирования стола.

Модуль описывает одну строку таблицы ``bookings`` в виде dataclass
:class:`Booking`. Здесь нет ORM и CRUD-логики — только описание данных. Один
объект :class:`Booking` описывает одну бронь: кто (:class:`~models.user.User`)
и какой стол (:class:`~models.tables.Table`) забронировал на указанное время.

Внешние связи выражены идентификаторами: ``user_id`` ссылается на таблицу
пользователей, ``table_id`` — на таблицу столов.

Пример использования::

    from models.booking import Booking

    booking = Booking(user_id=1, table_id=5, guests=4)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import ClassVar

__all__ = ["Booking", "TABLE"]

#: Имя таблицы в базе данных, которой соответствует модель.
TABLE = "bookings"


@dataclass
class Booking:
    """Бронь стола в ресторане.

    Поля соответствуют колонкам таблицы ``bookings``. Значения по умолчанию
    подобраны так, чтобы объект можно было создать до записи в базу: ``id``
    и ``created_at`` заполняются базой, ``status`` имеет осмысленное стартовое
    значение.

    :param user_id: внешняя связь с таблицей ``users`` — кто бронирует.
    :param table_id: внешняя связь с таблицей ``tables`` — какой стол бронируют.

    Поля ``user_id`` и ``table_id`` помечены метаданными ``references`` —
    драйвер использует их для создания внешних ключей (``FOREIGN KEY``).
    """

    #: Имя таблицы в базе данных (удобно передавать в методы драйвера).
    TABLE: ClassVar[str] = TABLE

    id: int | None = None
    user_id: int | None = field(
        default=None, metadata={"references": ("users", "id")}
    )
    table_id: int | None = field(
        default=None, metadata={"references": ("tables", "id")}
    )
    booking_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    guests: int = 1
    status: str = "pending"
    comment: str | None = None
    created_at: datetime | None = None
