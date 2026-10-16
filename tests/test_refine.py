"""Weapon refinement (+N): project rules say what refines, what it costs, how likely it is to
work and what a failure does (nothing, lose a level, or break the item)."""

import pytest
from test_octopath_style_battle import _project
from test_session_events import _session

from asteria.gameplay.modifiers import StatModifier
from asteria.rpg.refine import RefineRules


def _game(rules=None, gold=10_000):
    project = _project()
    if rules is not None:
        project.rpg_database.add_refine_rules(rules)
    project, game = _session(project)
    game.save.rpg_state.currencies["gold"] = gold
    hero = game.save.rpg_state.party_active_actor_ids[0]
    item = game.save.rpg_state.loadouts[hero].equipped()[0]
    return game, hero, item


RULES = dict(
    max_level=5,
    bonuses={"power": 4.0},
    currency="gold",
    base_cost=100,
    cost_growth=50,
)


def test_no_rules_means_no_refine():
    game, hero, item = _game()
    with pytest.raises(Exception, match="refine"):
        game.refine_equipment(hero, item.instance_id)


def test_refine_raises_level_pays_cost_and_adds_stats():
    game, hero, item = _game(RefineRules("r", **RULES))
    before = [m for m in item.modifiers() if m.stat == "power"]
    result = game.refine_equipment(hero, item.instance_id)
    assert result.outcome == "success" and item.refine_level == 1
    assert game.save.rpg_state.currencies["gold"] == 10_000 - 100
    game.refine_equipment(hero, item.instance_id)
    assert game.save.rpg_state.currencies["gold"] == 10_000 - 100 - 150  # cost grows
    added = [m for m in item.modifiers() if m.stat == "power"]
    assert sum(m.value for m in added) - sum(m.value for m in before) == pytest.approx(8.0)


def test_max_level_and_funds_are_enforced():
    game, hero, item = _game(RefineRules("r", **{**RULES, "max_level": 1}))
    game.refine_equipment(hero, item.instance_id)
    with pytest.raises(Exception, match="maximum"):
        game.refine_equipment(hero, item.instance_id)
    poor, hero, item = _game(RefineRules("r", **RULES), gold=10)
    with pytest.raises(Exception, match="gold"):
        poor.refine_equipment(hero, item.instance_id)
    assert item.refine_level == 0


def test_tag_filter_limits_what_can_refine():
    game, hero, item = _game(RefineRules("r", **{**RULES, "equipment_tags": ["no_such_tag"]}))
    with pytest.raises(Exception, match="cannot be refined"):
        game.refine_equipment(hero, item.instance_id)


@pytest.mark.parametrize(
    ("on_fail", "level", "broken"),
    [("keep", 2, False), ("drop", 1, False), ("break", 2, True)],
)
def test_failure_policy_is_an_option(on_fail, level, broken):
    rules = RefineRules("r", **{**RULES, "success": [1.0, 1.0, 0.0], "on_fail": on_fail})
    game, hero, item = _game(rules)
    game.refine_equipment(hero, item.instance_id)
    game.refine_equipment(hero, item.instance_id)
    result = game.refine_equipment(hero, item.instance_id)
    assert result.outcome == "failure"
    assert item.refine_level == level
    assert item.broken is broken
    assert game.save.rpg_state.currencies["gold"] == 10_000 - 100 - 150 - 200  # paid anyway


def test_safe_levels_never_fail():
    rules = RefineRules("r", **{**RULES, "success": [0.0], "on_fail": "drop", "safe_until": 2})
    game, hero, item = _game(rules)
    game.refine_equipment(hero, item.instance_id)
    game.refine_equipment(hero, item.instance_id)
    assert item.refine_level == 2


def test_rules_and_instance_round_trip():
    rules = RefineRules("r", **{**RULES, "success": [1.0, 0.5], "on_fail": "drop"})
    assert RefineRules.from_data(rules.to_data()) == rules
    game, hero, item = _game(rules)
    game.refine_equipment(hero, item.instance_id)
    data = item.to_data()
    assert data["refine"]["level"] == 1
    assert all(StatModifier.from_data(x) for x in data["refine"]["modifiers"])
    plain = _game()[2].to_data()
    assert "refine" not in plain  # untouched instances save exactly as before


def test_rules_validation():
    with pytest.raises(ValueError):
        RefineRules("r", max_level=0)
    with pytest.raises(ValueError):
        RefineRules("r", on_fail="explode")
    with pytest.raises(ValueError):
        RefineRules("r", success=[1.5])
    assert RefineRules("r", max_level=3).chance(2) == 1.0


def test_destroy_policy_removes_the_item():
    rules = RefineRules("r", **{**RULES, "success": [0.0], "on_fail": "destroy"})
    game, hero, item = _game(rules)
    game.refine_equipment(hero, item.instance_id)
    assert item.instance_id not in {
        x.instance_id for x in game.save.rpg_state.loadouts[hero].equipped()
    }
