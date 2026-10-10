"""Form-based Qt editors for shops, quests, factions, achievements, equipment sets and capture rules (CB10h).

Forms are generated from :data:`asteria.editor.game_systems_authoring.FORMS`
and edit canonical record data; every Apply goes through
:class:`GameSystemsAuthoringController`, the same API scripts use.
"""
from __future__ import annotations

import copy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .game_systems_authoring import FORMS, KINDS, GameSystemsAuthoringError, new_row

_BIG = 1_000_000_000


class _KeyValueTable(QWidget):
    """Two-column table with Add / Remove rows (``amounts`` and ``pairs`` fields)."""

    def __init__(self, headers, parent=None):
        super().__init__(parent)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(list(headers))
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(90)
        add, remove = QPushButton("Add"), QPushButton("Remove")
        add.clicked.connect(lambda: self.add_row("", ""))
        remove.clicked.connect(self.remove_row)
        buttons = QHBoxLayout()
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

    def add_row(self, a, b):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(a)))
        self.table.setItem(row, 1, QTableWidgetItem(str(b)))
        return row

    def remove_row(self):
        row = self.table.currentRow()
        if row < 0:
            row = self.table.rowCount() - 1
        if row >= 0:
            self.table.removeRow(row)

    def rows(self):
        out = []
        for row in range(self.table.rowCount()):
            a = self.table.item(row, 0)
            b = self.table.item(row, 1)
            out.append(((a.text() if a else "").strip(), (b.text() if b else "").strip()))
        return [r for r in out if r[0] or r[1]]


class _RefList(QListWidget):
    """Checkable list of references; keeps the authored order of checked entries."""

    def __init__(self, choices, parent=None):
        super().__init__(parent)
        self.choices = tuple(choices)
        self.setMinimumHeight(70)

    def set_values(self, values):
        self.clear()
        values = list(values)
        for choice in list(dict.fromkeys(values + list(self.choices))):
            item = QListWidgetItem(choice)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if choice in values else Qt.Unchecked)
            self.addItem(item)

    def values(self):
        return [self.item(i).text() for i in range(self.count()) if self.item(i).checkState() == Qt.Checked]

    def set_checked(self, value, checked=True):
        for i in range(self.count()):
            if self.item(i).text() == value:
                self.item(i).setCheckState(Qt.Checked if checked else Qt.Unchecked)
                return True
        return False


class _TableField(QGroupBox):
    """Master–detail editor for a list of nested records."""

    def __init__(self, label, fields, references, parent=None):
        super().__init__(label, parent)
        self.fields = fields
        self.rows = []
        self._current = -1
        self.list = QListWidget()
        self.list.setMaximumHeight(110)
        self.list.currentRowChanged.connect(self._select)
        self.detail = RecordForm(fields, references)
        self.detail.setEnabled(False)
        add, remove = QPushButton("Add"), QPushButton("Remove")
        add.clicked.connect(self.add_row)
        remove.clicked.connect(self.remove_row)
        buttons = QHBoxLayout()
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addLayout(buttons)
        layout.addWidget(self.detail)

    def _label(self, row):
        first = self.fields[0].key
        value = row.get(first, "")
        return f"{self.fields[0].label}: {value}"

    def _commit(self):
        if 0 <= self._current < len(self.rows):
            self.rows[self._current] = self.detail.data()
            item = self.list.item(self._current)
            if item is not None:
                item.setText(self._label(self.rows[self._current]))

    def _select(self, row):
        self._commit()
        self._current = row
        if 0 <= row < len(self.rows):
            self.detail.set_data(self.rows[row])
            self.detail.setEnabled(True)
        else:
            self.detail.setEnabled(False)

    def set_rows(self, rows):
        self._current = -1
        self.rows = [copy.deepcopy(r) for r in rows]
        self.list.blockSignals(True)
        self.list.clear()
        for row in self.rows:
            self.list.addItem(self._label(row))
        self.list.blockSignals(False)
        self.detail.setEnabled(False)
        if self.rows:
            self.list.setCurrentRow(0)

    def add_row(self):
        self._commit()
        self.rows.append(new_row(self.fields))
        self.list.addItem(self._label(self.rows[-1]))
        self.list.setCurrentRow(len(self.rows) - 1)
        return self.detail

    def remove_row(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.rows):
            self._current = -1
            del self.rows[row]
            self.list.takeItem(row)
            if self.rows:
                self.list.setCurrentRow(min(row, len(self.rows) - 1))
            else:
                self.detail.setEnabled(False)

    def values(self):
        self._commit()
        return [copy.deepcopy(r) for r in self.rows]


