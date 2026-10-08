"""Графический интерфейс мини-системы бронирования на tkinter.

Пакет содержит приложение :class:`gui.app.BookingApp` и вкладки для работы
с таблицами ``users``, ``tables`` и ``bookings``, а также служебную вкладку
для создания таблиц, заполнения тестовыми данными и очистки.
"""

from __future__ import annotations

from gui.app import BookingApp, main

__all__ = ["BookingApp", "main"]
