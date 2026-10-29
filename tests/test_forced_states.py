"""States that take the choice away: confusion and charm (the target is picked for you),
berserk (only some skills), doom (death when it runs out). All of it is state data."""

import dataclasses

import pytest
from test_break_battle import DAMAGE, _battle, _project

from asteria.gameplay import Effect, EffectOperation, EffectOperationKind
from asteria.gameplay.states import StateDefinition
from asteria.rpg import BattleStatePolicy
from asteria.runtime.game_session import GameSessionError


def _project_with_states():
    project = _project()
    states = project.gameplay_library.states._definitions
    policies = project.rpg_database.battle_state_policies
    states["confuse"] = StateDefinition("confuse", 4, contributed_tags=("status.confuse",))
    policies["confuse"] = BattleStatePolicy(
        "confuse", tick_trigger="rpg.battle.turn_ended", target_override="random_any"
    )
    states["charm"] = StateDefinition("charm", 4)
    policies["charm"] = BattleStatePolicy(
        "charm", tick_trigger="rpg.battle.turn_ended", target_override="random_ally"
    )
    states["berserk"] = StateDefinition("berserk", 4)
    policies["berserk"] = BattleStatePolicy(
        "berserk",
        tick_trigger="rpg.battle.turn_ended",
        allowed_ability_tags=("weapon.sword",),
        target_override="random_opponent",
    )
    kill = EffectOperation(EffectOperationKind.RESOURCE_SET, DAMAGE, 0.0)
    states["doom"] = StateDefinition("doom", 2, on_expire=(Effect("doom.kill", (kill,)),))
    policies["doom"] = BattleStatePolicy("doom", tick_trigger="rpg.battle.turn_ended")
    return project


def _afflict(game, member, state):
    game.battle.apply_state(state, member, member)


def _targets_over(game, hero, boss, ability, casts=40):
    seen = set()
    for _ in range(casts):
        game.battle.member(hero).subject.resources.set_current(DAMAGE, 5000)
        game.battle.member(boss).subject.resources.set_current(DAMAGE, 9000)
        game.drain_battle_log()
        try:
            game.use_ability(hero, ability, (boss,))
        except GameSessionError:
            continue
        seen.update(t for e in game.drain_battle_log() if e.kind == "action" for t in e.target_ids)
    return seen


def test_confusion_can_turn_an_attack_on_anyone_including_the_user():
    game, hero, boss = _battle(_project_with_states())
    assert _targets_over(game, hero, boss, "oct_sword") == {boss}  # no state: as aimed
    _afflict(game, hero, "confuse")
    assert _targets_over(game, hero, boss, "oct_sword") >= {hero, boss}


def test_charm_points_actions_at_allies_only():
    game, hero, boss = _battle(_project_with_states())
    _afflict(game, hero, "charm")
    seen = _targets_over(game, hero, boss, "oct_sword")
    allies = set(game.battle.parties["heroes"].ids())
    assert seen and seen <= allies  # only its own side, never the foe
    assert boss not in seen


def test_berserk_allows_only_the_listed_skills_and_picks_the_foe():
    game, hero, boss = _battle(_project_with_states())
    _afflict(game, hero, "berserk")
    reason = game.ability_unavailable(hero, "oct_fire")  # not a sword skill
    assert reason
    with pytest.raises((GameSessionError, ValueError)):
        game.use_ability(hero, "oct_fire", (boss,))
    assert not game.ability_unavailable(hero, "oct_sword")
    foes = set(game.battle.parties["enemies"].ids())
    seen = _targets_over(game, hero, boss, "oct_sword", casts=8)
    assert seen and seen <= foes  # always a foe, whoever was picked


def test_doom_kills_when_it_runs_out():
    game, hero, boss = _battle(_project_with_states())
    pool = game.battle.member(hero).subject.resources
    _afflict(game, hero, "doom")
    assert pool.current(DAMAGE) > 0
    member = game.battle.member(hero)
    for _ in range(2):  # it ticks at the end of each of its own turns
        game.battle.battle_states.apply_trigger("rpg.battle.turn_ended", (member,))
    assert pool.current(DAMAGE) == 0


def test_policy_fields_round_trip_validate_and_default_to_nothing():
    plain = BattleStatePolicy("p").to_data()
    assert "target_override" not in plain and "allowed_ability_tags" not in plain
    policy = BattleStatePolicy(
        "p", target_override="random_ally", allowed_ability_tags=["weapon.sword"]
    )
    again = BattleStatePolicy.from_data(policy.to_data())
    assert again.target_override == "random_ally"
    assert again.allowed_ability_tags == ("weapon.sword",)
    with pytest.raises(ValueError):
        BattleStatePolicy("p", target_override="everyone")
    assert dataclasses.is_dataclass(policy)
