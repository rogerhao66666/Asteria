from asteria.gameplay import ModifierOperation, StatModifier
from asteria.rpg import (
    ActorDefinition,
    ClassAssignment,
    ClassDefinition,
    EquipmentDefinition,
    EquipmentGrowthDefinition,
    EquipmentGrowthNodeDefinition,
    EquipmentGrowthReward,
    EquipmentGrowthRuntime,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
    PassiveDefinition,
    ProgressionAllocationRuntime,
    ProgressionGraphDefinition,
    ProgressionNodeDefinition,
    ProgressionNodeReward,
    RpgActorRuntime,
    resolve_actor_build,
)


def test_canonical_resolved_build_composes_multiclass_allocation_passive_and_equipment_growth():
    actor_def = ActorDefinition(
        "hero",
        class_assignments=(
            ClassAssignment("warrior", assignment_id="job-warrior", priority=0),
            ClassAssignment("mage", assignment_id="job-mage", priority=1),
        ),
        base_stats={"attack": 10, "magic": 5},
        base_resources={"hp": 100, "mp": 10},
        tags=("actor.player",),
        abilities=("basic_attack",),
    )
    classes = {
        "warrior": ClassDefinition("warrior", stat_bonuses={"attack": 3}, granted_tags=("capability.weapon.sword",), granted_abilities=("slash",)),
        "mage": ClassDefinition("mage", stat_bonuses={"magic": 4}, granted_tags=("capability.weapon.staff",), granted_abilities=("spark",)),
    }
    actor = RpgActorRuntime(actor_def, class_definitions=classes)
    passive = PassiveDefinition(
        "focus",
        tags=("passive.focus",),
        modifiers=(StatModifier("focus.attack", "attack", ModifierOperation.ADD, 2),),
        granted_abilities=("counter",),
    )
    actor.ability_state.equip_passive("focus")
    actor.ability_state.learn("heal")

    graph = ProgressionGraphDefinition(
        "hero_board",
        nodes=(ProgressionNodeDefinition(
            "training",
            rewards=ProgressionNodeReward(
                stat_bonuses={"attack": 5},
                resource_bonuses={"mp": 7},
                granted_capabilities=("capability.weapon.greatblade",),
                granted_abilities=("burst",),
            ),
        ),),
    )
    allocation = ProgressionAllocationRuntime((graph,), allocations={"hero_board": {"training": 1}})

    growth_def = EquipmentGrowthDefinition(
        "blade_growth",
        nodes=(EquipmentGrowthNodeDefinition(
            "awaken",
            rank_requirements={"xp": 1},
            rewards=EquipmentGrowthReward(
                modifiers=(StatModifier("growth.attack", "attack", ModifierOperation.ADD, 6),),
                granted_abilities=("blood_strike",),
                granted_capabilities=("capability.weapon.awakened",),
            ),
        ),),
    )
    blade = EquipmentDefinition(
        "blade",
        slot="weapon",
        modifiers=(StatModifier("blade.attack", "attack", ModifierOperation.ADD, 4),),
        growth_id="blade_growth",
    )
    growth = EquipmentGrowthRuntime(growth_def)
    growth.add_progress("xp", 1)
    item = EquippedItem(blade, instance_id="blade-1", growth=growth)
    loadout = EquipmentLoadout((EquipmentSlotDefinition("weapon"),))
    loadout.equip("weapon", item, validate_requirements=False)

    build = resolve_actor_build(
        actor,
        allocations=allocation,
        loadout=loadout,
        passives={"focus": passive},
    )
    assert build.stats.get("attack") == 30  # 10 + 3 + 5 + 4 + 6 + 2
    assert build.stats.get("magic") == 9
    assert build.resources.get("mp").maximum == 17
    assert "capability.weapon.greatblade" in build.capabilities
    assert "capability.weapon.awakened" in build.capabilities
    assert build.abilities == (
        "basic_attack", "slash", "spark", "burst", "heal", "blood_strike", "counter"
    )
    assert build.equipment_instance_ids == ("blade-1",)
    assert build.class_assignment_ids == ("job-warrior", "job-mage")
    assert build.ability_sources("blood_strike")[0].source_kind == "equipment_growth"


def test_resolved_build_is_derived_and_does_not_mutate_intrinsic_actor_state():
    actor = RpgActorRuntime(ActorDefinition("hero", base_stats={"attack": 10}))
    passive = PassiveDefinition(
        "buff",
        modifiers=(StatModifier("buff", "attack", ModifierOperation.ADD, 9),),
    )
    actor.ability_state.equip_passive("buff")
    build = resolve_actor_build(actor, passives={"buff": passive})
    assert build.stats.get("attack") == 19
    assert actor.stats.get("attack") == 10


def test_resolved_build_provenance_explains_sources():
    actor = RpgActorRuntime(
        ActorDefinition("hero", class_assignments=(ClassAssignment("job", assignment_id="j1"),), base_stats={"attack": 5}),
        class_definitions={"job": ClassDefinition("job", stat_bonuses={"attack": 2}, granted_abilities=("slash",))},
    )
    build = resolve_actor_build(actor)
    assert {(x.source_kind, x.source_id) for x in build.sources_for("stat", "attack")} == {
        ("intrinsic", "hero"), ("class", "j1")
    }
    assert build.ability_sources("slash")[0].source_id == "j1"
    summary = build.to_summary_data()
    assert summary["schema"] == "asteria.rpg.resolved_actor_build_summary"
    assert summary["actor_id"] == "hero"


def test_empty_optional_layers_still_resolve_canonical_build():
    actor = RpgActorRuntime(ActorDefinition("hero", base_stats={"speed": 12}, tags=("hero",), abilities=("wait",)))
    build = resolve_actor_build(actor)
    assert build.stats.get("speed") == 12
    assert build.tags.contains("hero")
    assert build.abilities == ("wait",)
    assert build.equipment_instance_ids == ()
