import json
import random

import pytest

from asteria.gameplay import GameplaySubject, ResourcePool, StatBlock, TagSet
from asteria.rpg import (
    InteractionDisposition,
    InteractionResolver,
    InteractionRule,
    OutcomeCheckDefinition,
    RpgDatabase,
)


def subject(*, stats=None, tags=()):
    return GameplaySubject(StatBlock(stats or {}), ResourcePool(), TagSet(tags))


def test_weakness_is_tag_driven_not_element_enum():
    resolver = InteractionResolver(
        [
            InteractionRule(
                "weak_fire",
                source_tags_all=("damage.fire",),
                target_tags_all=("weak.fire",),
                multiplier=1.5,
                outcome_tags=("outcome.weak",),
            )
        ]
    )
    result = resolver.resolve_value(
        100, subject(tags=("caster",)), subject(tags=("weak.fire",)), action_tags=("damage.fire",)
    )
    assert result.resolved_value == 150
    assert result.outcome_tags == ("outcome.weak",)


def test_resistance_and_stat_mitigation_compose_deterministically():
    resolver = InteractionResolver(
        [
            InteractionRule("armor", target_tags_all=("armored",), target_stat_terms={"defense": -0.5}, priority=20),
            InteractionRule(
                "fire_resist",
                source_tags_all=("damage.fire",),
                target_tags_all=("resist.fire",),
                multiplier=0.5,
                priority=10,
            ),
        ]
    )
    result = resolver.resolve_value(
        100, subject(), subject(stats={"defense": 40}, tags=("armored", "resist.fire")), action_tags=("damage.fire",)
    )
    assert result.resolved_value == 40
    assert result.matched_rules == ("armor", "fire_resist")


def test_immune_nullifies_value():
    resolver = InteractionResolver(
        [
            InteractionRule(
                "ghost",
                source_tags_all=("damage.physical",),
                target_tags_all=("immune.physical",),
                disposition="nullify",
                outcome_tags=("outcome.immune",),
                priority=100,
            )
        ]
    )
    result = resolver.resolve_value(
        999, subject(), subject(tags=("immune.physical",)), action_tags=("damage.physical",)
    )
    assert result.disposition is InteractionDisposition.NULLIFY
    assert result.resolved_value == 0


@pytest.mark.parametrize("disposition", ["absorb", "reflect"])
def test_absorb_and_reflect_are_routing_outcomes_not_negative_damage(disposition):
    resolver = InteractionResolver(
        [
            InteractionRule(
                "route",
                source_tags_all=("arcane",),
                target_tags_all=(f"{disposition}.arcane",),
                disposition=disposition,
            )
        ]
    )
    result = resolver.resolve_value(30, subject(), subject(tags=(f"{disposition}.arcane",)), action_tags=("arcane",))
    assert result.disposition.value == disposition
    assert result.resolved_value == 30


def test_arbitrary_species_and_weapon_interaction():
    resolver = InteractionResolver(
        [
            InteractionRule(
                "spear_airborne", source_tags_all=("weapon.spear",), target_tags_all=("trait.airborne",), multiplier=2
            )
        ]
    )
    assert (
        resolver.resolve_value(
            12, subject(), subject(tags=("trait.airborne",)), action_tags=("weapon.spear",)
        ).resolved_value
        == 24
    )


def test_rule_serialization_roundtrip():
    rule = InteractionRule("x", source_tags_any=("a", "b"), target_stat_terms={"guard": -0.25}, priority=4)
    assert InteractionRule.from_data(rule.to_data()) == rule


def test_generic_hit_check_uses_project_stats_and_seeded_rng():
    check = OutcomeCheckDefinition(
        "hit",
        0.7,
        source_stat_terms={"accuracy": 0.01},
        target_stat_terms={"evasion": -0.01},
        success_tags=("outcome.hit",),
        failure_tags=("outcome.evade",),
    )
    resolver = InteractionResolver(checks=[check])
    result = resolver.check(
        "hit", subject(stats={"accuracy": 10}), subject(stats={"evasion": 20}), rng=random.Random(1)
    )
    assert result.chance == pytest.approx(0.6)
    assert result.success is True
    assert result.outcome_tags == ("outcome.hit",)


