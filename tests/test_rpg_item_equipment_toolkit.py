from asteria.gameplay import (
    GameplayTrigger,
    ModifierOperation,
    StatModifier,
)
from asteria.rpg import (
    AttachmentDefinition,
    EquipmentDefinition,
    EquippedItem,
    Inventory,
    ItemDefinition,
    RpgDatabase,
    SocketDefinition,
    simple_rpg_database,
)


def test_item_inventory_roundtrip():
    inv = Inventory()
    inv.add("potion", 3)
    inv.remove("potion")
    assert inv.count("potion") == 2
    assert Inventory.from_data(inv.to_data()).to_data() == inv.to_data()
    item = ItemDefinition("potion", "Potion", tags=["item.consumable"], stack_limit=20)
    assert ItemDefinition.from_data(item.to_data()) == item


def test_socket_acceptance_is_tag_driven_not_gem_hardcoded():
    eq = EquipmentDefinition(
        "blade",
        slot="weapon",
        sockets=[SocketDefinition("a", accepted_tags=["attachment.weapon"])],
    )
    gem = AttachmentDefinition("ruby", tags=["attachment.weapon", "attachment.gem"])
    card = AttachmentDefinition("wolf_card", tags=["attachment.weapon", "attachment.card"])
    equipped = EquippedItem(eq)
    equipped.attach("a", gem)
    assert equipped.attachments["a"] == gem
    equipped.attach("a", card)
    assert equipped.attachments["a"] == card


def test_incompatible_or_locked_socket_rejected():
    eq = EquipmentDefinition(
        "armor",
        slot="body",
        sockets=[
            SocketDefinition("armor_only", accepted_tags=["attachment.armor"]),
            SocketDefinition("locked", locked=True),
        ],
    )
    weapon = AttachmentDefinition("ruby", tags=["attachment.weapon"])
    equipped = EquippedItem(eq)
    for socket in ("armor_only", "locked"):
        try:
            equipped.attach(socket, weapon)
        except ValueError:
            pass
        else:
            raise AssertionError("expected socket rejection")


def test_equipment_and_attachments_compose_modifiers_abilities_triggers():
    eq = EquipmentDefinition(
        "sword",
        slot="weapon",
        modifiers=[StatModifier("sword.atk", "attack", ModifierOperation.ADD, 10)],
        granted_abilities=["slash"],
        triggers=[GameplayTrigger("sword.equip", "on_equip")],
        sockets=[SocketDefinition("one")],
    )
    gem = AttachmentDefinition(
        "blood_gem",
        tags=["attachment.gem"],
        modifiers=[StatModifier("gem.atk", "attack", ModifierOperation.ADD, 5)],
        granted_abilities=["drain"],
        triggers=[GameplayTrigger("gem.hit", "on_hit")],
    )
    equipped = EquippedItem(eq)
    equipped.attach("one", gem)
    assert [x.modifier_id for x in equipped.modifiers()] == ["sword.atk", "gem.atk"]
    assert equipped.abilities() == ("slash", "drain")
    assert [x.trigger_id for x in equipped.triggers()] == ["sword.equip", "gem.hit"]


def test_rpg_database_v2_roundtrip_with_equipment_content():
    db = simple_rpg_database()
    restored = RpgDatabase.from_data(db.to_data())
    assert restored.to_data() == db.to_data()
    assert "iron_sword" in restored.equipment
    assert "ruby" in restored.attachments


def test_rpg_database_v1_remains_readable():
    db = simple_rpg_database()
    raw = db.to_data()
    raw["version"] = 1
    raw.pop("items")
    raw.pop("equipment")
    raw.pop("attachments")
    restored = RpgDatabase.from_data(raw)
    assert "hero" in restored.actors
    assert restored.items == {}


def test_simple_rpg_default_equipment_is_ready_but_editable():
    db = simple_rpg_database()
    equipped = EquippedItem(db.equipment["iron_sword"])
    equipped.attach("socket_1", db.attachments["ruby"])
    assert [x.value for x in equipped.modifiers()] == [10.0, 5.0]
