"""The gear page's "Who can wear it" line: a button per character who can, each opening that
character (``rpg.wearers.who_can_wear``); it follows the page's edits."""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

from asteria.editor.rpg.wearers import needs_anything, who_can_wear
from asteria.editor.ui.icons import icon

HELP = (
    "The characters whose own properties and jobs give what this gear needs (Needs, Needs"
    " one of, Forbidden). What they gain later (skill trees, level rewards, other gear) may"
    " let more wear it."
)


class WearersLine(QFrame):
    """``data``: the gear record the page edits (read again by ``refresh``)."""

    def __init__(self, project, data):
        super().__init__()
        self.setObjectName("WearersLine")
        self.project, self.data = project, data
        self.setToolTip(HELP)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(10, 6, 10, 6)
        self.row.setSpacing(6)
        self.refresh()

    def names(self):
        """The words and buttons shown, for tests: the characters by name, or a sentence."""
        shown = (self.row.itemAt(i).widget() for i in range(1, self.row.count()))
        return [w.text() for w in shown if w is not None]

    def refresh(self):
        while self.row.count():
            item = self.row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        title = QLabel("Who can wear it")
        title.setObjectName("WearersTitle")
        self.row.addWidget(title)
        wearers = who_can_wear(self.project, self.data)
        if not needs_anything(self.data):
            self.row.addWidget(QLabel("Everyone (it needs nothing)"))
        elif not wearers:
            nobody = QLabel("Nobody yet: no character has what it needs")
            nobody.setObjectName("WearersNobody")
            self.row.addWidget(nobody)
        else:
            for actor_id, name in wearers:
                button = QToolButton()
                button.setObjectName("WearersActor")
                button.setIcon(icon("actor"))
                button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
                button.setCursor(Qt.PointingHandCursor)
                button.setText(name)
                button.setToolTip(f"Open {name}'s page")
                button.clicked.connect(lambda _c=False, a=actor_id: self.open(a))
                self.row.addWidget(button)
        self.row.addStretch(1)

    def open(self, actor_id):
        navigate = getattr(self.window(), "navigate_to_problem", None)
        if navigate is not None:  # as a Problems row opens it (and Back returns)
            navigate(SimpleNamespace(target=("record", "rpg", "actors", actor_id)))


__all__ = ["WearersLine"]
