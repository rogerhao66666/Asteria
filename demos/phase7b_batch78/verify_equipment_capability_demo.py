"""Verify Batch 78 using the delivered canonical project and RPG save."""

import json
from pathlib import Path

from asteria.editor.model import EditorDocument
from asteria.editor.storage import load_document
from asteria.rpg import EquipmentLoadout, EquipmentSlotDefinition, EquippedItem, RpgRuntimeState

root = Path(__file__).resolve().parents[2]
document = EditorDocument()
load_document(
    document,
    root / "reference_projects" / "legacy" / "AsteriaPhase7B_EquipmentCapabilityDemo.asteria.json",
)
project = document.project
db = project.rpg_database
state = RpgRuntimeState.from_data(
    json.loads(
        (
            root / "reference_data" / "phase7b_batch78_equipment_capability_demo.save.json"
        ).read_text()
    ),
    db,
)
actor = db.build_actor("aria")
actor.restore(state.actor_snapshots["aria"])
allocation = state.progression_allocations["actor:aria"]

# Validate the real saved loadout.
loadout = state.loadouts["aria"]
assert len(loadout.equipped("weapon")) == 4
assert len(loadout.equipped("armor")) == 2
assert len(loadout.equipped("accessory")) == 4
assert [x.equipment.equipment_id for x in loadout.equipped("weapon")] == [
    "bronze_sword",
    "oak_staff",
    "hunter_bow",
    "titan_blade",
]

# Re-run the capability flow from a fresh loadout so the test proves the
# operation, not merely the persisted result.
fresh = EquipmentLoadout(
    [
        EquipmentSlotDefinition("weapon", capacity=8),
        EquipmentSlotDefinition("armor", capacity=12),
        EquipmentSlotDefinition("accessory", capacity=None),
    ]
)
for iid, eid in (
    ("sword-preview", "bronze_sword"),
    ("staff-preview", "oak_staff"),
    ("bow-preview", "hunter_bow"),
):
    actor.equip_item(
        fresh,
        "weapon",
        EquippedItem(db.equipment[eid], instance_id=iid),
        progression=state.progression,
        allocations=allocation,
        passives=db.passives,
    )

preview = EquippedItem(db.equipment["titan_blade"], instance_id="titan-preview")
blocked = actor.equipment_eligibility(
    fresh,
    "weapon",
    preview,
    progression=state.progression,
    allocations=allocation,
    passives=db.passives,
)
assert not blocked.allowed
assert blocked.missing_capabilities == ("capability.weapon.greatblade",)

actor.equip_item(
    fresh,
    "accessory",
    EquippedItem(db.equipment["mastery_badge"], instance_id="badge-preview"),
    progression=state.progression,
    allocations=allocation,
    passives=db.passives,
)
allowed = actor.equipment_eligibility(
    fresh,
    "weapon",
    preview,
    progression=state.progression,
    allocations=allocation,
    passives=db.passives,
)
assert allowed.allowed
actor.equip_item(
    fresh,
    "weapon",
    preview,
    progression=state.progression,
    allocations=allocation,
    passives=db.passives,
)

stats = actor.effective_stats(
    progression=state.progression,
    allocations=allocation,
    loadout=loadout,
    passives=db.passives,
)
capabilities = actor.effective_capabilities(
    progression=state.progression,
    allocations=allocation,
    loadout=loadout,
    passives=db.passives,
)
assert "capability.weapon.sword" in capabilities
assert "capability.weapon.staff" in capabilities
assert "capability.weapon.bow" in capabilities
assert "capability.weapon.greatblade" in capabilities

print("PASS — Asteria Phase 7B Batch 78 Equipment Capability Demo")
print("Project:", project.name)
print("Saved weapons:", [x.equipment.display_name for x in loadout.equipped("weapon")])
print("Saved armor count:", len(loadout.equipped("armor")))
print("Saved accessory count:", len(loadout.equipped("accessory")))
print("Titan Blade before badge:", blocked.reasons)
print("Titan Blade after badge: allowed")
print("Effective attack:", stats.get("attack"))
print(
    "Capabilities:", tuple(sorted(x for x in capabilities if x.startswith("capability.weapon.")))
)
