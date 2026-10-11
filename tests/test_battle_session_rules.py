"""CB3: playable battles take their rules from project data, not runtime code."""

import re
from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.project import Project
from asteria.rpg import BattleSessionRules, RpgDatabase
from asteria.rpg.targeting import TargetRelation
from asteria.runtime.game_session import GameSessionError, GameSessionRuntime

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "reference_projects" / "complex_reference_rpg"


def _project():
    return Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)


def _battle():
    project = _project()
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    game.start_encounter("boss_room")
    return project, game


def test_session_rules_round_trip_and_validate():
    rules = BattleSessionRules(
        "r",
        knockout_resource_id="hp",
        hit_trigger="hit",
        boost_resource_id="bp",
        boost_cost_per_level=2,
        boost_max_level=3,
    )
    assert BattleSessionRules.from_data(rules.to_data()) == rules
    assert rules.boost_enabled
    assert not BattleSessionRules("inert").boost_enabled
    with pytest.raises(ValueError):
        BattleSessionRules("bad", boost_cost_per_level=0)
    with pytest.raises(ValueError):
        BattleSessionRules("bad", boost_max_level=-1)


def test_database_v24_persists_rules_and_v23_still_loads():
    db = RpgDatabase()
    db.add_battle_session_rules(BattleSessionRules("r", knockout_resource_id="hp"))
    raw = db.to_data()
    assert raw["version"] == 29
    assert RpgDatabase.from_data(raw).battle_session_rules["r"].knockout_resource_id == "hp"
    legacy = dict(raw, version=23)
    legacy.pop("battle_session_rules")
    assert RpgDatabase.from_data(legacy).battle_session_rules == {}


def test_reference_project_declares_its_session_rules():
    rules = _project().rpg_database.battle_session_rules["reference_session"]
    assert (rules.knockout_resource_id, rules.boost_resource_id, rules.boost_max_level) == ("vitality", "momentum", 3)


def test_default_targets_follow_ability_targeting_data():
    _, game = _battle()
    hero = game.active_hero_ids()[0]
    db = game.project.rpg_database
    for ability_id, definition in db.battle_targeting.items():
        targets = game.default_targets(hero, ability_id)
        if definition.relation == TargetRelation.SELF:
            assert targets == (hero,)
            continue
        assert 0 < len(targets) <= max(1, definition.maximum_targets)
        sides = {game.battle.member(t).side for t in targets}
        if definition.relation == TargetRelation.OPPONENT:
            assert sides == {"enemies"}
        elif definition.relation == TargetRelation.ALLY:
            assert sides == {"heroes"}


def test_boost_spends_the_rules_resource_and_repeats_the_action():
    _, game = _battle()
    hero = game.active_hero_ids()[0]
    rules = game.rules
    game.battle.battle_resources.change(hero, rules.boost_resource_id, 2, trigger="test.setup")
    available = game.battle.battle_resources.current(hero, rules.boost_resource_id)
    level = game.max_boost_level(hero)
    assert level == min(rules.boost_max_level, int(available // rules.boost_cost_per_level))
    assert level >= 1
    with pytest.raises(GameSessionError):
        game.use_ability(hero, "strike", boost_level=level + 1)
    results = game.use_ability(hero, "strike", boost_level=level)
    assert 1 <= len(results) <= level + 1
    assert (
        game.battle.battle_resources.current(hero, rules.boost_resource_id)
        == available - level * rules.boost_cost_per_level
    )


def test_hits_feed_every_gauge_composition_through_the_rules_trigger():
    _, game = _battle()
    hero = game.active_hero_ids()[0]
    boss = next(x for x in game.active_enemy_ids() if x.startswith("astral_tyrant"))
    before = game.battle.battle_resources.current(boss, "stagger")
    game.use_ability(hero, "fire_arc", (boss,))
    assert game.battle.battle_resources.current(boss, "stagger") == before - 1


def test_turns_follow_the_battle_scheduler_and_enemies_act_between_heroes():
    _, game = _battle()
    hero, log = game.run_enemy_turns()
    assert hero is not None and game.battle.member(hero).side == "heroes"
    assert all(game.battle.member(m).side == "enemies" for m, _ in log)
    assert game.current_turn_actor() == hero
    game.use_ability(hero, "guard")
    game.end_turn()
    next_hero, _ = game.run_enemy_turns()
    assert next_hero is None or game.battle.member(next_hero).side == "heroes"


def test_knockout_resource_comes_from_rules():
    project, game = _battle()
    enemy = game.active_enemy_ids()[0]
    member = game.battle.member(enemy)
    member.subject.resources.set_current("vitality", 0)
    assert enemy not in game.active_enemy_ids()

    project.rpg_database.battle_session_rules.clear()
    assert game.rules.knockout_resource_id == ""
    assert enemy in game.active_enemy_ids()


def test_runtime_contains_no_project_specific_battle_ids():
    names = (
        "heal",
        "revive",
        "momentum",
        "vitality",
        "stagger",
        "stagger_system",
        "astral_tyrant",
        "strike",
        "fire_arc",
        "meteor",
        "party_barrier",
    )
    pattern = re.compile(r"""["'](""" + "|".join(names) + r""")["']""")
    offenders = [
        f"{path.name}:{number}"
        for path in sorted((REPO / "src" / "asteria" / "runtime").glob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line)
    ]
    assert offenders == []
