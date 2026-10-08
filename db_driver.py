"""Драйвер для работы с базой данных PostgreSQL.

Модуль предоставляет класс ``Database`` — обёртку над psycopg2 с готовыми
CRUD-методами и безопасной параметризацией запросов (защита от SQL-инъекций).

Параметры подключения читаются из файла ``.env`` (рядом с модулем) либо
передаются напрямую в конструктор. Шаблон для заполнения — ``.env.example``.

Пример использования::

    from db import Database, DatabaseError

    with Database() as db:
        user = db.create("users", {"name": "Ivan", "age": 30})
        adults = db.read("users", where={"age": 30}, order_by=("id", "DESC"))
        db.update("users", {"age": 31}, where={"id": user["id"]})
        db.delete("users", where={"id": user["id"]})
"""

from __future__ import annotations

import ctypes
import locale
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

__all__ = ["Database", "DatabaseError", "load_connection_params"]

ENV_FILE = Path(__file__).resolve().parent / ".env"

# Имена переменных окружения и значения по умолчанию для параметров psycopg2.
_ENV_KEYS = {
    "host": "PGHOST",
    "port": "PGPORT",
    "dbname": "PGDATABASE",
    "user": "PGUSER",
    "password": "PGPASSWORD",
}
_DEFAULTS = {
    "host": "localhost",
    "port": "5432",
    "dbname": "postgres",
    "user": "postgres",
    "password": "postgres",
}


class DatabaseError(Exception):
    """Ошибка при работе с базой данных."""


def _system_encoding() -> str:
    """Кодировка, в которой libpq отдаёт сообщения об ошибках на Windows."""
    if sys.platform == "win32":
        try:
            return f"cp{ctypes.windll.kernel32.GetACP()}"
        except (AttributeError, OSError):
            pass
    return locale.getpreferredencoding(False) or "utf-8"


def _decode_error(exc: Exception) -> str:
    """Возвращает читаемый текст ошибки.

    psycopg2 на Windows декодирует сообщения libpq как UTF-8, хотя они приходят
    в ANSI-кодировке (например, cp1251). В этом случае падает UnicodeDecodeError,
    но исходные байты доступны в ``exc.object`` — декодируем их сами.
    """
    raw = getattr(exc, "object", None)
    if isinstance(exc, UnicodeDecodeError) and isinstance(raw, (bytes, bytearray)):
        data = bytes(raw)
        for encoding in (_system_encoding(), "utf-8"):
            try:
                return data.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        return data.decode("utf-8", errors="replace")
    return str(exc)


def load_connection_params(env_file: str | os.PathLike | None = None, **overrides: Any) -> dict:
    """Собирает параметры подключения.

    Значения берутся в порядке приоритета: ``overrides`` > файл ``.env`` >
    переменные окружения > значения по умолчанию.
    """
    env_path = Path(env_file) if env_file is not None else ENV_FILE
    if env_path.exists():
        load_dotenv(env_path, override=True)

    params = {
        name: os.environ.get(env_key, _DEFAULTS[name])
        for name, env_key in _ENV_KEYS.items()
    }
    params.update({key: value for key, value in overrides.items() if value is not None})
    return params


