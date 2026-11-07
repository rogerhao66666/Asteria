"""The picture message window dialog keeps QWidget's own ``style()``, ``window()`` and
``font()``: its result is ``chosen_style()`` and its fields have their own names."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication, QStyle, QWidget  # noqa: E402

from asteria.editor import EditorDocument  # noqa: E402
from asteria.editor.menus.dialogue_window_dialog import DialogueWindowDialog  # noqa: E402


def test_the_dialog_keeps_the_widget_methods_and_names_its_result():
    QApplication.instance() or QApplication([])
    dialog = DialogueWindowDialog(EditorDocument(), None, ("pixel",))
    assert isinstance(dialog.style(), QStyle)
    dialog.style().polish(dialog)  # what the editor's theme does to every widget
    assert isinstance(dialog.window(), QWidget) and isinstance(dialog.font(), QFont)
    assert dialog.chosen_style() is None  # no picture chosen: no picture window
    dialog.deleteLater()
