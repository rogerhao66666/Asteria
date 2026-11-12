"""A table field whose rows are a few picks each, shown as one grid (D109): the fields' names
once at the top, a line per row (a drop-down per field, ✕ at its end), "+ Add" below. Game
Start ▸ Starting Equipment (hero, slot, gear) reads this way instead of a card per piece.

Same API as the page's other table fields (``rows``, ``set_rows``, ``add_row``,
``remove_row``, ``values``, ``changed``); a field asks for it with ``FormField.grid``.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
)

GRID_KINDS = ("ref", "optional_ref", "choice")  # the fields a grid row can hold


def fits_grid(fields):
    """Every field a pick from a list (a grid has a drop-down per cell)."""
    return bool(fields) and all(f.kind in GRID_KINDS for f in fields)


class GridTable(QGroupBox):
    """``choices(field)``: the ``(value, words, icon or None)`` a field's drop-down offers;
    ``fresh(rows)``: a new row's data."""

    changed = Signal()
    ROW = 32

    def __init__(self, label, fields, choices, fresh, parent=None):
        super().__init__("", parent)
        self.label = label
        self.setProperty("untitled", True)
        self.fields, self.choices, self.fresh = tuple(fields), choices, fresh
        self._rows = []
        self.table = QTableWidget(0, len(self.fields) + 1, self)
        self.table.setObjectName("FormGridTable")
        self.table.setHorizontalHeaderLabels([f.label for f in self.fields] + [""])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(self.ROW)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.wheelEvent = lambda event: event.ignore()  # the page scrolls, not it
        head = self.table.horizontalHeader()
        head.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for column in range(len(self.fields)):
            head.setSectionResizeMode(column, QHeaderView.Stretch)
        head.setSectionResizeMode(len(self.fields), QHeaderView.Fixed)
        self.table.setColumnWidth(len(self.fields), 34)
        self.empty = QLabel("None yet.")
        self.empty.setObjectName("FieldHint")
        add = QPushButton("+ Add")
        add.setObjectName("FormAddButton")
        add.clicked.connect(lambda: (self.add_row(), self.changed.emit()))
        buttons = QHBoxLayout()
        buttons.addWidget(add)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.addWidget(self.empty)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        self._show()

    @property
    def rows(self):
        return [copy.deepcopy(r) for r in self._rows]

    def values(self):
        return self.rows

    def set_rows(self, rows):
        self._rows = [copy.deepcopy(dict(r)) for r in rows]
        self._show()

    def add_row(self):
        self._rows.append(self.fresh(self._rows))
        self._show()
        return self._rows[-1]

    def remove_row(self):
        if self._rows:
            self._rows.pop()
            self._show()

    def _remove(self, index):
        del self._rows[index]
        self._show()
        self.changed.emit()

    def _picked(self, index, key, combo):
        self._rows[index][key] = combo.currentData()
        self.changed.emit()

    def _combo(self, index, f, value):
        combo = QComboBox()
        combo.setObjectName("FormGridPick")
        offered = list(self.choices(f))
        if f.kind == "optional_ref":
            offered.insert(0, ("", f.empty_label or "(none)", None))
        if value not in {v for v, _w, _i in offered}:  # a value the lists no longer have: kept
            offered.append((value, str(value), None))
        for choice, shown, icon in offered:
            if icon is not None:
                combo.addItem(icon, str(shown), choice)
            else:
                combo.addItem(str(shown), choice)
        combo.setCurrentIndex(max(0, combo.findData(value)))
        combo.activated.connect(lambda _i, k=f.key, c=combo: self._picked(index, k, c))
        return combo

    def _show(self):
        self.table.setRowCount(len(self._rows))
        for index, row in enumerate(self._rows):
            for column, f in enumerate(self.fields):
                self.table.setCellWidget(index, column, self._combo(index, f, row.get(f.key)))
            remove = QToolButton()
            remove.setText("✕")
            remove.setObjectName("FormGridRemove")
            remove.setToolTip("Remove this row")
            remove.clicked.connect(lambda _c=False, i=index: self._remove(i))
            self.table.setCellWidget(index, len(self.fields), remove)
        header = self.table.horizontalHeader().height() or 26
        self.table.setFixedHeight(header + self.ROW * len(self._rows) + 4)
        self.table.setVisible(bool(self._rows))
        self.empty.setVisible(not self._rows)


__all__ = ["GRID_KINDS", "GridTable", "fits_grid"]
