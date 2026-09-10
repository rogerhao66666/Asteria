from asteria.gameplay import (
    Effect,
    EffectOperation,
    PeriodicEffect,
    ResourcePool,
    StackingPolicy,
    StatBlock,
    StateDefinition,
    StateRegistry,
    StateRuntime,
    StatModifier,
    TagSet,
)


def runtime(definitions):
    stats = StatBlock({"power": 10})
    resources = ResourcePool()
    resources.define("hp", 100, current=100)
    tags = TagSet(["actor"])
    registry = StateRegistry(definitions)
    return StateRuntime(registry, stats, resources, tags)


def test_refresh_policy_does_not_add_stack():
    definition = StateDefinition("haste", 5, stacking="refresh")
    rt = runtime([definition])
    rt.apply("haste")
    rt.update(2)
    rt.apply("haste")
    active = rt.get("haste")
    assert active.stacks == 1
    assert active.remaining == 5


def test_stack_policy_caps_and_stacks_modifiers():
    definition = StateDefinition(
        "rage",
        10,
        stacking=StackingPolicy.STACK,
        max_stacks=3,
        modifiers=[StatModifier("rage_power", "power", "add", 2)],
    )
    rt = runtime([definition])
    rt.apply("rage")
    rt.apply("rage")
    rt.apply("rage")
    rt.apply("rage")
    assert rt.get("rage").stacks == 3
    assert rt.modifiers().evaluate("power", 10, tags=rt.tags) == 16


def test_periodic_effect_ticks_and_expires():
    damage = Effect("dot", [EffectOperation("resource_delta", "hp", -10)])
    definition = StateDefinition(
        "burning",
        2.5,
        periodic=[PeriodicEffect(1.0, damage)],
    )
    rt = runtime([definition])
    rt.apply("burning")

    assert rt.update(0.5) == ()
    assert rt.resources.current("hp") == 100
    assert rt.update(0.6) == ()
    assert rt.resources.current("hp") == 90
    assert rt.update(1.0) == ()
    assert rt.resources.current("hp") == 80
    assert rt.update(0.4) == ("burning",)
    assert rt.get("burning") is None


def test_stack_periodic_effect_scales_with_stacks():
    damage = Effect("dot", [EffectOperation("resource_delta", "hp", -5)])
    definition = StateDefinition(
        "poison",
        5,
        stacking="stack",
        max_stacks=3,
        periodic=[PeriodicEffect(1.0, damage)],
    )
    rt = runtime([definition])
    rt.apply("poison")
    rt.apply("poison")
    rt.update(1)
    assert rt.resources.current("hp") == 90


def test_on_apply_and_on_remove_effects():
    apply_fx = Effect("apply", [EffectOperation("tag_add", "state.shielded")])
    remove_fx = Effect("remove", [EffectOperation("tag_remove", "state.shielded")])
    definition = StateDefinition(
        "shield",
        1,
        on_apply=[apply_fx],
        on_remove=[remove_fx],
    )
    rt = runtime([definition])
    rt.apply("shield")
    assert rt.tags.contains("state.shielded")
    rt.update(1)
    assert not rt.tags.contains("state.shielded")


def test_replace_policy_resets_state():
    definition = StateDefinition("focus", 5, stacking="replace")
    rt = runtime([definition])
    first = rt.apply("focus")
    rt.update(3)
    second = rt.apply("focus")
    assert second is not first
    assert second.remaining == 5
    assert second.stacks == 1


def test_snapshot_restore_preserves_periodic_progress():
    damage = Effect("dot", [EffectOperation("resource_delta", "hp", -10)])
    definition = StateDefinition(
        "burn",
        10,
        periodic=[PeriodicEffect(2.0, damage)],
    )
    rt = runtime([definition])
    rt.apply("burn")
    rt.update(1.5)
    snap = rt.snapshot()

    restored = runtime([definition])
    restored.restore(snap)
    restored.update(0.5)
    assert restored.resources.current("hp") == 90
    assert restored.get("burn").remaining == 8.0


def test_state_definition_roundtrip():
    definition = StateDefinition(
        "blessing",
        8,
        modifiers=[StatModifier("power", "power", "multiply", 1.2)],
        on_apply=[Effect("apply", [EffectOperation("tag_add", "buffed")])],
        periodic=[
            PeriodicEffect(
                2,
                Effect("regen", [EffectOperation("resource_delta", "hp", 3)]),
            )
        ],
        on_remove=[Effect("remove", [EffectOperation("tag_remove", "buffed")])],
    )
    restored = StateDefinition.from_data(definition.to_data())
    assert restored == definition


def test_state_names_are_not_hardcoded_gameplay_rules():
    definition = StateDefinition(
        "machine.overheated",
        3,
        modifiers=[StatModifier("speed_penalty", "movement_rate", "multiply", 0.5)],
    )
    rt = runtime([definition])
    rt.apply("machine.overheated")
    assert rt.modifiers().evaluate("movement_rate", 20, tags=rt.tags) == 10
