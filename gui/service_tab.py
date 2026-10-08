"""Служебная вкладка: схема БД, тестовые данные и очистка таблиц."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from backend import clear_table, seed_test_data
from create_tables import create_tables
from db_driver import DatabaseError
from models.booking import Booking
from models.tables import Table
from models.user import User

# Порядок таблиц для операций: сначала зависимая таблица броней.
TABLE_ORDER = (Booking.TABLE, User.TABLE, Table.TABLE)


class ServiceTab(ttk.Frame):
    """Вкладка управления схемой и наполнением базы данных."""

    def __init__(self, master: tk.Misc, app: Any) -> None:
        super().__init__(master, padding=8)
        self.app = app
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._build_ui()

    def _build_ui(self) -> None:
        actions = ttk.LabelFrame(self, text="Операции с базой данных", padding=8)
        actions.grid(row=0, column=0, sticky="ew")

        ttk.Button(
            actions, text="Создать таблицы", command=self._on_create_tables
        ).grid(row=0, column=0, padx=(0, 6), pady=2, sticky="w")
        ttk.Button(
            actions, text="Заполнить тестовыми данными", command=self._on_seed
        ).grid(row=0, column=1, padx=(0, 6), pady=2, sticky="w")
        ttk.Button(
            actions, text="Очистить таблицы", command=self._on_clear
        ).grid(row=0, column=2, padx=(0, 6), pady=2, sticky="w")
        ttk.Button(
            actions, text="Обновить все вкладки", command=self._on_refresh_all
        ).grid(row=0, column=3, pady=2, sticky="w")

        log_frame = ttk.LabelFrame(self, text="Журнал операций", padding=8)
        log_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = tk.Text(log_frame, height=16, state="disabled", wrap="word")
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)

    # --- действия ---------------------------------------------------------------

    def _on_create_tables(self) -> None:
        try:
            create_tables()
        except DatabaseError as exc:
            self._error("Создание таблиц", exc)
            return
        self._log("Таблицы users, tables, bookings созданы (если их не было).")
        self.app.set_status("Схема базы данных готова.")

    def _on_seed(self) -> None:
        if not messagebox.askyesno(
            "Тестовые данные",
            "Добавить тестовых пользователей, столы и брони?",
        ):
            return
        try:
            counts = seed_test_data()
        except DatabaseError as exc:
            self._error("Заполнение тестовыми данными", exc)
            return
        summary = ", ".join(f"{table}: {count}" for table, count in counts.items())
        self._log(f"Добавлены тестовые данные — {summary}.")
        self.app.set_status("Тестовые данные добавлены.")
        self.app.refresh_all()

    def _on_clear(self) -> None:
        if not messagebox.askyesno(
            "Очистка таблиц",
            "Полностью очистить таблицы users, tables и bookings?\n"
            "Все данные будут удалены безвозвратно.",
        ):
            return
        try:
            for table in TABLE_ORDER:
                clear_table(table)
        except DatabaseError as exc:
            self._error("Очистка таблиц", exc)
            return
        self._log("Таблицы users, tables, bookings очищены (id сброшены).")
        self.app.set_status("Таблицы очищены.")
        self.app.refresh_all()

    def _on_refresh_all(self) -> None:
        self.app.refresh_all()
        self._log("Все вкладки обновлены.")
        self.app.set_status("Данные перезагружены.")

    # --- вспомогательные методы -------------------------------------------------

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _error(self, title: str, exc: Exception) -> None:
        messagebox.showerror(title, str(exc))
        self._log(f"{title}: ошибка — {exc}")
        self.app.set_status(f"{title}: {exc}")
