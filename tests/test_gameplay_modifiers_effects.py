import pytest

from asteria.authoring import AuthoringSession
from asteria.core import Entity, Scene
from asteria.gameplay import (
    Effect,
    EffectOperation,
    GameplayAttributesComponent,
    ModifierOperation,
    ModifierSet,
    ResourcePool,
    StatBlock,
    StatModifier,
    TagSet,
    apply_effect,
)
from asteria.project import Project


def test_modifier_order_add_then_multiply_then_override():
    modifiers = ModifierSet(
        [
            StatModifier("a", "power", ModifierOperation.ADD, 5),
            StatModifier("b", "power", ModifierOperation.MULTIPLY, 2),
        ]
    )
    assert modifiers.evaluate("power", 10) == 30

    modifiers.add(StatModifier("override", "power", ModifierOperation.OVERRIDE, 99))
    assert modifiers.evaluate("power", 10) == 99


def test_override_is_deterministic_by_priority_then_id():
    modifiers = ModifierSet(
        [
            StatModifier("z", "speed", "override", 7, priority=1),
            StatModifier("a", "speed", "override", 8, priority=2),
            StatModifier("b", "speed", "override", 9, priority=2),
        ]
    )
    assert modifiers.evaluate("speed", 1) == 9


def test_modifier_tag_requirements_and_blocks():
    modifier = StatModifier(
        "fire_bonus",
        "power",
        "add",
        10,
        required_tags=["weapon.staff"],
        blocked_tags=["state.silenced"],
    )
    modifiers = ModifierSet([modifier])

    assert modifiers.evaluate("power", 5, tags=TagSet(["weapon.staff"])) == 15
    assert modifiers.evaluate("power", 5, tags=TagSet(["weapon.staff", "state.silenced"])) == 5


def test_modifier_set_roundtrip():
    original = ModifierSet(
        [
            StatModifier(
                "m",
                "armor",
                "multiply",
                1.25,
                priority=3,
                required_tags=["stance.guard"],
            )
        ]
    )
    restored = ModifierSet.from_data(original.to_data())
    assert restored.evaluate("armor", 20, tags=TagSet(["stance.guard"])) == 25


def test_effect_applies_instantaneous_changes():
    stats = StatBlock({"power": 10})
    resources = ResourcePool()
    resources.define("hp", 100, current=50)
    tags = TagSet(["actor.player"])

    effect = Effect(
        "heal_and_empower",
        [
            EffectOperation("stat_delta", "power", 3),
            EffectOperation("resource_delta", "hp", 30),
            EffectOperation("tag_add", "state.blessed"),
        ],
    )

    result = apply_effect(effect, stats, resources, tags)

    assert result.applied
    assert stats.require("power") == 13
    assert resources.current("hp") == 80
    assert tags.contains("state.blessed")


def test_effect_respects_tag_gate():
    stats = StatBlock({"power": 10})
    resources = ResourcePool()
    resources.define("hp", 100)
    tags = TagSet(["enemy"])

    effect = Effect(
        "player_only",
        [EffectOperation("stat_delta", "power", 100)],
        required_tags=["actor.player"],
    )

    result = apply_effect(effect, stats, resources, tags)
    assert not result.applied
    assert stats.require("power") == 10


def test_effect_is_atomic_when_later_operation_fails():
    stats = StatBlock({"power": 10})
    resources = ResourcePool()
    resources.define("hp", 100, current=50)
    tags = TagSet()

    effect = Effect(
        "bad",
        [
            EffectOperation("stat_delta", "power", 5),
            EffectOperation("resource_delta", "missing_resource", -10),
        ],
    )

    with pytest.raises(KeyError):
        apply_effect(effect, stats, resources, tags)

    assert stats.require("power") == 10
    assert resources.current("hp") == 50


def test_effect_roundtrip():
    effect = Effect(
        "burn",
        [
            EffectOperation("resource_delta", "hp", -8),
            EffectOperation("tag_add", "state.burning"),
        ],
        required_tags=["alive"],
        blocked_tags=["immune.fire"],
    )
    restored = Effect.from_data(effect.to_data())
    assert restored == effect


def test_authoring_api_effect_is_canonical_and_modifier_is_read_only_evaluation():
    project = Project("Demo")
    scene = project.add_scene(Scene("Arena"))
    entity = scene.add_entity(Entity("Hero"))

    api = AuthoringSession(project)
    gameplay = api.scene("Arena").entity("Hero").gameplay
    gameplay.set_stat("power", 10)
    gameplay.define_resource("hp", 100, current=60)
    gameplay.add_tag("actor.player")

    modifiers = ModifierSet([StatModifier("weapon", "power", "add", 5)])
    assert gameplay.effective_stat("power", modifiers) == 15

    effect = Effect(
        "hit",
        [
            EffectOperation("resource_delta", "hp", -20),
            EffectOperation("tag_add", "state.hurt"),
        ],
    )
    result = gameplay.apply_effect(effect)
    assert result.applied

    component = entity.get(GameplayAttributesComponent)
    assert component.resources["hp"]["current"] == 40
    assert "state.hurt" in component.tags
