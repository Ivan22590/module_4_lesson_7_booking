"""Базовый класс вкладки для CRUD-интерфейса.

Модуль содержит описание поля :class:`Field` и класс :class:`CrudTab` —
переиспользуемую вкладку с таблицей записей (``ttk.Treeview``), формой ввода,
панелью поиска и фильтров, а также кнопками создания, обновления и удаления.

Конкретные вкладки («Пользователи», «Столы», «Брони») наследуются от
:class:`CrudTab` и переопределяют методы доступа к данным, делегируя их
функциям модуля :mod:`backend`.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from datetime import date, time
from tkinter import messagebox, ttk
from typing import Any, Callable

from db_driver import DatabaseError


@dataclass
class Field:
    """Описание одного поля сущности для формы, таблицы и фильтров.

    :param name: имя поля (совпадает с колонкой таблицы БД).
    :param label: подпись для интерфейса.
    :param kind: тип виджета — ``text``, ``int``, ``bool``, ``choice``,
        ``date``, ``time`` или ``fk`` (внешний ключ со списком значений).
    :param required: обязательное ли поле при создании/обновлении.
    :param choices: допустимые значения для ``kind="choice"``.
    :param show_in_table: показывать ли колонку в таблице записей.
    :param editable: доступно ли поле для редактирования в форме.
    :param filterable: показывать ли поле в панели фильтров.
    :param searchable: учитывать ли поле при подстрочном поиске.
    :param fk_provider: для ``kind="fk"`` — функция без аргументов,
        возвращающая список пар ``(значение, подпись)``.
    """

    name: str
    label: str
    kind: str = "text"
    required: bool = False
    choices: tuple[str, ...] = ()
    show_in_table: bool = True
    editable: bool = True
    filterable: bool = True
    searchable: bool = True
    fk_provider: Callable[[], list[tuple[Any, str]]] | None = None


class CrudTab(ttk.Frame):
    """Вкладка с таблицей записей, формой, поиском, фильтрами и CRUD-кнопками.

    Подклассы обязаны переопределить :meth:`field_specs`, :meth:`fetch_rows`,
    :meth:`fetch_one`, :meth:`create_record`, :meth:`update_record` и
    :meth:`delete_record`. Также рекомендуется задать :attr:`entity_name` —
    название сущности для сообщений.
    """

    #: Название сущности во множественном числе (для заголовков и статусов).
    entity_name = "записи"

    def __init__(self, master: tk.Misc, app: Any) -> None:
        super().__init__(master, padding=8)
        self.app = app
        self.fields: list[Field] = self.field_specs()

        # Служебное состояние.
        self._rows: list[dict] = []
        self._rows_by_id: dict[Any, dict] = {}
        self._selected_id: Any = None
        self._form_vars: dict[str, tk.Variable] = {}
        self._form_widgets: dict[str, ttk.Widget] = {}
        self._fk_maps: dict[str, dict[str, Any]] = {}
        self._fk_labels: dict[str, dict[Any, str]] = {}

        # Переменные фильтров и сортировки.
        self._filter_vars: dict[str, tk.Variable] = {}
        self._filter_maps: dict[str, dict[str, Any]] = {}
        self._filter_widgets: dict[str, ttk.Widget] = {}
        self._order_var = tk.StringVar()
        self._direction_var = tk.StringVar(value="ASC")
        self._limit_var = tk.StringVar()
        self._offset_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self.id_var = tk.StringVar()
        self.search_id_var = tk.StringVar()

        self._build_ui()
        self.refresh()

    # --- интерфейс, который переопределяют подклассы ---------------------------

    def field_specs(self) -> list[Field]:
        """Возвращает описание полей сущности."""
        raise NotImplementedError

    def fetch_rows(
        self,
        where: dict[str, Any] | None,
        order_by: Any,
        limit: int | None,
        offset: int | None,
    ) -> list[dict]:
        """Загружает записи из БД с учётом фильтров."""
        raise NotImplementedError

    def fetch_one(self, row_id: int) -> dict | None:
        """Загружает одну запись по ``id``."""
        raise NotImplementedError

    def create_record(self, data: dict[str, Any]) -> dict | None:
        """Создаёт запись по данным формы."""
        raise NotImplementedError

    def update_record(self, row_id: int, data: dict[str, Any]) -> Any:
        """Обновляет запись по ``id`` данными формы."""
        raise NotImplementedError

    def delete_record(self, row_id: int) -> Any:
        """Удаляет запись по ``id``."""
        raise NotImplementedError

    # --- построение интерфейса --------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._build_search_bar()
        self._build_filter_bar()
        self._build_body()

    def _build_search_bar(self) -> None:
        bar = ttk.LabelFrame(self, text="Поиск", padding=6)
        bar.grid(row=0, column=0, sticky="ew")

        ttk.Label(bar, text="Подстрока:").grid(row=0, column=0, padx=(0, 4))
        entry = ttk.Entry(bar, textvariable=self.search_var, width=32)
        entry.grid(row=0, column=1, padx=(0, 6))
        entry.bind("<Return>", lambda _event: self._apply_search())
        ttk.Button(bar, text="Найти", command=self._apply_search).grid(row=0, column=2)
        ttk.Button(bar, text="Сбросить", command=self._reset_search).grid(
            row=0, column=3, padx=(4, 16)
        )

        ttk.Label(bar, text="Поиск по ID:").grid(row=0, column=4, padx=(0, 4))
        id_entry = ttk.Entry(bar, textvariable=self.search_id_var, width=10)
        id_entry.grid(row=0, column=5, padx=(0, 6))
        id_entry.bind("<Return>", lambda _event: self._find_by_id())
        ttk.Button(bar, text="Найти", command=self._find_by_id).grid(row=0, column=6)

        self._search_hint = ttk.Label(
            bar, text="поиск по текстовым полям загруженных строк"
        )
        self._search_hint.grid(row=0, column=7, padx=(16, 0))

    def _build_filter_bar(self) -> None:
        bar = ttk.LabelFrame(self, text="Фильтры и сортировка", padding=6)
        bar.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        filterable = [f for f in self.fields if f.filterable]
        columns = 3
        for index, field in enumerate(filterable):
            row, col = divmod(index, columns)
            ttk.Label(bar, text=f"{field.label}:").grid(
                row=row, column=col * 2, sticky="e", padx=(0, 4), pady=2
            )
            widget = self._make_filter_widget(bar, field)
            widget.grid(row=row, column=col * 2 + 1, sticky="ew", padx=(0, 12), pady=2)

        sort_row = (len(filterable) + columns - 1) // columns
        ttk.Label(bar, text="Сортировка:").grid(
            row=sort_row, column=0, sticky="e", padx=(0, 4), pady=2
        )
        order_values = [f.name for f in self.fields if f.show_in_table]
        ttk.Combobox(
            bar,
            textvariable=self._order_var,
            values=[""] + order_values,
            state="readonly",
            width=14,
        ).grid(row=sort_row, column=1, sticky="ew", padx=(0, 12), pady=2)
        ttk.Combobox(
            bar,
            textvariable=self._direction_var,
            values=["ASC", "DESC"],
            state="readonly",
            width=6,
        ).grid(row=sort_row, column=2, sticky="w", padx=(0, 12), pady=2)

        ttk.Label(bar, text="Лимит:").grid(
            row=sort_row, column=3, sticky="e", padx=(0, 4), pady=2
        )
        ttk.Entry(bar, textvariable=self._limit_var, width=8).grid(
            row=sort_row, column=4, sticky="w", padx=(0, 12), pady=2
        )
        ttk.Label(bar, text="Смещение:").grid(
            row=sort_row, column=5, sticky="e", padx=(0, 4), pady=2
        )
        ttk.Entry(bar, textvariable=self._offset_var, width=8).grid(
            row=sort_row, column=6, sticky="w", pady=2
        )

        actions = ttk.Frame(bar)
        actions.grid(row=sort_row + 1, column=0, columnspan=7, sticky="w", pady=(6, 0))
        ttk.Button(actions, text="Применить", command=self._apply_filters).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(actions, text="Сбросить", command=self._reset_filters).pack(
            side="left"
        )

    def _make_filter_widget(self, master: tk.Misc, field: Field) -> ttk.Widget:
        if field.kind == "bool":
            var = tk.StringVar()
            widget = ttk.Combobox(
                master, textvariable=var, values=["", "Да", "Нет"], state="readonly",
                width=12,
            )
        elif field.kind == "choice":
            var = tk.StringVar()
            widget = ttk.Combobox(
                master, textvariable=var, values=["", *field.choices], state="readonly",
                width=12,
            )
        elif field.kind == "fk":
            var = tk.StringVar()
            mapping, _labels = self._load_fk_options(field)
            self._filter_maps[field.name] = mapping
            widget = ttk.Combobox(
                master, textvariable=var, values=["", *mapping], state="readonly",
                width=12,
            )
        else:
            var = tk.StringVar()
            widget = ttk.Entry(master, textvariable=var, width=14)
        self._filter_vars[field.name] = var
        self._filter_widgets[field.name] = widget
        return widget

    def _build_body(self) -> None:
        body = ttk.Frame(self)
        body.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        table_frame = ttk.Frame(body)
        table_frame.grid(row=0, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.table_fields = [f for f in self.fields if f.show_in_table]
        self.tree = ttk.Treeview(
            table_frame,
            columns=[f.name for f in self.table_fields],
            show="headings",
            selectmode="browse",
        )
        for field in self.table_fields:
            self.tree.heading(field.name, text=field.label)
            self.tree.column(field.name, width=110, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        self._build_form(body)

    def _build_form(self, master: tk.Misc) -> None:
        form = ttk.LabelFrame(master, text="Форма", padding=8)
        form.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        row = 0
        ttk.Label(form, text="ID:").grid(row=row, column=0, sticky="e", pady=2, padx=(0, 6))
        self._id_display = ttk.Entry(form, textvariable=self.id_var, width=24, state="readonly")
        self._id_display.grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        for field in self.fields:
            if not field.editable:
                continue
            ttk.Label(form, text=f"{field.label}:").grid(
                row=row, column=0, sticky="e", pady=2, padx=(0, 6)
            )
            widget = self._make_form_widget(form, field)
            widget.grid(row=row, column=1, sticky="ew", pady=2)
            row += 1

        buttons = ttk.Frame(form)
        buttons.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(buttons, text="Создать", command=self._on_create).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(buttons, text="Сохранить", command=self._on_update).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(buttons, text="Удалить", command=self._on_delete).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(buttons, text="Очистить форму", command=self._clear_form).pack(
            side="left"
        )
        self._add_form_actions(buttons)

        refresh_row = row + 1
        ttk.Button(form, text="Обновить список", command=lambda: self.refresh(notify=True)).grid(
            row=refresh_row, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

    def _add_form_actions(self, parent: ttk.Frame) -> None:
        """Хук для дополнительных кнопок формы в подклассах."""

    def _make_form_widget(self, master: tk.Misc, field: Field) -> ttk.Widget:
        if field.kind == "bool":
            var = tk.BooleanVar()
            widget = ttk.Checkbutton(master, variable=var, text="включено")
        elif field.kind == "choice":
            var = tk.StringVar()
            widget = ttk.Combobox(
                master, textvariable=var, values=list(field.choices), state="readonly",
                width=22,
            )
        elif field.kind == "fk":
            var = tk.StringVar()
            mapping, _labels = self._load_fk_options(field)
            self._fk_maps[field.name] = mapping
            widget = ttk.Combobox(
                master, textvariable=var, values=["", *mapping], state="readonly",
                width=22,
            )
        else:
            var = tk.StringVar()
            widget = ttk.Entry(master, textvariable=var, width=24)
        self._form_vars[field.name] = var
        self._form_widgets[field.name] = widget
        return widget

    def _reload_fk_options(self) -> None:
        """Обновляет значения выпадающих списков внешних ключей."""
        for field in self.fields:
            if field.kind != "fk":
                continue
            mapping, labels = self._load_fk_options(field)
            self._fk_maps[field.name] = mapping
            self._fk_labels[field.name] = labels
            form_widget = self._form_widgets.get(field.name)
            if isinstance(form_widget, ttk.Combobox):
                current = str(self._form_vars[field.name].get())
                form_widget.configure(values=["", *mapping])
                if current and current not in mapping:
                    self._form_vars[field.name].set("")
            filter_widget = self._filter_widgets.get(field.name)
            if isinstance(filter_widget, ttk.Combobox):
                self._filter_maps[field.name] = mapping
                filter_widget.configure(values=["", *mapping])

    def _load_fk_options(self, field: Field) -> tuple[dict[str, Any], dict[Any, str]]:
        """Возвращает отображения подпись→значение и значение→подпись для FK-поля."""
        mapping: dict[str, Any] = {}
        labels: dict[Any, str] = {}
        if field.fk_provider is None:
            return mapping, labels
        try:
            options = field.fk_provider()
        except DatabaseError:
            options = []
        for value, label in options:
            display = f"{value} — {label}" if label else str(value)
            mapping[display] = value
            labels[value] = display
        return mapping, labels

    # --- загрузка и отображение данных ------------------------------------------

    def refresh(self, notify: bool = False) -> None:
        """Перезагружает данные с учётом фильтров и перерисовывает таблицу."""
        try:
            where, order_by, limit, offset = self._collect_query()
        except ValueError as exc:
            self._rows = []
            if notify:
                messagebox.showerror("Фильтры", str(exc))
            self.app.set_status(f"Фильтры: {exc}")
            self._populate([])
            return
        self._reload_fk_options()
        try:
            self._rows = self.fetch_rows(where, order_by, limit, offset)
        except DatabaseError as exc:
            self._rows = []
            if notify:
                self._show_error(exc)
            self.app.set_status(f"Ошибка загрузки «{self.entity_name}»: {exc}")
        self._rows_by_id = {row.get("id"): row for row in self._rows}
        self._populate(self._visible_rows())

    def _populate(self, rows: list[dict]) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            values = [self._format_value(row.get(f.name), f) for f in self.table_fields]
            self.tree.insert("", "end", iid=str(row.get("id")), values=values)
        self.app.set_status(f"Показано записей «{self.entity_name}»: {len(rows)}")

    def _format_value(self, value: Any, field: Field) -> str:
        if value is None:
            return ""
        if field.kind == "bool":
            return "Да" if value else "Нет"
        return str(value)

    # --- поиск -------------------------------------------------------------------

    def _visible_rows(self) -> list[dict]:
        term = self.search_var.get().strip().lower()
        if not term:
            return self._rows
        result = []
        for row in self._rows:
            for field in self.fields:
                if not field.searchable:
                    continue
                value = row.get(field.name)
                if value is not None and term in str(value).lower():
                    result.append(row)
                    break
        return result

    def _apply_search(self) -> None:
        self._populate(self._visible_rows())

    def _reset_search(self) -> None:
        self.search_var.set("")
        self._populate(self._visible_rows())

    def _find_by_id(self) -> None:
        raw = self.search_id_var.get().strip()
        if not raw:
            messagebox.showinfo("Поиск по ID", "Введите ID записи.")
            return
        try:
            row_id = int(raw)
        except ValueError:
            messagebox.showerror("Поиск по ID", "ID должен быть целым числом.")
            return
        try:
            row = self.fetch_one(row_id)
        except DatabaseError as exc:
            self._show_error(exc)
            return
        if row is None:
            messagebox.showinfo("Поиск по ID", f"Запись с ID={row_id} не найдена.")
            self._populate([])
            return
        self._populate([row])
        self._select_row(row)

    # --- фильтры -----------------------------------------------------------------

    def _collect_query(self) -> tuple[dict[str, Any] | None, Any, int | None, int | None]:
        where: dict[str, Any] = {}
        for field in self.fields:
            if not field.filterable:
                continue
            var = self._filter_vars.get(field.name)
            if var is None:
                continue
            raw = var.get()
            if isinstance(raw, bool):
                raw = "Да" if raw else "Нет"
            raw = str(raw).strip()
            if not raw:
                continue
            try:
                where[field.name] = self._convert_filter_value(field, raw)
            except ValueError as exc:
                raise ValueError(f"Фильтр «{field.label}»: {exc}") from exc

        order_by = None
        column = self._order_var.get().strip()
        if column:
            order_by = (column, self._direction_var.get().strip() or "ASC")

        limit = self._parse_int(self._limit_var.get(), "Лимит")
        offset = self._parse_int(self._offset_var.get(), "Смещение")
        return (where or None), order_by, limit, offset

    def _convert_filter_value(self, field: Field, raw: str) -> Any:
        if field.kind == "bool":
            if raw not in ("Да", "Нет"):
                raise ValueError("ожидается «Да» или «Нет»")
            return raw == "Да"
        if field.kind == "fk":
            mapping = self._filter_maps.get(field.name, {})
            if raw not in mapping:
                raise ValueError("неизвестное значение")
            return mapping[raw]
        return self._convert_raw(field, raw)

    def _apply_filters(self) -> None:
        self.refresh(notify=True)

    def _reset_filters(self) -> None:
        for var in self._filter_vars.values():
            var.set("")
        self._order_var.set("")
        self._direction_var.set("ASC")
        self._limit_var.set("")
        self._offset_var.set("")
        self.refresh()

    # --- CRUD-действия -----------------------------------------------------------

    def _on_create(self) -> None:
        try:
            data = self._collect_form_data()
            created = self.create_record(data)
        except (ValueError, DatabaseError) as exc:
            self._show_error(exc, title="Создание записи")
            return
        self._clear_form()
        self.refresh()
        self.app.set_status(f"Создана запись «{self.entity_name}»: {created}")

    def _on_update(self) -> None:
        if self._selected_id is None:
            messagebox.showinfo("Обновление", "Выберите запись в таблице.")
            return
        try:
            data = self._collect_form_data()
            updated = self.update_record(self._selected_id, data)
        except (ValueError, DatabaseError) as exc:
            self._show_error(exc, title="Обновление записи")
            return
        self.refresh()
        self.app.set_status(f"Обновлена запись «{self.entity_name}» с ID={self._selected_id}")

    def _on_delete(self) -> None:
        if self._selected_id is None:
            messagebox.showinfo("Удаление", "Выберите запись в таблице.")
            return
        if not messagebox.askyesno(
            "Удаление", f"Удалить запись «{self.entity_name}» с ID={self._selected_id}?"
        ):
            return
        try:
            self.delete_record(self._selected_id)
        except DatabaseError as exc:
            self._show_error(exc, title="Удаление записи")
            return
        self._clear_form()
        self.refresh()
        self.app.set_status(f"Удалена запись «{self.entity_name}» с ID={self._selected_id}")

    # --- форма -------------------------------------------------------------------

    def _collect_form_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for field in self.fields:
            if not field.editable:
                continue
            var = self._form_vars.get(field.name)
            if var is None:
                continue
            if field.kind == "bool":
                data[field.name] = bool(var.get())
                continue
            raw = str(var.get()).strip()
            if not raw:
                if field.required:
                    raise ValueError(f"Поле «{field.label}» обязательно для заполнения.")
                data[field.name] = None
                continue
            if field.kind == "fk":
                mapping = self._fk_maps.get(field.name, {})
                if raw not in mapping:
                    raise ValueError(f"Поле «{field.label}»: неизвестное значение.")
                data[field.name] = mapping[raw]
                continue
            data[field.name] = self._convert_raw(field, raw)
        return data

    def _convert_raw(self, field: Field, raw: str) -> Any:
        if field.kind == "int":
            try:
                return int(raw)
            except ValueError:
                raise ValueError(f"Поле «{field.label}»: ожидается целое число.") from None
        if field.kind == "date":
            try:
                return date.fromisoformat(raw)
            except ValueError:
                raise ValueError(
                    f"Поле «{field.label}»: ожидается дата в формате ГГГГ-ММ-ДД."
                ) from None
        if field.kind == "time":
            try:
                return time.fromisoformat(raw)
            except ValueError:
                raise ValueError(
                    f"Поле «{field.label}»: ожидается время в формате ЧЧ:ММ."
                ) from None
        return raw

    def _on_select(self, _event: tk.Event) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        row = self._rows_by_id.get(self._to_id(selection[0]))
        if row is not None:
            self._fill_form(row)

    def _select_row(self, row: dict) -> None:
        row_id = str(row.get("id"))
        if self.tree.exists(row_id):
            self.tree.selection_set(row_id)
            self.tree.focus(row_id)
        self._fill_form(row)

    def _fill_form(self, row: dict) -> None:
        self._selected_id = row.get("id")
        self.id_var.set(str(row.get("id", "")))
        for field in self.fields:
            if not field.editable:
                continue
            var = self._form_vars.get(field.name)
            if var is None:
                continue
            value = row.get(field.name)
            if field.kind == "bool":
                var.set(bool(value))
            elif field.kind == "fk":
                labels = self._fk_labels.get(field.name) or self._ensure_fk_labels(field)
                var.set(labels.get(value, ""))
            else:
                var.set("" if value is None else str(value))

    def _ensure_fk_labels(self, field: Field) -> dict[Any, str]:
        mapping, labels = self._load_fk_options(field)
        self._fk_maps[field.name] = mapping
        self._fk_labels[field.name] = labels
        return labels

    def _clear_form(self) -> None:
        self._selected_id = None
        self.id_var.set("")
        for field in self.fields:
            if not field.editable:
                continue
            var = self._form_vars.get(field.name)
            if var is None:
                continue
            if field.kind == "bool":
                var.set(True)
            else:
                var.set("")
        if self.tree.selection():
            self.tree.selection_remove(*self.tree.selection())

    # --- вспомогательные методы --------------------------------------------------

    @staticmethod
    def _to_id(raw: str) -> Any:
        try:
            return int(raw)
        except ValueError:
            return raw

    @staticmethod
    def _parse_int(raw: str, label: str) -> int | None:
        raw = raw.strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            raise ValueError(f"{label}: ожидается целое число.") from None

    def _show_error(self, exc: Exception, title: str = "Ошибка базы данных") -> None:
        messagebox.showerror(title, str(exc))
        self.app.set_status(f"{title}: {exc}")
