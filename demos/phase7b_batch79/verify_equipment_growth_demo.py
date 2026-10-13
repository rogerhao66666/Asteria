"""Verify Batch 79 using the delivered canonical Asteria project and RPG save."""

import json
from pathlib import Path

from asteria.editor.model import EditorDocument
from asteria.editor.storage import load_document
from asteria.gameplay import StatBlock, TagSet
from asteria.rpg import RpgRuntimeState

root = Path(__file__).resolve().parents[2]
document = EditorDocument()
load_document(document, root / "AsteriaPhase7B_EquipmentGrowthDemo.asteria.json")
project = document.project
db = project.rpg_database
state = RpgRuntimeState.from_data(
    json.loads(
        (root / "reference_data" / "phase7b_batch79_equipment_growth_demo.save.json").read_text()
    ),
    db,
)

loadout = state.loadouts["aria"]
item = next(x for x in loadout.equipped("weapon") if x.instance_id == "blood-demo-1")
assert item.equipment.equipment_id == "blood_blade"
assert item.growth is not None
assert item.growth.counter("xp") == 60
assert item.growth.rank("weapon_level") == 3
assert item.growth.rank("blood_awakening") == 1
assert item.evolution_target_id == "crimson_fang"
assert "awakening" in item.unlocked_socket_ids()
assert item.attachments["awakening"].attachment_id == "growth_ruby"
assert "capability.weapon.blood_awakened" in item.tags()
assert "power_strike" in item.abilities()

# Prove the growth modifiers contribute through the same loadout path used by actors.
base = StatBlock({"attack": 0})
resolved = loadout.modifier_set().evaluate_block(base, tags=TagSet(loadout.tags()))
assert resolved.get("attack") >= 22  # Blood Blade base 12 + growth 2+3+5, plus other saved gear.

# Branch exclusivity remains live after save/load.
item.growth.add_progress("usage_mastery", 25)
blocked = item.growth.preview_unlock("swift_awakening")
assert not blocked.allowed
assert blocked.reasons == ("exclusive with blood_awakening",)

print("PASS — Asteria Phase 7B Batch 79 Equipment Growth Demo")
print("Project:", project.name)
print("Equipment instance:", item.instance_id, item.equipment.display_name)
print("Weapon level rank:", item.growth.rank("weapon_level"))
print("Growth counters:", dict(sorted(item.growth.counters.items())))
print("Unlocked socket:", item.unlocked_socket_ids())
print("Attachment:", item.attachments["awakening"].display_name)
print("Evolution target:", item.evolution_target_id)
print("Growth capability:", "capability.weapon.blood_awakened" in item.tags())
print("Alternate branch:", blocked.reasons)
