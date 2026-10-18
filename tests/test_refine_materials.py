"""Refining asks for materials and can be protected by an item; gear commands can name an
equipped item by its slot ("slot:armor") instead of its instance id."""

import random
from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.project import Project
from asteria.rpg.refine import RefineRules
from asteria.runtime.game_session import GameSessionError, GameSessionRuntime

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


def _session():
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    game.join_party("hero_02")
    game.rearm("hero_02", "a_dawn_robe")
    return game


class _Never:
    def random(self):
        return 0.999  # every roll fails


def test_materials_and_the_protection_item_round_trip():
    rules = RefineRules("r", materials={"silver_ore": 2}, protect_item="blessed_scroll")
    again = RefineRules.from_data(rules.to_data())
    assert again.materials == (("silver_ore", 2),) and again.protect_item == "blessed_scroll"


def test_a_protected_refine_keeps_its_level_and_uses_up_the_scroll():
    game = _session()
    bag = game.save.rpg_state.inventory
    game.save.rpg_state.currencies["gold"] = 99999.0
    bag.add("silver_ore", 20)
    ore = bag.count("silver_ore")
    game.refine_rng = random.Random(1)
    for _ in range(4):  # the first levels never fail (safe_until) or rarely do
        game.refine_equipment("hero_02", "slot:armor")
    armor = game.save.rpg_state.loadouts["hero_02"].equipped("armor")[0]
    level = armor.refine_level
    assert level >= 2 and bag.count("silver_ore") == ore - 4  # one ore per attempt
    game.refine_rng = _Never()
    with pytest.raises(GameSessionError, match="blessed_scroll"):
        game.refine_equipment("hero_02", "slot:armor", protect=True)  # no scroll yet
    bag.add("blessed_scroll", 1)
    result = game.refine_equipment("hero_02", "slot:armor", protect=True)
    assert result.outcome == "protected" and armor.refine_level == level
    assert bag.count("blessed_scroll") == 0
    result = game.refine_equipment("hero_02", "slot:armor")  # unprotected: it drops a level
    assert result.outcome == "failure" and armor.refine_level == level - 1


def test_an_empty_slot_is_an_error():
    game = _session()
    with pytest.raises(GameSessionError, match="wears nothing"):
        game.refine_equipment("hero_02", "slot:accessory")
