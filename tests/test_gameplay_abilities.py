from asteria.gameplay import (
    AbilityCost,
    AbilityDefinition,
    AbilityEffect,
    AbilityRegistry,
    AbilityRuntime,
    AbilityTarget,
    Effect,
    EffectOperation,
    GameplaySubject,
    NumericCondition,
    ResourcePool,
    StatBlock,
    TagSet,
    TargetingRule,
    ValueFormula,
)


def make_subject(*, stats=None, resources=None, tags=()):
    pool = ResourcePool()
    for name, pair in (resources or {}).items():
        pool.define(name, pair[1], current=pair[0])
    return GameplaySubject(
        StatBlock(stats or {}),
        pool,
        TagSet(tags),
        None,
    )


def test_single_target_ability_spends_cost_and_applies_effect():
    src = AbilityTarget(
        "hero",
        make_subject(
            resources={"mp": (20, 20)},
            tags=["actor.player"],
        ),
    )
    tgt = AbilityTarget(
        "slime",
        make_subject(
            resources={"hp": (50, 50)},
            tags=["enemy"],
        ),
    )

    ability = AbilityDefinition(
        "spark",
        targeting=TargetingRule(required_tags=["enemy"]),
        costs=[AbilityCost("mp", 5)],
        effects=[
            AbilityEffect(
                "selected",
                Effect("damage", [EffectOperation("resource_delta", "hp", -12)]),
            )
        ],
    )

    result = AbilityRuntime(AbilityRegistry([ability])).execute("spark", src, [tgt])

    assert result.executed
    assert src.subject.resources.current("mp") == 15
    assert tgt.subject.resources.current("hp") == 38


def test_self_effect_and_selected_effect_can_coexist():
    src = AbilityTarget(
        "hero", make_subject(resources={"hp": (40, 100), "mp": (20, 20)})
    )
    tgt = AbilityTarget("enemy", make_subject(resources={"hp": (100, 100)}))

    ability = AbilityDefinition(
        "drain",
        targeting=TargetingRule(),
        effects=[
            AbilityEffect(
                "selected",
                Effect("hurt", [EffectOperation("resource_delta", "hp", -10)]),
            ),
            AbilityEffect(
                "self",
                Effect("heal", [EffectOperation("resource_delta", "hp", 5)]),
            ),
        ],
    )

    result = AbilityRuntime(AbilityRegistry([ability])).execute("drain", src, [tgt])

    assert result.executed
    assert src.subject.resources.current("hp") == 45
    assert tgt.subject.resources.current("hp") == 90


def test_targeting_rule_rejects_wrong_tags_and_self():
    src = AbilityTarget("hero", make_subject(tags=["actor.player"]))
    friend = AbilityTarget("friend", make_subject(tags=["actor.player"]))

    ability = AbilityDefinition(
        "enemy_only",
        targeting=TargetingRule(required_tags=["enemy"]),
    )

    rt = AbilityRuntime(AbilityRegistry([ability]))

    result = rt.execute("enemy_only", src, [friend])
    assert not result.executed
    assert "missing_required_tags:friend" in result.errors

    result = rt.execute("enemy_only", src, [src])
    assert not result.executed
    assert "self_target_not_allowed:hero" in result.errors


def test_target_count_limits_are_generic():
    src = AbilityTarget("hero", make_subject())
    a = AbilityTarget("a", make_subject())
    b = AbilityTarget("b", make_subject())
    c = AbilityTarget("c", make_subject())

    ability = AbilityDefinition(
        "two_target_skill",
        targeting=TargetingRule(minimum_targets=2, maximum_targets=2),
    )
    rt = AbilityRuntime(AbilityRegistry([ability]))

    assert not rt.execute("two_target_skill", src, [a]).executed
    assert rt.execute("two_target_skill", src, [a, b]).executed
    assert not rt.execute("two_target_skill", src, [a, b, c]).executed


def test_condition_can_gate_ability():
    src = AbilityTarget("hero", make_subject(resources={"hp": (20, 100)}))
    tgt = AbilityTarget("enemy", make_subject())

    ability = AbilityDefinition(
        "desperation",
        conditions=NumericCondition("source", "resource_ratio", "hp", "<=", 0.25),
    )
    rt = AbilityRuntime(AbilityRegistry([ability]))
    assert rt.execute("desperation", src, [tgt]).executed

    src.subject.resources.set_current("hp", 80)
    result = rt.execute("desperation", src, [tgt])
    assert not result.executed
    assert "conditions_failed" in result.errors


