from asteria.gameplay import (
    FormulaBuilder,
    FormulaCondition,
    FormulaContext,
    ResourcePool,
    StatBlock,
    TagSet,
    ValueFormula,
)


def context(
    source_stats=None,
    target_stats=None,
    source_resources=None,
    target_resources=None,
    source_tags=(),
    target_tags=(),
):
    sr = ResourcePool()
    for name, values in (source_resources or {}).items():
        sr.define(name, values[1], current=values[0])
    tr = ResourcePool()
    for name, values in (target_resources or {}).items():
        tr.define(name, values[1], current=values[0])
    return FormulaContext(
        StatBlock(source_stats or {}),
        sr,
        TagSet(source_tags),
        StatBlock(target_stats or {}),
        tr,
        TagSet(target_tags),
    )


def test_beginner_constant_formula():
    formula = ValueFormula.constant(25)
    assert formula.evaluate(context()) == 25


def test_weapon_scaling_against_target_defense():
    formula = (
        FormulaBuilder()
        .constant(25)
        .source_stat("attack", 1.0)
        .target_stat("defense", -0.5)
        .build()
    )
    result = formula.evaluate(
        context(
            source_stats={"attack": 40},
            target_stats={"defense": 20},
        )
    )
    assert result == 55


def test_multi_stat_creative_scaling():
    formula = (
        FormulaBuilder()
        .constant(20)
        .source_stat("magic", 1.8)
        .source_stat("dexterity", 0.4)
        .target_stat("magic_defense", -0.5)
        .build()
    )
    result = formula.evaluate(
        context(
            source_stats={"magic": 10, "dexterity": 5},
            target_stats={"magic_defense": 8},
        )
    )
    assert result == 36


def test_formula_can_scale_from_current_or_max_resource():
    formula = (
        FormulaBuilder()
        .source_resource_current("mp", 0.4)
        .source_resource_max("hp", 0.2)
        .build()
    )
    result = formula.evaluate(
        context(source_resources={"mp": (50, 100), "hp": (80, 200)})
    )
    assert result == 60


def test_element_like_weakness_is_generic_tag_condition():
    condition = FormulaCondition(required_target_tags=["weak.slash"])
    formula = (
        FormulaBuilder()
        .constant(20)
        .source_stat("strength", 1.0)
        .multiply_when(1.5, condition)
        .build()
    )
    normal = formula.evaluate(
        context(
            source_stats={"strength": 10},
            target_tags=["enemy"],
        )
    )
    weak = formula.evaluate(
        context(
            source_stats={"strength": 10},
            target_tags=["enemy", "weak.slash"],
        )
    )
    assert normal == 30
    assert weak == 45


def test_condition_can_use_source_and_target_tags():
    condition = FormulaCondition(
        required_source_tags=["stance.rage"],
        required_target_tags=["enemy.boss"],
        blocked_target_tags=["immune.execute"],
    )
    formula = FormulaBuilder().constant(10).multiply_when(2, condition).build()
    assert (
        formula.evaluate(
            context(source_tags=["stance.rage"], target_tags=["enemy.boss"])
        )
        == 20
    )
    assert (
        formula.evaluate(
            context(
                source_tags=["stance.rage"],
                target_tags=["enemy.boss", "immune.execute"],
            )
        )
        == 10
    )


def test_formula_clamp():
    formula = FormulaBuilder().constant(-50).clamp(minimum=0).build()
    assert formula.evaluate(context()) == 0


def test_formula_roundtrip():
    formula = (
        FormulaBuilder()
        .constant(40)
        .source_stat("strength", 1.5)
        .target_stat("armor", -0.7)
        .multiply_when(
            1.5,
            FormulaCondition(required_target_tags=["weak.slash"]),
        )
        .clamp(minimum=0, maximum=9999)
        .build()
    )
    restored = ValueFormula.from_data(formula.to_data())
    ctx = context(
        source_stats={"strength": 20},
        target_stats={"armor": 10},
        target_tags=["weak.slash"],
    )
    assert restored.evaluate(ctx) == formula.evaluate(ctx)


def test_beginner_and_advanced_are_same_canonical_type():
    beginner = ValueFormula.constant(25)
    advanced = FormulaBuilder().constant(25).source_stat("attack", 1).build()
    assert isinstance(beginner, ValueFormula)
    assert isinstance(advanced, ValueFormula)
    assert beginner.to_data()["schema"] == advanced.to_data()["schema"]
