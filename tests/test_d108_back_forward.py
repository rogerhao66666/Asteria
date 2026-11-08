"""D108: every jump (a usage card's record, a problem, a search result) keeps where the editor
was; View ▸ Back (Ctrl+[) returns there and Forward (Ctrl+]) goes again."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("ASTERIA_MUTE", "1")
pytest.importorskip("PySide6")

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


@pytest.fixture
def window():  # one a test: conftest deletes it after (a module one outlived its file)
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project
    from asteria.runtime.component_registry import default_component_registry

    QApplication.instance() or QApplication([])
    project = Project.load_json(DEMO / "project.asteria.json", default_component_registry())
    window = AsteriaEditorWindow(project)
    window.document.file_path = DEMO / "project.asteria.json"
    window.document.mark_saved()
    yield window
    window.document.mark_saved()


def _jump(window, *target):
    assert window.navigate_to_problem(SimpleNamespace(target=target))


def test_back_and_forward_walk_the_jumps(window):
    stat = ("game_system", "stat_definitions", "str")
    job = ("record", "rpg", "classes", "brave")
    tag = ("game_system", "tag_definitions", "consumable")
    window.open_target(SimpleNamespace(target=stat))  # where the author is (no jump yet)
    _jump(window, *job)  # a usage card's record
    _jump(window, *tag)
    assert window.current_place() == tag
    assert window.back_action.isEnabled() and not window.forward_action.isEnabled()
    window.back_action.trigger()
    assert window.current_place() == job
    window.back_action.trigger()
    assert window.current_place() == stat
    assert not window.back_action.isEnabled() and window.forward_action.isEnabled()
    window.forward_action.trigger()
    assert window.current_place() == job
    _jump(window, "game_system", "stat_definitions", "speed")  # a new jump: no forward
    assert not window.forward_action.isEnabled()


def test_a_page_without_a_record_is_a_place_too(window):
    from asteria.editor.project.workspace import WorkspaceMode

    window.workspace.set_mode(WorkspaceMode.SCENE)
    _jump(window, "game_system", "stat_definitions", "str")
    window.go_back()
    assert window.workspace.mode == WorkspaceMode.SCENE


def test_the_keys_are_ctrl_brackets(window):
    assert window.back_action.shortcut().toString() == "Ctrl+["
    assert window.forward_action.shortcut().toString() == "Ctrl+]"
