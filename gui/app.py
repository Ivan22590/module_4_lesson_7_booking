"""Главное окно приложения с вкладками.

Модуль собирает вкладки «Пользователи», «Столы», «Брони» и «Сервис»
в один интерфейс :class:`BookingApp` с общей строкой состояния.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.bookings_tab import BookingTab
from gui.service_tab import ServiceTab
from gui.tables_tab import TableTab
from gui.users_tab import UserTab

#: Вкладки приложения в порядке отображения.
TABS = (
    (UserTab, "Пользователи"),
    (TableTab, "Столы"),
    (BookingTab, "Брони"),
    (ServiceTab, "Сервис"),
)


class BookingApp(tk.Tk):
    """Главное окно мини-системы бронирования."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Система бронирования — PostgreSQL")
        self.geometry("1280x800")
        self.minsize(1024, 640)

        try:
            ttk.Style().theme_use("clam")
        except tk.TclError:
            pass

        self._status_var = tk.StringVar(value="Готово.")
        self._build_status_bar()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        self.tabs: list[ttk.Frame] = []
        for tab_class, title in TABS:
            tab = tab_class(self.notebook, self)
            self.notebook.add(tab, text=title)
            self.tabs.append(tab)

    def _build_status_bar(self) -> None:
        status = ttk.Label(
            self,
            textvariable=self._status_var,
            relief="sunken",
            anchor="w",
            padding=(6, 3),
        )
        status.pack(side="bottom", fill="x")

    def set_status(self, text: str) -> None:
        """Обновляет текст в строке состояния."""
        self._status_var.set(text)

    def refresh_all(self) -> None:
        """Перезагружает данные во всех вкладках, поддерживающих обновление."""
        for tab in self.tabs:
            refresh = getattr(tab, "refresh", None)
            if callable(refresh):
                refresh()


def main() -> None:
    """Запускает графический интерфейс приложения."""
    app = BookingApp()
    app.mainloop()
