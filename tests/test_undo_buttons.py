"""Undo and Redo as buttons at the foot of the record pages, in place of the old
"Changes apply as you edit · Ctrl+Z undoes" line: they follow the window's Edit actions."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_the_buttons_follow_and_run_the_window_actions(app):
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMainWindow

    from asteria.editor.undo_buttons import UndoRedoButtons

    ran = []

    class Window(QMainWindow):
        def __init__(self):
            super().__init__()
            self.undo_action = QAction("Undo Rename", self)
            self.redo_action = QAction("Redo", self)
            self.redo_action.setEnabled(False)

        def undo(self):
            ran.append("undo")

        def redo(self):
            ran.append("redo")

    window = Window()
    buttons = UndoRedoButtons()
    assert not buttons.undo_button.isEnabled()  # no window yet: nothing to undo
    window.setCentralWidget(buttons)
    window.show()
    assert buttons.undo_button.isEnabled() and not buttons.redo_button.isEnabled()
    buttons.undo_button.click()
    assert ran == ["undo"]
    window.redo_action.setEnabled(True)  # the window refreshed its actions
    assert buttons.redo_button.isEnabled()
    buttons.redo_button.click()
    assert ran == ["undo", "redo"]
    window.close()


def test_no_page_prints_the_undo_line_any_more(app):
    from PySide6.QtWidgets import QLabel

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.undo_buttons import UndoRedoButtons

    window = AsteriaEditorWindow(None)
    assert not [lb for lb in window.findChildren(QLabel) if "Ctrl+Z" in lb.text()]
    assert len(window.findChildren(UndoRedoButtons)) >= 2  # Game Data, Game Systems
    window.close()
    from pathlib import Path

    editor = Path(__file__).resolve().parents[1] / "src" / "asteria" / "editor"
    for name in ("authoring_hub_widget.py", "game_systems_widget.py", "game_start_widget.py"):
        text = (editor / name).read_text(encoding="utf-8")
        assert "Ctrl+Z undoes" not in text and "UndoRedoButtons()" in text, name