class Database:
    """Драйвер доступа к PostgreSQL с CRUD-методами.

    Класс можно использовать как контекстный менеджер — соединение откроется
    при входе и закроется при выходе::

        with Database() as db:
            db.fetchall("SELECT 1")
    """

    def __init__(self, env_file: str | os.PathLike | None = None, **params: Any) -> None:
        """Создаёт драйвер.

        :param env_file: путь к файлу ``.env`` (по умолчанию — рядом с модулем).
        :param params: необязательные переопределения параметров подключения
            (``host``, ``port``, ``dbname``, ``user``, ``password``).
        """
        self._params = load_connection_params(env_file, **params)
        self._conn: psycopg2.extensions.connection | None = None

    # --- управление соединением -------------------------------------------------

    @property
    def connection(self) -> psycopg2.extensions.connection:
        """Активное соединение (открывается при первом обращении)."""
        if self._conn is None or self._conn.closed:
            self._conn = self._connect()
        return self._conn

    def _connect(self) -> psycopg2.extensions.connection:
        try:
            return psycopg2.connect(**self._params)
        except (psycopg2.Error, UnicodeDecodeError) as exc:
            raise DatabaseError(_decode_error(exc)) from exc

    def connect(self) -> "Database":
        """Явно открывает соединение и возвращает сам драйвер."""
        self.connection
        return self

    def close(self) -> None:
        """Закрывает соединение, если оно открыто."""
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
        self._conn = None

    def __enter__(self) -> "Database":
        return self.connect()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # --- низкоуровневые помощники ----------------------------------------------

    def _run(self, query, params: Sequence | None = None) -> tuple[list[dict], int]:
        """Выполняет запрос и возвращает ``(строки, число затронутых строк)``.

        Ошибки оборачиваются в :class:`DatabaseError`, транзакция откатывается.
        """
        conn = self.connection
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                rows = [dict(row) for row in cur.fetchall()] if cur.description else []
                rowcount = cur.rowcount
            conn.commit()
            return rows, rowcount
        except (psycopg2.Error, UnicodeDecodeError) as exc:
            conn.rollback()
            raise DatabaseError(_decode_error(exc)) from exc

    def fetchall(self, query, params: Sequence | None = None) -> list[dict]:
        """Выполняет произвольный SELECT и возвращает список словарей."""
        return self._run(query, params)[0]

    def fetchone(self, query, params: Sequence | None = None) -> dict | None:
        """Выполняет произвольный SELECT и возвращает первую строку или ``None``."""
        rows = self._run(query, params)[0]
        return rows[0] if rows else None

    def execute(self, query, params: Sequence | None = None) -> int:
        """Выполняет произвольный запрос и возвращает число затронутых строк."""
        return self._run(query, params)[1]

    # --- построение частей запроса ---------------------------------------------

    @staticmethod
    def _build_where(where: Mapping[str, Any] | Iterable[tuple[str, Any]] | None):
        """Строит безопасное условие WHERE из словаря/списка пар ``колонка: значение``.

        Значение ``None`` превращается в ``IS NULL``. Все значения передаются
        как параметры, а имена колонок экранируются через ``sql.Identifier``.
        Если условий нет, возвращает ``(None, [])``.
        """
        if not where:
            return None, []

        items = where.items() if isinstance(where, Mapping) else where
        parts = []
        params: list[Any] = []
        for column, value in items:
            if value is None:
                parts.append(sql.SQL("{} IS NULL").format(sql.Identifier(column)))
            else:
                parts.append(sql.SQL("{} = %s").format(sql.Identifier(column)))
                params.append(value)
        return sql.SQL(" AND ").join(parts), params

    @staticmethod
    def _build_order_by(order_by) -> Any:
        """Строит безопасное выражение ORDER BY.

        Принимает имя колонки, пару ``(колонка, "ASC"/"DESC")`` или список таких
        элементов. Направление сортировки проверяется по белому списку.
        """
        if isinstance(order_by, str):
            order_by = [order_by]
        elif (
            isinstance(order_by, (tuple, list))
            and len(order_by) == 2
            and isinstance(order_by[1], str)
            and order_by[1].upper() in ("ASC", "DESC")
        ):
            # Одиночная пара (колонка, направление), а не список колонок.
            order_by = [order_by]

        parts = []
        for item in order_by:
            if isinstance(item, (tuple, list)):
                column, direction = item
            else:
                column, direction = item, "ASC"
            direction = str(direction).upper()
            if direction not in ("ASC", "DESC"):
                raise ValueError(f"Недопустимое направление сортировки: {direction!r}")
            parts.append(
                sql.SQL("{} {}").format(sql.Identifier(column), sql.SQL(direction))
            )
        return sql.SQL(", ").join(parts)

    # --- CRUD -------------------------------------------------------------------

    def create(self, table: str, data: Mapping[str, Any]) -> dict | None:
        """Вставляет строку и возвращает её целиком.

        :param table: имя таблицы.
        :param data: словарь ``{колонка: значение}``.
        """
        if not data:
            raise ValueError("data не может быть пустым")

        columns = list(data)
        query = sql.SQL("INSERT INTO {table} ({cols}) VALUES ({vals}) RETURNING *").format(
            table=sql.Identifier(table),
            cols=sql.SQL(", ").join(sql.Identifier(col) for col in columns),
            vals=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )
        rows, _ = self._run(query, [data[col] for col in columns])
        return rows[0] if rows else None

    def read(
        self,
        table: str,
        columns: Sequence[str] | None = None,
        where: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
        order_by: Any = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict]:
        """Возвращает строки таблицы, удовлетворяющие условию.

        :param columns: список колонок (по умолчанию — все).
        :param where: условие отбора (словарь или список пар ``(колонка, значение)``).
        :param order_by: колонка, пара ``(колонка, "ASC"/"DESC")`` или их список.
        :param limit: максимальное число строк.
        :param offset: смещение выборки.
        """
        cols = (
            sql.SQL("*")
            if not columns
            else sql.SQL(", ").join(sql.Identifier(col) for col in columns)
        )
        query = sql.SQL("SELECT {cols} FROM {table}").format(
            cols=cols, table=sql.Identifier(table)
        )
        params: list[Any] = []

        clause, where_params = self._build_where(where)
        if clause is not None:
            query = query + sql.SQL(" WHERE ") + clause
            params.extend(where_params)

        if order_by:
            query = query + sql.SQL(" ORDER BY ") + self._build_order_by(order_by)

        if limit is not None:
            query = query + sql.SQL(" LIMIT %s")
            params.append(limit)

        if offset is not None:
            query = query + sql.SQL(" OFFSET %s")
            params.append(offset)

        return self._run(query, params)[0]

    def read_one(
        self,
        table: str,
        columns: Sequence[str] | None = None,
        where: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
        order_by: Any = None,
    ) -> dict | None:
        """Возвращает одну строку (или ``None``), см. :meth:`read`."""
        rows = self.read(table, columns=columns, where=where, order_by=order_by, limit=1)
        return rows[0] if rows else None

    def update(
        self,
        table: str,
        data: Mapping[str, Any],
        where: Mapping[str, Any] | Iterable[tuple[str, Any]],
    ) -> list[dict]:
        """Обновляет строки и возвращает обновлённые записи.

        :param data: новые значения ``{колонка: значение}``.
        :param where: условие отбора; обязателен, чтобы не обновить всю таблицу.
        """
        if not data:
            raise ValueError("data не может быть пустым")
        if not where:
            raise ValueError("where обязателен для update")

        assignments = sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(col)) for col in data
        )
        clause, where_params = self._build_where(where)
        query = sql.SQL(
            "UPDATE {table} SET {assignments} WHERE {clause} RETURNING *"
        ).format(
            table=sql.Identifier(table),
            assignments=assignments,
            clause=clause,
        )
        rows, _ = self._run(query, list(data.values()) + where_params)
        return rows

    def delete(
        self,
        table: str,
        where: Mapping[str, Any] | Iterable[tuple[str, Any]],
    ) -> list[dict]:
        """Удаляет строки и возвращает удалённые записи.

        :param where: условие отбора; обязателен, чтобы не очистить всю таблицу.
        """
        if not where:
            raise ValueError("where обязателен для delete")

        clause, where_params = self._build_where(where)
        query = sql.SQL("DELETE FROM {table} WHERE {clause} RETURNING *").format(
            table=sql.Identifier(table),
            clause=clause,
        )
        rows, _ = self._run(query, where_params)
        return rows
