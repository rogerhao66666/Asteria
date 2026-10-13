from asteria.presentation import EquipmentScreenProfile, EquipmentScreenRuntime
from asteria.rpg.items import (
    AttachmentDefinition,
    EquipmentDefinition,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
    SocketDefinition,
)


def _catalog():
    blade = EquipmentDefinition(
        "blade_alpha",
        "Blade Alpha",
        slot="main",
        tags=("blade", "metal"),
        granted_abilities=("slash",),
        sockets=(SocketDefinition("gem", accepted_tags=("gem",)),),
        required_capabilities=("blade_use",),
    )
    charm = EquipmentDefinition(
        "swift_charm",
        "Swift Charm",
        slot="accessory",
        tags=("charm",),
        granted_abilities=("haste",),
    )
    relic = EquipmentDefinition(
        "relic_core",
        "Relic Core",
        slot="relic_matrix",
        tags=("relic",),
        growth_id="relic_path",
    )
    return blade, charm, relic


def _loadout():
    blade, charm, relic = _catalog()
    gem = AttachmentDefinition("ruby", "Ruby", tags=("gem",))
    equipped_blade = EquippedItem(blade, {"gem": gem}, "blade:01")
    loadout = EquipmentLoadout(
        (
            EquipmentSlotDefinition("main", accepted_tags=("blade",), capacity=1),
            EquipmentSlotDefinition("accessory", accepted_tags=("charm",), capacity=2),
            EquipmentSlotDefinition("relic_matrix", accepted_tags=("relic",), capacity=None),
        )
    )
    loadout.equip("main", equipped_blade, capabilities=("blade_use",))
    return loadout


def test_projects_arbitrary_slots_capacities_and_equipped_items():
    view = EquipmentScreenRuntime().project(_loadout(), _catalog(), capabilities=("blade_use",))
    slots = {x.slot_id: x for x in view.slots}
    assert slots["main"].capacity == 1
    assert slots["accessory"].capacity == 2
    assert slots["relic_matrix"].capacity is None
    assert slots["main"].items[0].equipment_id == "blade_alpha"


def test_projects_socket_attachment_without_mutation():
    loadout = _loadout()
    before = loadout.to_data()
    view = EquipmentScreenRuntime(
        EquipmentScreenProfile(socket_labels={"gem": "Gem Socket"})
    ).project(loadout, _catalog(), capabilities=("blade_use",))
    main = next(x for x in view.slots if x.slot_id == "main")
    socket = main.items[0].sockets[0]
    assert socket.label == "Gem Socket"
    assert socket.attachment_id == "ruby"
    assert socket.locked is False
    assert loadout.to_data() == before


def test_candidate_eligibility_uses_existing_capability_rules_read_only():
    runtime = EquipmentScreenRuntime()
    runtime.project(_loadout(), _catalog(), capabilities=())
    runtime.select_slot("main")
    view = runtime.project(_loadout(), _catalog(), capabilities=())
    blade = next(x for x in view.candidates if x.equipment_id == "blade_alpha")
    assert blade.eligible is False
    assert any("blade_use" in reason for reason in blade.reasons)

    view = runtime.project(_loadout(), _catalog(), capabilities=("blade_use",))
    blade = next(x for x in view.candidates if x.equipment_id == "blade_alpha")
    assert blade.eligible is True


def test_slot_selection_filters_compatibility_without_fixed_slot_names():
    profile = EquipmentScreenProfile(include_incompatible_candidates=False)
    runtime = EquipmentScreenRuntime(profile)
    runtime.project(_loadout(), _catalog(), capabilities=("blade_use",))
    runtime.select_slot("relic_matrix")
    view = runtime.project(_loadout(), _catalog(), capabilities=("blade_use",))
    assert [x.equipment_id for x in view.candidates] == ["relic_core"]


def test_query_and_paging_are_presentation_only():
    catalog = tuple(
        EquipmentDefinition(f"item_{i}", f"Item {i}", slot="main", tags=("blade",))
        for i in range(15)
    )
    profile = EquipmentScreenProfile(page_size=5)
    runtime = EquipmentScreenRuntime(profile)
    runtime.project(_loadout(), catalog)
    assert len(runtime.page(0)) == 5
    assert len(runtime.page(2)) == 5

    runtime.set_query("item_1")
    view = runtime.project(_loadout(), catalog)
    assert all("item_1" in x.equipment_id for x in view.candidates)


def test_labels_are_project_owned():
    profile = EquipmentScreenProfile(
        slot_labels={"main": "Primary Matrix"},
        equipment_labels={"blade_alpha": "Aster Blade"},
    )
    view = EquipmentScreenRuntime(profile).project(
        _loadout(), _catalog(), capabilities=("blade_use",)
    )
    main = next(x for x in view.slots if x.slot_id == "main")
    assert main.label == "Primary Matrix"
    blade = next(x for x in view.candidates if x.equipment_id == "blade_alpha")
    assert blade.label == "Aster Blade"


def test_profile_and_navigation_snapshot_roundtrip():
    profile = EquipmentScreenProfile(
        page_size=3,
        slot_labels={"main": "Main"},
        include_incompatible_candidates=False,
    )
    runtime = EquipmentScreenRuntime(profile)
    runtime.project(_loadout(), _catalog(), capabilities=("blade_use",))
    runtime.select_slot("accessory")
    runtime.set_query("charm")
    snapshot = runtime.snapshot()

    restored = EquipmentScreenRuntime(profile)
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot


def test_no_weapon_armor_or_fixed_slot_assumption():
    profile = EquipmentScreenProfile()
    runtime = EquipmentScreenRuntime(profile)
    loadout = EquipmentLoadout(
        (EquipmentSlotDefinition("sigil_array", accepted_tags=("sigil",), capacity=7),)
    )
    catalog = (EquipmentDefinition("moon_sigil", slot="sigil_array", tags=("sigil",)),)
    view = runtime.project(loadout, catalog)
    assert view.slots[0].slot_id == "sigil_array"
    assert view.slots[0].capacity == 7
    assert view.candidates[0].equipment_id == "moon_sigil"
