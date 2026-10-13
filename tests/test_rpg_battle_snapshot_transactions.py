import json

from asteria.gameplay import (
    AbilityCost,
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
    ValueFormula,
)
from asteria.rpg import (
    ActionTimingDefinition,
    ActionTransactionPolicy,
    BattleAction,
    BattleRuntime,
    BattleSchedulerDefinition,
    BattleSnapshot,
    CostCommitMode,
    InterruptCostPolicy,
    Party,
    PartyMember,
)


def subject(hp=100, mp=20, speed=10):
    r = ResourcePool()
    r.define("hp", 100, current=hp)
    r.define("mp", 20, current=mp)
    return GameplaySubject(StatBlock({"speed": speed}), r, TagSet())


def runtime():
    reg = AbilityRegistry()
    reg.register(
        AbilityDefinition(
            "meteor",
            targeting=TargetingRule(minimum_targets=1, maximum_targets=1),
            costs=[AbilityCost("mp", ValueFormula.constant(7))],
            effects=[
                AbilityEffect(
                    AbilityTargetMode.SELECTED,
                    Effect(
                        "meteor", [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", -25)]
                    ),
                )
            ],
        )
    )
    return AbilityRuntime(reg)


def battle(*, policy=None, seed=123):
    hero = PartyMember(
        "hero", "heroes", subject(speed=100), ability_ids=("meteor",), initiative=100
    )
    enemy = PartyMember(
        "enemy", "enemies", subject(speed=20), ability_ids=("meteor",), initiative=20
    )
    return BattleRuntime(
        [Party("heroes", [hero]), Party("enemies", [enemy])],
        runtime(),
        scheduler_definition=BattleSchedulerDefinition(
            "ct", mode="continuous", timeline_scale=100
        ),
        action_timing_definitions=[ActionTimingDefinition("meteor", cast_time=5)],
        transaction_policies=[] if policy is None else [policy],
        rng_seed=seed,
    )


def test_snapshot_is_json_serializable_and_roundtrips_mutable_battle_state():
    b = battle()
    b.next_actor()
    b.submit_action(BattleAction("hero", "meteor", ("enemy",)))
    b.set_objective_flag("door_open", True)
    snap = b.snapshot()
    raw = json.loads(json.dumps(snap.to_data()))
    assert BattleSnapshot.from_data(raw).to_data()["objective_flags"] == {"door_open": True}
    b.member("hero").subject.resources.change("hp", -90)
    b.action_timing.cancel("hero")
    b.restore_snapshot(raw)
    assert b.member("hero").subject.resources.current("hp") == 100
    assert b.action_timing.next_pending().ability_id == "meteor"
    assert b.objectives.flags["door_open"] is True


def test_snapshot_restore_replays_internal_rng_identically():
    b = battle(seed=77)
    snap = b.snapshot()
    first = [b.rng.random() for _ in range(8)]
    b.restore_snapshot(snap)
    second = [b.rng.random() for _ in range(8)]
    assert first == second


def test_start_commit_pays_once_not_twice():
    policy = ActionTransactionPolicy("meteor", cost_commit=CostCommitMode.START)
    b = battle(policy=policy)
    b.next_actor()
    pending = b.submit_action(BattleAction("hero", "meteor", ("enemy",)))
    assert b.member("hero").subject.resources.current("mp") == 13
    b.resolve_due_actions(pending.resolve_at)
    assert b.member("hero").subject.resources.current("mp") == 13
    assert b.member("enemy").subject.resources.current("hp") == 75


def test_interrupt_refund_policy_refunds_start_cost():
    policy = ActionTransactionPolicy(
        "meteor",
        cost_commit=CostCommitMode.START,
        interrupt_cost=InterruptCostPolicy.REFUND,
    )
    b = battle(policy=policy)
    b.next_actor()
    b.submit_action(BattleAction("hero", "meteor", ("enemy",)))
    assert b.member("hero").subject.resources.current("mp") == 13
    assert b.interrupt_action("hero", force=True).interrupted
    assert b.member("hero").subject.resources.current("mp") == 20


def test_interrupt_keep_policy_keeps_start_cost():
    policy = ActionTransactionPolicy(
        "meteor",
        cost_commit=CostCommitMode.START,
        interrupt_cost=InterruptCostPolicy.KEEP,
    )
    b = battle(policy=policy)
    b.next_actor()
    b.submit_action(BattleAction("hero", "meteor", ("enemy",)))
    b.interrupt_action("hero", force=True)
    assert b.member("hero").subject.resources.current("mp") == 13


def test_transaction_reservation_survives_snapshot_restore():
    policy = ActionTransactionPolicy(
        "meteor",
        cost_commit=CostCommitMode.START,
        interrupt_cost=InterruptCostPolicy.REFUND,
    )
    b = battle(policy=policy)
    b.next_actor()
    pending = b.submit_action(BattleAction("hero", "meteor", ("enemy",)))
    snap = b.snapshot()
    b.resolve_due_actions(pending.resolve_at)
    assert b.member("enemy").subject.resources.current("hp") == 75
    b.restore_snapshot(snap)
    assert b.member("enemy").subject.resources.current("hp") == 100
    assert b.member("hero").subject.resources.current("mp") == 13
    b.interrupt_action("hero", force=True)
    assert b.member("hero").subject.resources.current("mp") == 20


def test_snapshot_restores_summoned_combatant_topology():
    b = battle()
    summon = PartyMember(
        "sprite", "heroes", subject(hp=40, speed=30), ability_ids=("meteor",), initiative=30
    )
    b.summon(summon, owner_id="hero")
    snap = b.snapshot()
    b.remove_combatant("sprite")
    # Rebuild a compatible battle without the summon, then restore the checkpoint.
    fresh = battle()
    fresh.restore_snapshot(snap)
    assert "sprite" in fresh.members
    assert fresh.combatants.state("sprite").summon_owner_id == "hero"
    assert fresh.member("sprite").subject.resources.current("hp") == 40


def test_snapshot_restores_transform_stack_and_revert_capability():
    b = battle()
    transformed = PartyMember(
        "hero", "heroes", subject(hp=80, mp=11, speed=150), ability_ids=("meteor",), initiative=150
    )
    b.transform("hero", transformed, form_id="dragon")
    snap = b.snapshot()
    fresh = battle()
    fresh.restore_snapshot(snap)
    assert fresh.combatants.state("hero").form_id == "dragon"
    assert fresh.member("hero").initiative == 150
    fresh.revert_transform("hero")
    assert fresh.member("hero").initiative == 100


def test_database_v20_persists_transaction_policy_and_v19_is_backward_readable():
    from asteria.rpg import RpgDatabase

    db = RpgDatabase()
    db.add_action_transaction(
        ActionTransactionPolicy(
            "meteor",
            cost_commit=CostCommitMode.START,
            interrupt_cost=InterruptCostPolicy.REFUND,
        )
    )
    raw = db.to_data()
    assert raw["version"] == 30
    restored = RpgDatabase.from_data(raw)
    assert restored.action_transactions["meteor"].interrupt_cost == InterruptCostPolicy.REFUND
    old = json.loads(json.dumps(raw))
    old["version"] = 19
    old.pop("action_transactions")
    assert RpgDatabase.from_data(old).action_transactions == {}
