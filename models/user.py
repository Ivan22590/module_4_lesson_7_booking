"""Модель данных пользователя мини-системы бронирования.

Модуль описывает одну строку таблицы ``users`` в виде dataclass :class:`User`.
Здесь нет ORM и CRUD-логики — только описание данных.

Пример использования::

    from models.user import User

    user = User(username="ivan", email="ivan@example.com")
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

__all__ = ["User", "TABLE"]

#: Имя таблицы в базе данных, которой соответствует модель.
TABLE = "users"


@dataclass
class User:
    """Пользователь системы бронирования.

    Поля соответствуют колонкам таблицы ``users``. Значения по умолчанию
    подобраны так, чтобы объект можно было создать до записи в базу: ``id``
    и ``created_at`` заполняются базой, ``role`` и ``is_active`` имеют
    осмысленные стартовые значения.
    """

    #: Имя таблицы в базе данных (удобно передавать в методы драйвера).
    TABLE: ClassVar[str] = TABLE

    id: int | None = None
    username: str = ""
    email: str = ""
    password_hash: str = ""
    full_name: str | None = None
    phone: str | None = None
    role: str = "client"
    is_active: bool = True
    created_at: datetime | None = None
