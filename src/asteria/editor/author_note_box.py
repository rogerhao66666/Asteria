"""The Note box under a Game Data record: the makers' own note on it, kept in the database's
``author_notes`` ({store: {record id: text}}). The game never shows or translates it; an edit
is one undo step, applied a moment after typing stops (as the record's own fields are)."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QCheckBox, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from .record_notes import is_shown, note_command, note_of, shown_command, shown_kind


class AuthorNoteBox(QWidget):
    def __init__(self, document=None, parent=None):
        super().__init__(parent)
        self.document = document
        self.store = self.key = self.record = None
        self.shown = None  # the record form's latest Players See It switch (``switch``)
        label = QLabel("Note")
        label.setObjectName("FieldLabel")
        self.text = QPlainTextEdit()
        self.text.setFixedHeight(84)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self.apply)
        self.text.textChanged.connect(self._timer.start)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(label)
        layout.addWidget(self.text)

    def set_record(self, store, key, record=None):
        """Show the note on ``key`` of ``store`` (``key`` None: no record, the box greys) and,
        for a ``record`` whose description the game shows, its Players See It."""
        self.flush()
        if (store, key) != (self.store, self.key):
            self.shown = None  # the form builds the new record's switch (not when it is kept)
        self.store, self.key, self.record = store, key, record
        project = getattr(self.document, "project", None)
        text = note_of(project, store, key) if project is not None and key is not None else ""
        self.text.blockSignals(True)
        self.text.setPlainText(text)
        self.text.blockSignals(False)
        self.setEnabled(key is not None and project is not None)

    def switch(self):
        """A new Players See It switch for the record's form, under its description (the form
        builds one each time it lays the record out), or None for a kind the game never
        describes."""
        project = getattr(self.document, "project", None)
        if project is None or shown_kind(self.record) is None:
            return None
        switch = QCheckBox("Players See It")
        switch.setToolTip(
            "Ticked: the game shows the description. Unticked: it stays in the editor."
        )
        switch.setChecked(is_shown(project, self.record))
        switch.toggled.connect(self._shown_toggled)
        self.shown = switch
        return switch

    def _shown_toggled(self, checked):
        project = getattr(self.document, "project", None)
        if project is None or self.record is None:
            return
        command = shown_command(project, self.record, checked)
        if command is not None:
            self.document.execute(command)

    def flush(self):
        if self._timer.isActive():
            self._timer.stop()
            self.apply()

    def apply(self):
        project = getattr(self.document, "project", None)
        if project is None or self.key is None:
            return False
        command = note_command(project, self.store, self.key, self.text.toPlainText())
        if command is None:
            return False
        self.document.execute(command)
        return True
