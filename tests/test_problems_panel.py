"""CB10 / EDT-15: project-wide Problems list with navigation to the offending item."""

from dataclasses import replace
from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.editor.problems import collect_problems, locate_record_message
from asteria.project import Project

REF = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"


def _document(path=REF):
    document = EditorDocument()
    document.set_project(Project.load_json(REF, document.component_registry), file_path=path)
    return document


def _break(project):
    db = project.rpg_database
    actor = db.actors["hero_01"]
    db.actors["hero_01"] = replace(actor, abilities=(*actor.abilities, "ghost_skill"))
    encounter_id = sorted(db.encounters)[0]
    enemy = sorted(db.enemies)[0]
    db.enemies.pop(enemy)
    return encounter_id, enemy


def test_reference_project_has_no_problems():
    assert collect_problems(_document()) == []


def test_every_broken_reference_is_listed_with_its_record_not_just_the_first():
    document = _document()
    _break(document.project)
    problems = collect_problems(document)
    messages = [p.message for p in problems]
    assert "actor hero_01 references unknown ability ghost_skill" in messages
    by_target = {p.target for p in problems}
    assert ("record", "rpg", "actors", "hero_01") in by_target
    assert any(t[:3] == ("record", "rpg", "encounters") for t in by_target)
    assert len(problems) >= 2  # Project.validate alone would report a single combined error
    located = [p.message for p in problems if p.target]
    assert not [p for p in problems if not p.target and any(m in p.message for m in located)]  # no wrapped repeats


def test_messages_map_to_the_editor_that_owns_the_record():
    assert locate_record_message("shop smithy references unknown item x") == ("game_system", "shops", "smithy")
    assert locate_record_message("progression graph g node n references unknown passive p") == (
        "record",
        "rpg",
        "graphs",
        "g",
    )
    assert locate_record_message("equipment growth gr node n x")[:3] == ("record", "rpg", "growth")
    assert locate_record_message("enemy behavior binding references unknown enemy e") == ()


def test_script_syntax_errors_point_at_the_line(tmp_path):
    document = _document(tmp_path / "game.asteria.json")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "broken.py").write_text("x = 1\nif x\n    pass\n")
    (problem,) = [p for p in collect_problems(document, resource_root=REF.parent) if p.area == "Scripts"]
    assert problem.target == ("script", str(tmp_path / "scripts" / "broken.py"), 2)
    assert problem.location == "broken.py:2"


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    value = AsteriaEditorWindow(None)
    value.document.set_project(Project.load_json(REF, value.document.component_registry), file_path=REF)
    value.refresh_all()
    yield value
    value.document.mark_saved()
    value.close()
    app.processEvents()


def test_problems_dock_lists_filters_and_navigates(window):
    from asteria.editor.workspace import WorkspaceMode

    panel = window.problems_widget
    assert panel.refresh() == [] and "No problems" in panel.summary.text()
    encounter_id, _ = _break(window.document.project)
    panel.refresh()
    assert panel.tree.topLevelItemCount() == len(panel.problems) >= 2
    assert window.problems_dock.windowTitle() == f"Problems ({len(panel.problems)})"
    panel.area.setCurrentText("Abilities")
    assert [p.area for p in panel.visible_problems()] == ["Abilities"] and panel.tree.topLevelItemCount() == 1
    (ability,) = panel.visible_problems()
    assert window.navigate_to_problem(ability)
    assert window.workspace.mode == WorkspaceMode.RPG
    assert window.rpg_authoring.child.category_id == "actors"
    assert window.rpg_authoring.child.selected_ids == ["hero_01"]
    panel.area.setCurrentText("All areas")
    encounter = next(p for p in panel.problems if p.target[:3] == ("record", "rpg", "encounters"))
    panel._activated(panel.tree.topLevelItem(panel.problems.index(encounter)))  # double-click path
    assert window.rpg_authoring.child.selected_ids == [encounter_id]


def test_navigation_to_sprites_timelines_scripts_and_game_systems(window):
    from asteria.editor.problems import Problem

    sheet = window.animation_editor.api.sheets()[-1]
    assert window.navigate_to_problem(Problem("error", "Sprites", "x", ("sprite", sheet)))
    assert window.navigate_to_problem(Problem("error", "Action Timeline", "x", ("sequence", "heal")))
    window.game_systems_editor.set_kind("shops")
    window.game_systems_editor.new_record("problem_shop")
    window.game_systems_editor.set_kind("quests")
    assert window.navigate_to_problem(Problem("error", "RPG Database", "x", ("game_system", "shops", "problem_shop")))
    assert window.game_systems_editor.kind_id == "shops"
    assert not window.navigate_to_problem(Problem("error", "Project", "x"))
