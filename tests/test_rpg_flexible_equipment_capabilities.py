import pytest

from asteria.core.lifecycle import LifecycleHookBus
from asteria.rpg import (
    ActorDefinition,
    ClassDefinition,
    EquipmentDefinition,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
    PassiveDefinition,
    RpgActorRuntime,
)


def _runtime(*, actor_tags=(), class_tags=()):
    actor = ActorDefinition(
        "aria",
        tags=actor_tags,
        class_id="fighter",
        base_stats={"attack": 10},
    )
    cls = ClassDefinition("fighter", granted_tags=class_tags)
    return RpgActorRuntime(actor, cls)


def _caps(actor, *, loadout=None, passives=None):
    return actor.effective_tags(loadout=loadout, passives=passives).values()


def test_equipment_requirements_are_explainable_and_not_weapon_enums():
    sword = EquipmentDefinition(
        "great_blade",
        slot="weapon",
        tags=("weapon", "weapon.great_blade"),
        required_capabilities=("proficiency.great_blade",),
    )
    loadout = EquipmentLoadout([EquipmentSlotDefinition("weapon", capacity=8)])
    actor = _runtime(class_tags=("proficiency.sword",))
    item = EquippedItem(sword, instance_id="blade-1")

    result = loadout.check_equip("weapon", item, capabilities=_caps(actor))
    assert result.allowed is False
    assert result.missing_capabilities == ("proficiency.great_blade",)
    assert "missing required capabilities" in result.reasons[0]

    with pytest.raises(ValueError, match="proficiency.great_blade"):
        loadout.equip("weapon", item, capabilities=_caps(actor))


def test_passive_or_other_equipment_can_grant_capability_without_special_engine_rule():
    actor = _runtime()
    passive = PassiveDefinition("weapon_master", tags=("proficiency.great_blade",))
    actor.ability_state.equip_passive("weapon_master")
    great_blade = EquipmentDefinition(
        "great_blade",
        slot="weapon",
        required_capabilities=("proficiency.great_blade",),
    )
    loadout = EquipmentLoadout([EquipmentSlotDefinition("weapon", capacity=None)])
    loadout.equip(
        "weapon",
        EquippedItem(great_blade, instance_id="gb-1"),
        capabilities=_caps(actor, passives={"weapon_master": passive}),
    )
    assert len(loadout.equipped("weapon")) == 1

    # Equipment tags use the same canonical capability vocabulary and can unlock
    # later equipment without a bespoke "weapon mastery" subsystem.
    badge = EquipmentDefinition(
        "training_badge",
        slot="accessory",
        tags=("proficiency.spear",),
    )
    spear = EquipmentDefinition(
        "dragon_spear",
        slot="weapon",
        required_capabilities=("proficiency.spear",),
    )
    mixed = EquipmentLoadout(
        [
            EquipmentSlotDefinition("weapon", capacity=None),
            EquipmentSlotDefinition("accessory", capacity=None),
        ]
    )
    mixed.equip("accessory", EquippedItem(badge, instance_id="badge-1"))
    mixed.equip(
        "weapon",
        EquippedItem(spear, instance_id="spear-1"),
        capabilities=_caps(actor, loadout=mixed),
    )
    assert mixed.equipped("weapon")[0].equipment.equipment_id == "dragon_spear"


def test_any_and_forbidden_capabilities_are_generic_rules():
    relic = EquipmentDefinition(
        "relic_focus",
        slot="focus",
        any_capabilities=("school.fire", "school.ice"),
        forbidden_capabilities=("state.silenced_equipment",),
    )
    assert relic.eligibility(("school.fire",)).allowed
    assert not relic.eligibility(("school.wind",)).allowed
    blocked = relic.eligibility(("school.ice", "state.silenced_equipment"))
    assert not blocked.allowed
    assert blocked.forbidden_capabilities == ("state.silenced_equipment",)


