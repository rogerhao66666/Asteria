"""New from Template: the two reference projects are copied as editable starting points."""

import json

import pytest

from asteria.editor.project_templates import (
    TEMPLATES,
    available_templates,
    create_from_template,
)


def test_both_templates_are_installed_and_listed():
    templates = available_templates()
    assert templates[0].template_id == "full_verification"  # listed first: the one to learn from
    assert {t.template_id for t in templates} == {
        "full_verification",
        "basic_rpg",
        "party_rpg",
        "action_rpg",
        "empty",
    }


@pytest.mark.parametrize("template", [t.template_id for t in TEMPLATES])
def test_a_template_is_copied_renamed_and_opens(template, tmp_path):
    if template == "empty":  # no sample data: a bare project, nothing to compare with
        path = create_from_template("empty", "My Game", tmp_path / "game")
        assert json.loads(path.read_text())["name"] == "My Game"
        return
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
        assert window.new_template_action.text() == "New Project…"
    finally:
        window.document.mark_saved()
        window.close()
        app.processEvents()


def test_the_packaged_templates_match_the_reference_projects_and_carry_a_guide(tmp_path):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "sync_templates", Path(__file__).resolve().parents[1] / "scripts" / "sync_templates.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.stale() == []  # run scripts/sync_templates.py after rebuilding a demo
    path = create_from_template("action_rpg", "Guided", tmp_path / "guided")
    guide = path.parent / "START_HERE.md"
    assert guide.is_file() and "Where each rule lives" in guide.read_text()
    from asteria.editor.project_templates import PACKAGE

    assert (PACKAGE / "party_rpg" / "START_HERE.md").is_file()