class RecordForm(QWidget):
    """Widgets for one record described by a tuple of FormField specs."""

    changed = Signal()

    def __init__(self, fields, references, parent=None):
        super().__init__(parent)
        self.fields = tuple(fields)
        self.references = references
        self.widgets = {}
        self._original = {}
        form = QFormLayout(self)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for f in self.fields:
            widget = self._build(f)
            self.widgets[f.key] = widget
            if f.kind in ("group", "table"):
                form.addRow(widget)
            else:
                form.addRow(f.label, widget)

    def _build(self, f):
        if f.kind == "id":
            widget = QLineEdit()
            widget.setReadOnly(True)
            return widget
        if f.kind == "text":
            return QLineEdit()
        if f.kind == "multiline":
            widget = QPlainTextEdit()
            widget.setMaximumHeight(70)
            return widget
        if f.kind == "int":
            widget = QSpinBox()
            widget.setRange(-_BIG, _BIG)
            return widget
        if f.kind == "float":
            widget = QDoubleSpinBox()
            widget.setRange(-_BIG, _BIG)
            widget.setDecimals(3)
            return widget
        if f.kind == "bool":
            return QCheckBox()
        if f.kind == "choice":
            widget = QComboBox()
            widget.addItems(list(f.choices))
            return widget
        if f.kind in ("ref", "optional_ref"):
            widget = QComboBox()
            if f.kind == "optional_ref":
                widget.addItem("")
            widget.addItems(list(self.references(f.source)))
            return widget
        if f.kind == "optional_int":
            box = QWidget()
            row = QHBoxLayout(box)
            row.setContentsMargins(0, 0, 0, 0)
            box.check = QCheckBox("Limited")
            box.spin = QSpinBox()
            box.spin.setRange(0, _BIG)
            box.check.toggled.connect(box.spin.setEnabled)
            row.addWidget(box.check)
            row.addWidget(box.spin, 1)
            return box
        if f.kind == "ref_list":
            return _RefList(self.references(f.source))
        if f.kind == "string_list":
            widget = QLineEdit()
            widget.setPlaceholderText("comma, separated, values")
            return widget
        if f.kind == "amounts":
            return _KeyValueTable(("Key", "Amount"))
        if f.kind == "pairs":
            return _KeyValueTable(("Threshold", "Name"))
        if f.kind == "group":
            box = QGroupBox(f.label)
            layout = QVBoxLayout(box)
            box.form = RecordForm(f.fields, self.references)
            layout.addWidget(box.form)
            return box
        if f.kind == "table":
            return _TableField(f.label, f.fields, self.references)
        raise ValueError(f"unknown form field kind: {f.kind}")

    def set_data(self, data):
        self._original = copy.deepcopy(data)
        for f in self.fields:
            widget, value = self.widgets[f.key], data.get(f.key, f.default)
            if f.kind in ("id", "text"):
                widget.setText("" if value is None else str(value))
            elif f.kind == "multiline":
                widget.setPlainText(str(value or ""))
            elif f.kind == "int":
                widget.setValue(int(value or 0))
            elif f.kind == "float":
                widget.setValue(float(value or 0.0))
            elif f.kind == "bool":
                widget.setChecked(bool(value))
            elif f.kind in ("choice", "ref", "optional_ref"):
                text = "" if value is None else str(value)
                if widget.findText(text) < 0:
                    widget.addItem(text)
                widget.setCurrentIndex(widget.findText(text))
            elif f.kind == "optional_int":
                widget.check.setChecked(value is not None)
                widget.spin.setEnabled(value is not None)
                widget.spin.setValue(int(value or 0))
            elif f.kind == "ref_list":
                widget.set_values(value or ())
            elif f.kind == "string_list":
                widget.setText(", ".join(value or ()))
            elif f.kind == "amounts":
                widget.table.setRowCount(0)
                for k, v in dict(value or {}).items():
                    widget.add_row(k, f"{float(v):g}")
            elif f.kind == "pairs":
                widget.table.setRowCount(0)
                for t, n in value or ():
                    widget.add_row(f"{float(t):g}", n)
            elif f.kind == "group":
                widget.form.set_data(value or {})
            elif f.kind == "table":
                widget.set_rows(value or ())

    def data(self):
        out = copy.deepcopy(self._original)
        for f in self.fields:
            widget = self.widgets[f.key]
            if f.kind in ("id", "text"):
                out[f.key] = widget.text().strip()
            elif f.kind == "multiline":
                out[f.key] = widget.toPlainText()
            elif f.kind in ("int", "float"):
                out[f.key] = widget.value()
            elif f.kind == "bool":
                out[f.key] = widget.isChecked()
            elif f.kind in ("choice", "ref", "optional_ref"):
                out[f.key] = widget.currentText()
            elif f.kind == "optional_int":
                out[f.key] = widget.spin.value() if widget.check.isChecked() else None
            elif f.kind == "ref_list":
                out[f.key] = widget.values()
            elif f.kind == "string_list":
                out[f.key] = [x.strip() for x in widget.text().split(",") if x.strip()]
            elif f.kind == "amounts":
                out[f.key] = {k: _number(v, k) for k, v in widget.rows()}
            elif f.kind == "pairs":
                out[f.key] = [[_number(t, n), n] for t, n in widget.rows()]
            elif f.kind == "group":
                out[f.key] = widget.form.data()
            elif f.kind == "table":
                out[f.key] = widget.values()
        return out


