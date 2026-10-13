"""A layout that places widgets left to right and wraps to a new line when the row is full.

Rows of action buttons (Add / Key at Frame / Remove...) use it, so a narrow panel shows its
buttons on
two lines instead of forcing the whole editor wider.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout


class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self._items = []
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._place(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._place(rect, apply=True)

    def sizeHint(self):
        width = sum(item.sizeHint().width() for item in self._items) + self.spacing() * max(
            0, len(self._items) - 1
        )
        height = max((item.sizeHint().height() for item in self._items), default=0)
        m = self.contentsMargins()
        return QSize(width + m.left() + m.right(), height + m.top() + m.bottom())

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _place(self, rect, *, apply):
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line = area.x(), area.y(), 0
        visible = [
            item for item in self._items if not (item.widget() and item.widget().isHidden())
        ]
        right_aligned = bool(self.alignment() & Qt.AlignRight)
        rows, row = [], []
        for item in visible:
            hint = item.sizeHint()
            if row and x + hint.width() > area.right() + 1:
                rows.append((row, line))
                x, y, line, row = area.x(), y + line + self.spacing(), 0, []
            row.append((item, QPoint(x, y), hint))
            x += hint.width() + self.spacing()
            line = max(line, hint.height())
        if row:
            rows.append((row, line))
        if apply:
            for placed, _ in rows:
                shift = 0
                if right_aligned and placed:
                    last = placed[-1]
                    shift = max(0, area.right() + 1 - (last[1].x() + last[2].width()))
                for item, point, hint in placed:
                    item.setGeometry(QRect(point + QPoint(shift, 0), hint))
        return y + line - rect.y() + m.bottom()
