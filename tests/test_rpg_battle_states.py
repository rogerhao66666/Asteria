import random

import pytest

from asteria.gameplay import (
    AbilityDefinition,
    AbilityRegistry,
    AbilityRuntime,
    Effect,
    EffectOperation,
    GameplaySubject,
    PeriodicEffect,
    ResourcePool,
    StatBlock,
    StateDefinition,
    StateRegistry,
    StateRuntime,
    TagSet,
    TargetingRule,
)
from asteria.rpg import (
    BattleAction,
    BattleRuntime,
    BattleStatePolicy,
    BattleStateRuntime,
    Party,
    PartyMember,
    RpgDatabase,
)


def subject(*, tags=(), stats=None, states=()):
    stat_block = StatBlock(stats or {"status_power": 0, "status_resist": 0, "speed": 10})
    resources = ResourcePool()
    resources.define("hp", 100, current=100)
    tag_set = TagSet(tags)
    registry = StateRegistry(states)
    state_runtime = StateRuntime(registry, stat_block, resources, tag_set)
    return GameplaySubject(stat_block, resources, tag_set, state_runtime)


def test_policy_roundtrip_and_open_trigger_vocabulary():
    policy = BattleStatePolicy(
        "silence",
        base_chance=0.75,
        source_stat_terms={"status_power": 0.01},
        target_stat_terms={"status_resist": -0.01},
        immune_target_tags=["immune.silence"],
        duration_multiplier=0.5,
        duration_target_stat_terms={"status_resist": -0.01},
        blocked_ability_tags=["ability.magic"],
        tick_trigger="custom.clock.pulse",
        tick_amount=0.25,
    )
    assert BattleStatePolicy.from_data(policy.to_data()) == policy
    assert policy.tick_trigger == "custom.clock.pulse"


def test_state_application_uses_chance_stats_and_source_provenance():
    state = StateDefinition("poison", 4)
    src = subject(stats={"status_power": 20, "status_resist": 0, "speed": 10}, states=[state])
    dst = subject(stats={"status_power": 0, "status_resist": 10, "speed": 10}, states=[state])
    policy = BattleStatePolicy(
        "poison", base_chance=0.5, source_stat_terms={"status_power": 0.01}, target_stat_terms={"status_resist": -0.01}
    )
    result = BattleStateRuntime([policy]).apply("poison", "hero", src, "slime", dst, rng=random.Random(1))
    assert result.applied
    assert result.chance == pytest.approx(0.6)
    assert dst.states.get("poison").source_id == "hero"


def test_immunity_is_tag_driven_not_state_name_driven():
    state = StateDefinition("machine.overheat", 3)
    src = subject(states=[state])
    dst = subject(tags=["boss.phase1.control_immune"], states=[state])
    policy = BattleStatePolicy("machine.overheat", immune_target_tags=["boss.phase1.control_immune"])
    result = BattleStateRuntime([policy]).apply("machine.overheat", "a", src, "b", dst, rng=random.Random(0))
    assert result.immune and not result.applied
    assert dst.states.get("machine.overheat") is None


def test_duration_resistance_can_shorten_state_without_hardcoded_status_logic():
    state = StateDefinition("slow", 10)
    src = subject(states=[state])
    dst = subject(stats={"status_power": 0, "status_resist": 25, "speed": 10}, states=[state])
    policy = BattleStatePolicy("slow", duration_multiplier=1, duration_target_stat_terms={"status_resist": -0.02})
    result = BattleStateRuntime([policy]).apply("slow", "a", src, "b", dst, rng=random.Random(1))
    assert result.duration == pytest.approx(5)
    assert dst.states.get("slow").remaining == pytest.approx(5)


def test_prevent_action_and_tag_specific_silence_share_one_policy_model():
    states = [StateDefinition("stun", 1), StateDefinition("silence", 2)]
    actor = subject(states=states)
    rt = BattleStateRuntime(
        [
            BattleStatePolicy("stun", prevent_action=True),
            BattleStatePolicy("silence", blocked_ability_tags=["ability.magic"]),
        ]
    )
    actor.states.apply("silence")
    assert not rt.ability_availability(actor, ["ability.magic"]).allowed
    assert rt.ability_availability(actor, ["ability.physical"]).allowed
    actor.states.apply("stun")
    assert not rt.ability_availability(actor, ["ability.physical"]).allowed


def test_trigger_ticks_only_states_bound_to_that_lifecycle():
    states = [StateDefinition("poison", 3), StateDefinition("aura", 3)]
    actor = subject(states=states)
    actor.states.apply("poison")
    actor.states.apply("aura")
    member = PartyMember("hero", "heroes", actor)
    rt = BattleStateRuntime([BattleStatePolicy("poison", tick_trigger="rpg.battle.turn_ended")])
    rt.apply_trigger("rpg.battle.turn_ended", [member])
    assert actor.states.get("poison").remaining == 2
    assert actor.states.get("aura").remaining == 3


def test_periodic_effect_can_tick_on_battle_lifecycle():
    poison = StateDefinition(
        "poison",
        3,
        periodic=[PeriodicEffect(1, Effect("poison_tick", [EffectOperation("resource_delta", "hp", -7)]))],
    )
    actor = subject(states=[poison])
    actor.states.apply("poison")
    member = PartyMember("hero", "heroes", actor)
    rt = BattleStateRuntime([BattleStatePolicy("poison", tick_trigger="rpg.battle.turn_ended")])
    rt.apply_trigger("rpg.battle.turn_ended", [member])
    assert actor.resources.current("hp") == 93


