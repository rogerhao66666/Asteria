import pytest

from asteria.core import LifecycleHookBus
from asteria.gameplay import ModifierOperation, StatBlock, StatModifier, TagSet
from asteria.rpg import (
    AttachmentDefinition,
    EquipmentDefinition,
    EquipmentGrowthDefinition,
    EquipmentGrowthNodeDefinition,
    EquipmentGrowthReward,
    EquipmentGrowthRuntime,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
    RpgDatabase,
    SocketDefinition,
)


def make_growth():
    return EquipmentGrowthDefinition(
        "blood_blade_growth",
        nodes=(
            EquipmentGrowthNodeDefinition(
                "temper",
                max_rank=3,
                rank_requirements=({"xp": 10}, {"xp": 30}, {"xp": 60}),
                rewards=(
                    EquipmentGrowthReward(
                        modifiers=(StatModifier("temper1", "attack", ModifierOperation.ADD, 2),)
                    ),
                    EquipmentGrowthReward(
                        modifiers=(StatModifier("temper2", "attack", ModifierOperation.ADD, 3),),
                        granted_tags=("growth.tempered",),
                    ),
                    EquipmentGrowthReward(
                        modifiers=(StatModifier("temper3", "attack", ModifierOperation.ADD, 5),),
                        unlocked_sockets=("awakening",),
                    ),
                ),
            ),
            EquipmentGrowthNodeDefinition(
                "blood_path",
                auto_unlock=False,
                prerequisites=(("temper", 2),),
                exclusive_group="awakening_path",
                rank_requirements={"boss_dragon": 1},
                rewards=EquipmentGrowthReward(
                    granted_abilities=("life_steal",),
                    granted_capabilities=("weapon.blood_awakened",),
                    evolution_equipment_id="crimson_fang",
                ),
            ),
            EquipmentGrowthNodeDefinition(
                "swift_path",
                auto_unlock=False,
                prerequisites=(("temper", 2),),
                exclusive_group="awakening_path",
                rank_requirements={"usage_mastery": 20},
                rewards=EquipmentGrowthReward(granted_tags=("growth.swift",)),
            ),
        ),
    )


def make_equipment():
    return EquipmentDefinition(
        "blood_blade",
        slot="weapon",
        tags=("weapon",),
        modifiers=(StatModifier("base", "attack", ModifierOperation.ADD, 10),),
        sockets=(SocketDefinition("awakening", accepted_tags=("gem",), locked=True),),
        growth_id="blood_blade_growth",
    )


def test_equipment_growth_auto_levels_are_per_instance_and_affect_build_contributions():
    growth = make_growth()
    weapon = make_equipment()
    item = EquippedItem(
        weapon,
        instance_id="blade-a",
        growth=EquipmentGrowthRuntime(growth),
    )
    assert item.growth.rank("temper") == 0
    item.growth.add_progress("xp", 35)
    assert item.growth.rank("temper") == 2
    assert "growth.tempered" in item.tags()

    loadout = EquipmentLoadout([EquipmentSlotDefinition("weapon")])
    loadout.equip("weapon", item)
    stats = loadout.modifier_set().evaluate_block(StatBlock({"attack": 0}), tags=TagSet(item.tags()))
    assert stats.get("attack") == 15

    second = EquippedItem(
        weapon,
        instance_id="blade-b",
        growth=EquipmentGrowthRuntime(growth),
    )
    assert second.growth.rank("temper") == 0


def test_equipment_growth_can_unlock_locked_socket_and_persist_attachment():
    growth = make_growth()
    weapon = make_equipment()
    gem = AttachmentDefinition("ruby", tags=("gem",))
    item = EquippedItem(weapon, instance_id="blade-a", growth=EquipmentGrowthRuntime(growth))
    with pytest.raises(ValueError, match="socket is locked"):
        item.attach("awakening", gem)
    item.growth.add_progress("xp", 60)
    assert item.growth.rank("temper") == 3
    assert item.unlocked_socket_ids() == ("awakening",)
    item.attach("awakening", gem)

    raw = item.to_data()
    restored = EquippedItem.from_data(
        raw,
        equipment={weapon.equipment_id: weapon},
        attachments={gem.attachment_id: gem},
        growth_definitions={growth.growth_id: growth},
    )
    assert restored.growth.counter("xp") == 60
    assert restored.growth.rank("temper") == 3
    assert restored.attachments["awakening"].attachment_id == "ruby"


