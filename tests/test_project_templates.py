"""New from Template: the two reference projects are copied as editable starting points."""

import json

import pytest

from asteria.editor.project_templates import (
    TEMPLATES,
    available_templates,
    create_from_template,
)


def test_both_templates_are_installed_and_listed():
    assert {t.template_id for t in available_templates()} == {"party_rpg", "action_rpg"}


@pytest.mark.parametrize("template", [t.template_id for t in TEMPLATES])
def test_a_template_is_copied_renamed_and_opens(template, tmp_path):
    from asteria.editor import EditorDocument
    from asteria.project import Project

    source = next(t for t in TEMPLATES if t.template_id == template).source
    before = (source / "project.asteria.json").read_text()
    path = create_from_template(template, "My Game", tmp_path / "game")
    assert path.name == "project.asteria.json"
    assert json.loads(path.read_text())["name"] == "My Game"
    assert (tmp_path / "game" / "playable_assets").is_dir()  # the art comes along
    assert not (tmp_path / "game" / "build_project.py").exists()  # build scripts stay home
    project = Project.load_json(path, EditorDocument().component_registry)
    project.validate()
    assert project.name == "My Game" and project.scenes()
    assert (source / "project.asteria.json").read_text() == before  # the template is untouched


def test_a_template_refuses_a_folder_with_files_and_an_empty_name(tmp_path):
    (tmp_path / "taken").mkdir()
    (tmp_path / "taken" / "x.txt").write_text("x")
    with pytest.raises(ValueError):
        create_from_template("action_rpg", "A", tmp_path / "taken")
    with pytest.raises(ValueError):
        create_from_template("action_rpg", "  ", tmp_path / "fresh")
    with pytest.raises(ValueError):
        create_from_template("nope", "A", tmp_path / "fresh")


def test_the_editor_opens_a_new_project_from_a_template(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow(Project("Empty"))
    try:
        path = window.new_from_template("action_rpg", "Mine", tmp_path / "mine")
        assert window.document.file_path == path
        assert window.document.project.name == "Mine"
        assert any(s.name.startswith("Hollowbrook") for s in window.document.project.scenes())
        assert window.new_template_action.text() == "New from Template…"
    finally:
        window.document.mark_saved()
        window.close()
        app.processEvents()