def test_check_can_be_used_for_crit_block_parry_or_custom_names():
    checks = [OutcomeCheckDefinition(name, chance) for name, chance in [("crit", 1), ("block", 0), ("lucky_break", 1)]]
    resolver = InteractionResolver(checks=checks)
    src, dst = subject(), subject()
    assert resolver.check("crit", src, dst, rng=random.Random(3)).success
    assert not resolver.check("block", src, dst, rng=random.Random(3)).success
    assert resolver.check("lucky_break", src, dst, rng=random.Random(3)).success


def test_check_tag_requirements_can_make_check_not_applicable():
    resolver = InteractionResolver(checks=[OutcomeCheckDefinition("parry", 1, required_target_tags=("stance.parry",))])
    result = resolver.check("parry", subject(), subject(), rng=random.Random(1))
    assert result.applicable is False and result.success is None


def test_database_v10_owns_rules_and_checks_and_reads_v9():
    db = RpgDatabase()
    db.add_interaction_rule(InteractionRule("weak", source_tags_all=("fire",), multiplier=2))
    db.add_outcome_check(OutcomeCheckDefinition("hit", 0.9))
    raw = db.to_data()
    assert raw["version"] == 29
    restored = RpgDatabase.from_data(raw)
    assert "weak" in restored.interaction_rules and "hit" in restored.outcome_checks

    legacy = json.loads(json.dumps(raw))
    legacy["version"] = 9
    legacy.pop("interaction_rules")
    legacy.pop("outcome_checks")
    restored_legacy = RpgDatabase.from_data(legacy)
    assert restored_legacy.interaction_rules == {}
    assert restored_legacy.outcome_checks == {}


def test_duplicate_ids_rejected():
    with pytest.raises(ValueError):
        InteractionResolver([InteractionRule("x"), InteractionRule("x")])
    with pytest.raises(ValueError):
        InteractionResolver(checks=[OutcomeCheckDefinition("x", 1), OutcomeCheckDefinition("x", 1)])


def test_256_rules_have_no_engine_cap():
    rules = [InteractionRule(f"r{i}", source_tags_all=(f"tag.{i}",), multiplier=1.01) for i in range(256)]
    resolver = InteractionResolver(rules)
    result = resolver.resolve_value(100, subject(), subject(), action_tags=("tag.255",))
    assert result.matched_rules == ("r255",)
    assert result.resolved_value == pytest.approx(101)


def test_checks_feed_outcome_tags_back_into_value_rules():
    resolver = InteractionResolver(
        [
            InteractionRule("miss_nullifies", source_tags_all=("outcome.evade",), disposition="nullify", priority=100),
            InteractionRule("crit_bonus", source_tags_all=("outcome.critical",), multiplier=2, priority=50),
        ],
        [
            OutcomeCheckDefinition("hit", 0, failure_tags=("outcome.evade",)),
            OutcomeCheckDefinition("crit", 1, success_tags=("outcome.critical",)),
        ],
    )
    result = resolver.resolve(20, subject(), subject(), check_ids=("hit", "crit"), rng=random.Random(1))
    assert result.value.disposition is InteractionDisposition.NULLIFY
    assert result.value.resolved_value == 0
    assert result.outcome_tags == ("outcome.critical", "outcome.evade")


def test_battle_runtime_exposes_interaction_resolution_seam():
    from asteria.gameplay import AbilityDefinition, AbilityRegistry, AbilityRuntime, TargetingRule
    from asteria.rpg import BattleAction, BattleRuntime, Party, PartyMember

    hero = subject(stats={"accuracy": 10})
    beetle = subject(tags=("weak.fire",))
    ability = AbilityDefinition("fire", targeting=TargetingRule(), tags=("damage.fire",))
    battle = BattleRuntime(
        [
            Party("heroes", [PartyMember("hero", "heroes", hero, ability_ids=("fire",))]),
            Party("foes", [PartyMember("beetle", "foes", beetle)]),
        ],
        AbilityRuntime(AbilityRegistry([ability])),
        interaction_rules=[
            InteractionRule("weak", source_tags_all=("damage.fire",), target_tags_all=("weak.fire",), multiplier=1.5)
        ],
    )
    result = battle.resolve_interaction(BattleAction("hero", "fire", ("beetle",)), "beetle", 40)
    assert result.value.resolved_value == 60
