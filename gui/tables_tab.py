"""Вкладка «Столы» для работы с таблицей ``tables``."""

from __future__ import annotations

from typing import Any

from backend import (
    create_table,
    delete_table,
    get_table,
    get_tables,
    update_table,
)
from gui.base import CrudTab, Field
from models.tables import Table


class TableTab(CrudTab):
    """Вкладка CRUD-операций над столами."""

    entity_name = "столы"

    def field_specs(self) -> list[Field]:
        return [
            Field("id", "ID", kind="int", editable=False),
            Field("number", "Номер", kind="int", required=True),
            Field("seats", "Мест", kind="int", required=True),
            Field("location", "Расположение", required=True),
            Field("description", "Описание"),
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
        return get_tables(where=where, order_by=order_by, limit=limit, offset=offset)

    def fetch_one(self, row_id: int) -> dict | None:
        return get_table(row_id)

    def create_record(self, data: dict[str, Any]) -> dict | None:
        return create_table(Table(**data))

    def update_record(self, row_id: int, data: dict[str, Any]) -> Any:
        return update_table(row_id, data)

    def delete_record(self, row_id: int) -> Any:
        return delete_table(row_id)
