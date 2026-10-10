"""CB10 / EDT-09: script editor — highlighting, API completion, traceback navigation, files, reload, run."""

from pathlib import Path

import pytest

from asteria.editor.script_tools import complete, script_frames

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"


def _namespace():
    from test_session_events import _project

    from asteria.authoring.runner import script_namespace

    return script_namespace(_project())


def test_completion_resolves_live_authoring_api_members_without_executing_code():
    ns = _namespace()
    assert complete("project.sc", 10, ns) == ("sc", ["scene", "scene_named", "scenes"])
    assert "print" in complete("pri", 3, ns)[1] and "project" in complete("proj", 4, ns)[1]
    assert complete("unknown.x", 9, ns) == ("x", [])
    assert complete("project.scenes().", 17, ns)[1] == []  # calls are never evaluated


def test_traceback_frames_belong_to_the_script_file():
    text = (
        "Traceback (most recent call last):\n"
        '  File "/x/editor/runner.py", line 90, in run\n    exec(code)\n'
        '  File "scripts/main.py", line 3, in <module>\n    helper()\n'
        '  File "scripts/main.py", line 7, in helper\n    1 / 0\n'
        "ZeroDivisionError: division by zero\n"
    )
    assert script_frames(text, "scripts/main.py") == [(3, "<module>", "helper()"), (7, "helper", "1 / 0")]


@pytest.fixture
def window(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.core import Entity, Scene, Transform
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project

    app = QApplication.instance() or QApplication([])
    project = Project("Game")
    scene = project.add_scene(Scene("Town"))
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform(1.0, 2.0))
    value = AsteriaEditorWindow(project)
    value.document.file_path = tmp_path / "game.asteria.json"
    value.code_workspace.load_default_script()
    yield value
    value.document.mark_saved()
    value.close()
    app.processEvents()


def test_highlighting_classifies_python_and_asteria_globals(window):
    highlighter = window.code_workspace.highlighter
    line = 'for hero in project.scenes():  # loop "x"'
    assert highlighter.format_at(line, 0) == "keyword"
    assert highlighter.format_at(line, line.index("project")) == "global"
    assert highlighter.format_at(line, line.index("#") + 2) == "comment"


def test_typing_dot_offers_api_members_and_inserting_completes(window):
    code = window.code_workspace
    code.editor.setPlainText("")
    code.editor.insertPlainText('scene = project.scene_named("Town")\nscene.')
    names = code.completer.model().stringList()  # popup opened by the "."
    assert "entities" in names and "create_entity" in names
    code.editor.insertPlainText("ent")
    assert code.show_completions() == ["entities", "entity", "entity_named"]
    code.insert_completion("entities")
    assert code.editor.toPlainText().endswith("scene.entities")


def test_run_error_shows_traceback_frames_that_jump_to_the_line(window):
    code = window.code_workspace
    code.editor.setPlainText('scene = project.scene_named("Town")\n\ndef boom():\n    return 1 / 0\n\nboom()\n')
    code._request_run()
    assert "ZeroDivisionError" in code.output.toPlainText()
    assert code.frames.count() == 2
    code._frame_clicked(code.frames.item(1))
    assert code.editor.textCursor().blockNumber() == 3  # line 4: return 1 / 0


MOVE_HERO = (
    'hero = project.scene_named("Town").entity_named("Hero")\nhero.transform.position = (40, 50)\nprint("moved")\n'
)


def test_script_files_new_save_reload_and_run_edits_the_project(window, tmp_path):
    from asteria.core import Transform

    code = window.code_workspace
    code.new_script("tools")
    script = tmp_path / "scripts" / "tools.py"
    assert script.is_file() and code.script_list.currentText() == "tools.py"
    code.editor.setPlainText(MOVE_HERO)
    assert code.save_default_script() and script.read_text() == MOVE_HERO
    script.write_text('print("edited outside")\n')
    code.reload_script()
    assert code.editor.toPlainText() == 'print("edited outside")\n'
    code.editor.setPlainText(MOVE_HERO)
    code._request_run()
    assert "moved" in code.output.toPlainText()
    hero = window.document.project.scenes()[0].entities()[0].get(Transform)
    assert (hero.x, hero.y) == (40.0, 50.0)
    window.document.undo()  # the whole run is one undoable step
    assert (hero.x, hero.y) == (1.0, 2.0)
    code.open_script("main.py")
    assert code.script_list.currentText() == "main.py"