def test_equipment_growth_branching_and_evolution_target_are_generic_rules():
    growth = make_growth()
    item = EquippedItem(make_equipment(), instance_id="blade-a", growth=EquipmentGrowthRuntime(growth))
    item.growth.add_progress("xp", 30)
    item.growth.add_progress("boss_dragon", 1)
    item.growth.unlock("blood_path")
    assert item.evolution_target_id == "crimson_fang"
    assert "life_steal" in item.abilities()
    assert "weapon.blood_awakened" in item.tags()
    item.growth.add_progress("usage_mastery", 20)
    preview = item.growth.preview_unlock("swift_path")
    assert not preview.allowed
    assert preview.reasons == ("exclusive with blood_path",)


def test_equipment_growth_arbitrary_counters_support_non_xp_growth():
    growth = EquipmentGrowthDefinition(
        "relic_bond",
        nodes=(
            EquipmentGrowthNodeDefinition(
                "bonded",
                rank_requirements={"bond": 5, "material_invested": 3, "boss_flag": 1},
                rewards=EquipmentGrowthReward(granted_tags=("relic.awakened",)),
            ),
        ),
    )
    runtime = EquipmentGrowthRuntime(growth)
    runtime.add_progress("bond", 5)
    runtime.add_progress("material_invested", 3)
    assert runtime.rank("bonded") == 0
    runtime.add_progress("boss_flag", 1)
    assert runtime.rank("bonded") == 1


def test_equipment_growth_lifecycle_hooks_cover_progress_and_unlock():
    hooks = LifecycleHookBus()
    seen = []
    hooks.subscribe("rpg.equipment_growth.progressed", lambda event: seen.append(event.name))
    hooks.subscribe("rpg.equipment_growth.node_unlocked", lambda event: seen.append(event.name))
    runtime = EquipmentGrowthRuntime(make_growth(), hooks=hooks, source="blade-a")
    runtime.add_progress("xp", 10)
    assert seen == ["rpg.equipment_growth.progressed", "rpg.equipment_growth.node_unlocked"]


def test_equipment_instance_v1_remains_readable_without_growth():
    weapon = EquipmentDefinition("old_blade", slot="weapon")
    raw = {
        "schema": "asteria.rpg.equipment_instance",
        "version": 1,
        "instance_id": "old-1",
        "equipment_id": "old_blade",
        "attachments": {},
    }
    restored = EquippedItem.from_data(raw, equipment={"old_blade": weapon}, attachments={})
    assert restored.growth is None
    assert restored.to_data()["version"] == 2


def test_rpg_database_v8_persists_growth_and_validates_references():
    growth = make_growth()
    db = RpgDatabase()
    db.add_equipment_growth(growth)
    db.add_equipment(make_equipment())
    db.add_equipment(EquipmentDefinition("crimson_fang", slot="weapon"))
    assert db.validate()
    raw = db.to_data()
    assert raw["version"] == 23
    restored = RpgDatabase.from_data(raw)
    assert restored.equipment_growth["blood_blade_growth"].nodes[0].max_rank == 3

    bad = RpgDatabase()
    bad.add_equipment(EquipmentDefinition("bad", growth_id="missing"))
    with pytest.raises(ValueError, match="unknown equipment growth"):
        bad.validate()


def test_growth_definition_rejects_cycles_and_runtime_rejects_bad_rank():
    with pytest.raises(ValueError, match="cycle"):
        EquipmentGrowthDefinition(
            "bad",
            nodes=(
                EquipmentGrowthNodeDefinition("a", prerequisites=("b",)),
                EquipmentGrowthNodeDefinition("b", prerequisites=("a",)),
            ),
        )
    growth = make_growth()
    with pytest.raises(ValueError, match="invalid growth rank"):
        EquipmentGrowthRuntime(growth, ranks={"temper": 99})


def test_rpg_database_v7_remains_readable_without_equipment_growth():
    db = RpgDatabase()
    raw = db.to_data()
    raw["version"] = 7
    raw.pop("equipment_growth")
    restored = RpgDatabase.from_data(raw)
    assert restored.equipment_growth == {}
