"""Verify Batch 80 against one canonical Project + RPG save."""

from pathlib import Path
import json

from asteria.editor.model import EditorDocument
from asteria.editor.storage import load_document
from asteria.rpg import RpgRuntimeState, resolve_actor_from_state

root = Path(__file__).resolve().parents[2]
document = EditorDocument()
load_document(document, root / "AsteriaPhase7B_ResolvedBuildDemo.asteria.json")
project = document.project
db = project.rpg_database
state = RpgRuntimeState.from_data(
    json.loads(
        (root / "reference_data" / "phase7b_batch80_resolved_build_demo.save.json").read_text()
    ),
    db,
)
build = resolve_actor_from_state("aria", db, state)

assert build.actor_id == "aria"
assert len(build.class_assignment_ids) == 3
assert "firestorm" in build.abilities
assert "power_strike" in build.abilities
assert "capability.weapon.blood_awakened" in build.capabilities
assert "blood-demo-1" in build.equipment_instance_ids
assert build.stats.get("attack") > 30
assert build.ability_sources("power_strike")

print("PASS — Asteria Phase 7B Batch 80 Canonical Resolved Actor Build Demo")
print("Project:", project.name)
print("Actor:", build.actor_id)
print("Classes:", build.class_assignment_ids)
print("Equipment instances:", build.equipment_instance_ids)
print("Effective stats:", build.stats.to_data()["values"])
print("Capabilities:", [x for x in build.capabilities if x.startswith("capability.")])
print("Abilities:", build.abilities)
print(
    "Power Strike sources:",
    [(x.source_kind, x.source_id) for x in build.ability_sources("power_strike")],
)
