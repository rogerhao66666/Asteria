"""Qt form for the project's Game Start (the New Game state). Edits apply on their own a moment
after typing stops (undoable); a problem is shown and nothing is applied."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from .game_start_authoring import GameStartAuthoringError
from .game_systems_widget import RecordForm
from .project_empty_state import ProjectEmptyState
from .undo_buttons import UndoRedoButtons


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
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self.auto_apply)
        self._unannounced = False
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(UndoRedoButtons())  # edits apply on their own: a step back or on
        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(self.status)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self):
        self.flush_edits()
        if self.controller.document.project is None:
            self.form = None
            self.scroll.setWidget(ProjectEmptyState("Open a project to edit its Game Start."))
            return
        self.form = RecordForm(
            self.controller.form, self.controller.references, document=self.controller.document
        )
        self.form.set_data(self.controller.form_data())
        self.form.changed.connect(self._timer.start)
        self.scroll.setWidget(self.form)

    def auto_apply(self):
        if self.form is None:
            return False
        try:
            self.controller.apply(self.form.data())
        except (GameStartAuthoringError, ValueError, TypeError) as exc:
            self.status.setStyleSheet("color: #d9534f;")
            self.status.setText("⚠  Not applied: " + str(exc))
            return False
        self.status.setText("")
        self._unannounced = True
        return True

    def flush_edits(self):
        if self._timer.isActive():
            self._timer.stop()
            self.auto_apply()
        if self._unannounced:
            self._unannounced = False
            self.changed.emit()

    def hideEvent(self, event):  # noqa: N802 - Qt API
        self.flush_edits()
        super().hideEvent(event)

    def apply(self):
        """Apply now and rebuild the page (scripts and tests)."""
        self._timer.stop()
        if not self.auto_apply():
            return False
        self._unannounced = False
        self.status.setText("Game Start applied")
        self.changed.emit()
        self.refresh()
        return True
