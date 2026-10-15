"""Battle weather: its own setting, tags on the fighters, drawn in battle, gone after."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.events.world_commands import WorldCommand
from asteria.project import Project
from asteria.runtime.game_session import GameSessionError, GameSessionRuntime
from asteria.runtime.world_command_handlers import WorldCommandError

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "octopath_demo"


def _project():
    return Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)


def _session():
    project = _project()
    return GameSessionRuntime(project, project.game_start.instantiate(project))


def _encounter(game):
    return sorted(game.project.rpg_database.encounters)[0]


def test_no_weather_by_default_and_validation():
    game = _session()
    assert game.battle_weather() is None
    with pytest.raises(GameSessionError):
        game.set_battle_weather("meteors")
    assert game.set_battle_weather("rain", 0.8, 30.0) == ("rain", 0.8, 30.0)
    assert game.set_battle_weather("rain", 5.0)[1] == 1.0  # intensity is clamped
    assert game.set_battle_weather("none") is None and game.battle_weather() is None


def test_every_fighter_gets_the_weather_tag_for_the_battle_only():
    game = _session()
    game.set_battle_weather("snow")
    game.start_encounter(_encounter(game))
    assert all(m.subject.tags.contains("weather.snow") for m in game.battle.members.values())
    game.set_battle_weather("rain")  # changed during the battle
    for member in game.battle.members.values():
        assert member.subject.tags.contains("weather.rain")
        assert not member.subject.tags.contains("weather.snow")
    game.set_battle_weather("none")
    assert not any(
        t.startswith("weather.")
        for m in game.battle.members.values()
        for t in m.subject.tags.values()
    )


def test_the_weather_tag_is_not_saved_with_the_heroes():
    game = _session()
    game.set_battle_weather("rain")
    game.start_encounter(_encounter(game))
    for member_id in game.active_enemy_ids():
        game.battle.member(member_id).subject.resources.set_current("vitality", 0)
    game.finish_victory()
    for snapshot in game.save.rpg_state.actor_snapshots.values():
        assert "weather.rain" not in snapshot.tags["values"]


def test_an_interaction_rule_can_key_off_the_weather():
    from asteria.rpg import BattleAction, InteractionRule

    project = _project()
    project.rpg_database.add_interaction_rule(
        InteractionRule(
            "rain_amplifies",
            source_tags_all=("weapon.sword",),
            target_tags_all=("weather.rain",),
            multiplier=3.0,
        )
    )
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    game.start_encounter(_encounter(game))
    hero = game.save.rpg_state.party_active_actor_ids[0]
    foe = next(m for m, member in game.battle.members.items() if member.side == "enemies")

    def damage():
        pool = game.battle.member(foe).subject.resources
        pool.set_current("vitality", pool.maximum("vitality"))
        before = pool.current("vitality")
        game.battle.execute(BattleAction(hero, "attack_sword", (foe,)))
        return before - pool.current("vitality")

    dry = damage()
    game.set_battle_weather("rain")
    wet = damage()
    assert dry > 0 and wet == pytest.approx(dry * 3.0)


def test_the_command_sets_the_weather_and_rejects_nonsense():
    game = _session()
    game.world_commands.dispatch(WorldCommand("SET_BATTLE_WEATHER", {"kind": "leaves"}))
    assert game.battle_weather()[0] == "leaves"
    with pytest.raises(WorldCommandError):
        game.world_commands.dispatch(WorldCommand("SET_BATTLE_WEATHER", {"kind": "lava"}))


def test_the_battle_environment_uses_the_battle_weather(monkeypatch):
    pytest.importorskip("pygame")
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = _project()
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT, width=960, height=540
    )
    runtime.open()
    try:
        assert runtime._resolve_environment("battle").weather == "none"
        runtime.game.set_battle_weather("rain", 0.7)
        env = runtime._resolve_environment("battle")
        assert (env.weather, env.weather_intensity) == ("rain", 0.7) and env.active
        assert env.weather_max_particles > 0
        assert runtime._resolve_environment("field").weather != "rain"  # the map is unaffected
    finally:
        runtime.close()
