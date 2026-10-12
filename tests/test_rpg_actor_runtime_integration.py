from asteria.gameplay import ModifierOperation, StatModifier
from asteria.rpg import (
    ActorDefinition,
    AttachmentDefinition,
    EquipmentDefinition,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
    ProgressionMilestone,
    ProgressionRuntime,
    ProgressionTrackDefinition,
    RpgActorRuntime,
    RpgDatabase,
    RpgRuntimeState,
    SocketDefinition,
)


def setup_runtime():
    actor = ActorDefinition(
        "pilot",
        base_stats={"power": 10, "sensor": 3},
        base_resources={"charge": {"maximum": 100, "current": 70}},
        tags=["organic"],
        abilities=["scan"],
    )
    runtime = RpgActorRuntime(actor)
    track = ProgressionTrackDefinition(
        "mastery",
        milestones=[
            ProgressionMilestone(
                1,
                0,
                stat_bonuses={"power": 2},
                granted_tags=["trained"],
                granted_abilities=["focus"],
            ),
            ProgressionMilestone(
                2,
                10,
                stat_bonuses={"power": 3, "sensor": 1},
                granted_abilities=["burst"],
            ),
        ],
    )
    progression = ProgressionRuntime([track], {"mastery": 10})
    gear = EquipmentDefinition(
        "amp",
        slot="tool",
        tags=["amplifier"],
        modifiers=[StatModifier("amp.power", "power", ModifierOperation.MULTIPLY, 2)],
        granted_abilities=["overdrive"],
        sockets=[SocketDefinition("socket")],
    )
    attachment = AttachmentDefinition("chip", tags=["precision"], granted_abilities=["calibrate"])
    item = EquippedItem(gear, instance_id="amp.001")
    item.attach("socket", attachment)
    loadout = EquipmentLoadout([EquipmentSlotDefinition("tool")])
    loadout.equip("tool", item)
    return actor, runtime, track, progression, gear, attachment, loadout


def test_effective_actor_composes_runtime_progression_and_equipment_without_baking():
    _, runtime, _, progression, _, _, loadout = setup_runtime()
    effective = runtime.effective_stats(progression=progression, loadout=loadout)
    assert effective.get("power") == 30  # (10 + 2 + 3) * 2
    assert effective.get("sensor") == 4
    assert runtime.stats.get("power") == 10
    assert runtime.effective_tags(progression=progression, loadout=loadout).contains_all(
        ["organic", "trained", "amplifier", "precision"]
    )
    assert runtime.effective_abilities(progression=progression, loadout=loadout) == (
        "scan",
        "focus",
        "burst",
        "overdrive",
        "calibrate",
    )


def test_unequip_immediately_removes_derived_contributions():
    _, runtime, _, progression, _, _, loadout = setup_runtime()
    assert runtime.effective_stats(progression=progression, loadout=loadout).get("power") == 30
    loadout.unequip("tool")
    assert runtime.effective_stats(progression=progression, loadout=loadout).get("power") == 15
    assert "overdrive" not in runtime.effective_abilities(progression=progression, loadout=loadout)


def test_actor_snapshot_roundtrip_restores_only_mutable_intrinsic_state():
    actor, runtime, *_ = setup_runtime()
    runtime.stats.add("power", 7)
    runtime.resources.change("charge", -20)
    runtime.tags.add("story.changed")
    raw = runtime.snapshot().to_data()
    restored = RpgActorRuntime(actor).restore(raw)
    assert restored.stats.get("power") == 17
    assert restored.resources.current("charge") == 50
    assert restored.tags.contains("story.changed")


def test_runtime_save_state_v2_carries_actor_snapshots_and_v1_is_backward_readable():
    actor, runtime, track, progression, gear, attachment, loadout = setup_runtime()
    db = RpgDatabase()
    db.add_actor(actor)
    db.add_equipment(gear)
    db.add_attachment(attachment)
    db.add_progression_track(track)
    state = RpgRuntimeState(
        progression=progression,
        loadouts={"pilot": loadout},
        party_actor_ids=["pilot"],
        actor_snapshots={"pilot": runtime.snapshot()},
    )
    raw = state.to_data()
    assert raw["version"] == 8 and raw["actor_snapshots"]["pilot"]["actor_id"] == "pilot"
    restored = RpgRuntimeState.from_data(raw, db)
    actor2 = RpgActorRuntime(actor).restore(restored.actor_snapshots["pilot"])
    assert actor2.resources.current("charge") == 70

    legacy = dict(raw)
    legacy["version"] = 1
    legacy.pop("actor_snapshots")
    legacy.pop("progression_allocations")
    legacy.pop("actor_progression")
    legacy.pop("party_active_actor_ids")
    legacy.pop("party_placements")
    legacy.pop("shop_stock")
    legacy.pop("quests")
    legacy.pop("world")
    legacy.pop("equipment_bag")
    restored_v1 = RpgRuntimeState.from_data(legacy, db)
    assert restored_v1.actor_snapshots == {}
