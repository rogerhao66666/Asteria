"""Spreadsheet-style editors for canonical record fields.

The authoring hub used to render every list/dict field as a stack of group
boxes driven by "+"/"−" tool buttons, which gave no indication of what a row
was supposed to contain. These widgets render the same data as a table that is
edited by double-clicking a cell (plus a right-click menu for row add/remove),
which is how comparable RPG authoring tools present the same data.

Nested values inside a cell are shown in a compact inline form ("hp=10, mp=4")
and parsed back against the previous value, so the canonical deserializer still
sees the same Python types it did before.
"""
from __future__ import annotations

import json

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QAbstractItemView, QHeaderView, QMenu, QStyledItemDelegate,
        QTableWidget, QTableWidgetItem,
    )
    QT_AVAILABLE = True
except ImportError:  # pragma: no cover - headless import guard
    QT_AVAILABLE = False

    class QTableWidget:  # type: ignore[no-redef]
        pass

    class QStyledItemDelegate:  # type: ignore[no-redef]
        pass


class _FullCellEditorDelegate(QStyledItemDelegate):
    """Qt sizes a spawned cell editor from the item's own CSS padding (via
    the style's text sub-rect), not from the row's actual height — so once
    `::item` has vertical padding, the editor comes out shorter than the row
    it sits in and floats inside it looking shrunk, clipping the very text
    it's there to edit. The row height here is deliberately taller than the
    padded text needs (see ROW_HEIGHT below), which only makes the mismatch
    bigger. Forcing the editor to the full cell rect sidesteps that
    calculation entirely instead of trying to tune padding numbers to match."""

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


def is_scalar(value):
    return value is None or isinstance(value, (bool, int, float, str))


def prettify(key):
    return str(key).replace("_", " ").strip().title()


def format_cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        text = f"{value:g}" if isinstance(value, float) else str(value)
        return text
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if all(is_scalar(v) for v in value.values()):
            return ", ".join(f"{k}={format_cell(v)}" for k, v in value.items())
        return json.dumps(value)
    if isinstance(value, list):
        if all(is_scalar(v) for v in value):
            return ", ".join(format_cell(v) for v in value)
        return json.dumps(value)
    return str(value)


def _parse_number(text, template):
    try:
        number = float(text)
    except ValueError:
        return template
    return int(number) if isinstance(template, int) and not isinstance(template, bool) else number


def parse_cell(text, template):
    """Parse edited cell text back into the type `template` already had."""
    text = str(text).strip()
    if isinstance(template, bool):
        return text.lower() in ("true", "1", "yes", "on")
    if isinstance(template, (int, float)):
        return _parse_number(text, template)
    if template is None or isinstance(template, str):
        return None if (template is None and not text) else text
    if isinstance(template, dict):
        if template and not all(is_scalar(v) for v in template.values()):
            return _parse_json(text, template)
        sample = next((v for v in template.values() if is_scalar(v)), 0.0)
        result = {}
        for chunk in text.split(","):
            if not chunk.strip():
                continue
            key, _, raw = chunk.partition("=")
            key = key.strip()
            if key:
                result[key] = parse_cell(raw.strip(), template.get(key, sample))
        return result
    if isinstance(template, list):
        if template and not all(is_scalar(v) for v in template):
            return _parse_json(text, template)
        sample = template[0] if template else ""
        return [parse_cell(x.strip(), sample) for x in text.split(",") if x.strip()]
    return template


def _parse_json(text, template):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return template


# A row can only be added to an empty list if the editor knows what a row of
# that field looks like; these mirror the canonical `to_data()` shapes.
LIST_TEMPLATES = {
    "milestones": {"rank": 1, "required_total": 0.0, "stat_bonuses": {}, "granted_abilities": [], "granted_tags": []},
    "class_assignments": {
        "schema": "asteria.rpg.class_assignment", "version": 1, "class_id": "",
        "assignment_id": "", "role": "class", "enabled": True, "priority": 0,
        "progression_track_ids": [], "tags": [],
    },
    "nodes": {
        "schema": "asteria.rpg.progression_node", "version": 1, "node_id": "",
        "display_name": "", "max_rank": 1, "rank_costs": [{}],
        "rewards": [{"stat_bonuses": {}, "resource_bonuses": {}, "granted_tags": [],
                     "granted_abilities": [], "unlocked_passives": [], "granted_capabilities": []}],
        "prerequisites": [], "any_prerequisites": [], "exclusive_group": None, "tags": [],
    },
    "prerequisites": {"node_id": "", "minimum_rank": 1},
    "any_prerequisites": {"node_id": "", "minimum_rank": 1},
    "modifiers": {"stat": "", "add": 0.0, "multiply": 1.0},
    "members": {"enemy_id": "", "count": 1},
    "slots": {"slot_id": "", "row": 0, "column": 0},
    "placements": {"actor_id": "", "slot_id": ""},
}


