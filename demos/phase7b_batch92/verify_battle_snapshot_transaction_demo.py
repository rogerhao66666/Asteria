from asteria.gameplay import (
    AbilityCost, AbilityDefinition, AbilityEffect, AbilityRegistry, AbilityRuntime,
    AbilityTargetMode, Effect, EffectOperation, EffectOperationKind, GameplaySubject,
    ResourcePool, StatBlock, TagSet, TargetingRule, ValueFormula,
)
from asteria.rpg import (
    ActionTimingDefinition, ActionTransactionPolicy, BattleAction, BattleRuntime,
    BattleSchedulerDefinition, CostCommitMode, InterruptCostPolicy, Party, PartyMember,
)


def subject(speed):
    resources = ResourcePool(); resources.define("hp", 100); resources.define("mp", 20)
    return GameplaySubject(StatBlock({"speed": speed}), resources, TagSet())

reg = AbilityRegistry([AbilityDefinition(
    "meteor", targeting=TargetingRule(minimum_targets=1, maximum_targets=1),
    costs=[AbilityCost("mp", ValueFormula.constant(7))],
    effects=[AbilityEffect(AbilityTargetMode.SELECTED, Effect(
        "meteor", [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", -25)]
    ))],
)])
hero = PartyMember("hero", "heroes", subject(100), ability_ids=("meteor",), initiative=100)
enemy = PartyMember("enemy", "enemies", subject(20), ability_ids=("meteor",), initiative=20)
battle = BattleRuntime(
    [Party("heroes", [hero]), Party("enemies", [enemy])], AbilityRuntime(reg),
    scheduler_definition=BattleSchedulerDefinition("ct", mode="continuous", timeline_scale=100),
    action_timing_definitions=[ActionTimingDefinition("meteor", cast_time=5)],
    transaction_policies=[ActionTransactionPolicy(
        "meteor", cost_commit=CostCommitMode.START,
        interrupt_cost=InterruptCostPolicy.REFUND,
    )],
    rng_seed=92,
)
battle.next_actor()
pending = battle.submit_action(BattleAction("hero", "meteor", ("enemy",)))
assert hero.subject.resources.current("mp") == 13
checkpoint = battle.snapshot()
rolls = [battle.rng.random() for _ in range(4)]
battle.resolve_due_actions(pending.resolve_at)
assert enemy.subject.resources.current("hp") == 75
battle.restore_snapshot(checkpoint)
assert battle.member("enemy").subject.resources.current("hp") == 100
assert [battle.rng.random() for _ in range(4)] == rolls
assert battle.interrupt_action("hero", force=True).interrupted
assert battle.member("hero").subject.resources.current("mp") == 20
print("Batch 92 deterministic snapshot + transaction demo: PASS")