def test_state_snapshot_v2_preserves_source_without_replaying_on_apply():
    marked = Effect("mark", [EffectOperation("resource_delta", "hp", -10)])
    definition = StateDefinition("marked", 5, on_apply=[marked])
    a = subject(states=[definition])
    a.states.apply("marked", source_id="boss")
    assert a.resources.current("hp") == 90
    snap = a.states.snapshot()
    assert snap["version"] == 2
    b = subject(states=[definition])
    b.states.restore(snap)
    assert b.resources.current("hp") == 100
    assert b.states.get("marked").source_id == "boss"


def test_state_snapshot_v1_stays_backward_readable():
    definition = StateDefinition("legacy", 5)
    rt = subject(states=[definition]).states
    rt.restore(
        {
            "schema": "asteria.state_runtime",
            "version": 1,
            "active": [{"state_id": "legacy", "remaining": 2, "stacks": 1, "periodic_elapsed": []}],
        }
    )
    assert rt.get("legacy").remaining == 2
    assert rt.get("legacy").source_id is None


def battle_fixture():
    defs = [StateDefinition("stun", 1), StateDefinition("silence", 2)]
    hero = subject(states=defs)
    enemy = subject(states=defs)
    registry = AbilityRegistry(
        [
            AbilityDefinition("slash", targeting=TargetingRule(), tags=["ability.physical"]),
            AbilityDefinition("fire", targeting=TargetingRule(), tags=["ability.magic"]),
        ]
    )
    runtime = AbilityRuntime(registry)
    parties = [
        Party("heroes", [PartyMember("hero", "heroes", hero, ability_ids=["slash", "fire"], initiative=10)]),
        Party("enemies", [PartyMember("enemy", "enemies", enemy, ability_ids=["slash"], initiative=1)]),
    ]
    battle = BattleRuntime(
        parties,
        runtime,
        state_policies=[
            BattleStatePolicy("stun", prevent_action=True, tick_trigger="rpg.battle.turn_ended"),
            BattleStatePolicy("silence", blocked_ability_tags=["ability.magic"], tick_trigger="rpg.battle.turn_ended"),
        ],
    )
    return battle


def test_battle_runtime_apply_state_and_ability_availability():
    battle = battle_fixture()
    applied = battle.apply_state("silence", "enemy", "hero", rng=random.Random(1))
    assert applied.applied
    assert not battle.ability_availability("hero", "fire").allowed
    assert battle.ability_availability("hero", "slash").allowed
    with pytest.raises(ValueError, match="blocked by active state"):
        battle.execute(BattleAction("hero", "fire", ["enemy"]))


def test_battle_turn_end_advances_bound_status_and_expires_it():
    battle = battle_fixture()
    battle.apply_state("stun", "enemy", "hero", rng=random.Random(1))
    assert not battle.ability_availability("hero", "slash").allowed
    # Batch 86 scheduler consumes a fully action-blocked turn automatically.
    assert battle.next_actor().member_id == "enemy"
    assert battle.member("hero").subject.states.get("stun") is None
    assert battle.ability_availability("hero", "slash").allowed


def test_database_v11_owns_battle_state_policies_and_v10_is_backward_readable():
    db = RpgDatabase()
    db.add_battle_state_policy(BattleStatePolicy("poison", immune_target_tags=["immune.poison"]))
    data = db.to_data()
    assert data["version"] == 28
    restored = RpgDatabase.from_data(data)
    assert restored.battle_state_policies["poison"].immune_target_tags == ("immune.poison",)

    legacy = dict(data)
    legacy["version"] = 10
    legacy.pop("battle_state_policies")
    restored_legacy = RpgDatabase.from_data(legacy)
    assert restored_legacy.battle_state_policies == {}


def test_many_custom_states_have_no_engine_cap():
    definitions = [StateDefinition(f"custom.{i}", 2) for i in range(256)]
    actor = subject(states=definitions)
    policies = [BattleStatePolicy(d.state_id) for d in definitions]
    rt = BattleStateRuntime(policies)
    for definition in definitions:
        result = rt.apply(definition.state_id, "source", actor, "target", actor, rng=random.Random(1))
        assert result.applied
    assert len(actor.states.active_states()) == 256


def test_on_expire_is_distinct_from_manual_remove_for_doom_like_rules():
    doom = StateDefinition(
        "doom",
        1,
        on_expire=[Effect("doom_resolve", [EffectOperation("resource_delta", "hp", -99)])],
    )
    a = subject(states=[doom])
    a.states.apply("doom")
    a.states.remove("doom")
    assert a.resources.current("hp") == 100
    a.states.apply("doom")
    a.states.advance("doom", 1)
    assert a.resources.current("hp") == 1


def test_remove_trigger_supports_sleep_wake_style_composition():
    sleep = StateDefinition("sleep", 5)
    actor = subject(states=[sleep])
    actor.states.apply("sleep")
    member = PartyMember("hero", "heroes", actor)
    rt = BattleStateRuntime(
        [BattleStatePolicy("sleep", prevent_action=True, remove_triggers=["rpg.battle.damage_received"])]
    )
    rt.apply_trigger("rpg.battle.damage_received", [member])
    assert actor.states.get("sleep") is None
