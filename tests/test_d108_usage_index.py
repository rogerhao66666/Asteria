"""D108: the Usage cards read one index of the project (what reads each stat, what carries and
reads each property) instead of walking the whole project for every card. The index is kept
while the document's revision stays the same and built again after any edit or undo."""

import os
from dataclasses import replace
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


@pytest.fixture
def controller():
    from asteria.editor import EditorDocument
    from asteria.editor.rpg.game_systems_authoring import GameSystemsAuthoringController
    from asteria.project import Project
    from asteria.runtime.component_registry import default_component_registry

    project = Project.load_json(DEMO / "project.asteria.json", default_component_registry())
    return GameSystemsAuthoringController(EditorDocument(project))


def _builds(monkeypatch):
    from asteria.editor.rpg import usage_index

    built = []
    original = usage_index.UsageIndex.build.__func__

    def counting(cls, project):
        built.append(project)
        return original(cls, project)

    monkeypatch.setattr(usage_index.UsageIndex, "build", classmethod(counting))
    return built


def test_one_index_serves_every_card_until_an_edit(controller, monkeypatch):
    built = _builds(monkeypatch)
    for key in ("str", "speed", "power", "vitality"):
        controller.info("stat_definitions", key)
    for key in ("consumable", "capability.weapon.*"):
        controller.info("tag_definitions", key)
    assert len(built) == 1


def test_an_edit_and_its_undo_show_on_the_card(controller):
    from asteria.editor.rpg.game_systems_authoring import _MapCommand

    document, items = controller.document, controller.project.rpg_database.items
    before = controller.info("tag_definitions", "consumable").text()
    assert "Items: has it · 16 records" in before
    old = items["alarm_clock"]
    new = replace(old, tags=tuple(x for x in old.tags if x != "consumable"))
    document.execute(_MapCommand(items, "alarm_clock", new, old, "Edit item"))
    assert "Items: has it · 15 records" in controller.info("tag_definitions", "consumable").text()
    document.undo()
    assert controller.info("tag_definitions", "consumable").text() == before


def test_the_index_gives_the_same_cards_as_a_fresh_walk(controller):
    """A card from the kept index equals one built without it (every stat and property of the
    demo: the same words, records and jumps)."""
    from asteria.editor.rpg.stat_usage import stat_usage
    from asteria.editor.rpg.tag_usage import tag_usage
    from asteria.editor.rpg.usage_index import usage_index

    project = controller.project
    db = project.rpg_database
    index = usage_index(project, controller.document.revision)
    for stat_id in db.stat_definitions:
        assert stat_usage(project, stat_id, index) == stat_usage(project, stat_id)
    for tag_id in list(db.tag_definitions)[:40]:
        assert tag_usage(project, tag_id, index) == tag_usage(project, tag_id)


def test_without_a_stamp_the_index_is_built_each_time(controller, monkeypatch):
    from asteria.editor.rpg.stat_usage import stat_usage

    built = _builds(monkeypatch)
    stat_usage(controller.project, "str")
    stat_usage(controller.project, "str")
    assert len(built) == 2  # a test or a script changing the project directly sees its change
