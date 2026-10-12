"""GP-02 in the game session: ability cost, cooldown, targeting data, cast / recovery timing, tags."""

import dataclasses

import pytest
from test_session_events import _session

from asteria.rpg.battle_session_rules import BattleSessionRules
from asteria.runtime.game_session import GameSessionError


def _battle(*, timing="immediate", cooldown=None):
    project, _ = _session()
    db = project.rpg_database
    if timing != "immediate":
        rules = db.battle_session_rules
        first = sorted(rules)[0]
        rules[first] = dataclasses.replace(rules[first], action_timing=timing)
    if cooldown:
        library = project.gameplay_library.abilities
        ability_id, turns = cooldown
        library._definitions[ability_id] = dataclasses.replace(library.get(ability_id), cooldown_turns=turns)
    project, game = _session(project)
    game.start_encounter("boss_room")
    return game


def _hero_turn(game):
    actor, _ = game.run_enemy_turns()
    return actor


def test_cost_is_paid_and_targets_follow_the_ability_targeting_data():
    game = _battle()
    hero = _hero_turn(game)
    ability = next(
        a
        for a in game.resolve_actor_build(hero).abilities
        if game.battle.ability_runtime.registry.get(a) and game.battle.ability_runtime.registry.get(a).costs
    )
    cost = game.battle.ability_runtime.registry.get(ability).costs[0]
    pool = game.battle.member(hero).subject.resources
    before = pool.current(cost.resource)
    game.use_ability(hero, ability)
    assert pool.current(cost.resource) < before  # the cost (a formula) was paid
    targets = game.default_targets(hero, "strike")
    assert targets and all(game.battle.member(t).side == "enemies" for t in targets)


def test_cooldown_blocks_the_ability_for_its_users_next_turns():
    game = _battle(cooldown=("strike", 1))
    hero = _hero_turn(game)
    target = game.default_targets(hero, "strike")
    game.use_ability(hero, "strike", target)
    assert game.battle.cooldown_remaining(hero, "strike") == 1
    game.end_turn()
    for _ in range(20):  # the same hero's next turn: strike is cooling down
        if _hero_turn(game) == hero:
            break
        game.end_turn()
    with pytest.raises(ValueError, match="cooling down"):
        game.use_ability(hero, "strike", game.default_targets(hero, "strike"))
    game.end_turn()
    for _ in range(20):  # one more turn later it is ready again
        if _hero_turn(game) == hero:
            break
        game.end_turn()
    assert game.battle.cooldown_remaining(hero, "strike") == 0
    game.use_ability(hero, "strike", game.default_targets(hero, "strike"))


def test_timeline_mode_casts_resolve_later_and_recovery_delays_the_next_turn():
    game = _battle(timing="timeline")
    hero = _hero_turn(game)
    target = game.default_targets(hero, "strike")
    hp = game.battle.member(target[0]).subject.resources
    resource = game.rules.knockout_resource_id
    before = hp.current(resource)
    ready_before = {t.member_id: t.ready_time for t in game.battle.scheduler.pending()}.get(hero)
    assert game.use_ability(hero, "strike", target) == ()  # a cast: nothing resolves yet
    assert [e.kind for e in game.battle_log][-1] == "cast_started"
    assert hp.current(resource) == before
    game.end_turn()
    for _ in range(20):  # the timeline moves on; the cast resolves when it reaches resolve_at
        if hp.current(resource) < before:
            break
        game.run_enemy_turns()
        game.end_turn()
    assert hp.current(resource) < before
    assert any(e.kind == "action" and e.member_id == hero for e in game.battle_log)
    ready_after = {t.member_id: t.ready_time for t in game.battle.scheduler.pending()}.get(hero)
    timing = game.battle.action_timing.definition_for("strike")
    if ready_before is not None and ready_after is not None:
        assert ready_after >= ready_before + timing.windup + timing.recovery - 1e-6


def test_immediate_mode_is_the_default_and_rules_round_trip():
    rules = BattleSessionRules("r", action_timing="timeline")
    assert BattleSessionRules.from_data(rules.to_data()) == rules
    assert "action_timing" not in BattleSessionRules("r").to_data()
    with pytest.raises(ValueError):
        BattleSessionRules("r", action_timing="realtime")
    game = _battle()
    hero = _hero_turn(game)
    assert game.use_ability(hero, "strike", game.default_targets(hero, "strike"))  # resolves now
    with pytest.raises(GameSessionError):
        game.use_ability(hero, "strike", ())  # no targets
