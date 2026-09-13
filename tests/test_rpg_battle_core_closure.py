import json

from asteria.core.lifecycle import LifecycleHookBus
from asteria.gameplay import (
    AbilityCost, AbilityDefinition, AbilityEffect, AbilityRegistry, AbilityRuntime,
    AbilityTargetMode, Effect, EffectOperation, EffectOperationKind, GameplaySubject,
    ResourcePool, StateDefinition, StateRegistry, StateRuntime, StatBlock, TagSet,
    TargetingRule, ValueFormula,
)
from asteria.rpg import (
    ActionSequenceDefinition, ActionSequenceStep, ActionTimingDefinition,
    ActionTransactionPolicy, AICondition, AIDecisionRule, BattleAction,
    BattleResourceDefinition, BattleRuntime, BattleSchedulerDefinition,
    BattleStatePolicy, BattleTargetingDefinition, BossPhaseDefinition, CostCommitMode, EnemyAIDefinition,
    GaugeCompositionDefinition, GaugeImpactRule, GaugeThresholdRule,
    InterruptCostPolicy, Party, PartyMember, ReactionDefinition,
)


def subject(*, hp=100, mp=20, speed=10, states=()):
    stats = StatBlock({"speed": speed})
    resources = ResourcePool()
    resources.define("hp", 100, current=hp)
    resources.define("mp", 20, current=mp)
    tags = TagSet()
    registry = StateRegistry(states)
    return GameplaySubject(stats, resources, tags, StateRuntime(registry, stats, resources, tags))


