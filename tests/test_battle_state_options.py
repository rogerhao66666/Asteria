"""Battle state options (a chance to lose a turn, a chance to be cured, random durations, one
state of a group at a time, ticks told), states a move applies by chance and not on a miss,
capture shake checks, and a creature called back losing its battle counters."""

import random

import pytest

from asteria.core.lifecycle import LifecycleHookBus
from asteria.gameplay import (
    Effect,
    EffectOperation,
    GameplaySubject,
    ResourcePool,
    StatBlock,
    StateDefinition,
    StateRegistry,
    StateRuntime,
    TagSet,
)
from asteria.gameplay.formulas import ValueFormula
from asteria.gameplay.states import PeriodicEffect
from asteria.rpg.battle_states import BattleStatePolicy, BattleStateRuntime
from asteria.rpg.capture import CaptureRule

READY, ENDED = "rpg.battle.turn_ready", "rpg.battle.turn_ended"


class _Member:
    def __init__(self, member_id, subject):
        self.member_id, self.subject = member_id, subject


def _subject(registry, hp=80, tags=()):
    stats, resources, tag_set = StatBlock({"speed": 10}), ResourcePool(), TagSet(tags)
    resources.define("hp", hp)
    return GameplaySubject(
        stats, resources, tag_set, StateRuntime(registry, stats, resources, tag_set)
    )


def _registry():
    registry = StateRegistry()
    eighth = ValueFormula(expression='-floor(target.maximum("hp") / 8)')
    hurt = PeriodicEffect(1.0, Effect("eighth", [EffectOperation("resource_delta", "hp", eighth)]))
    for state_id, periodic in (
        ("poison", (hurt,)),
        ("sleep", ()),
        ("paralysis", ()),
        ("freeze", ()),
    ):
        registry.register(StateDefinition(state_id, 1_000_000.0, periodic=periodic))
    return registry


def _runtime(*policies, seed=0):
    bus = LifecycleHookBus()
    seen = []
    for hook in ("state_ticked", "state_expired", "state_removed"):
        bus.subscribe(f"rpg.battle.{hook}", lambda e, hook=hook: seen.append((hook, e.data)))
    runtime = BattleStateRuntime(policies, hooks=bus)
    runtime.rng = random.Random(seed)
    return runtime, seen


def test_poison_hurts_an_eighth_each_turn_end_and_says_so():
    runtime, seen = _runtime(BattleStatePolicy("poison", tick_trigger=ENDED))
    subject = _subject(_registry())
    runtime.apply("poison", "a", subject, "b", subject, rng=random.Random(0))
    member = _Member("b", subject)
    runtime.apply_trigger(ENDED, (member,))
    runtime.apply_trigger(ENDED, (member,))
    assert subject.resources.current("hp") == 60.0
    assert [h for h, _ in seen] == ["state_ticked", "state_ticked"]
    assert seen[0][1]["changes"] == {"hp": -10.0}


def test_sleep_lasts_a_random_number_of_turns_and_stops_them():
    policy = BattleStatePolicy(
        "sleep", tick_trigger=READY, prevent_action=True, duration_range=[2, 5]
    )
    lengths = set()
    for seed in range(40):
        runtime, _seen = _runtime(policy, seed=seed)
        subject = _subject(_registry())
        result = runtime.apply("sleep", "a", subject, "b", subject, rng=random.Random(seed))
        lengths.add(result.duration)
        assert not runtime.ability_availability(subject).allowed
    assert lengths == {2.0, 3.0, 4.0, 5.0}
    assert BattleStatePolicy.from_data(policy.to_data()) == policy
    with pytest.raises(ValueError):
        BattleStatePolicy("sleep", duration_range=[5, 2])


