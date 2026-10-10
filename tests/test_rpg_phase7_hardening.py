import pytest

from asteria.core import LifecycleHookBus
from asteria.gameplay import ResourcePool, StatBlock, TagSet
from asteria.rpg import (
    AttachmentDefinition,
    EquipmentDefinition,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
    Inventory,
    ItemDefinition,
    ProgressionMilestone,
    ProgressionRuntime,
    ProgressionTrackDefinition,
    RewardRoll,
    RewardRuntime,
    SocketDefinition,
    use_inventory_item,
)


def test_public_replace_seams_preserve_identity_and_replace_contents():
    stats = StatBlock({"x": 1})
    same_stats = id(stats)
    stats.replace_from(StatBlock({"y": 2}))
    assert id(stats) == same_stats and stats.names() == ("y",) and stats.get("y") == 2

    resources = ResourcePool()
    resources.define("energy", 10, current=4)
    same_resources = id(resources)
    other = ResourcePool()
    other.define("heat", 20, current=7)
    resources.replace_from(other)
    assert id(resources) == same_resources and resources.names() == ("heat",) and resources.current("heat") == 7

    tags = TagSet(["a"])
    same_tags = id(tags)
    tags.replace_from(TagSet(["b"]))
    assert id(tags) == same_tags and tags.values() == ("b",)


def test_item_use_no_longer_requires_private_storage_commit():
    inventory = Inventory()
    inventory.add("empty", 1)
    item = ItemDefinition("empty")
    stats = StatBlock({"x": 1})
    resources = ResourcePool()
    resources.define("meter", 1)
    tags = TagSet(["base"])
    result = use_inventory_item(inventory, item, stats, resources, tags)
    assert result.used and inventory.count("empty") == 0


def test_reward_validation_is_atomic_before_any_mutation():
    track = ProgressionTrackDefinition("xp", milestones=[ProgressionMilestone(1, 0)])
    progression = ProgressionRuntime([track], {"xp": 3})
    inventory = Inventory()
    inventory.add("potion", 2)
    currencies = {"gold": 5.0}
    runtime = RewardRuntime(inventory=inventory, progression=progression, currencies=currencies)

    with pytest.raises(KeyError, match="unknown progression"):
        runtime.apply(RewardRoll({"gold": 10}, {"missing": 1}, {"potion": 1}))

    assert currencies == {"gold": 5.0}
    assert progression.total("xp") == 3
    assert inventory.count("potion") == 2


def test_reward_roll_rejects_invalid_negative_values_before_mutation():
    track = ProgressionTrackDefinition("xp", milestones=[ProgressionMilestone(1, 0)])
    progression = ProgressionRuntime([track])
    currencies = {"gold": 5.0}
    runtime = RewardRuntime(progression=progression, currencies=currencies)
    with pytest.raises(ValueError, match="currency"):
        runtime.apply(RewardRoll({"gold": -1}, {}, {}))
    assert currencies == {"gold": 5.0}


def test_reward_rolls_back_state_if_lifecycle_subscriber_raises_mid_commit():
    track = ProgressionTrackDefinition("xp", milestones=[ProgressionMilestone(1, 0)])
    hooks = LifecycleHookBus()

    def explode(event):
        raise RuntimeError("observer failed")

    hooks.subscribe("rpg.progression.after_add", explode)
    progression = ProgressionRuntime([track], hooks=hooks)
    inventory = Inventory()
    inventory.add("potion", 1)
    currencies = {"gold": 2.0}
    runtime = RewardRuntime(inventory=inventory, progression=progression, currencies=currencies, hooks=hooks)

    with pytest.raises(RuntimeError, match="observer failed"):
        runtime.apply(RewardRoll({"gold": 8}, {"xp": 4}, {"potion": 2}))

    assert currencies == {"gold": 2.0}
    assert progression.total("xp") == 0
    assert inventory.count("potion") == 1


def test_equipment_lifecycle_hook_exposes_stable_instance_identity():
    hooks = LifecycleHookBus()
    events = []
    hooks.subscribe("rpg.equipment.after_equip", lambda event: events.append(event))
    eq = EquipmentDefinition("tool", slot="tool")
    item = EquippedItem(eq, instance_id="tool.unique.7")
    loadout = EquipmentLoadout([EquipmentSlotDefinition("tool")], hooks=hooks)
    loadout.equip("tool", item)
    assert events[0].data["instance_id"] == "tool.unique.7"
    assert events[0].data["equipment_id"] == "tool"


def test_equipment_socket_collection_remains_uncapped_by_engine():
    sockets = [SocketDefinition(f"s{i}") for i in range(256)]
    eq = EquipmentDefinition("matrix", slot="custom", sockets=sockets)
    attachment = AttachmentDefinition("node")
    item = EquippedItem(eq, instance_id="matrix.1")
    for socket in sockets:
        item.attach(socket.socket_id, attachment)
    assert len(item.attachments) == 256
