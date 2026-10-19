"""Layouts that use the width they get, so a form shows as much as fits instead of one long column.

* ``ResponsiveForm`` - label / field pairs flow into as many columns as fit (1-4, about
  ``column_width``
  pixels each); full-width rows (groups, tables) span every column. It re-flows when its width
  changes.
* ``ResponsiveSplit`` - two parts side by side when wide enough (a list next to its detail form),
  stacked
  when narrow.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class _Cell(QWidget):
    """One label / field pair. Its minimum height is the larger of its plain minimum (what a
    table inside needs) and its height at its own width (a caption wrapped onto two lines):
    neither the table nor the field under a long caption is squeezed."""

    def hasHeightForWidth(self):  # noqa: N802 - Qt API
        return False

    def minimumSizeHint(self):  # noqa: N802 - Qt API
        size = super().minimumSizeHint()
        layout = self.layout()
        if layout is not None and self.width() > 0 and layout.hasHeightForWidth():
            size.setHeight(max(size.height(), layout.heightForWidth(self.width())))
        return size

    def sizeHint(self):  # noqa: N802 - Qt API
        size = super().sizeHint()
        size.setHeight(max(size.height(), self.minimumSizeHint().height()))
        return size

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self.updateGeometry()  # a new width can wrap the caption differently


def _field_cell(label, widget):
    """A label above its field (no crowded label column; every field gets the cell's whole
    width)."""
    cell = _Cell()
    box = QVBoxLayout(cell)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(3)
    if isinstance(widget, QCheckBox) and not widget.text():
        # a switch carries its own label beside the box; the empty line above keeps the box
        # level with the fields next to it
        widget.setText(label)
        label = " "
    caption = QLabel(label)
    caption.setObjectName("FieldLabel")
    caption.setBuddy(widget)
    caption.setWordWrap(True)
    box.addWidget(caption)
    box.addWidget(widget)
    cell.caption = caption
    return cell


class ResponsiveForm(QWidget):
    def __init__(self, parent=None, *, column_width=340, max_columns=4):
        super().__init__(parent)
        self.column_width = int(column_width)
        self.max_columns = int(max_columns)
        self.rows = []  # (cell widget, False | "span" | True)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(10)
        self.columns = 0

    def add_row(self, label, widget, *, span=False):
        """``span``: the field takes a whole row (tables of key / amount pairs, long text)."""
        self.rows.append((_field_cell(label, widget), "span" if span else False))
        self._place(force=True)

    def add_wide(self, widget):
        self.rows.append((widget, True))
        self._place(force=True)

    def minimumSizeHint(self):  # noqa: N802 - re-flows to one column, so one column is the minimum
        widths = [w.minimumSizeHint().width() for w, _ in self.rows] or [0]
        return QSize(min(max(widths), self.column_width), super().minimumSizeHint().height())

    def columns_for(self, width):
        wanted = max(1, min(self.max_columns, int(width) // self.column_width))
        # hysteresis: only add a column with 24 px to spare, so a scroll bar appearing /
        # disappearing
        # cannot flip the layout back and forth
        if wanted > self.columns > 0 and int(width) < wanted * self.column_width + 24:
            return self.columns
        return wanted

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._place()

    def _place(self, force=False):
        columns = self.columns_for(self.width() or self.column_width)
        if columns == self.columns and not force:
            return
        self.columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        for c in range(self.max_columns):
            self.grid.setColumnStretch(c, 0)
        row = col = 0
        for widget, wide in self.rows:
            if wide:
                if col:
                    row, col = row + 1, 0
                self.grid.addWidget(widget, row, 0, 1, columns)
                row += 1
                continue
            self.grid.addWidget(widget, row, col, Qt.AlignTop)  # neighbours line up at the top
            col += 1
            if col == columns:
                row, col = row + 1, 0
        for c in range(columns):
            self.grid.setColumnStretch(c, 1)
        for r in range(self.grid.rowCount()):
            self.grid.setRowStretch(r, 0)
        self.grid.setRowStretch(
            row + 1, 1
        )  # fields pack at the top; spare height stays below them


class ResponsiveSplit(QWidget):
    """``first`` beside ``second`` when at least ``side_by_side_at`` pixels wide, else ``first``
    above."""

    def __init__(
        self,
        first,
        second,
        parent=None,
        *,
        side_by_side_at=520,
        first_share=1,
        second_share=2,
        stacked_height=130,
    ):
        super().__init__(parent)
        self.stacked_height = int(stacked_height)
        self.side_by_side_at = int(side_by_side_at)
        self.first, self.second = first, second
        self.box = QBoxLayout(QBoxLayout.TopToBottom, self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(10)
        self.box.addWidget(first, first_share)
        self.box.addWidget(second, second_share)
        first.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        first.setMaximumHeight(self.stacked_height)

    @property
    def side_by_side(self):
        return self.box.direction() == QBoxLayout.LeftToRight

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        wanted = (
            QBoxLayout.LeftToRight
            if self.width() >= self.side_by_side_at
            else QBoxLayout.TopToBottom
        )
        if self.box.direction() != wanted:
            self.box.setDirection(wanted)
            # stacked, the first part (a list) stays short so the form below it is visible
            self.first.setMaximumHeight(
                16777215 if wanted == QBoxLayout.LeftToRight else self.stacked_height
            )


class ResponsiveColumns(QWidget):
    """Panels (group boxes) flow into as many columns as fit, each about ``column_width`` wide,
    filling
    columns top to bottom so the tallest column stays short; one column when narrow."""

    def __init__(self, panels=(), parent=None, *, column_width=360, max_columns=3):
        super().__init__(parent)
        self.column_width = int(column_width)
        self.max_columns = int(max_columns)
        self.panels = list(panels)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        self.columns = 0
        self._place(force=True)

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._place()

    def minimumSizeHint(self):  # noqa: N802 - re-flows to one column, so one panel is the minimum width
        widths = [p.minimumSizeHint().width() for p in self.panels] or [0]
        return QSize(max(widths), super().minimumSizeHint().height())

    def _place(self, force=False):
        width = self.width() or 1
        columns = max(1, min(self.max_columns, len(self.panels) or 1, width // self.column_width))
        if columns > self.columns > 0 and width < columns * self.column_width + 24:  # hysteresis
            columns = self.columns
        if columns == self.columns and not force:
            return
        self.columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        heights = [0] * columns
        rows = [0] * columns
        for panel in self.panels:  # each panel goes to the currently shortest column
            c = heights.index(min(heights))
            self.grid.addWidget(panel, rows[c], c)
            rows[c] += 1
            heights[c] += max(panel.sizeHint().height(), 1)
        for c in range(self.max_columns):
            self.grid.setColumnStretch(c, 1 if c < columns else 0)
        self.grid.setRowStretch(max(rows), 1)
