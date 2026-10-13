"""Verify Batch 76 using the same canonical playable project/save delivered to users."""

from pathlib import Path
import json

from asteria.editor.model import EditorDocument
from asteria.editor.storage import load_document
from asteria.rpg import RpgRuntimeState

root = Path(__file__).resolve().parents[2]
document = EditorDocument()
load_document(document, root / "AsteriaPhase7B_AbilityPassiveDemo.asteria.json")
project = document.project
save = json.loads(
    (root / "reference_data" / "phase7b_batch76_ability_passive_demo.save.json").read_text()
)
state = RpgRuntimeState.from_data(save, project.rpg_database)
actor = project.rpg_database.build_actor("aria")
actor.restore(state.actor_snapshots["aria"])

resolved = actor.resolve_abilities(
    progression=state.progression,
    loadout=state.loadouts.get("aria"),
    passives=project.rpg_database.passives,
    evolution_rules=project.rpg_database.ability_evolutions.values(),
)
stats = actor.effective_stats(
    progression=state.progression,
    loadout=state.loadouts.get("aria"),
    passives=project.rpg_database.passives,
)
tags = actor.effective_tags(
    progression=state.progression,
    loadout=state.loadouts.get("aria"),
    passives=project.rpg_database.passives,
)

assert "heal" in resolved.abilities
assert "counter_stance" in resolved.abilities
assert "firestorm" in resolved.abilities
assert "fireball" not in resolved.abilities
assert resolved.sources_for("heal")[0].source_kind == "learned"
assert resolved.sources_for("counter_stance")[0].source_kind == "passive"
assert resolved.sources_for("firestorm")[0].source_kind == "evolution"
assert stats.get("attack") == 38.0
assert tags.contains("passive.counter_ready")

print("PASS — Asteria Phase 7B Batch 76 Ability/Passive Demo")
print("Project:", project.name)
print("Learned:", actor.ability_state.learned_abilities)
print("Passives:", actor.ability_state.active_passives)
print("Resolved abilities:", resolved.abilities)
print("Attack with passive:", stats.get("attack"))
print("Fireball provenance -> Firestorm:", resolved.sources_for("firestorm"))
