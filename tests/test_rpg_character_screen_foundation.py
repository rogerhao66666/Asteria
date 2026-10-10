from asteria.gameplay import ResourcePool, StatBlock, TagSet
from asteria.presentation import (
    CharacterScreenProfile,
    CharacterScreenRuntime,
)
from asteria.rpg.ability_build import AbilityGrant
from asteria.rpg.items import (
    EquipmentDefinition,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
)
from asteria.rpg.progression import ProgressionMilestone, ProgressionRuntime, ProgressionTrackDefinition
from asteria.rpg.resolved_build import ResolvedActorBuild


def _build():
    resources = ResourcePool()
    resources.define("life", 120, current=90)
    resources.define("focus", 8, current=3)
    return ResolvedActorBuild(
        actor_id="aria",
        stats=StatBlock({"power": 17, "speed": 23, "guard": 9}),
        resources=resources,
        tags=TagSet(("human", "alchemist")),
        capabilities=("alchemy", "light_armor"),
        abilities=("quick_mix", "dash"),
        ability_grants=(
            AbilityGrant("quick_mix", "class", "chemist"),
            AbilityGrant("dash", "equipment", "boots:01"),
        ),
        active_passives=("careful_measure",),
        class_assignment_ids=("chemist:primary", "scout:secondary"),
        equipment_instance_ids=("blade:01", "boots:01"),
        triggers=(),
        contributions=(),
    )


def _loadout():
    loadout = EquipmentLoadout(
        (
            EquipmentSlotDefinition("main_hand", capacity=1),
            EquipmentSlotDefinition("accessory", capacity=2),
        )
    )
    blade = EquipmentDefinition("bronze_blade", "Bronze Blade", slot="main_hand")
    charm = EquipmentDefinition("swift_charm", "Swift Charm", slot="accessory")
    loadout.equip("main_hand", EquippedItem(blade, instance_id="blade:01"), validate_requirements=False)
    loadout.equip("accessory", EquippedItem(charm, instance_id="charm:01"), validate_requirements=False)
    return loadout


def _progression():
    track = ProgressionTrackDefinition(
        "chemist_mastery",
        "Chemist Mastery",
        milestones=(
            ProgressionMilestone(1, 0),
            ProgressionMilestone(2, 100),
            ProgressionMilestone(3, 250),
        ),
    )
    return ProgressionRuntime((track,), totals={"chemist_mastery": 135})


def test_character_screen_projects_canonical_resolved_build_without_mutation():
    build = _build()
    before = build.to_summary_data()
    runtime = CharacterScreenRuntime()
    view = runtime.project(build, display_name="Aria")

    assert view.actor_id == "aria"
    assert view.display_name == "Aria"
    assert {x.stat_id for x in view.stats} == {"power", "speed", "guard"}
    assert {x.resource_id for x in view.resources} == {"life", "focus"}
    assert view.active_passives == ("careful_measure",)
    assert view.class_assignment_ids == ("chemist:primary", "scout:secondary")
    assert build.to_summary_data() == before


def test_profile_controls_labels_resource_roles_and_sections():
    profile = CharacterScreenProfile(
        section_order=("overview", "resources", "abilities", "equipment"),
        hidden_sections=("overview",),
        stat_labels={"power": "PWR"},
        resource_labels={"focus": "Focus"},
        resource_presentations={"focus": "pips"},
        ability_labels={"quick_mix": "Quick Mix"},
    )
    view = CharacterScreenRuntime(profile).project(_build())
    assert [x.section_id for x in view.sections] == ["resources", "abilities", "equipment"]
    focus = next(x for x in view.resources if x.resource_id == "focus")
    assert focus.label == "Focus"
    assert focus.presentation == "pips"
    quick_mix = next(x for x in view.abilities if x.ability_id == "quick_mix")
    assert quick_mix.label == "Quick Mix"


