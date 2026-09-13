from __future__ import annotations

import random

from asteria.gameplay import AbilityRegistry, AbilityRuntime, GameplaySubject, ResourcePool, StatBlock, TagSet
from asteria.rpg import (
    BattleEscapeRule,
    BattleObjectiveCondition,
    BattleObjectiveDefinition,
    BattleRuntime,
    Party,
    PartyMember,
)


def subject(hp, **stats):
    resources = ResourcePool(); resources.define("hp", hp)
    return GameplaySubject(StatBlock(stats), resources, TagSet())


heroes = [
    PartyMember("guardian", "heroes", subject(100, speed=20), initiative=20),
    PartyMember("mage", "heroes", subject(80, speed=12), initiative=12),
]
enemies = [PartyMember("beetle", "enemies", subject(120, pursuit=8), initiative=10)]
objective = BattleObjectiveDefinition(
    "seal.portal",
    success_conditions=(BattleObjectiveCondition("flag", "portal.sealed"),),
    failure_conditions=(BattleObjectiveCondition("member_active", "guardian", "==", False),),
    winning_sides=("heroes",), defeated_sides=("enemies",),
)
escape = BattleEscapeRule(
    "retreat", "heroes", base_chance=0.35,
    source_stat="speed", source_scale=0.01,
    opponent_stat="pursuit", opponent_scale=0.005,
)
battle = BattleRuntime(
    [Party("heroes", heroes), Party("enemies", enemies)],
    AbilityRuntime(AbilityRegistry()),
    is_active=lambda m: m.subject.resources.current("hp") > 0,
    objective_definitions=(objective,), escape_rules=(escape,),
)

assert not battle.resolve_outcome().finished
battle.set_objective_flag("portal.sealed", True)
outcome = battle.resolve_outcome()
assert outcome.finished and outcome.winning_sides == ("heroes",)

battle = BattleRuntime(
    [Party("heroes", heroes), Party("enemies", enemies)],
    AbilityRuntime(AbilityRegistry()),
    is_active=lambda m: m.subject.resources.current("hp") > 0,
    escape_rules=(escape,),
)
result = battle.attempt_escape("retreat", rng=random.Random(1))
print("objective:", outcome.objective_ids, "winner:", outcome.winning_sides)
print("escape chance:", round(result.chance, 3), "roll:", round(result.roll, 3), "success:", result.succeeded)
print("PASS")
