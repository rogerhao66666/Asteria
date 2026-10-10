import pytest

from asteria.rpg import (
    AttachmentDefinition,
    EquipmentDefinition,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
    SocketDefinition,
)


def definitions(socket_count=2):
    eq = EquipmentDefinition(
        "blade",
        slot="weapon",
        tags=["equipment.weapon"],
        sockets=[SocketDefinition(f"s{i}", accepted_tags=["attachment.weapon"]) for i in range(socket_count)],
    )
    ruby = AttachmentDefinition("ruby", tags=["attachment.weapon", "gem"])
    sapphire = AttachmentDefinition("sapphire", tags=["attachment.weapon", "gem"])
    return eq, ruby, sapphire


def test_same_definition_can_have_distinct_persistent_instances_and_socket_contents():
    eq, ruby, sapphire = definitions()
    a = EquippedItem(eq, instance_id="blade.001")
    a.attach("s0", ruby)
    b = EquippedItem(eq, instance_id="blade.002")
    b.attach("s0", sapphire)
    ra = EquippedItem.from_data(
        a.to_data(),
        equipment={"blade": eq},
        attachments={"ruby": ruby, "sapphire": sapphire},
    )
    rb = EquippedItem.from_data(
        b.to_data(),
        equipment={"blade": eq},
        attachments={"ruby": ruby, "sapphire": sapphire},
    )
    assert ra.instance_id == "blade.001" and ra.attachments["s0"].attachment_id == "ruby"
    assert rb.instance_id == "blade.002" and rb.attachments["s0"].attachment_id == "sapphire"


def test_equipment_definition_has_no_engine_socket_count_cap():
    eq, ruby, _ = definitions(128)
    item = EquippedItem(eq, instance_id="many.sockets")
    for i in range(128):
        item.attach(f"s{i}", ruby)
    assert len(item.attachments) == 128


def test_loadout_roundtrip_preserves_instances_and_attachments():
    eq, ruby, sapphire = definitions()
    loadout = EquipmentLoadout([EquipmentSlotDefinition("weapon", capacity=2)])
    a = EquippedItem(eq, instance_id="a")
    a.attach("s0", ruby)
    b = EquippedItem(eq, instance_id="b")
    b.attach("s1", sapphire)
    loadout.equip("weapon", a)
    loadout.equip("weapon", b)
    raw = loadout.to_data()
    restored = EquipmentLoadout.from_data(
        raw, equipment={"blade": eq}, attachments={"ruby": ruby, "sapphire": sapphire}
    )
    items = restored.equipped("weapon")
    assert [x.instance_id for x in items] == ["a", "b"]
    assert items[0].attachments["s0"].attachment_id == "ruby"
    assert items[1].attachments["s1"].attachment_id == "sapphire"


def test_loadout_rejects_same_instance_twice():
    eq, _, _ = definitions()
    loadout = EquipmentLoadout([EquipmentSlotDefinition("weapon", capacity=2)])
    item = EquippedItem(eq, instance_id="unique")
    loadout.equip("weapon", item)
    with pytest.raises(ValueError, match="already equipped"):
        loadout.equip("weapon", item)


def test_slot_capacity_can_be_explicitly_unlimited():
    eq, _, _ = definitions()
    loadout = EquipmentLoadout([EquipmentSlotDefinition("weapon", capacity=None)])
    for i in range(100):
        loadout.equip("weapon", EquippedItem(eq, instance_id=f"i{i}"))
    assert len(loadout.equipped("weapon")) == 100
    raw = loadout.to_data()
    assert raw["slots"][0]["capacity"] is None
