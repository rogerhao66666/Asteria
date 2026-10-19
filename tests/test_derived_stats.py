"""Derived stats: a stat computed from others as project data (attack from Strength...)."""

import pytest

from asteria.gameplay import StatBlock
from asteria.rpg import RpgDatabase
from asteria.rpg.derived_stats import DerivedStatRule, apply_derived_stats


def test_rules_add_their_formula_in_order_with_floor_and_cap():
    stats = StatBlock({"str": 10, "dex": 4, "power": 5})
    rules = (
        DerivedStatRule("crit", terms={"power": 0.5}, maximum=12, order=1),  # reads power below
        DerivedStatRule("power", terms={"str": 2, "dex": 0.5}),
        DerivedStatRule("evade", terms={"dex": -10}),  # never below 0
        DerivedStatRule("hp_regen", terms={"str": 1}, applies_to="enemies"),
    )
    applied = apply_derived_stats(stats, rules, side="actors")
    assert stats.get("power") == 5 + 20 + 2  # gear's 5 stays, the formula adds
    assert stats.get("crit") == 12  # 13.5 capped
    assert stats.get("evade") == 0
    assert not stats.contains("hp_regen")
    assert [s for s, _ in applied] == ["evade", "power", "crit"]


def test_a_rule_is_data_and_refuses_reading_itself():
    rule = DerivedStatRule("accuracy", "Accuracy", terms={"dex": 1, "luk": 0.5}, base=10)
    assert DerivedStatRule.from_data(rule.to_data()) == rule
    assert rule.formula_text() == "accuracy += 10 + 1 x dex + 0.5 x luk"
    with pytest.raises(ValueError):
        DerivedStatRule("power", terms={"power": 1})
    db = RpgDatabase()
    db.add_derived_stat(rule)
    assert RpgDatabase.from_data(db.to_data()).derived_stats["accuracy"] == rule