def _number(text, label):
    try:
        return float(text)
    except ValueError:
        raise GameSystemsAuthoringError(f"{label}: '{text}' is not a number") from None


class GameSystemsEditorWidget(QWidget):
    """Browse, create, duplicate, edit and delete game-system definitions."""

    changed = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.kind_box = QComboBox()
        for kind in KINDS:
            self.kind_box.addItem(kind.label, kind.kind_id)
        self.kind_box.currentIndexChanged.connect(self.refresh)
        self.browser = QListWidget()
        self.browser.setSelectionMode(QAbstractItemView.SingleSelection)
        self.browser.currentRowChanged.connect(self._selected)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.form = None
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.used_by = QLabel("")
        buttons = QHBoxLayout()
        for label, slot in (("New…", self._new_clicked), ("Duplicate…", self._duplicate_clicked),
                            ("Delete", self.delete_selected), ("Apply Changes", self.apply)):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        header = QHBoxLayout()
        header.addWidget(QLabel("Game Systems"))
        header.addStretch(1)
        header.addWidget(self.kind_box)
        split = QSplitter()
        split.addWidget(self.browser)
        split.addWidget(self.scroll)
        split.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(split, 1)
        layout.addWidget(self.used_by)
        layout.addWidget(self.status)
        layout.addLayout(buttons)
        self.refresh()

    @property
    def kind_id(self):
        return self.kind_box.currentData()

    @property
    def selected_id(self):
        item = self.browser.currentItem()
        return None if item is None else item.text()

    def set_kind(self, kind_id):
        self.kind_box.setCurrentIndex(self.kind_box.findData(kind_id))

    def refresh(self, select=None):
        current = select or self.selected_id
        if self.controller.document.project is None:
            self.browser.clear()
            self.scroll.setWidget(QLabel("Open a Project to edit game systems."))
            self.form = None
            return
        self.form = RecordForm(FORMS[self.kind_id], self.controller.references)
        self.scroll.setWidget(self.form)
        self.browser.blockSignals(True)
        self.browser.clear()
        ids = self.controller.ids(self.kind_id)
        self.browser.addItems(list(ids))
        self.browser.blockSignals(False)
        self.form.setEnabled(bool(ids))
        if ids:
            self.browser.setCurrentRow(ids.index(current) if current in ids else 0)
        else:
            self.used_by.setText("")

    def _selected(self, row):
        key = self.selected_id
        if key is None:
            return
        self.form.set_data(self.controller.form_data(self.kind_id, key))
        self.form.setEnabled(True)
        users = self.controller.where_used(self.kind_id, key)
        self.used_by.setText("Used by: " + ", ".join(users) if users else "")

    def _report(self, text, ok=True):
        self.status.setStyleSheet("" if ok else "color: #d9534f;")
        self.status.setText(text)

    def _attempt(self, action, message, select=None):
        try:
            action()
        except (GameSystemsAuthoringError, ValueError, TypeError) as exc:
            self._report(str(exc), ok=False)
            return False
        self._report(message)
        self.changed.emit()
        self.refresh(select)
        return True

    def apply(self):
        key = self.selected_id
        if key is None:
            return False
        return self._attempt(lambda: self.controller.edit(self.kind_id, key, self.form.data()), f"Applied {key}", key)

    def new_record(self, key):
        key = str(key).strip()
        return self._attempt(lambda: self.controller.create_new(self.kind_id, key), f"Created {key}", key)

    def duplicate_as(self, key):
        source = self.selected_id
        if source is None:
            return False
        key = str(key).strip()
        return self._attempt(lambda: self.controller.duplicate(self.kind_id, source, key), f"Duplicated as {key}", key)

    def delete_selected(self):
        key = self.selected_id
        if key is None:
            return False
        return self._attempt(lambda: self.controller.delete(self.kind_id, key), f"Deleted {key}")

    def _new_clicked(self):
        kind = self.kind_id
        if kind == "capture_rules":
            choices = [x for x in self.controller.references("enemies") if x not in self.controller.ids(kind)]
            key, ok = QInputDialog.getItem(self, "New Capture Rule", "Enemy:", choices, 0, False)
        else:
            key, ok = QInputDialog.getText(self, "New", "ID:")
        if ok and str(key).strip():
            self.new_record(key)

    def _duplicate_clicked(self):
        if self.selected_id is None:
            return
        key, ok = QInputDialog.getText(self, "Duplicate", "New ID:")
        if ok and key.strip():
            self.duplicate_as(key)
