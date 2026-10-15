"""Battle extension rules and enemy levels inside a real game session (octopath demo data)."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.project import Project
from asteria.rpg import BattleExtensionRules, StealEntry, StealTable
from asteria.rpg.enemy_levels import DifficultyLevel, EnemyLevelRules
from asteria.runtime.game_session import GameSessionError, GameSessionRuntime

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "octopath_demo"
HP = "vitality"


def _session(extension=None, levels=None):
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    if extension is not None:
        project.rpg_database.add_battle_extension_rules(extension)
    if levels is not None:
        project.rpg_database.add_enemy_level_rules(levels)
    return GameSessionRuntime(project, project.game_start.instantiate(project))


def _first_encounter(game):
    return sorted(game.project.rpg_database.encounters)[0]


def test_session_without_rules_has_no_extensions_and_cannot_steal():
    game = _session()
    game.start_encounter(_first_encounter(game))
    assert game.battle.extensions is None and game.opening == "normal"
    assert game.enemy_levels == {}
    with pytest.raises(GameSessionError):
        game.steal("x", "y")


def test_rules_reach_the_battle_and_the_opening_is_rolled():
    rules = BattleExtensionRules("ext", damage_resource=HP, preemptive_chance=1.0)
    game = _session(rules)
    game.start_encounter(_first_encounter(game))
    assert game.battle.extensions.rules is rules
    assert game.opening == "preemptive"
    foes = {m for m, member in game.battle.members.items() if member.side == "enemies"}
    assert not foes & {e.member_id for e in game.battle.turn_queue.pending()}


def test_steal_through_the_session_logs_and_fills_the_bag():
    probe = _session()
    probe.start_encounter(_first_encounter(probe))
    foe = next(m for m, member in probe.battle.members.items() if member.side == "enemies")
    enemy_id = foe.split(":")[0]
    table = StealTable(enemy_id, (StealEntry("potion", 1.0, 2),))
    game = _session(BattleExtensionRules("ext", steal_tables=(table,)))
    game.start_encounter(_first_encounter(game))
    hero = game.save.rpg_state.party_active_actor_ids[0]
    before = game.save.rpg_state.inventory.count("potion")
    result = game.steal(hero, foe)
    assert result.stolen and game.save.rpg_state.inventory.count("potion") == before + 2
    assert game.steal(hero, foe).reason == "already_stolen"
    entries = [e for e in game.drain_battle_log() if e.kind == "steal"]
    assert [e.data["stolen"] for e in entries] == [True, False]


def test_enemy_levels_scale_stats_and_rewards():
    levels = EnemyLevelRules(
        "lv",
        resource_growth={HP: 1.0},
        reward_growth=0.5,
        party_level_offset=4,
        difficulties=(DifficultyLevel("normal"), DifficultyLevel("hard", 2.0, 2.0)),
        default_difficulty="normal",
    )
    plain = _session()
    plain.start_encounter(_first_encounter(plain))
    foe = next(m for m, member in plain.battle.members.items() if member.side == "enemies")
    base_hp = plain.battle.member(foe).subject.resources.maximum(HP)

    game = _session(levels=levels)
    game.start_encounter(_first_encounter(game))
    level = game.enemy_levels[foe]
    scaled_hp = game.battle.member(foe).subject.resources.maximum(HP)
    assert level == game._party_level() + 4 and level > 1
    assert scaled_hp == pytest.approx(base_hp * (1 + (level - 1)))

    game.set_difficulty("hard")
    assert game.difficulty == "hard"
    with pytest.raises(GameSessionError):
        game.set_difficulty("nightmare")


def test_difficulty_survives_in_the_save_variables():
    levels = EnemyLevelRules(
        "lv", difficulties=(DifficultyLevel("easy", 0.5), DifficultyLevel("hard", 2.0))
    )
    game = _session(levels=levels)
    game.set_difficulty("hard")
    other = GameSessionRuntime(game.project, game.save)
    assert other.difficulty == "hard"


def test_mastery_uses_persist_in_the_world_counters():
    probe = _session()
    probe.start_encounter(_first_encounter(probe))
    hero = probe.save.rpg_state.party_active_actor_ids[0]
    ability = probe.battle.member(hero).ability_ids[0]
    rules = BattleExtensionRules("ext", mastery={ability: (1, 3)})
    game = _session(rules)
    game.start_encounter(_first_encounter(game))
    game.battle.extensions.mastery_uses[(hero, ability)] = 2
    game._store_mastery()
    assert game.world.counters[f"mastery.{hero}|{ability}"] == 2.0
    game.mode, game.battle = "field", None
    game.start_encounter(_first_encounter(game))
    assert game.battle.extensions.mastery_uses[(hero, ability)] == 2
    assert game.battle.extensions.mastery_level(hero, ability) == 1


def test_session_builds_an_aftermath_from_a_won_battle():
    game = _session()
    game.start_encounter(_first_encounter(game))
    before = game.capture_hero_state()
    hero = game.save.rpg_state.party_active_actor_ids[0]
    assert before[hero]["level"] >= 1 and before[hero]["stats"]
    for member_id in game.active_enemy_ids():
        game.battle.member(member_id).subject.resources.set_current(HP, 0)
    applied = game.finish_victory()
    game.grant_actor_experience(hero, 5000, level_threshold=1000)
    aftermath = game.build_aftermath(applied, before, {hero: 5000})
    actor = next(x for x in aftermath.actors if x.actor_id == hero)
    assert actor.experience_gained == 5000 and actor.leveled_up
    assert aftermath.defeated and aftermath.pages()[0].kind == "rewards"
