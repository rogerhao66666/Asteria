"""Small pieces the main window's parts share: dock cards, the overflow buttons, event-sequence
arguments."""

from __future__ import annotations

from asteria.editor.project.workspace import WorkspaceMode
from asteria.editor.ui.scrolling_tabs import scrollable

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QFrame, QMainWindow, QVBoxLayout, QWidget
except ImportError:
    QApplication = None
    QMainWindow = object
    Qt = None


def _dock_card(widget):
    host = QWidget()
    host.setObjectName("DockContentHost")
    outer = QVBoxLayout(host)
    outer.setContentsMargins(12, 12, 12, 16)
    outer.setSpacing(0)
    card = QFrame(host)
    card.setObjectName("DockContentCard")
    card.setAttribute(Qt.WA_StyledBackground, True)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(1, 1, 1, 1)
    layout.setSpacing(0)
    area = scrollable(widget)
    area.setProperty("dockContentSurface", True)
    area.viewport().setProperty("dockContentSurface", True)
    widget.setProperty("dockContentSurface", True)
    area.setObjectName(f"{widget.metaObject().className()}Scroll")
    area.setViewportMargins(0, 0, 0, 0)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    layout.addWidget(area)
    outer.addWidget(card)
    return host


def _dock_scrollable(widget):
    return _dock_card(widget)


def _scene_dock_scrollable(widget):
    return _dock_card(widget)


WORKSPACE_ICONS = {
    WorkspaceMode.SCENE: "scene",
    WorkspaceMode.RPG: "rpg",
    WorkspaceMode.BATTLE: "battle",
    WorkspaceMode.UI: "ui",
    WorkspaceMode.EVENT: "events",
    WorkspaceMode.CODE: "code",
    WorkspaceMode.MULTIPLAYER: "multiplayer",
}


def draw_overflow_buttons(*bars):
    """Give a bar's "more than fits" button a picture of ours. Qt's own is a system symbol that
    takes the whole editor down on macOS 27 when it is first painted, the moment the window is
    too narrow for the tool bar."""
    from PySide6.QtWidgets import QToolButton

    from asteria.editor.ui.icons import icon

    for bar in bars:
        for button in bar.findChildren(QToolButton):
            if button.objectName() in ("qt_toolbar_ext_button", "qt_menubar_ext_button"):
                button.setIcon(icon("overflow", "#c8cbd6"))


def _sequence_kwargs(args):
    return {
        "tracks": args["tracks"],
        "cutscene": args.get("cutscene", False),
        "skippable": args.get("skippable", False),
        "wait": args.get("wait", "all"),
    }
