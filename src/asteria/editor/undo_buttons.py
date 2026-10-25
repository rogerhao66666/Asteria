"""Undo and Redo as two buttons at the foot of a record page (Game Data, Game Systems, Game
Start). They run the window's own Edit ▸ Undo / Redo (the same step, the same refresh) and
grey out with them; a page shown without the editor window keeps them greyed."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from .icons import icon


class UndoRedoButtons(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.undo_button = self._button("Undo", "undo")
        self.redo_button = self._button("Redo", "redo")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.undo_button)
        layout.addWidget(self.redo_button)
        self._bound = None  # the window whose actions the buttons follow

    def _button(self, text, name):
        button = QPushButton(icon(name, "#8f96a3"), text)  # styled like Duplicate… beside
        button.setObjectName(f"Form{text}Button")
        button.setEnabled(False)
        button.clicked.connect(lambda: self._run(name))
        return button

    def showEvent(self, event):  # noqa: N802 - Qt
        super().showEvent(event)
        self.bind(self.window())

    def bind(self, window):
        """Follow ``window``'s ``undo_action`` / ``redo_action`` (enabled, tooltip)."""
        if window is self._bound or not hasattr(window, "undo_action"):
            return
        self._bound = window
        for button, action in (
            (self.undo_button, window.undo_action),
            (self.redo_button, window.redo_action),
        ):
            action.changed.connect(lambda b=button, a=action: self._follow(b, a))
            self._follow(button, action)

    @staticmethod
    def _follow(button, action):
        button.setEnabled(action.isEnabled())
        button.setToolTip(action.toolTip())

    def _run(self, name):
        window = self._bound
        if window is not None:
            getattr(window, name)()


__all__ = ["UndoRedoButtons"]
