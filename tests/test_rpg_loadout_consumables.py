from asteria.gameplay import (
    Effect,
    EffectOperation,
    EffectOperationKind,
    ModifierOperation,
    ResourcePool,
    StatBlock,
    StatModifier,
    TagSet,
)
from asteria.rpg import (
    EquipmentDefinition,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
    Inventory,
    ItemDefinition,
    use_inventory_item,
)


def test_loadout_aggregates_equipment_and_attachment_contributions():
    sword = EquipmentDefinition(
        "sword",
        slot="weapon",
        tags=["equipment.weapon"],
        modifiers=[StatModifier("sword.attack", "attack", ModifierOperation.ADD, 10)],
        granted_abilities=["slash"],
    )
    ring = EquipmentDefinition(
        "ring",
        slot="accessory",
        tags=["equipment.accessory"],
        granted_abilities=["blink"],
    )
    loadout = EquipmentLoadout(
        [
            EquipmentSlotDefinition("weapon", accepted_tags=["equipment.weapon"]),
            EquipmentSlotDefinition(
                "accessory", accepted_tags=["equipment.accessory"], capacity=2
            ),
        ]
    )
    loadout.equip("weapon", EquippedItem(sword))
    loadout.equip("accessory", EquippedItem(ring))
    assert loadout.modifier_set().evaluate("attack", 5) == 15
    assert loadout.abilities() == ("blink", "slash") or loadout.abilities() == (
        "slash",
        "blink",
    )
    assert "equipment.weapon" in loadout.tags()


def test_slot_rejects_wrong_equipment():
    armor = EquipmentDefinition("armor", slot="body", tags=["equipment.armor"])
    loadout = EquipmentLoadout(
        [EquipmentSlotDefinition("weapon", accepted_tags=["equipment.weapon"])]
    )
    try:
        loadout.equip("weapon", EquippedItem(armor))
    except ValueError:
        pass
    else:
        raise AssertionError("expected slot rejection")


def test_capacity_and_unequip():
    slot = EquipmentSlotDefinition("ring", capacity=2)
    loadout = EquipmentLoadout([slot])
    a = EquippedItem(EquipmentDefinition("a", slot="ring"))
    b = EquippedItem(EquipmentDefinition("b", slot="ring"))
    c = EquippedItem(EquipmentDefinition("c", slot="ring"))
    loadout.equip("ring", a)
    loadout.equip("ring", b)
    try:
        loadout.equip("ring", c)
    except ValueError:
        pass
    else:
        raise AssertionError("expected full slot")
    assert loadout.unequip("ring") is a


def test_consumable_effect_and_inventory_consumption():
    potion = ItemDefinition(
        "potion",
        use_effects=[
            Effect("heal", [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", 30)])
        ],
    )
    inv = Inventory()
    inv.add("potion")
    stats = StatBlock()
    resources = ResourcePool()
    resources.define("hp", 100, current=40)
    tags = TagSet()
    result = use_inventory_item(inv, potion, stats, resources, tags)
    assert result.used and resources.current("hp") == 70 and inv.count("potion") == 0


def test_failed_consumable_is_atomic_and_not_consumed():
    item = ItemDefinition(
        "keyed",
        use_effects=[
            Effect("ok", [EffectOperation(EffectOperationKind.STAT_DELTA, "score", 5)]),
            Effect("requires_boss", [], required_tags=["boss"]),
        ],
    )
    inv = Inventory()
    inv.add("keyed")
    stats = StatBlock({"score": 0})
    resources = ResourcePool()
    tags = TagSet()
    result = use_inventory_item(inv, item, stats, resources, tags)
    assert not result.used
    assert stats.get("score") == 0
    assert inv.count("keyed") == 1


def test_item_v1_backward_read():
    raw = ItemDefinition("old", "Old").to_data()
    raw["version"] = 1
    raw.pop("use_effects")
    restored = ItemDefinition.from_data(raw)
    assert restored.use_effects == ()
