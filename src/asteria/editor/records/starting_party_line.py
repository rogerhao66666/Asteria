"""The character page's "In the starting party" switch (D111): ticked, the character is in
Game Start ▸ Party; the switch writes there (one undoable step), so the party has one home and
both pages show it. A button opens that card."""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QToolButton

from asteria.editor.ui.icons import icon

HELP = (
    "Ticked: this character is in the party when a new game starts (Game Start ▸ Party, where"
    " the order is set). Unticked: they join later, through an event."
)


def in_starting_party(project, actor_id):
    state = project.game_start.rpg_state_data or {}
    return actor_id in state.get("party_actor_ids", ())


class StartingPartyLine(QFrame):
    """``data``: the actor record the page edits (its id is read when the switch is used)."""

    def __init__(self, document, data):
        super().__init__()
        self.setObjectName("StartingPartyLine")
        self.document, self.data = document, data
        self.setToolTip(HELP)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(8)
        self.check = QCheckBox("In the starting party")
        self.check.setToolTip(HELP)
        self.check.toggled.connect(self._toggled)
        row.addWidget(self.check)
        self.error = QLabel()
        self.error.setObjectName("WearersNobody")
        self.error.hide()
        row.addWidget(self.error)
        row.addStretch(1)
        self.open_button = QToolButton()
        self.open_button.setObjectName("WearersActor")
        self.open_button.setIcon(icon("actor"))
        self.open_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.open_button.setCursor(Qt.PointingHandCursor)
        self.open_button.setText("Game Start ▸ Party")
        self.open_button.setToolTip("Open Game Start ▸ Party: who starts, in which order")
        self.open_button.clicked.connect(self.open_party)
        row.addWidget(self.open_button)
        self.refresh()

    @property
    def actor_id(self):
        return str(self.data.get("actor_id", ""))

    def refresh(self):
        """Read again from Game Start (after an undo, or an edit on that page)."""
        self.check.blockSignals(True)
        self.check.setChecked(in_starting_party(self.document.project, self.actor_id))
        self.check.blockSignals(False)

    def _toggled(self, ticked):
        from asteria.editor.rpg.game_start_authoring import (
            GameStartAuthoringController,
            GameStartAuthoringError,
        )

        controller = GameStartAuthoringController(self.document)
        data = controller.form_data()
        party = [a for a in data["party_actor_ids"] if a != self.actor_id]
        if ticked:
            party.append(self.actor_id)  # joins at the end; Game Start ▸ Party orders them
        data["party_actor_ids"] = party
        try:
            controller.apply(data)
        except (GameStartAuthoringError, ValueError, TypeError) as exc:
            self.error.setText("⚠  Not applied: " + str(exc))
            self.error.show()
            self.refresh()
            return
        self.error.hide()
        window = self.window()
        refresh = getattr(window, "refresh_all", None)
        if refresh is not None:  # Game Start's page shows the new party too (after this click)
            QTimer.singleShot(0, window, refresh)

    def open_party(self):
        navigate = getattr(self.window(), "navigate_to_problem", None)
        if navigate is not None:
            navigate(SimpleNamespace(target=("game_start", "Party")))


__all__ = ["StartingPartyLine", "in_starting_party"]