def ability_runtime():
    registry = AbilityRegistry()
    registry.register(AbilityDefinition(
        "hit", targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
        effects=[AbilityEffect(AbilityTargetMode.SELECTED, Effect(
            "hit.effect", [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", -10)]
        ))],
    ))
    registry.register(AbilityDefinition(
        "meteor", targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
        costs=[AbilityCost("mp", ValueFormula.constant(7))],
        effects=[AbilityEffect(AbilityTargetMode.SELECTED, Effect(
            "meteor.effect", [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", -25)]
        ))],
    ))
    registry.register(AbilityDefinition(
        "counter", targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
        effects=[AbilityEffect(AbilityTargetMode.SELECTED, Effect(
            "counter.effect", [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", -4)]
        ))],
    ))
    return AbilityRuntime(registry)


def make_battle(*, hooks=None, states=(), **kwargs):
    hero = PartyMember("hero", "heroes", subject(speed=10, states=states), ability_ids=("hit", "meteor", "counter"), initiative=10)
    enemy = PartyMember("enemy", "enemies", subject(speed=10, states=states), ability_ids=("hit", "meteor", "counter"), initiative=10)
    return BattleRuntime(
        [Party("heroes", [hero]), Party("enemies", [enemy])], ability_runtime(), hooks=hooks,
        scheduler_definition=BattleSchedulerDefinition("ct", mode="continuous", timeline_scale=100),
        **kwargs,
    )


def test_equal_speed_order_is_stable_and_survives_snapshot_restore():
    battle = make_battle()
    first = battle.next_actor().member_id
    snap = battle.snapshot()
    second = battle.next_actor().member_id
    battle.restore_snapshot(snap)
    assert battle.next_actor().member_id == second
    assert first == "enemy"  # member-id tie break is the current deterministic default policy.


def test_break_threshold_can_interrupt_cast_and_refund_through_hook_seam():
    hooks = LifecycleHookBus(); holder = {}
    hooks.subscribe("custom.break", lambda event: holder["battle"].interrupt_action(event.source, force=True))
    broken = StateDefinition("broken", 2)
    composition = GaugeCompositionDefinition(
        "poise",
        impacts=[GaugeImpactRule("pressure", "stagger", "battle.hit", delta=-30)],
        thresholds=[GaugeThresholdRule("zero", "stagger", "at_or_below", 0, state_id="broken", emit_trigger="custom.break")],
    )
    battle = make_battle(
        hooks=hooks, states=(broken,),
        resource_definitions=[BattleResourceDefinition("stagger", minimum=0, maximum=30, start_mode="maximum")],
        state_policies=[BattleStatePolicy("broken")],
        gauge_composition_definitions=[composition],
        action_timing_definitions=[ActionTimingDefinition("meteor", cast_time=5)],
        transaction_policies=[ActionTransactionPolicy("meteor", cost_commit=CostCommitMode.START, interrupt_cost=InterruptCostPolicy.REFUND)],
    )
    holder["battle"] = battle
    battle.submit_action(BattleAction("enemy", "meteor", ("hero",)))
    assert battle.member("enemy").subject.resources.current("mp") == 13
    result = battle.apply_gauge_impact("poise", "hero", "enemy", trigger="battle.hit")
    assert result.thresholds[0].state_applied
    assert battle.action_timing.pending() == ()
    assert battle.member("enemy").subject.resources.current("mp") == 20


def test_multihit_sequence_observes_state_change_on_later_hit():
    hooks = LifecycleHookBus(); holder = {}; before = []
    broken = StateDefinition("broken", 3)
    sequence = ActionSequenceDefinition("triple", steps=[ActionSequenceStep("hit", repeat=3)])
    composition = GaugeCompositionDefinition(
        "stagger",
        impacts=[GaugeImpactRule("hit_pressure", "stagger", "battle.hit", delta=-20)],
        thresholds=[GaugeThresholdRule("break", "stagger", "at_or_below", 0, state_id="broken")],
    )
    def on_before(event):
        if event.data["action"].ability_id == "hit":
            before.append(holder["battle"].member("enemy").subject.states.get("broken") is not None)
    def on_after(event):
        if event.data["result"].action.ability_id == "hit":
            holder["battle"].apply_gauge_impact("stagger", "hero", "enemy", trigger="battle.hit")
    hooks.subscribe("rpg.battle.before_action", on_before)
    hooks.subscribe("rpg.battle.after_action", on_after)
    battle = make_battle(
        hooks=hooks, states=(broken,),
        resource_definitions=[BattleResourceDefinition("stagger", minimum=0, maximum=30, start_mode="maximum")],
        state_policies=[BattleStatePolicy("broken")],
        gauge_composition_definitions=[composition], action_sequence_definitions=[sequence],
    )
    holder["battle"] = battle
    _, results, failures = battle.execute_sequence("triple", ("hero",), ("enemy",))
    assert len(results) == 3 and not failures
    assert before == [False, False, True]


def test_ko_mid_sequence_uses_authored_sequence_failure_policy_without_crashing():
    hooks = LifecycleHookBus(); holder = {}; count = {"n": 0}
    sequence = ActionSequenceDefinition("triple", steps=[ActionSequenceStep("hit", repeat=3)], interruption_policy="cancel_remaining")
    def after(event):
        if event.data["result"].action.ability_id == "hit":
            count["n"] += 1
            if count["n"] == 1:
                holder["battle"].incapacitate("enemy")
    hooks.subscribe("rpg.battle.after_action", after)
    battle = make_battle(hooks=hooks, action_sequence_definitions=[sequence], targeting_definitions=[BattleTargetingDefinition("hit")])
    holder["battle"] = battle
    _, results, failures = battle.execute_sequence("triple", ("hero",), ("enemy",))
    assert len(results) == 1
    assert len(failures) == 1


def test_reaction_chain_and_rng_replay_are_identical_after_snapshot_restore():
    reaction = ReactionDefinition(
        "counter", "rpg.battle.after_action", "event_targets",
        target_selector="event_source", ability_id="counter", max_per_chain=1,
    )
    battle = make_battle(reaction_definitions=[reaction], rng_seed=77)
    snap = battle.snapshot()
    _, first = battle.execute_with_reactions(BattleAction("hero", "hit", ("enemy",)))
    state1 = (battle.member("hero").subject.resources.current("hp"), battle.member("enemy").subject.resources.current("hp"), [x.reaction_id for x in first.requests], battle.rng.random())
    battle.restore_snapshot(snap)
    _, second = battle.execute_with_reactions(BattleAction("hero", "hit", ("enemy",)))
    state2 = (battle.member("hero").subject.resources.current("hp"), battle.member("enemy").subject.resources.current("hp"), [x.reaction_id for x in second.requests], battle.rng.random())
    assert state1 == state2


def test_boss_phase_can_change_between_hits_via_normal_ai_hook_points():
    hooks = LifecycleHookBus(); holder = {}; phases = []
    phase1 = BossPhaseDefinition("p1", conditions=[AICondition("resource_ratio", params={"resource_id": "hp", "op": ">", "value": .8})], priority=10, decision_rule_ids=("poke",))
    phase2 = BossPhaseDefinition("p2", conditions=[AICondition("resource_ratio", params={"resource_id": "hp", "op": "<=", "value": .8})], priority=20, decision_rule_ids=("poke",), enter_hook="custom.phase2")
    ai = EnemyAIDefinition("boss", rules=[AIDecisionRule("poke", "ability", payload={"ability_id": "hit"})], phases=[phase1, phase2], initial_phase_id="p1")
    hooks.subscribe("custom.phase2", lambda event: phases.append(event.data["phase_id"]))
    battle = make_battle(hooks=hooks, enemy_ai_definitions=[ai])
    # Author/project decides when phase reevaluation happens; engine supplies stable AI and hook seams.
    battle.execute(BattleAction("hero", "meteor", ("enemy",)))
    decision = battle.enemy_ai.decide(battle, "boss", "enemy", rng=battle.rng)
    assert decision.phase_id == "p2"
    assert phases == ["p2"]


def test_snapshot_payload_remains_json_serializable_after_cross_system_activity():
    battle = make_battle(rng_seed=9)
    battle.execute(BattleAction("hero", "hit", ("enemy",)))
    raw = json.loads(json.dumps(battle.snapshot().to_data()))
    assert raw["schema"] == "asteria.rpg.battle_snapshot"
