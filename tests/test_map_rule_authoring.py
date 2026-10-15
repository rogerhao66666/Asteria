"""Undoable region-rule editing used beside the region paint controls."""

import pytest

from asteria.editor.map_rule_authoring import (
    MapRuleAuthoringController,
    MapRuleAuthoringError,
)
from asteria.editor.model import EditorDocument
from asteria.project import Project
from asteria.rpg.map_rules import AreaRule, MapRuleSet


def test_region_rule_edit_and_remove_are_undoable_and_preserve_ruleset_settings():
    project = Project("Game")
    original = MapRuleSet(
        "field",
        (AreaRule("tag:ice", slippery=True),),
        region_layer="hazards",
        crouch_visibility=0.5,
    )
    project.rpg_database.add_map_rule_set(original)
    document = EditorDocument(project)
    controller = MapRuleAuthoringController(document)

    controller.set_region_rule(AreaRule("region:8", damage_resource="hp", damage_per_second=4))

    edited = controller.ruleset
    assert edited.region_layer == "hazards" and edited.crouch_visibility == 0.5
    assert edited.rule("tag:ice").slippery
    assert edited.rule("region:8").damage_per_second == 4
    assert document.undo()
    assert controller.ruleset == original
    assert document.redo()
    assert controller.remove_region_rule(8)
    assert controller.ruleset.rule("region:8") is None
    assert document.undo()
    assert controller.ruleset.rule("region:8").damage_resource == "hp"


def test_region_rule_controller_creates_a_ruleset_and_rejects_missing_or_tag_rules():
    document = EditorDocument(Project("Game"))
    controller = MapRuleAuthoringController(document)
    with pytest.raises(MapRuleAuthoringError, match="ruleset"):
        controller.set_region_rule(AreaRule("region:1"))

    created = controller.create_ruleset()
    assert created.rules_id == "map"
    assert controller.set_region_rule(AreaRule("region:1"))
    with pytest.raises(MapRuleAuthoringError, match="region"):
        controller.set_region_rule(AreaRule("tag:ice"))
    assert document.undo()
    assert controller.ruleset.rules == ()
