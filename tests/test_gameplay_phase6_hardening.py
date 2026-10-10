from asteria.gameplay import (
    AbilityDefinition,
    AbilityEffect,
    AbilityRegistry,
    AbilityRuntime,
    AbilityTarget,
    Effect,
    EffectOperation,
    FormulaBuilder,
    GameplayConditionContext,
    GameplaySubject,
    GameplayTrigger,
    ResourcePool,
    StatBlock,
    StateDefinition,
    StateRegistry,
    StateRuntime,
    TagSet,
    TriggerRuntime,
)


def make_subject(*, hp=100, attack=20, defense=10, tags=()):
    resources = ResourcePool()
    resources.define("hp", 100, current=hp)
    return GameplaySubject(
        StatBlock({"attack": attack, "defense": defense}),
        resources,
        TagSet(tags),
        None,
    )


def test_stack_on_apply_runs_once_per_application_not_once_per_existing_stack():
    resources = ResourcePool()
    resources.define("hp", 100, current=50)
    registry = StateRegistry(
        [
            StateDefinition(
                "stacking_regen",
                10,
                stacking="stack",
                max_stacks=3,
                on_apply=[Effect("apply_heal", [EffectOperation("resource_delta", "hp", 5)])],
            )
        ]
    )
    runtime = StateRuntime(registry, StatBlock(), resources, TagSet())
    runtime.apply("stacking_regen")
    assert resources.current("hp") == 55
    runtime.apply("stacking_regen")
    assert resources.current("hp") == 60
    runtime.apply("stacking_regen")
    assert resources.current("hp") == 65


def test_periodic_effect_does_not_tick_after_expiry_when_large_dt_crosses_boundary():
    resources = ResourcePool()
    resources.define("hp", 100, current=100)
    registry = StateRegistry(
        [
            StateDefinition(
                "short_dot",
                2.5,
                periodic=[
                    __import__("asteria.gameplay", fromlist=["PeriodicEffect"]).PeriodicEffect(
                        1.0,
                        Effect("dot", [EffectOperation("resource_delta", "hp", -10)]),
                    )
                ],
            )
        ]
    )
    runtime = StateRuntime(registry, StatBlock(), resources, TagSet())
    runtime.apply("short_dot")
    runtime.update(10.0)
    # Ticks at 1s and 2s only; 3s+ are beyond expiry.
    assert resources.current("hp") == 80
    assert runtime.get("short_dot") is None


def test_trigger_accepts_project_defined_event_key_and_roundtrips():
    trigger = GameplayTrigger(
        "reactor_alarm",
        "reactor.temperature.crossed",
        effects=[Effect("flag", [EffectOperation("tag_add", "alarm.hot")])],
    )
    restored = GameplayTrigger.from_data(trigger.to_data())
    assert restored.event == "reactor.temperature.crossed"

    subject = make_subject()
    context = GameplayConditionContext(subject, None)
    result = TriggerRuntime([restored]).dispatch("reactor.temperature.crossed", context)
    assert result[0].fired
    assert subject.tags.contains("alarm.hot")


def test_formula_driven_effect_value_roundtrip():
    formula = FormulaBuilder().source_stat("attack", 1.0).target_stat("defense", -0.5).build()
    effect = Effect("scaled_damage", [EffectOperation("resource_delta", "hp", formula)])
    assert Effect.from_data(effect.to_data()) == effect


def test_ability_can_apply_formula_driven_damage():
    source = AbilityTarget("hero", make_subject(attack=30, tags=["actor.player"]))
    target = AbilityTarget("enemy", make_subject(defense=10, tags=["enemy"]))
    formula = FormulaBuilder().source_stat("attack", -1.0).target_stat("defense", 0.5).build()
    ability = AbilityDefinition(
        "scaled_strike",
        effects=[
            AbilityEffect(
                "selected",
                Effect("scaled_damage", [EffectOperation("resource_delta", "hp", formula)]),
            )
        ],
    )
    result = AbilityRuntime(AbilityRegistry([ability])).execute("scaled_strike", source, [target])
    assert result.executed
    # -30 + 5 = -25 resource delta
    assert target.subject.resources.current("hp") == 75


def test_formula_effect_uses_each_selected_target_context():
    source = AbilityTarget("hero", make_subject(attack=30))
    weak = AbilityTarget("weak", make_subject(defense=0))
    armored = AbilityTarget("armored", make_subject(defense=20))
    formula = FormulaBuilder().source_stat("attack", -1.0).target_stat("defense", 0.5).build()
    from asteria.gameplay import TargetingRule

    ability = AbilityDefinition(
        "cleave",
        targeting=TargetingRule(minimum_targets=1, maximum_targets=2),
        effects=[
            AbilityEffect(
                "selected",
                Effect("scaled", [EffectOperation("resource_delta", "hp", formula)]),
            )
        ],
    )
    AbilityRuntime(AbilityRegistry([ability])).execute("cleave", source, [weak, armored])
    assert weak.subject.resources.current("hp") == 70
    assert armored.subject.resources.current("hp") == 80


def test_formula_effect_without_context_fails_before_mutating():
    from asteria.gameplay import apply_effect

    subject = make_subject()
    formula = FormulaBuilder().source_stat("attack", -1).build()
    effect = Effect("needs_context", [EffectOperation("resource_delta", "hp", formula)])
    try:
        apply_effect(effect, subject.stats, subject.resources, subject.tags)
    except ValueError as exc:
        assert "formula_context" in str(exc)
    else:
        raise AssertionError("expected formula context failure")
    assert subject.resources.current("hp") == 100