def test_paralysis_stops_about_one_turn_in_four():
    policy = BattleStatePolicy("paralysis", tick_trigger=READY, prevent_chance=0.25)
    runtime, _seen = _runtime(policy, seed=3)
    subject = _subject(_registry())
    runtime.apply("paralysis", "a", subject, "b", subject, rng=random.Random(0))
    member, stopped = _Member("b", subject), 0
    for _ in range(4000):
        runtime.apply_trigger(READY, (member,))
        first = runtime.ability_availability(subject).allowed
        assert runtime.ability_availability(subject).allowed == first  # held for the turn
        stopped += not first
    assert 0.22 < stopped / 4000 < 0.28


def test_freeze_thaws_one_time_in_five_before_acting():
    policy = BattleStatePolicy(
        "freeze", tick_trigger=READY, prevent_action=True, remove_chance=0.2
    )
    turns = []
    for seed in range(400):
        runtime, seen = _runtime(policy, seed=seed)
        subject = _subject(_registry())
        runtime.apply("freeze", "a", subject, "b", subject, rng=random.Random(0))
        member = _Member("b", subject)
        for turn in range(1, 200):
            runtime.apply_trigger(READY, (member,))
            if subject.states.get("freeze") is None:
                assert seen[-1] == ("state_removed", {"state_id": "freeze", "trigger": "chance"})
                assert runtime.ability_availability(subject).allowed
                turns.append(turn)
                break
    assert 4.0 < sum(turns) / len(turns) < 6.0  # one in five: five turns on average


def test_one_state_of_a_group_at_a_time():
    policies = [BattleStatePolicy(s, exclusive_group="ailment") for s in ("poison", "sleep")]
    runtime, _seen = _runtime(*policies)
    subject = _subject(_registry())
    assert runtime.apply("poison", "a", subject, "b", subject).applied
    again = runtime.apply("poison", "a", subject, "b", subject)
    other = runtime.apply("sleep", "a", subject, "b", subject)
    assert (again.applied, again.reason) == (False, "already")
    assert (other.applied, other.reason) == (False, "exclusive")


def test_a_move_applies_its_state_by_its_own_chance_and_never_on_a_miss():
    from asteria.gameplay.abilities import AbilityDefinition

    data = {
        "schema": "asteria.ability_definition",
        "version": 1,
        "ability_id": "sting",
        "targeting": {
            "minimum_targets": 1,
            "maximum_targets": 1,
            "allow_self": False,
            "required_tags": [],
            "blocked_tags": [],
        },
        "costs": [],
        "conditions": {"type": "group", "mode": "all", "conditions": []},
        "effects": [],
        "tags": ["ability"],
        "apply_states": [{"state": "poison", "chance": 0.3, "unless_outcome": ["outcome.miss"]}],
    }
    definition = AbilityDefinition.from_data(data)
    entry = definition.apply_states[0]
    assert entry["chance"] == 0.3 and entry["unless_outcome"] == ["outcome.miss"]
    assert AbilityDefinition.from_data(definition.to_data()).apply_states == (entry,)
    plain = AbilityDefinition.from_data({**data, "apply_states": [{"state": "poison"}]})
    assert "chance" not in plain.apply_states[0]
    with pytest.raises(ValueError):
        AbilityDefinition.from_data({**data, "apply_states": [{"state": "x", "chance": 2}]})


def test_capture_shake_checks_keep_the_odds_and_count_the_shakes():
    rule = CaptureRule("*", mode="rate", item_id="ball", shake_checks=4)
    assert CaptureRule.from_data(rule.to_data()) == rule
    rng = random.Random(7)
    results = [rule.roll(0.3, rng) for _ in range(20000)]
    caught = sum(c for c, _ in results) / len(results)
    assert 0.28 < caught < 0.32
    assert all((s == 4) == c for c, s in results)
    assert {s for _, s in results} == {0, 1, 2, 3, 4}
    single = CaptureRule("*", mode="rate", item_id="ball")
    assert single.roll(1.0, rng) == (True, 1) and single.roll(0.0, rng) == (False, 0)
