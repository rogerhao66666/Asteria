import pytest

from asteria.gameplay import (
    AbilityDefinition,
    AbilityEffect,
    AbilityRegistry,
    AbilityRuntime,
    AbilityTargetMode,
    Effect,
    EffectOperation,
    EffectOperationKind,
    GameplaySubject,
    ResourcePool,
    StatBlock,
    TagSet,
    TargetingRule,
)
from asteria.rpg import (
    ActionTimingDefinition,
    BattleAction,
    BattleActionTimingRuntime,
    BattleRuntime,
    BattleScheduler,
    BattleSchedulerDefinition,
    Party,
    PartyMember,
    RpgDatabase,
)


def subject(hp=100):
    resources = ResourcePool()
    resources.define("hp", 100, current=hp)
    return GameplaySubject(StatBlock(), resources, TagSet())


def ability_runtime():
    registry = AbilityRegistry()
    for aid, damage in (("quick", 5), ("meteor", 25), ("heavy", 15)):
        registry.register(
            AbilityDefinition(
                aid,
                targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
                effects=[
                    AbilityEffect(
                        AbilityTargetMode.SELECTED,
                        Effect(aid, [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", -damage)]),
                    )
                ],
            )
        )
    return AbilityRuntime(registry)


def make_battle(timings=()):
    hero = PartyMember("hero", "heroes", subject(), ability_ids=("quick", "meteor", "heavy"), initiative=100)
    enemy = PartyMember("enemy", "enemies", subject(), ability_ids=("quick",), initiative=20)
    return BattleRuntime(
        [Party("heroes", [hero]), Party("enemies", [enemy])],
        ability_runtime(),
        scheduler_definition=BattleSchedulerDefinition("ct", mode="continuous", timeline_scale=100),
        action_timing_definitions=timings,
    )


def test_timing_definition_roundtrip_and_windup():
    d = ActionTimingDefinition("meteor", startup=1, cast_time=4, recovery=3, priority=9, interrupt_threshold=2)
    assert d.windup == 5
    assert ActionTimingDefinition.from_data(d.to_data()) == d


def test_pending_queue_orders_same_time_by_priority_then_sequence():
    rt = BattleActionTimingRuntime(
        [
            ActionTimingDefinition("a", cast_time=5, priority=1),
            ActionTimingDefinition("b", cast_time=5, priority=10),
        ]
    )
    rt.begin(BattleAction("x", "a", ("z",)), current_time=0)
    rt.begin(BattleAction("y", "b", ("z",)), current_time=0)
    assert [x.ability_id for x in rt.pending()] == ["b", "a"]


def test_interrupt_respects_interruptible_and_threshold():
    rt = BattleActionTimingRuntime([ActionTimingDefinition("cast", cast_time=5, interrupt_threshold=10)])
    rt.begin(BattleAction("hero", "cast", ("enemy",)), current_time=0)
    assert not rt.interrupt("hero", power=9).interrupted
    assert rt.interrupt("hero", power=10).interrupted
    assert rt.pending() == ()


def test_uninterruptible_action_requires_force():
    rt = BattleActionTimingRuntime([ActionTimingDefinition("cast", cast_time=5, interruptible=False)])
    rt.begin(BattleAction("hero", "cast", ("enemy",)), current_time=0)
    assert rt.interrupt("hero", power=999).reason == "not_interruptible"
    assert rt.interrupt("hero", force=True).interrupted


def test_shift_pending_cast_clamps_to_start_time():
    rt = BattleActionTimingRuntime([ActionTimingDefinition("cast", cast_time=5)])
    rt.begin(BattleAction("hero", "cast", ("enemy",)), current_time=10)
    changed = rt.shift("hero", -999)
    assert changed[0].resolve_at == 10


def test_continuous_scheduler_timeline_shift_delay_and_advance():
    members = [PartyMember("hero", "h", subject(), initiative=100)]
    s = BattleScheduler(members, BattleSchedulerDefinition("ct", mode="continuous", timeline_scale=100))
    assert s.peek().ready_time == 1
    s.shift_member("hero", 4)
    assert s.peek().ready_time == 5
    s.shift_member("hero", -99)
    assert s.peek().ready_time == s.current_time


def test_submit_cast_delays_resolution_and_next_readiness():
    battle = make_battle([ActionTimingDefinition("meteor", startup=1, cast_time=4, recovery=3)])
    assert battle.next_actor().member_id == "hero"
    pending = battle.submit_action(BattleAction("hero", "meteor", ("enemy",)))
    assert pending.resolve_at == pytest.approx(6.0)  # hero became ready at t=1; 5 windup
    assert battle.member("enemy").subject.resources.current("hp") == 100
    hero_next = next(x for x in battle.scheduler.pending() if x.member_id == "hero")
    # Base next interval is 1, plus 5 windup + 3 recovery.
    assert hero_next.ready_time == pytest.approx(10.0)
    battle.resolve_due_actions(6.0)
    assert battle.member("enemy").subject.resources.current("hp") == 75


def test_immediate_action_resolves_now_and_recovery_delays_next_turn():
    battle = make_battle([ActionTimingDefinition("quick", recovery=2)])
    assert battle.next_actor().member_id == "hero"
    result = battle.submit_action(BattleAction("hero", "quick", ("enemy",)))
    assert result.execution_result.executed
    assert battle.member("enemy").subject.resources.current("hp") == 95
    hero_next = next(x for x in battle.scheduler.pending() if x.member_id == "hero")
    assert hero_next.ready_time == pytest.approx(4.0)  # ready t=1 + base 1 + recovery 2


def test_interrupting_cast_prevents_effect_resolution():
    battle = make_battle([ActionTimingDefinition("meteor", cast_time=5, interrupt_threshold=3)])
    battle.next_actor()
    battle.submit_action(BattleAction("hero", "meteor", ("enemy",)))
    assert battle.interrupt_action("hero", power=3).interrupted
    battle.resolve_due_actions(100)
    assert battle.member("enemy").subject.resources.current("hp") == 100


def test_shift_timeline_moves_both_actor_readiness_and_cast_resolution():
    battle = make_battle([ActionTimingDefinition("meteor", cast_time=5)])
    battle.next_actor()
    pending = battle.submit_action(BattleAction("hero", "meteor", ("enemy",)))
    old_ready = next(x.ready_time for x in battle.scheduler.pending() if x.member_id == "hero")
    battle.shift_timeline("hero", 2)
    assert battle.action_timing.next_pending().resolve_at == pending.resolve_at + 2
    assert next(x.ready_time for x in battle.scheduler.pending() if x.member_id == "hero") == old_ready + 2


def test_timing_runtime_snapshot_restores_pending_order():
    rt = BattleActionTimingRuntime([ActionTimingDefinition("cast", cast_time=3, priority=2)])
    rt.begin(BattleAction("hero", "cast", ("enemy",)), current_time=4)
    restored = BattleActionTimingRuntime.from_data(rt.to_data())
    assert restored.pending() == rt.pending()


def test_database_v15_owns_action_timings_and_v14_backward_read():
    db = RpgDatabase()
    db.add_action_timing(ActionTimingDefinition("meteor", cast_time=5))
    data = db.to_data()
    assert data["version"] == 30
    restored = RpgDatabase.from_data(data)
    assert restored.action_timings["meteor"].cast_time == 5
    old = RpgDatabase().to_data()
    old["version"] = 14
    old.pop("action_timings")
    restored_old = RpgDatabase.from_data(old)
    assert restored_old.action_timings == {}
