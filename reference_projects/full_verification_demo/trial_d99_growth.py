"""D99: every job raises VIT and MP each level (both Grow with Level), and the jobs' roles
use the words the game reads: ``primary`` (the main job) and ``secondary`` (a sub job)."""

import json
from pathlib import Path

path = Path("reference_projects/full_verification_demo/project.asteria.json")
raw = json.loads(path.read_text())
db = raw["rpg_database"]
HP, MP = "vitality", "technique"
for job in db["classes"]:
    growth = dict(job.get("level_growth") or {})
    health = float((job.get("resource_growth") or {}).get(HP, 80.0))
    # sturdier jobs grow more VIT; casters more MP (their INT growth)
    growth["vit"] = round(0.3 + health / 160, 2)
    job["level_growth"] = dict(sorted(growth.items()))
    mana = round(2.0 + growth.get("int", 0.0) * 5.0, 1)
    job["resource_growth"] = dict(sorted({**job.get("resource_growth", {}), MP: mana}.items()))
ROLES = {"main": "primary", "sub": "secondary"}
for actor in db["actors"]:
    for assignment in actor["class_assignments"]:
        assignment["role"] = ROLES.get(assignment["role"], assignment["role"])
path.write_text(json.dumps(raw, indent=2) + "\n")
