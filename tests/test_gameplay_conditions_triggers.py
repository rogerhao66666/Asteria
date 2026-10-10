from asteria.gameplay import (
    ConditionGroup,
    Effect,
    EffectOperation,
    GameplayConditionContext,
    GameplaySubject,
    GameplayTrigger,
    NumericCondition,
    ResourcePool,
    StatBlock,
    StateCondition,
    StateDefinition,
    StateRegistry,
    StateRuntime,
    TagCondition,
    TagSet,
    TriggerRuntime,
    deserialize_condition,
    serialize_condition,
)


def subject(*, stats=None, resources=None, tags=(), states=None):
    pool = ResourcePool()
    for name, pair in (resources or {}).items():
        pool.define(name, pair[1], current=pair[0])
    return GameplaySubject(
        StatBlock(stats or {}),
        pool,
        TagSet(tags),
        states,
    )


def test_numeric_condition_supports_stat_and_resource_ratio():
    source = subject(
        stats={"power": 12},
        resources={"hp": (20, 100)},
    )
    ctx = GameplayConditionContext(source)

    assert NumericCondition("source", "stat", "power", ">=", 10).evaluate(ctx)
    assert NumericCondition("source", "resource_ratio", "hp", "<", 0.5).evaluate(ctx)


def test_tag_conditions_can_target_source_or_target():
    ctx = GameplayConditionContext(
        subject(tags=["stance.rage"]),
        subject(tags=["enemy.boss"]),
    )
    assert TagCondition("source", "stance.rage").evaluate(ctx)
    assert TagCondition("target", "enemy.boss").evaluate(ctx)
    assert TagCondition("target", "immune.fire", present=False).evaluate(ctx)


def test_state_condition_reads_state_runtime():
    reg = StateRegistry([StateDefinition("poison", 5, stacking="stack", max_stacks=3)])
    src = subject()
    runtime = StateRuntime(reg, src.stats, src.resources, src.tags)
    runtime.apply("poison")
    runtime.apply("poison")
    src = GameplaySubject(src.stats, src.resources, src.tags, runtime)

    ctx = GameplayConditionContext(src)
    assert StateCondition("source", "poison", minimum_stacks=2).evaluate(ctx)
    assert not StateCondition("source", "poison", minimum_stacks=3).evaluate(ctx)


def test_condition_groups_all_any_none():
    ctx = GameplayConditionContext(subject(stats={"power": 10}, tags=["ready"]))
    a = NumericCondition("source", "stat", "power", ">=", 10)
    b = TagCondition("source", "ready")
    c = TagCondition("source", "missing")

    assert ConditionGroup([a, b], mode="all").evaluate(ctx)
    assert ConditionGroup([c, b], mode="any").evaluate(ctx)
    assert ConditionGroup([c], mode="none").evaluate(ctx)


def test_condition_roundtrip_nested():
    condition = ConditionGroup(
        [
            NumericCondition("source", "stat", "speed", ">", 5),
            ConditionGroup(
                [
                    TagCondition("target", "enemy"),
                    TagCondition("target", "immune", present=False),
                ],
                mode="all",
            ),
        ],
        mode="all",
    )

    restored = deserialize_condition(serialize_condition(condition))
    assert restored == condition


def test_trigger_dispatches_effect_when_condition_matches():
    src = subject(resources={"hp": (20, 100)}, tags=["actor.player"])
    target = subject(resources={"hp": (100, 100)}, tags=["enemy"])
    ctx = GameplayConditionContext(src, target)

    trigger = GameplayTrigger(
        "desperation_hit",
        "on_hit",
        conditions=NumericCondition("source", "resource_ratio", "hp", "<=", 0.25),
        effects=[Effect("bonus_damage", [EffectOperation("resource_delta", "hp", -30)])],
    )

    results = TriggerRuntime([trigger]).dispatch("on_hit", ctx)

    assert results[0].fired
    assert target.resources.current("hp") == 70


def test_trigger_does_not_fire_when_condition_fails():
    src = subject(resources={"hp": (80, 100)})
    target = subject(resources={"hp": (100, 100)})
    ctx = GameplayConditionContext(src, target)

    trigger = GameplayTrigger(
        "desperation_hit",
        "on_hit",
        conditions=NumericCondition("source", "resource_ratio", "hp", "<=", 0.25),
        effects=[Effect("bonus_damage", [EffectOperation("resource_delta", "hp", -30)])],
    )

    results = TriggerRuntime([trigger]).dispatch("on_hit", ctx)

    assert not results[0].fired
    assert target.resources.current("hp") == 100


def test_trigger_can_apply_to_explicit_effect_target():
    src = subject(resources={"hp": (50, 100)})
    target = subject(resources={"hp": (50, 100)})
    ctx = GameplayConditionContext(src, target)

    trigger = GameplayTrigger(
        "lifesteal",
        "on_hit",
        effects=[Effect("heal_source", [EffectOperation("resource_delta", "hp", 10)])],
    )

    TriggerRuntime([trigger]).dispatch(
        "on_hit",
        ctx,
        effect_target=src,
    )

    assert src.resources.current("hp") == 60
    assert target.resources.current("hp") == 50


def test_trigger_roundtrip():
    trigger = GameplayTrigger(
        "boss_execute",
        "on_hit",
        conditions=ConditionGroup(
            [
                TagCondition("target", "enemy.boss"),
                NumericCondition("target", "resource_ratio", "hp", "<", 0.2),
            ]
        ),
        effects=[Effect("execute", [EffectOperation("resource_set", "hp", 0)])],
    )

    restored = GameplayTrigger.from_data(trigger.to_data())
    assert restored == trigger
