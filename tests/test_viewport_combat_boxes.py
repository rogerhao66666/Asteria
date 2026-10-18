"""Hit and hurt boxes are a debug view in the scene editor: hidden until View > Show Hit && Hurt
Boxes; colliders (what blocks) always show."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from asteria.editor.collision_overlay import CombatBox  # noqa: E402
from asteria.editor.viewport_widget import shown_combat_boxes  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_only_blocking_boxes_show_unless_asked():
    boxes = tuple(CombatBox(kind, "e", ()) for kind in ("solid", "hurtbox", "hitbox", "trigger"))
    assert [b.kind for b in shown_combat_boxes(boxes)] == ["solid", "trigger"]
    assert len(shown_combat_boxes(boxes, hit_and_hurt=True)) == 4


def test_the_view_menu_turns_them_on_and_off(app):
    from asteria.editor.shell import AsteriaEditorWindow

    window = AsteriaEditorWindow(None)
    action = window.combat_boxes_action
    assert not action.isChecked() and not window.viewport.show_combat_boxes
    action.setChecked(True)
    assert window.viewport.show_combat_boxes
    action.setChecked(False)
    assert not window.viewport.show_combat_boxes
    window.close()