def row_template(field_name, existing):
    """Shape for a new row: copy the last row, else a known template."""
    if existing:
        return json.loads(json.dumps(existing[-1]))
    template = LIST_TEMPLATES.get(str(field_name))
    return json.loads(json.dumps(template)) if template else None


# Tables always show this many rows even when the data has fewer, so a field is
# something you type into rather than something you first have to press "+" on.
# Typing in the last row appends another; clearing rows shrinks back to here.
# Kept small enough that the default rows are visible without scrolling the
# table itself — the page around it scrolls, not the table (see
# AdapterFamilyWidget's shared editor_page QScrollArea).
DEFAULT_BLANK_ROWS = 4

# Row height in pixels. Taller than Qt's own default so a cell's text has
# breathing room and isn't crowded by the row above/below while editing.
ROW_HEIGHT = 28


class _EditableTable(QTableWidget):
    """Base table: inline editing plus a right-click add/remove row menu.

    Rows beyond the data are real, editable blank rows: filling the last one
    commits it to the record and grows the table, so a list is never a dead
    empty box waiting for an add button.
    """

    def __init__(self, on_changed, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self._loading = False
        self._on_changed = on_changed
        self.setObjectName("RecordTable")
        self.setItemDelegate(_FullCellEditorDelegate(self))
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)
        self.setGridStyle(Qt.SolidLine)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.AnyKeyPressed
        )
        # The table itself never scrolls — its minimum height always covers
        # every row (see _fit()), and the page it sits on scrolls instead.
        # A table with its own internal scrollbar next to a page scrollbar is
        # exactly the "two scroll regions fighting" layout this avoids.
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Horizontally it is the opposite: a table with more columns than fit
        # must scroll *itself*. Without a minimum it can shrink to nothing,
        # and without the freedom to shrink it would instead push the whole
        # form wider than the page and drag every other panel off to the left.
        self.setMinimumWidth(160)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self.itemChanged.connect(self._item_changed)

    def _show_menu(self, point):
        menu = QMenu(self)
        add = menu.addAction("Add Row")
        remove = menu.addAction("Remove Row")
        remove.setEnabled(self.currentRow() >= 0)
        chosen = menu.exec(self.viewport().mapToGlobal(point))
        if chosen is add:
            self.add_row()
        elif chosen is remove:
            self.remove_row(self.currentRow())

    def _item_changed(self, item):
        if self._loading:
            return
        self.sync()
        self._on_changed()
        if self.rowCount() != self._wanted_rows():
            row, column = self.currentRow(), self.currentColumn()
            self.reload()
            self.setCurrentCell(min(row, self.rowCount() - 1), column)

    def _wanted_rows(self):
        return max(DEFAULT_BLANK_ROWS, self.data_rows() + 1)

    def _fill_blanks(self, first_blank):
        for row in range(first_blank, self.rowCount()):
            for column in range(self.columnCount()):
                if self.item(row, column) is None:
                    self.setItem(row, column, QTableWidgetItem(""))

    # Past this many columns, stretching squeezes every header into an
    # unreadable stub ("lode I", "olay Na"); size to content and scroll instead.
    _STRETCH_COLUMN_LIMIT = 4

    def _fit(self):
        header = self.horizontalHeader()
        stretch = self.columnCount() <= self._STRETCH_COLUMN_LIMIT
        for column in range(self.columnCount()):
            header.setSectionResizeMode(
                column, QHeaderView.Stretch if stretch else QHeaderView.Interactive
            )
        if not stretch:
            self.resizeColumnsToContents()
            for column in range(self.columnCount()):
                width = max(self.columnWidth(column), header.sectionSizeHint(column) + 12)
                self.setColumnWidth(column, width)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff if stretch else Qt.ScrollBarAsNeeded
        )
        header_height = self.horizontalHeader().height() or ROW_HEIGHT
        extra = header_height + (0 if stretch else 16)
        self.setMinimumHeight(self.rowCount() * ROW_HEIGHT + extra)

    def add_row(self):
        """Rows grow by typing; this only makes the spare row visible."""
        self.setRowCount(self.rowCount() + 1)
        self._fill_blanks(self.rowCount() - 1)
        self._fit()
        self.setCurrentCell(self.rowCount() - 1, 0)
        self.editItem(self.item(self.rowCount() - 1, 0))

    def remove_row(self, row):
        if not 0 <= row < self.rowCount():
            return
        self._loading = True
        for column in range(self.columnCount()):
            self.setItem(row, column, QTableWidgetItem(""))
        self._loading = False
        self.sync()
        self._on_changed()
        self.reload()

    # Subclasses own the data side.
    def data_rows(self):
        raise NotImplementedError

    def sync(self):
        """Rebuild the record from every non-empty row in the grid."""
        raise NotImplementedError


