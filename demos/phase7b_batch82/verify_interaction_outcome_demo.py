from __future__ import annotations

import json
import random
from pathlib import Path

from asteria.gameplay import GameplaySubject, ResourcePool, StatBlock, TagSet
from asteria.rpg import InteractionResolver, RpgDatabase

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "AsteriaPhase7B_InteractionOutcomeDemo.asteria.json"


def subject(stats=None, tags=()):
    return GameplaySubject(StatBlock(stats or {}), ResourcePool(), TagSet(tags))


def main():
    raw = json.loads(PROJECT.read_text())
    db = RpgDatabase.from_data(raw["rpg_database"])
    resolver = InteractionResolver(db.interaction_rules.values(), db.outcome_checks.values())

    hero = subject({"accuracy": 20, "critical": 10})
    beetle = subject({"defense": 40, "evasion": 5}, ("weak.fire", "trait.armored"))
    fire = resolver.resolve(
        100, hero, beetle, action_tags=("damage.fire",), check_ids=("hit",), rng=random.Random(7)
    )
    assert fire.checks[0].success is True
    assert fire.value.resolved_value == 120.0  # (100 - 20 DEF mitigation) * 1.5 weakness
    assert "outcome.weak" in fire.outcome_tags

    ghost = subject(tags=("immune.physical",))
    physical = resolver.resolve_value(80, hero, ghost, action_tags=("damage.physical",))
    assert physical.resolved_value == 0
    assert physical.disposition.value == "nullify"

    absorber = subject(tags=("absorb.arcane",))
    absorbed = resolver.resolve_value(55, hero, absorber, action_tags=("damage.arcane",))
    assert absorbed.disposition.value == "absorb" and absorbed.resolved_value == 55

    print("Batch 82 interaction/outcome demo PASS")
    print("fire_value=", fire.value.resolved_value)
    print("fire_rules=", fire.value.matched_rules)
    print("fire_tags=", fire.outcome_tags)
    print("physical=", physical.disposition.value, physical.resolved_value)
    print("arcane=", absorbed.disposition.value, absorbed.resolved_value)


if __name__ == "__main__":
    main()
