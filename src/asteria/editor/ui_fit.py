"""Small layout helpers shared by editor widgets."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox


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
