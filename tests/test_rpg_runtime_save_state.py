import pytest

from asteria.rpg import (
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
    Inventory,
    ProgressionRuntime,
    RpgRuntimeState,
    simple_rpg_database,
)


def make_state():
    db = simple_rpg_database()
    inventory = Inventory()
    inventory.add("potion", 3)
    progression = ProgressionRuntime(db.progression_tracks.values())
    progression.add("level", 10)
    loadout = EquipmentLoadout([EquipmentSlotDefinition("weapon")])
    sword = EquippedItem(db.equipment["iron_sword"], instance_id="hero.sword.001")
    sword.attach("socket_1", db.attachments["ruby"])
    loadout.equip("weapon", sword)
    state = RpgRuntimeState(
        inventory=inventory,
        progression=progression,
        loadouts={"hero": loadout},
        party_actor_ids=["hero"],
        currencies={"gold": 123},
    )
    return db, state


def test_runtime_state_roundtrip_restores_player_rpg_state():
    db, state = make_state()
    raw = state.to_data()
    restored = RpgRuntimeState.from_data(raw, db)
    assert restored.inventory.count("potion") == 3
    assert restored.progression.total("level") == 10
    assert restored.party_actor_ids == ("hero",)
    assert restored.currencies["gold"] == 123
    sword = restored.loadouts["hero"].equipped("weapon")[0]
    assert sword.instance_id == "hero.sword.001"
    assert sword.attachments["socket_1"].attachment_id == "ruby"


def test_runtime_state_rejects_unknown_inventory_definition():
    db, state = make_state()
    raw = state.to_data()
    raw["inventory"]["counts"]["missing"] = 1
    with pytest.raises(ValueError, match="unknown item"):
        RpgRuntimeState.from_data(raw, db)


def test_runtime_state_rejects_unknown_party_actor():
    db, state = make_state()
    raw = state.to_data()
    raw["party_actor_ids"].append("missing")
    with pytest.raises(ValueError, match="unknown actor"):
        RpgRuntimeState.from_data(raw, db)


def test_runtime_state_rejects_unknown_equipment_reference():
    db, state = make_state()
    raw = state.to_data()
    raw["loadouts"]["hero"]["equipped"]["weapon"][0]["equipment_id"] = "missing"
    with pytest.raises(KeyError, match="unknown equipment"):
        RpgRuntimeState.from_data(raw, db)


def test_runtime_state_has_no_party_size_engine_cap():
    db, state = make_state()
    # Party identity collection itself is arbitrary-length. Use valid actor IDs by
    # constructing a database with many unique actors.
    from asteria.rpg import ActorDefinition

    ids = ["hero"]
    for i in range(100):
        actor_id = f"guest_{i}"
        db.add_actor(ActorDefinition(actor_id))
        ids.append(actor_id)
    state.party_actor_ids = tuple(ids)
    assert state.validate(db)
    assert len(state.party_actor_ids) == 101