def test_equipment_projection_supports_arbitrary_slot_names_and_capacities():
    profile = CharacterScreenProfile(
        slot_labels={"main_hand": "Primary", "accessory": "Charm Slots"},
        equipment_labels={"bronze_blade": "Bronze Blade", "swift_charm": "Swift Charm"},
    )
    view = CharacterScreenRuntime(profile).project(_build(), loadout=_loadout())
    slots = {x.slot_id: x for x in view.equipment}

    assert slots["main_hand"].label == "Primary"
    assert slots["main_hand"].capacity == 1
    assert slots["main_hand"].items[0].label == "Bronze Blade"
    assert slots["accessory"].capacity == 2
    assert slots["accessory"].items[0].equipment_id == "swift_charm"


def test_abilities_keep_provenance_from_resolved_build():
    view = CharacterScreenRuntime().project(_build())
    quick_mix = next(x for x in view.abilities if x.ability_id == "quick_mix")
    dash = next(x for x in view.abilities if x.ability_id == "dash")
    assert quick_mix.source_labels == ("class:chemist",)
    assert dash.source_labels == ("equipment:boots:01",)


def test_progression_projection_supports_arbitrary_tracks():
    profile = CharacterScreenProfile(progression_labels={"chemist_mastery": "Mixture Mastery"})
    view = CharacterScreenRuntime(profile).project(_build(), progression=_progression())
    track = view.progression[0]
    assert track.track_id == "chemist_mastery"
    assert track.label == "Mixture Mastery"
    assert track.total == 135
    assert track.rank == 2


def test_snapshot_restore_is_deterministic():
    profile = CharacterScreenProfile(
        resource_presentations={"focus": "pips"},
        equipment_labels={"bronze_blade": "Bronze Blade", "swift_charm": "Swift Charm"},
    )
    runtime = CharacterScreenRuntime(profile)
    runtime.project(_build(), loadout=_loadout(), progression=_progression())
    snapshot = runtime.snapshot()

    restored = CharacterScreenRuntime(profile)
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot


def test_profile_roundtrip_is_project_owned():
    profile = CharacterScreenProfile(
        section_order=("overview", "equipment", "abilities"),
        hidden_sections=("status",),
        stat_labels={"speed": "SPD"},
        resource_labels={"life": "Vitality"},
        resource_presentations={"life": "ring"},
        slot_labels={"main_hand": "Weapon"},
        equipment_labels={"bronze_blade": "Bronze Blade"},
        ability_labels={"dash": "Dash"},
        progression_labels={"chemist_mastery": "Mastery"},
    )
    assert CharacterScreenProfile.from_data(profile.to_data()) == profile


def test_no_fixed_hp_mp_or_weapon_slot_requirement():
    profile = CharacterScreenProfile(
        resource_presentations={"resolve": "ring", "heat": "number"},
        slot_labels={"relic_matrix": "Relic Matrix"},
    )
    resources = ResourcePool()
    resources.define("resolve", 10, current=7)
    resources.define("heat", 100, current=42)
    build = ResolvedActorBuild(
        "custom",
        StatBlock({"tempo": 12}),
        resources,
        TagSet(()),
        (),
        (),
        (),
        (),
        (),
        (),
        (),
        (),
    )
    loadout = EquipmentLoadout((EquipmentSlotDefinition("relic_matrix", capacity=None),))
    view = CharacterScreenRuntime(profile).project(build, loadout=loadout)
    assert {x.resource_id for x in view.resources} == {"resolve", "heat"}
    assert view.equipment[0].slot_id == "relic_matrix"
    assert view.equipment[0].capacity is None


def test_section_navigation_is_presentation_only_and_snapshot_safe():
    build = _build()
    before = build.to_summary_data()
    runtime = CharacterScreenRuntime()
    runtime.project(build)
    assert runtime.view.selected_section_id == "overview"
    runtime.select_section("abilities")
    assert runtime.view.selected_section_id == "abilities"
    assert build.to_summary_data() == before

    snapshot = runtime.snapshot()
    restored = CharacterScreenRuntime()
    restored.restore(snapshot)
    assert restored.view.selected_section_id == "abilities"
    assert restored.snapshot() == snapshot
