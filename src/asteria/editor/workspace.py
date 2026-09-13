from __future__ import annotations

from enum import Enum

try:
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import QStackedWidget, QTabBar, QVBoxLayout, QWidget

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

    class QWidget:
        pass


class WorkspaceMode(str, Enum):
    SCENE = "scene"
    RPG = "rpg"
    BATTLE = "battle"
    UI = "ui"
    EVENT = "event"
    CODE = "code"


class EditorWorkspace(QWidget):
    """Central mode switcher for authoring views.

    The workspace owns presentation only. Project/Scene/Event data stays in the
    canonical engine/editor models used by the individual pages.
    """

    if QT_AVAILABLE:
        modeChanged = Signal(str)

    ORDER = (
        WorkspaceMode.SCENE,
        WorkspaceMode.RPG,
        WorkspaceMode.BATTLE,
        WorkspaceMode.UI,
        WorkspaceMode.EVENT,
        WorkspaceMode.CODE,
    )

    def __init__(self, pages: dict[WorkspaceMode, QWidget], parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required for EditorWorkspace")
        super().__init__(parent)
        missing = [mode for mode in self.ORDER if mode not in pages]
        if missing:
            raise ValueError(f"missing workspace pages: {missing}")

        self.tabs = QTabBar(self)
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.stack = QStackedWidget(self)
        self._modes = list(self.ORDER)
        self._pages = dict(pages)

        labels = {
            WorkspaceMode.SCENE: "Scene",
            WorkspaceMode.RPG: "Character",
            WorkspaceMode.BATTLE: "Battle",
            WorkspaceMode.UI: "UI / Presentation",
            WorkspaceMode.EVENT: "Events",
            WorkspaceMode.CODE: "Code",
        }
        for mode in self._modes:
            self.tabs.addTab(labels[mode])
            self.stack.addWidget(self._pages[mode])

        self.tabs.currentChanged.connect(self._tab_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tabs)
        layout.addWidget(self.stack, 1)
        self.set_mode(WorkspaceMode.SCENE)

    @property
    def mode(self):
        return self._modes[self.stack.currentIndex()]

    def page(self, mode):
        return self._pages[WorkspaceMode(mode)]

    def set_mode(self, mode):
        mode = WorkspaceMode(mode)
        index = self._modes.index(mode)
        changed = self.stack.currentIndex() != index
        self.tabs.blockSignals(True)
        try:
            self.tabs.setCurrentIndex(index)
        finally:
            self.tabs.blockSignals(False)
        self.stack.setCurrentIndex(index)
        if changed:
            self.modeChanged.emit(mode.value)

    def _tab_changed(self, index):
        if not 0 <= index < len(self._modes):
            return
        self.stack.setCurrentIndex(index)
        self.modeChanged.emit(self._modes[index].value)
