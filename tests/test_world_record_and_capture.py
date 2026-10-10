"""CB11: reputation, relationships, achievements, bestiary (WLD-02) and capture (RPG-08)."""

import json
import random

import pytest
from test_session_events import BOSS_PROGRAM, _interact, _replace_program, _session

from asteria.events import EventInstruction
from asteria.rpg import (
    AchievementDefinition,
    CaptureRule,
    FactionDefinition,
    QuestDefinition,
    QuestObjective,
    RpgDatabase,
    RpgRuntimeState,
    WorldRecord,
)
from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.game_session import GameSessionError


def _content(project):
    db = project.rpg_database
    db.add_faction(
        FactionDefinition(
            "guild",
            "Adventurers' Guild",
            minimum=-50,
            maximum=50,
            ranks=[(0, "Neutral"), (20, "Friendly"), (45, "Honored")],
        )
    )
    db.add_achievement(AchievementDefinition("friend", "Guild Friend", kind="reputation", target="guild", value=20))
    db.add_achievement(AchievementDefinition("slayer", "Wisp Slayer", kind="defeated", target="mender_wisp", value=2))
    db.add_achievement(AchievementDefinition("chatty", "Chatty", kind="counter", target="talks", value=3))
    db.add_quest(QuestDefinition("errand", objectives=[QuestObjective("go")]))
    db.add_achievement(AchievementDefinition("errand_done", kind="quest", target="errand"))
    base = db.actors["hero_01"]
    db.add_actor(
        type(base)(
            "tyrant_ally",
            "Tyrant (Ally)",
            base_stats=base.base_stats,
            base_resources=base.base_resources,
            abilities=base.abilities,
        )
    )
    db.add_capture_rule(CaptureRule("astral_tyrant", "tyrant_ally", base_chance=0.0, low_health_bonus=1.0))
    db.validate()
    return db


def test_faction_ranks_clamp_and_records_round_trip():
    faction = FactionDefinition("guild", minimum=-10, maximum=10, ranks=[(0, "Neutral"), (5, "Friendly")])
    record = WorldRecord()
    assert record.change_reputation(faction, 25) == 10 and faction.rank(10) == "Friendly"
    assert record.change_reputation(faction, -30) == -10 and faction.rank(-10) == ""
    record.note_enemy("slime", "seen")
    record.add_counter("talks", 2)
    assert WorldRecord.from_data(json.loads(json.dumps(record.to_data()))) == record
    with pytest.raises(ValueError):
        FactionDefinition("x", minimum=0, maximum=10, initial=20)


def test_events_drive_reputation_counters_and_unlock_achievements():
    project, game = _session()
    _content(project)
    _replace_program(
        project,
        BOSS_PROGRAM,
        [
            EventInstruction("WORLD", {"command": "CHANGE_REPUTATION", "args": {"faction_id": "guild", "amount": 25}}),
            EventInstruction(
                "WORLD", {"command": "CHANGE_RELATIONSHIP", "args": {"subject_id": "innkeeper", "amount": 2}}
            ),
            EventInstruction("WORLD", {"command": "ADD_COUNTER", "args": {"counter_id": "talks", "amount": 3}}),
            EventInstruction("END"),
        ],
    )
    _interact(game)
    world = game.world
    assert world.reputation["guild"] == 25 and world.relationships["innkeeper"] == 2
    assert set(world.achievements) == {"friend", "chatty"}
    ctx = game.save.event_context
    assert ctx.get_switch("achievement.friend.unlocked") and ctx.get_variable("reputation.guild") == 25
    game.start_quest("errand")
    game.advance_quest("errand", "go")
    assert "errand_done" in world.achievements


def _fight_to_victory(game):
    for enemy_id in tuple(game.active_enemy_ids()):
        while enemy_id in game.active_enemy_ids():
            for hero_id in tuple(game.active_hero_ids()):
                if enemy_id in game.active_enemy_ids():
                    game.execute(hero_id, "strike", (enemy_id,))


def test_capture_joins_the_roster_and_skips_reward_and_defeat(tmp_path):
    project, game = _session()
    _content(project)
    game.start_encounter("boss_room")
    assert game.world.bestiary["astral_tyrant"]["seen"] == 1
    with pytest.raises(GameSessionError):
        game.attempt_capture("hero_01", "mender_wisp:2")  # no capture rule
    tyrant = "astral_tyrant:1"
    assert game.attempt_capture("hero_01", tyrant, rng=random.Random(0)) is False  # full health: 0%
    resources = game.battle.member(tyrant).subject.resources
    resource = game.rules.knockout_resource_id
    resources.set_current(resource, 1)
    assert game.attempt_capture("hero_01", tyrant, rng=random.Random(0)) is True
    assert tyrant not in game.active_enemy_ids()
    assert [e.kind for e in game.battle_log].count("capture") == 2
    _fight_to_victory(game)
    renown = game.save.rpg_state.currencies.get("renown", 0)
    game.finish_victory()
    state = game.save.rpg_state
    assert "tyrant_ally" in state.party_actor_ids and "tyrant_ally" not in state.party_active_actor_ids
    assert game.world.bestiary["astral_tyrant"] == {"seen": 1, "defeated": 0, "captured": 1}
    assert game.world.bestiary["mender_wisp"]["defeated"] == 2 and "slayer" in game.world.achievements
    assert state.currencies.get("renown", 0) >= renown
    game.set_active_party(state.party_active_actor_ids[:5] + ("tyrant_ally",))
    path = tmp_path / "save.json"
    game.sync_world_state().save_json(path)
    restored = GameRuntimeSave.load_json(path, project)
    assert restored.rpg_state.world == game.world
    assert "tyrant_ally" in restored.rpg_state.party_active_actor_ids


def test_database_round_trip_and_reference_validation():
    project, _ = _session()
    db = _content(project)
    loaded = RpgDatabase.from_data(json.loads(json.dumps(db.to_data())))
    assert loaded.factions == db.factions and loaded.achievements == db.achievements
    assert loaded.capture_rules == db.capture_rules
    db.add_achievement(AchievementDefinition("bad", kind="defeated", target="nobody"))
    with pytest.raises(ValueError):
        db.validate()
    with pytest.raises(TypeError):
        RpgRuntimeState(world={})
