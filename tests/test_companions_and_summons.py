"""RPG-08: creatures and companions - capture, summon (enemy minions, allies from the roster, by event),
growth of a captured companion, and keeping companions in reserve (storage) across save / load."""

import random

import pytest
from test_session_events import _session
from test_world_record_and_capture import _content, _fight_to_victory

from asteria.events import WorldCommand
from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.game_session import GameSessionError


def _battle():
    project, game = _session()
    _content(project)
    game.start_encounter("boss_room")
    return project, game


def test_a_boss_summons_minions_it_owns_and_they_take_turns():
    project, game = _battle()
    boss = next(e for e in game.active_enemy_ids() if e.startswith("astral_tyrant"))
    minion = next(e for e in project.rpg_database.enemies if e != "astral_tyrant")
    before = set(game.active_enemy_ids())
    added = game.summon(enemy_id=minion, count=2, owner_id=boss)
    assert len(added) == 2 and set(added).isdisjoint(before) and set(added) <= set(game.active_enemy_ids())
    for member_id in added:
        state = game.battle.combatants.state(member_id)
        assert state.summon_owner_id == boss and state.summon_generation == 1  # the boss is generation 0
    assert [e.member_id for e in game.battle_log if e.kind == "summoned"] == list(added)
    assert set(added) <= {t.member_id for t in game.battle.scheduler.pending()}  # they get turns


def test_a_companion_in_reserve_is_called_into_the_battle_and_events_can_summon():
    project, game = _session()
    _content(project)
    state = game.save.rpg_state
    active = state.party_active_actor_ids
    reserve = next(a for a in state.party_actor_ids if a not in active)
    game.start_encounter("boss_room")
    (ally,) = game.summon(actor_id=reserve)
    assert ally == reserve and ally in game.active_hero_ids()
    with pytest.raises(GameSessionError):
        game.summon(actor_id=reserve)  # already fighting
    minion = next(e for e in project.rpg_database.enemies if e != "astral_tyrant")
    result = game.world_commands.dispatch(WorldCommand("SUMMON", {"enemy_id": minion, "count": 1}))
    assert len(result) == 1 and result[0] in game.active_enemy_ids()  # what a battle event program runs


def test_a_captured_companion_grows_and_is_kept_in_reserve_across_save_and_load(tmp_path):
    project, game = _battle()
    tyrant = next(e for e in game.active_enemy_ids() if e.startswith("astral_tyrant"))
    game.battle.member(tyrant).subject.resources.set_current(game.rules.knockout_resource_id, 1)
    assert game.attempt_capture("hero_01", tyrant, rng=random.Random(0)) is True
    _fight_to_victory(game)
    game.finish_victory()
    state = game.save.rpg_state
    assert "tyrant_ally" in state.party_actor_ids and "tyrant_ally" not in state.party_active_actor_ids  # stored
    level = state.actor_progression["tyrant_ally"].level
    grown = game.grant_actor_experience("tyrant_ally", 2500, level_threshold=1000)
    assert grown["new_level"] > level  # the companion grows like any party member
    path = tmp_path / "companions.json"
    game.sync_world_state().save_json(path)
    restored = GameRuntimeSave.load_json(path, project).rpg_state
    assert "tyrant_ally" in restored.party_actor_ids and "tyrant_ally" not in restored.party_active_actor_ids
    assert restored.actor_progression["tyrant_ally"].level == grown["new_level"]


def test_summoned_combatants_appear_on_the_battle_screen(resource_root, monkeypatch):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from test_playable_battle_loop import _boss_runtime

    runtime = _boss_runtime(resource_root)
    try:
        game = runtime.game
        runtime._ui_mode = "field"
        game.start_encounter("boss_room")
        adapter = runtime._battle_presentation
        adapter.begin()
        runtime._frame([], 0.016)
        before = {v.member_id for v in adapter.screen.scene.combatants}
        minion = next(e for e in game.project.rpg_database.enemies if e != "astral_tyrant")
        (added,) = game.summon(enemy_id=minion)
        runtime._frame([], 0.016)
        shown = {v.member_id for v in adapter.screen.scene.combatants}
        assert shown == before | {added}
        assert adapter.screen.scene.visual_for(added).member_id == added and game.battle.member(added).side == "enemies"
        runtime._frame([], 0.016)  # draws with the newcomer
    finally:
        runtime.close()
