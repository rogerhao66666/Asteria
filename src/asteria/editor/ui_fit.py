"""Small layout helpers shared by editor widgets."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QStyledItemDelegate


def fit_combo_boxes(root, *, cap=260, padding=44):
    """Give every combo box under ``root`` the width of its longest item (up to ``cap``), so a
    chosen id is never cut off. Call it again after the items change."""
    for combo in root.findChildren(QComboBox):
        metrics = combo.fontMetrics()
        widest = max(
            (metrics.horizontalAdvance(combo.itemText(i)) for i in range(combo.count())),
            default=0,
        )
        combo.setMinimumWidth(min(cap, widest + padding))


def fit_list_to_width(view):
    """A list whose long ids shorten in the middle ("battle.com…crimson_warlord") instead of
    scrolling sideways; hovering an item shows its whole text."""
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    view.setItemDelegate(_ViewWidthDelegate(view))

    def add_tooltips(_parent, first, last):
        for row in range(first, last + 1):
            item = view.item(row)
            if item is not None and not item.toolTip():
                item.setToolTip(item.text())

    view.model().rowsInserted.connect(add_tooltips)
    add_tooltips(None, 0, view.count() - 1)


class _ViewWidthDelegate(QStyledItemDelegate):
    """Items no wider than the list, so a long one is elided in the middle (its distinct end
    stays) rather than scrolled to."""

    def initStyleOption(self, option, index):  # noqa: N802 - Qt API
        super().initStyleOption(option, index)
        option.textElideMode = Qt.ElideMiddle

    def sizeHint(self, option, index):  # noqa: N802 - Qt API
        size = super().sizeHint(option, index)
        size.setWidth(min(size.width(), max(1, self.parent().viewport().width() - 2)))
        return size
