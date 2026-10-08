"""Модель данных стола ресторана.

Модуль описывает одну строку таблицы ``tables`` в виде dataclass :class:`Table`.
Здесь нет ORM и CRUD-логики — только описание данных. Один объект
:class:`Table` описывает один конкретный стол.

Пример использования::

    from models.tables import Table

    table = Table(number=5, seats=4, location="terrace")
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

__all__ = ["Table", "TABLE"]

#: Имя таблицы в базе данных, которой соответствует модель.
TABLE = "tables"


@dataclass
class Table:
    """Стол ресторана, доступный для бронирования.

    Поля соответствуют колонкам таблицы ``tables``. Значения по умолчанию
    подобраны так, чтобы объект можно было создать до записи в базу: ``id``
    и ``created_at`` заполняются базой, ``seats`` и ``is_active`` имеют
    осмысленные стартовые значения.
    """

    #: Имя таблицы в базе данных (удобно передавать в методы драйвера).
    TABLE: ClassVar[str] = TABLE

    id: int | None = None
    number: int = 0
    seats: int = 2
    location: str = "main_hall"
    description: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
