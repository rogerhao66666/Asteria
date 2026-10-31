"""The Scene workspace's panel switch: a row of coloured squares in the title bar of each left
panel (Project, Tiles, Layers), each with its key in the corner, the way LDtk switches its side
panels. Every left panel carries a copy of the row, so it is always in the same place.

``PanelSwitch(window)`` builds the row for an editor window; ``window.show_left_panel(name)``
opens the panel and the row's buttons follow the dock tab Qt keeps underneath (collapsed to
nothing: the row is the switch).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QWidget

from .icons import ACCENTS, icon

# (dock object name, the icon drawn in white, the key that opens it, the tool tip's words)
PANELS = (
    ("ProjectSceneDock", "project", "P", "Project"),
    ("TilePaletteDock", "tiles", "T", "Tiles"),
    ("LayersDock", "layers", "L", "Layers"),
)
PANEL_COLOURS = {
    "ProjectSceneDock": ACCENTS["project"],
    "TilePaletteDock": ACCENTS["tiles"],
    "LayersDock": ACCENTS["layers"],
}
BUTTON_SIZE = (38, 32)


class KeyedButton(QToolButton):
    """A tool button with its shortcut key written small in the bottom-right corner."""

    def __init__(self, key="", parent=None):
        super().__init__(parent)
        self.key = key
        self.key_colour = QColor(255, 255, 255, 190)

    def paintEvent(self, event):  # noqa: N802 - Qt API
        super().paintEvent(event)
        if not self.key:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont(self.font())
        font.setPointSizeF(max(7.0, self.font().pointSizeF() * 0.62))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self.key_colour)
        rect = QRectF(self.rect()).adjusted(0, 0, -4, -2)
        painter.drawText(rect, Qt.AlignRight | Qt.AlignBottom, self.key)
        painter.end()


class PanelSwitch(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.setObjectName("PanelSwitch")
        self.window_ref = window
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.buttons = {}
        for name, drawing, key, words in PANELS:
            button = KeyedButton(key, self)
            button.setObjectName("PanelSwitchButton")
            button.setProperty("panel", name)
            button.setCheckable(True)
            button.setAutoExclusive(False)
            button.setFixedSize(*BUTTON_SIZE)
            button.setIcon(icon(drawing, "#ffffff"))
            button.setIconSize(QSize(18, 18))
            button.setToolTip(f"{words} ({key})")
            button.clicked.connect(lambda checked=False, n=name: self._open(n))
            row.addWidget(button)
            self.buttons[name] = button
        row.addStretch(1)

    def _open(self, name):
        self.window_ref.show_left_panel(name)
        self.sync(name)

    def sync(self, current):
        """Mark ``current`` (a dock object name) as the open panel."""
        for name, button in self.buttons.items():
            button.setChecked(name == current)
