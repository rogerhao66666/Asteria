"""Load the Batch 75 demo project/save and verify multi-job composition.

Run from the repository root:
    PYTHONPATH=src python demos/phase7b_batch75/verify_multiclass_demo.py

The .asteria project can also be opened in Asteria Editor and played as the
normal reference world. This script verifies the RPG data embedded in that
playable project and its companion runtime save.
"""

import json
from pathlib import Path

from asteria.editor.model import EditorDocument
from asteria.editor.storage import load_document
from asteria.rpg import RpgRuntimeState

root = Path(__file__).resolve().parents[2]
document = EditorDocument()
load_document(
    document, root / "reference_projects" / "legacy" / "AsteriaPhase7B_MultiClassDemo.asteria.json"
)
project = document.project
save_data = json.loads(
    (root / "reference_data" / "phase7b_batch75_multiclass_demo.save.json").read_text()
)
state = RpgRuntimeState.from_data(save_data, project.rpg_database)
actor = project.rpg_database.build_actor("aria")
stats = actor.effective_stats(progression=state.progression)

expected = {"attack": 33.0, "defense": 16.0, "magic": 25.0, "speed": 18.0}
actual = {key: stats.get(key) for key in expected}
assert actual == expected, (actual, expected)
assert actor.effective_abilities(progression=state.progression) == (
    "basic_attack",
    "power_strike",
    "fireball",
    "aimed_shot",
)
assert [a.role for a in actor.class_assignments] == ["primary", "secondary", "special"]

print("PASS — Asteria Phase 7B Batch 75 Multi-Class Demo")
print("Project:", project.name)
print("Jobs:", [(a.role, a.class_id) for a in actor.class_assignments])
print("Job ranks:", {k: state.progression.rank(k) for k in state.progression.definitions})
print("Effective stats:", actual)
print("Abilities:", actor.effective_abilities(progression=state.progression))
