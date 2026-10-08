"""Вкладка «Пользователи» для работы с таблицей ``users``."""

from __future__ import annotations

from typing import Any

from backend import create_user, delete_user, get_user, get_users, update_user
from gui.base import CrudTab, Field
from models.user import User


class UserTab(CrudTab):
    """Вкладка CRUD-операций над пользователями."""

    entity_name = "пользователи"

    def field_specs(self) -> list[Field]:
        return [
            Field("id", "ID", kind="int", editable=False),
            Field("username", "Логин", required=True),
            Field("email", "Email", required=True),
            Field("password_hash", "Хеш пароля", required=True, show_in_table=False),
            Field("full_name", "ФИО"),
            Field("phone", "Телефон"),
            Field(
                "role",
                "Роль",
                kind="choice",
                choices=("client", "admin", "manager"),
                required=True,
            ),
            Field("is_active", "Активен", kind="bool"),
            Field("created_at", "Создан", editable=False),
        ]

    def fetch_rows(
        self,
        where: dict[str, Any] | None,
        order_by: Any,
        limit: int | None,
        offset: int | None,
    ) -> list[dict]:
        return get_users(where=where, order_by=order_by, limit=limit, offset=offset)

    def fetch_one(self, row_id: int) -> dict | None:
        return get_user(row_id)

    def create_record(self, data: dict[str, Any]) -> dict | None:
        return create_user(User(**data))

    def update_record(self, row_id: int, data: dict[str, Any]) -> Any:
        return update_user(row_id, data)

    def delete_record(self, row_id: int) -> Any:
        return delete_user(row_id)