class MappingTable(_EditableTable):
    """Two-column Name/Value table over a dict of scalars (stats, bonuses)."""

    def __init__(self, mapping, on_changed, *, name_header="Name", suggestions=(), parent=None):
        super().__init__(on_changed, parent)
        self._mapping = mapping
        self._suggestions = tuple(suggestions)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels([name_header, "Value"])
        self.reload()

    def data_rows(self):
        return len(self._mapping)

    def reload(self):
        self._loading = True
        keys = list(self._mapping)
        self.setRowCount(self._wanted_rows())
        for row, key in enumerate(keys):
            self.setItem(row, 0, QTableWidgetItem(str(key)))
            self.setItem(row, 1, QTableWidgetItem(format_cell(self._mapping[key])))
        self._fill_blanks(len(keys))
        self._loading = False
        self._fit()

    def sync(self):
        previous = dict(self._mapping)
        rebuilt = {}
        for row in range(self.rowCount()):
            name = self._text(row, 0).strip()
            if not name:
                continue
            template = previous.get(name, 0.0)
            rebuilt[name] = parse_cell(self._text(row, 1), template)
        self._mapping.clear()
        self._mapping.update(rebuilt)

    def _text(self, row, column):
        item = self.item(row, column)
        return item.text() if item is not None else ""


class ScalarListTable(_EditableTable):
    """One-column table over a list of scalars (tags, granted ability ids)."""

    def __init__(self, owner, key, on_changed, *, header=None, parent=None):
        super().__init__(on_changed, parent)
        self._owner = owner
        self._key = key
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels([header or prettify(key)])
        self.reload()

    @property
    def _items(self):
        return self._owner[self._key]

    def data_rows(self):
        return len(self._items)

    def reload(self):
        self._loading = True
        items = list(self._items)
        self.setRowCount(self._wanted_rows())
        for row, value in enumerate(items):
            self.setItem(row, 0, QTableWidgetItem(format_cell(value)))
        self._fill_blanks(len(items))
        self._loading = False
        self._fit()

    def sync(self):
        items = self._items
        sample = items[0] if items else ""
        values = []
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            text = item.text().strip() if item is not None else ""
            if text:
                values.append(parse_cell(text, sample))
        items[:] = values


class RecordListTable(_EditableTable):
    """Column-per-field table over a list of records (milestones, nodes…)."""

    def __init__(self, owner, key, on_changed, parent=None):
        super().__init__(on_changed, parent)
        self._owner = owner
        self._key = key
        self._fields = ()
        self.reload()

    @property
    def _items(self):
        return self._owner[self._key]

    def data_rows(self):
        return len(self._items)

    def _columns(self):
        columns = []
        for item in self._items:
            if isinstance(item, dict):
                for field in item:
                    if field not in columns and field not in ("schema", "version"):
                        columns.append(field)
        if not columns:
            template = LIST_TEMPLATES.get(str(self._key)) or {}
            columns = [f for f in template if f not in ("schema", "version")]
        return columns

    def reload(self):
        self._loading = True
        self._fields = self._columns()
        items = list(self._items)
        self.setColumnCount(max(1, len(self._fields)))
        self.setHorizontalHeaderLabels(
            [prettify(f) for f in self._fields] or ["(no fields)"]
        )
        self.setRowCount(self._wanted_rows())
        for row, item in enumerate(items):
            for column, field in enumerate(self._fields):
                value = item.get(field) if isinstance(item, dict) else item
                self.setItem(row, column, QTableWidgetItem(format_cell(value)))
        self._fill_blanks(len(items))
        self._loading = False
        self._fit()

    def sync(self):
        items = self._items
        rows = []
        for row in range(self.rowCount()):
            texts = [self._text(row, c) for c in range(len(self._fields))]
            if not any(text.strip() for text in texts):
                continue
            base = items[len(rows)] if len(rows) < len(items) else row_template(self._key, items)
            if not isinstance(base, dict):
                base = {field: "" for field in self._fields}
            record = json.loads(json.dumps(base))
            for column, field in enumerate(self._fields):
                record[field] = parse_cell(texts[column], base.get(field))
            rows.append(record)
        items[:] = rows

    def _text(self, row, column):
        item = self.item(row, column)
        return item.text() if item is not None else ""
