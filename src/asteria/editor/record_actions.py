"""The foot of a record page, the same on every one (Game Data, Game Systems, Enemy AI,
Behavior Trees, Real-Time Combat, Ability Timelines, Particle Effects): the page's own buttons
on the left; Undo and Redo, then New…, Duplicate… and Delete on the right."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout


def record_action_bar(*record_buttons, extras=(), undo=True):
    """A row: ``extras`` at the left, then a stretch, Undo / Redo (``undo``) and
    ``record_buttons`` (New…, Duplicate…, Delete - whichever the page has) at the right.
    Returns ``(row, undo_buttons or None)``."""
    row = QHBoxLayout()
    row.setSpacing(6)
    for widget in extras:
        row.addWidget(widget)
    row.addStretch(1)
    undo_buttons = None
    if undo:
        from .undo_buttons import UndoRedoButtons

        undo_buttons = UndoRedoButtons()  # edits apply on their own: a step back or on
        row.addWidget(undo_buttons)
    for button in record_buttons:
        row.addWidget(button)
    return row, undo_buttons