def test_cost_can_use_value_formula():
    src = AbilityTarget(
        "hero",
        make_subject(
            stats={"focus": 10},
            resources={"mp": (50, 50)},
        ),
    )
    tgt = AbilityTarget("enemy", make_subject())

    cost_formula = ValueFormula.constant(7)
    ability = AbilityDefinition(
        "formula_cost",
        costs=[AbilityCost("mp", cost_formula)],
    )
    result = AbilityRuntime(AbilityRegistry([ability])).execute(
        "formula_cost", src, [tgt]
    )
    assert result.executed
    assert src.subject.resources.current("mp") == 43


def test_insufficient_cost_does_not_apply_effect():
    src = AbilityTarget(
        "hero",
        make_subject(
            resources={"mp": (2, 20)},
        ),
    )
    tgt = AbilityTarget(
        "enemy",
        make_subject(
            resources={"hp": (50, 50)},
        ),
    )

    ability = AbilityDefinition(
        "expensive",
        costs=[AbilityCost("mp", 5)],
        effects=[
            AbilityEffect(
                "selected",
                Effect("damage", [EffectOperation("resource_delta", "hp", -20)]),
            )
        ],
    )

    result = AbilityRuntime(AbilityRegistry([ability])).execute("expensive", src, [tgt])
    assert not result.executed
    assert src.subject.resources.current("mp") == 2
    assert tgt.subject.resources.current("hp") == 50


def test_execution_is_atomic_if_late_effect_fails():
    src = AbilityTarget(
        "hero",
        make_subject(
            resources={"mp": (20, 20)},
        ),
    )
    tgt = AbilityTarget(
        "enemy",
        make_subject(
            resources={"hp": (50, 50)},
        ),
    )

    ability = AbilityDefinition(
        "atomic",
        costs=[AbilityCost("mp", 5)],
        effects=[
            AbilityEffect(
                "selected",
                Effect("damage", [EffectOperation("resource_delta", "hp", -10)]),
            ),
            AbilityEffect(
                "selected",
                Effect("bad", [EffectOperation("resource_delta", "missing", -1)]),
            ),
        ],
    )

    rt = AbilityRuntime(AbilityRegistry([ability]))
    try:
        rt.execute("atomic", src, [tgt])
    except KeyError:
        pass
    else:
        raise AssertionError("expected invalid effect to fail")

    assert src.subject.resources.current("mp") == 20
    assert tgt.subject.resources.current("hp") == 50


def test_ability_definition_roundtrip():
    ability = AbilityDefinition(
        "arcane_burst",
        targeting=TargetingRule(
            minimum_targets=1,
            maximum_targets=3,
            required_tags=["enemy"],
            blocked_tags=["immune.arcane"],
        ),
        costs=[AbilityCost("mana", 12)],
        conditions=NumericCondition("source", "stat", "focus", ">=", 5),
        effects=[
            AbilityEffect(
                "selected",
                Effect("burst", [EffectOperation("resource_delta", "hp", -25)]),
            )
        ],
        tags=["ability.magic", "school.arcane"],
    )

    restored = AbilityDefinition.from_data(ability.to_data())
    assert restored == ability


def test_ability_names_and_target_tags_are_not_hardcoded_rpg_rules():
    src = AbilityTarget(
        "reactor",
        make_subject(
            resources={"charge": (10, 10)},
            tags=["machine"],
        ),
    )
    tgt = AbilityTarget(
        "coolant",
        make_subject(
            resources={"temperature": (80, 100)},
            tags=["system.coolant"],
        ),
    )

    ability = AbilityDefinition(
        "vent_heat",
        targeting=TargetingRule(required_tags=["system.coolant"]),
        costs=[AbilityCost("charge", 1)],
        effects=[
            AbilityEffect(
                "selected",
                Effect("cool", [EffectOperation("resource_delta", "temperature", -20)]),
            )
        ],
    )

    result = AbilityRuntime(AbilityRegistry([ability])).execute("vent_heat", src, [tgt])
    assert result.executed
    assert tgt.subject.resources.current("temperature") == 60
