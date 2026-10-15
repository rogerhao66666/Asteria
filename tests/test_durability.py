"""Equipment durability: wear, breaking, repair, nicknames and what a broken item gives."""

import pytest

from asteria.gameplay import ModifierOperation, StatBlock, StatModifier
from asteria.rpg.durability import DurabilityRules, WearEvent
from asteria.rpg.items import (
    EquipmentDefinition,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
)

SWORD = EquipmentDefinition(
    "sword",
    "Sword",
    slot="weapon",
    tags=("blade",),
    modifiers=(StatModifier("atk", "attack", ModifierOperation.ADD, 5),),
    granted_abilities=("slash",),
)
ARMOR = EquipmentDefinition(
    "mail",
    "Mail",
    slot="armor",
    modifiers=(StatModifier("def", "defense", ModifierOperation.ADD, 3),),
)


def _loadout(*items):
    loadout = EquipmentLoadout(
        [EquipmentSlotDefinition("weapon"), EquipmentSlotDefinition("armor")]
    )
    for slot, item in items:
        loadout.equip(slot, item, validate_requirements=False)
    return loadout


def _rules(**extra):
    return DurabilityRules(
        "wear",
        max_durability={"sword": 3},
        default_max=2,
        wear=(WearEvent("attack", ["weapon"]), WearEvent("hit", ["armor"], 1.0)),
        **extra,
    )


def _attack(loadout):
    return loadout.modifier_set().evaluate_block(StatBlock({"attack": 10, "defense": 5}))


def test_new_instances_get_full_durability_from_the_rules():
    rules = _rules()
    sword, armor = EquippedItem(SWORD), EquippedItem(ARMOR)
    rules.ensure(sword)
    rules.ensure(armor)
    assert (sword.durability, sword.max_durability) == (3, 3)
    assert (armor.durability, armor.max_durability) == (2, 2)
    plain = EquippedItem(EquipmentDefinition("ring", "Ring", slot="armor"))
    DurabilityRules("x").ensure(plain)
    assert plain.durability is None and not plain.broken  # does not wear out


def test_wear_only_touches_the_slots_of_that_event():
    rules = _rules()
    loadout = _loadout(("weapon", EquippedItem(SWORD)), ("armor", EquippedItem(ARMOR)))
    rules.apply_wear(loadout, "attack")
    sword, armor = loadout.equipped("weapon")[0], loadout.equipped("armor")[0]
    assert sword.durability == 2 and armor.durability is None
    rules.apply_wear(loadout, "hit")
    assert armor.durability == 1
    assert rules.apply_wear(loadout, "unknown") == ()


def test_a_broken_item_stays_equipped_but_gives_nothing():
    rules = _rules()
    loadout = _loadout(("weapon", EquippedItem(SWORD)), ("armor", EquippedItem(ARMOR)))
    assert _attack(loadout).get("attack") == 15 and loadout.abilities() == ("slash",)
    for _ in range(2):
        rules.apply_wear(loadout, "attack")
    assert _attack(loadout).get("attack") == 15
    broke = rules.apply_wear(loadout, "attack")
    assert [i.equipment.equipment_id for i in broke] == ["sword"]
    sword = loadout.equipped("weapon")[0]
    assert sword.broken and loadout.equipped("weapon") == (sword,)
    assert _attack(loadout).get("attack") == 10 and _attack(loadout).get("defense") == 8
    assert loadout.abilities() == () and "blade" not in loadout.tags()
    assert rules.apply_wear(loadout, "attack") == ()  # already broken: nothing more to wear


def test_destroy_removes_the_item_when_it_breaks():
    rules = _rules(on_break="destroy")
    loadout = _loadout(("weapon", EquippedItem(SWORD)))
    for _ in range(3):
        rules.apply_wear(loadout, "attack")
    assert loadout.equipped("weapon") == ()


def test_repair_restores_points_and_prices_them():
    rules = _rules(repair_currency="gold", repair_cost_per_point=12.5)
    item = rules.ensure(EquippedItem(SWORD))
    item.durability = 0.0
    assert rules.repair_cost(item) == ("gold", 38.0)  # 3 points * 12.5, rounded up
    assert rules.repair_cost(item, 1) == ("gold", 13.0)
    assert rules.repair(item, 1) == 1 and item.durability == 1 and not item.broken
    assert rules.repair(item) == 2 and item.durability == item.max_durability
    assert rules.repair(item) == 0
    assert rules.repair(EquippedItem(ARMOR)) == 0


def test_durability_and_nickname_survive_a_save():
    rules = _rules()
    loadout = _loadout(("weapon", rules.ensure(EquippedItem(SWORD))))
    item = loadout.equipped("weapon")[0]
    item.durability = 1.0
    assert item.rename("  Old   Faithful ") == "Old Faithful"
    restored = EquipmentLoadout.from_data(
        loadout.to_data(), equipment={"sword": SWORD}, attachments={}
    ).equipped("weapon")[0]
    assert (restored.durability, restored.max_durability) == (1.0, 3.0)
    assert restored.nickname == "Old Faithful"
    plain = EquippedItem(ARMOR).to_data()
    assert "durability" not in plain and "nickname" not in plain  # old saves are unchanged


def test_nicknames_have_a_length_limit():
    item = EquippedItem(SWORD)
    with pytest.raises(ValueError):
        item.rename("x" * 30)
    assert item.rename("ok", max_length=2) == "ok"


def test_rules_round_trip_and_validate():
    rules = _rules(on_break="destroy", repair_currency="gold", repair_cost_per_point=2)
    assert DurabilityRules.from_data(rules.to_data()) == rules
    with pytest.raises(ValueError):
        DurabilityRules("x", on_break="explode")
    with pytest.raises(ValueError):
        WearEvent("hit", [])
    with pytest.raises(ValueError):
        DurabilityRules("x", max_durability={"sword": 0})
