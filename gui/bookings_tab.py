"""Вкладка «Брони» для работы с таблицей ``bookings``."""

from __future__ import annotations

from tkinter import messagebox, ttk
from typing import Any

from backend import (
    check_table_availability,
    create_booking,
    delete_booking,
    get_booking,
    get_bookings,
    get_tables,
    get_users,
    update_booking,
)
from db_driver import DatabaseError
from gui.base import CrudTab, Field
from models.booking import Booking


class BookingTab(CrudTab):
    """Вкладка CRUD-операций над бронями.

    Связи ``user_id`` и ``table_id`` выбираются из выпадающих списков,
    заполняемых текущими пользователями и столами из базы.
    """

    entity_name = "брони"

    def field_specs(self) -> list[Field]:
        return [
            Field("id", "ID", kind="int", editable=False),
            Field(
                "user_id",
                "Пользователь",
                kind="fk",
                required=True,
                fk_provider=self._user_options,
            ),
            Field(
                "table_id",
                "Стол",
                kind="fk",
                required=True,
                fk_provider=self._table_options,
            ),
            Field("booking_date", "Дата (ГГГГ-ММ-ДД)", kind="date", required=True),
            Field("start_time", "Начало (ЧЧ:ММ)", kind="time", required=True),
            Field("end_time", "Конец (ЧЧ:ММ)", kind="time", required=True),
            Field("guests", "Гостей", kind="int", required=True),
            Field(
                "status",
                "Статус",
                kind="choice",
                choices=("pending", "confirmed", "cancelled", "completed"),
                required=True,
            ),
            Field("comment", "Комментарий"),
            Field("created_at", "Создана", editable=False),
        ]

    @staticmethod
    def _user_options() -> list[tuple[Any, str]]:
        return [
            (row["id"], row.get("username") or row.get("email") or "")
            for row in get_users(order_by=("id", "ASC"))
        ]

    @staticmethod
    def _table_options() -> list[tuple[Any, str]]:
        return [
            (
                row["id"],
                f"Стол {row.get('number')} ({row.get('seats')} мест)",
            )
            for row in get_tables(order_by=("id", "ASC"))
        ]

    def fetch_rows(
        self,
        where: dict[str, Any] | None,
        order_by: Any,
        limit: int | None,
        offset: int | None,
    ) -> list[dict]:
        return get_bookings(where=where, order_by=order_by, limit=limit, offset=offset)

    def fetch_one(self, row_id: int) -> dict | None:
        return get_booking(row_id)

    def _add_form_actions(self, parent: ttk.Frame) -> None:
        ttk.Button(
            parent,
            text="Проверить доступность",
            command=self._on_check_availability,
        ).pack(side="left", padx=(4, 0))

    def _on_check_availability(self) -> None:
        """Проверяет, свободен ли выбранный стол в указанное время."""
        try:
            data = self._collect_form_data()
        except ValueError as exc:
            messagebox.showerror("Проверка доступности", str(exc))
            return
        table_id = data.get("table_id")
        booking_date = data.get("booking_date")
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        if None in (table_id, booking_date, start_time, end_time):
            messagebox.showinfo(
                "Проверка доступности",
                "Заполните стол, дату и время начала/окончания.",
            )
            return
        try:
            available = check_table_availability(
                table_id,
                booking_date,
                start_time,
                end_time,
                exclude_booking_id=self._selected_id,
            )
        except (ValueError, DatabaseError) as exc:
            messagebox.showerror("Проверка доступности", str(exc))
            return
        if available:
            messagebox.showinfo(
                "Проверка доступности", "Стол свободен в выбранное время."
            )
            self.app.set_status("Стол свободен в выбранное время.")
        else:
            messagebox.showwarning(
                "Проверка доступности",
                "Стол занят: есть пересекающаяся бронь.",
            )
            self.app.set_status("Стол занят: есть пересекающаяся бронь.")

    def create_record(self, data: dict[str, Any]) -> dict | None:
        return create_booking(Booking(**data))

    def update_record(self, row_id: int, data: dict[str, Any]) -> Any:
        return update_booking(row_id, data)

    def delete_record(self, row_id: int) -> Any:
        return delete_booking(row_id)