def test_slots_support_many_weapons_armors_and_unlimited_accessories():
    loadout = EquipmentLoadout(
        [
            EquipmentSlotDefinition("weapon", capacity=8),
            EquipmentSlotDefinition("armor", capacity=12),
            EquipmentSlotDefinition("accessory", capacity=None),
        ]
    )
    weapon = EquipmentDefinition("blade", slot="weapon")
    armor = EquipmentDefinition("plate", slot="armor")
    accessory = EquipmentDefinition("ring", slot="accessory")

    for i in range(8):
        loadout.equip("weapon", EquippedItem(weapon, instance_id=f"w{i}"))
    for i in range(12):
        loadout.equip("armor", EquippedItem(armor, instance_id=f"a{i}"))
    for i in range(128):
        loadout.equip("accessory", EquippedItem(accessory, instance_id=f"r{i}"))

    assert len(loadout.equipped("weapon")) == 8
    assert len(loadout.equipped("armor")) == 12
    assert len(loadout.equipped("accessory")) == 128
    with pytest.raises(ValueError, match="slot is full"):
        loadout.equip("weapon", EquippedItem(weapon, instance_id="w8"))


def test_equipment_schema_v1_remains_readable_and_v2_round_trips_requirements():
    legacy = {
        "schema": "asteria.rpg.equipment",
        "version": 1,
        "equipment_id": "old_sword",
        "display_name": "Old Sword",
        "slot": "weapon",
        "tags": ["weapon"],
        "modifiers": [],
        "granted_abilities": [],
        "triggers": [],
        "sockets": [],
    }
    old = EquipmentDefinition.from_data(legacy)
    assert old.required_capabilities == ()
    assert old.eligibility(()).allowed

    modern = EquipmentDefinition(
        "staff",
        slot="weapon",
        required_capabilities=("proficiency.staff",),
        any_capabilities=("school.arcane", "school.divine"),
        forbidden_capabilities=("curse.no_staff",),
    )
    restored = EquipmentDefinition.from_data(modern.to_data())
    assert restored == modern
    assert restored.to_data()["version"] == 3


def test_restricted_equipment_loadout_can_restore_before_actor_context_is_resolved():
    staff = EquipmentDefinition(
        "staff",
        slot="weapon",
        required_capabilities=("proficiency.staff",),
    )
    source = EquipmentLoadout([EquipmentSlotDefinition("weapon", capacity=2)])
    source.equip(
        "weapon",
        EquippedItem(staff, instance_id="staff-1"),
        capabilities=("proficiency.staff",),
    )
    data = source.to_data()
    restored = EquipmentLoadout.from_data(data, equipment={"staff": staff}, attachments={})
    assert restored.equipped("weapon")[0].instance_id == "staff-1"


def test_rejected_equipment_requirement_is_lifecycle_connectable():
    hooks = LifecycleHookBus()
    seen = []
    hooks.subscribe("rpg.equipment.equip_rejected", lambda event: seen.append(event))
    loadout = EquipmentLoadout([EquipmentSlotDefinition("weapon")], hooks=hooks)
    item = EquippedItem(
        EquipmentDefinition(
            "sealed_blade",
            slot="weapon",
            required_capabilities=("license.sealed_blade",),
        ),
        instance_id="sealed-1",
    )
    with pytest.raises(ValueError):
        loadout.equip("weapon", item, capabilities=())
    assert len(seen) == 1
    assert seen[0].data["equipment_id"] == "sealed_blade"
    assert seen[0].data["missing_capabilities"] == ("license.sealed_blade",)


def test_multiple_copies_of_same_equipment_stack_modifiers_by_instance_identity():
    from asteria.gameplay import ModifierOperation, StatBlock, StatModifier

    ring = EquipmentDefinition(
        "power_ring",
        slot="accessory",
        modifiers=(
            StatModifier("power_ring.attack", "attack", ModifierOperation.ADD, 2),
        ),
    )
    loadout = EquipmentLoadout([EquipmentSlotDefinition("accessory", capacity=None)])
    loadout.equip("accessory", EquippedItem(ring, instance_id="ring-a"))
    loadout.equip("accessory", EquippedItem(ring, instance_id="ring-b"))
    result = loadout.modifier_set().evaluate_block(StatBlock({"attack": 10}))
    assert result.get("attack") == 14
