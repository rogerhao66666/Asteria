"""Qt form for the project's Game Start (the New Game state)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from .game_start_authoring import GameStartAuthoringError
from .game_systems_widget import RecordForm
from .project_empty_state import ProjectEmptyState


class GameStartEditorWidget(QWidget):
    changed = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.form = None
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setViewportMargins(0, 0, 10, 0)  # fields never touch the scroll bar
        self.status = QLabel("")
        self.status.setWordWrap(True)
        apply_button = QPushButton("Apply Changes")
        apply_button.clicked.connect(self.apply)
        revert_button = QPushButton("Revert")
        revert_button.clicked.connect(self.refresh)
        buttons = QHBoxLayout()
        buttons.addWidget(apply_button)
        buttons.addWidget(revert_button)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(self.status)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self):
        if self.controller.document.project is None:
            self.form = None
            self.scroll.setWidget(ProjectEmptyState("Open a project to edit its Game Start."))
            return
        self.form = RecordForm(self.controller.form, self.controller.references)
        self.form.set_data(self.controller.form_data())
        self.scroll.setWidget(self.form)

    def apply(self):
        if self.form is None:
            return False
        try:
            self.controller.apply(self.form.data())
        except (GameStartAuthoringError, ValueError, TypeError) as exc:
            self.status.setStyleSheet("color: #d9534f;")
            self.status.setText(str(exc))
            return False
        self.status.setStyleSheet("")
        self.status.setText("Game Start applied")
        self.changed.emit()
        self.refresh()
        return True
