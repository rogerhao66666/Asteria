from __future__ import annotations

from dataclasses import dataclass

from .abilities import (
    AbilityCost,
    AbilityDefinition,
    AbilityEffect,
    TargetingRule,
)
from .action_timeline import ActionCue, ActionTimeline
from .effects import Effect, EffectOperation
from .formulas import FormulaBuilder, ValueFormula
from .stats import ResourcePool, StatBlock
from .tags import TagSet


@dataclass(frozen=True, slots=True)
class GameplayStarterAttributes:
    stats: StatBlock
    resources: ResourcePool
    tags: TagSet


def simple_rpg_attributes():
    """Ready-to-use starter values. These are template data, never engine rules."""
    stats = StatBlock(
        {
            "attack": 10,
            "defense": 10,
            "magic": 10,
            "resistance": 10,
            "speed": 10,
        }
    )
    resources = ResourcePool()
    resources.define("hp", 100, current=100)
    resources.define("mp", 30, current=30)
    return GameplayStarterAttributes(stats, resources, TagSet(["actor.player"]))


def standard_physical_formula(base=10):
    return FormulaBuilder().constant(base).source_stat("attack", 1.0).target_stat("defense", -0.5).build()


def standard_magic_formula(base=10):
    return FormulaBuilder().constant(base).source_stat("magic", 1.2).target_stat("resistance", -0.5).build()


def flat_formula(value=10):
    return ValueFormula.constant(value)


def basic_attack_ability(damage=10):
    return AbilityDefinition(
        "basic_attack",
        targeting=TargetingRule(
            minimum_targets=1,
            maximum_targets=1,
            required_tags=["enemy"],
        ),
        effects=[
            AbilityEffect(
                "selected",
                Effect(
                    "basic_attack_damage",
                    [EffectOperation("resource_delta", "hp", -float(damage))],
                ),
            )
        ],
        tags=["ability.attack"],
    )


def simple_heal_ability(amount=20, cost=5):
    return AbilityDefinition(
        "simple_heal",
        targeting=TargetingRule(
            minimum_targets=1,
            maximum_targets=1,
            allow_self=True,
        ),
        costs=[AbilityCost("mp", cost)],
        effects=[
            AbilityEffect(
                "selected",
                Effect(
                    "simple_heal",
                    [EffectOperation("resource_delta", "hp", float(amount))],
                ),
            )
        ],
        tags=["ability.support"],
    )


def basic_melee_timeline(ability_id="basic_attack"):
    return ActionTimeline(
        "basic_melee",
        [
            ActionCue("attack_animation", 0.00, "animation", {"clip": "attack"}),
            ActionCue("slash_vfx", 0.18, "vfx", {"preset": "slash.basic"}),
            ActionCue("gameplay_hit", 0.20, "gameplay_ability", {"ability_id": ability_id}),
            ActionCue("impact_audio", 0.20, "audio", {"preset": "impact.light"}),
            ActionCue("impact_screen", 0.20, "screen_fx", {"hit_stop": 0.035}),
            ActionCue("impact_camera", 0.21, "camera", {"preset": "impact.small"}),
        ],
    )


@dataclass(frozen=True, slots=True)
class GameplayPresetCatalog:
    formulas: dict
    abilities: dict
    timelines: dict

    @classmethod
    def defaults(cls):
        return cls(
            formulas={
                "standard_physical": standard_physical_formula(),
                "standard_magic": standard_magic_formula(),
                "flat": flat_formula(),
            },
            abilities={
                "basic_attack": basic_attack_ability(),
                "simple_heal": simple_heal_ability(),
            },
            timelines={
                "basic_melee": basic_melee_timeline(),
            },
        )
