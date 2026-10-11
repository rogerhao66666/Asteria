"""Dock title bar: the panel's icon, its title, a thin accent stripe, and float / close buttons."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from .icons import ACCENTS, icon, pixmap


def _button_icon(kind):
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QIcon, QPen, QPixmap

    result = QIcon()
    for ratio in (1.0, 2.0, 3.0):
        pm = QPixmap(round(14 * ratio), round(14 * ratio))
        pm.setDevicePixelRatio(ratio)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#8b93a5"), 1.5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        if kind == "close":
            p.drawLine(QPointF(3.5, 3.5), QPointF(10.5, 10.5))
            p.drawLine(QPointF(10.5, 3.5), QPointF(3.5, 10.5))
        else:  # float: two overlapping windows
            p.drawRoundedRect(QRectF(2.5, 4.5, 7, 7), 1.5, 1.5)
            p.drawPolyline([QPointF(5, 2.5), QPointF(11.5, 2.5), QPointF(11.5, 9)])
        p.end()
        result.addPixmap(pm)
    return result


class DockTitleBar(QWidget):
    def __init__(self, dock, icon_name, accent=None):
        super().__init__(dock)
        self.setObjectName("DockTitleBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.dock = dock
        self.accent = QColor(ACCENTS.get(accent or icon_name, accent or ACCENTS["primary"]))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 6, 5)
        layout.setSpacing(7)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(pixmap(icon_name, 16, self.accent.name(), self.devicePixelRatioF() or 2.0))
        self.title = QLabel(dock.windowTitle())
        self.title.setObjectName("DockTitle")
        layout.addWidget(self.icon_label)
        layout.addWidget(self.title, 1)
        self.float_button = self._button("float", "Float / dock this panel", self._toggle_float)
        self.close_button = self._button("close", "Close this panel (View ▸ Panels reopens it)", dock.close)
        layout.addWidget(self.float_button)
        layout.addWidget(self.close_button)
        dock.windowTitleChanged.connect(self.title.setText)
        dock.setWindowIcon(icon(icon_name, self.accent.name()))  # shown on the dock's tab when tabified

    def _button(self, kind, tip, slot):
        button = QToolButton(self)
        button.setObjectName("DockTitleButton")
        button.setIcon(_button_icon(kind))
        button.setIconSize(QSize(14, 14))
        button.setToolTip(tip)
        button.setAutoRaise(True)
        button.clicked.connect(slot)
        return button

    def _toggle_float(self):
        self.dock.setFloating(not self.dock.isFloating())

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(0, 0, 3, self.height(), self.accent)  # accent stripe
        painter.end()

    def sizeHint(self):
        hint = super().sizeHint()
        return QSize(hint.width(), max(hint.height(), 30))


def decorate_dock(dock, icon_name, accent=None):
    dock.setTitleBarWidget(DockTitleBar(dock, icon_name, accent))
    return dock
