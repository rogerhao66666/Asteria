"""Game Start ▸ Starting Equipment (D110): what every character wears when a new game starts,
read only. Each character's own page sets it (Starting Equipment); a click on a character opens
that page, a click on a piece opens the piece's.
"""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QToolButton, QWidget

from asteria.editor.rpg.wearers import starting_wear
from asteria.editor.ui.flow_layout import FlowLayout
from asteria.editor.ui.icons import icon

HELP = (
    "What each character wears when a new game starts, a character who joins later too. Set it"
    " on the character's page (Starting Equipment); click a character to go there."
)


class StartingWearView(QWidget):
    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.setObjectName("StartingWear")
        self.document = document
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(6)
        self.grid.setColumnStretch(1, 1)
        self.refresh()

    def rows(self):
        """``(name, [piece words])`` per character shown, for tests."""
        out = []
        for row in range(self.grid.rowCount()):
            who = self.grid.itemAtPosition(row, 0)
            pieces = self.grid.itemAtPosition(row, 1)
            if who is None or pieces is None:
                continue
            flow = pieces.widget().layout()
            words = [flow.itemAt(i).widget().text() for i in range(flow.count())]
            out.append((who.widget().text(), words))
        return out

    def refresh(self):
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        project = getattr(self.document, "project", None)
        if project is None:
            return
        gear = _gear_words(self.document)
        for row, (actor_id, name, pieces, kept) in enumerate(starting_wear(project)):
            who = _button("WearersActor", name, icon("actor"))
            who.setToolTip(f"Open {name}'s page")
            who.clicked.connect(lambda _c=False, a=actor_id: self.open("actors", a))
            self.grid.addWidget(who, row, 0, Qt.AlignTop)
            box = QWidget()
            flow = FlowLayout(box, spacing=6)
            for _slot_id, slot_name, equipment_id in pieces:
                words, picture = gear.get(equipment_id, (equipment_id, None))
                piece = _button("StartingPiece", f"{slot_name}: {words}", picture)
                piece.setToolTip(f"Open {words}'s page")
                piece.clicked.connect(lambda _c=False, e=equipment_id: self.open("equipment", e))
                flow.addWidget(piece)
            if not pieces:
                flow.addWidget(_dim("Nothing worn"))
            if kept:
                note = _dim("Kept in Game Start (an older project)")
                note.setToolTip(
                    "This project's Game Start still holds what this character wears; it is"
                    " used as it is. Their page's Starting Equipment counts once it is gone."
                )
                flow.addWidget(note)
            self.grid.addWidget(box, row, 1)

    def open(self, category, record_id):
        navigate = getattr(self.window(), "navigate_to_problem", None)
        if navigate is not None:  # as a Problems row opens it (and Back returns)
            navigate(SimpleNamespace(target=("record", "rpg", category, record_id)))


def _gear_words(document):
    """``{equipment_id: (name, icon or None)}``."""
    from asteria.editor.records.form_chips import load_record_icon
    from asteria.editor.records.vocabulary import vocabulary_for

    return {
        c.value: (c.label, load_record_icon(document, c.icon) if c.icon else None)
        for c in vocabulary_for(document).choices("equipment")
    }


def _button(name, text, picture):
    button = QToolButton()
    button.setObjectName(name)
    button.setText(text)
    if picture is not None:
        button.setIcon(picture)
    button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    button.setCursor(Qt.PointingHandCursor)
    return button


def _dim(text):
    label = QLabel(text)
    label.setObjectName("StartingNote")
    return label


__all__ = ["HELP", "StartingWearView"]
