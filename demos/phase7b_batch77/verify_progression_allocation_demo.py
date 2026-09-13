"""Verify Batch 77 using the delivered playable project and canonical RPG save."""
from pathlib import Path
import json

from asteria.editor.model import EditorDocument
from asteria.editor.storage import load_document
from asteria.rpg import ProgressionAllocationRuntime, RpgRuntimeState

root = Path(__file__).resolve().parents[2]
document = EditorDocument()
load_document(document, root / "AsteriaPhase7B_ProgressionAllocationDemo.asteria.json")
project = document.project
save = json.loads((root / "reference_data" / "phase7b_batch77_progression_allocation_demo.save.json").read_text())
state = RpgRuntimeState.from_data(save, project.rpg_database)
allocation = state.progression_allocations["actor:aria"]
actor = project.rpg_database.build_actor("aria")
actor.restore(state.actor_snapshots["aria"])

contribution = allocation.contribution()
resolved = actor.resolve_abilities(
    progression=state.progression,
    allocations=allocation,
    loadout=state.loadouts.get("aria"),
    passives=project.rpg_database.passives,
    evolution_rules=project.rpg_database.ability_evolutions.values(),
)
stats = actor.effective_stats(
    progression=state.progression,
    allocations=allocation,
    loadout=state.loadouts.get("aria"),
    passives=project.rpg_database.passives,
)
tags = actor.effective_tags(
    progression=state.progression,
    allocations=allocation,
    loadout=state.loadouts.get("aria"),
    passives=project.rpg_database.passives,
)

assert allocation.rank("aria_growth_board", "core_training") == 2
assert allocation.balance("ap") == 5
assert allocation.balance("jp") == 2
assert contribution.stat_bonuses["attack"] == 5
assert "battle_instinct" in contribution.unlocked_passives
assert "heal" in resolved.abilities
assert resolved.sources_for("heal")[0].source_kind == "allocation"
assert tags.contains("build.warrior_focus")
assert stats.get("attack") == 43.0
blocked = allocation.preview_allocate("aria_growth_board", "arcane_focus")
assert not blocked.allowed and any("exclusive" in reason for reason in blocked.reasons)

# Round-trip the same allocation state independently as an extra save check.
roundtrip = ProgressionAllocationRuntime.from_data(
    allocation.to_data(), project.rpg_database.progression_graphs.values()
)
assert roundtrip.rank("aria_growth_board", "field_medic") == 1

print("PASS — Asteria Phase 7B Batch 77 Progression Allocation Demo")
print("Project:", project.name)
print("Allocated ranks:", allocation.allocations)
print("Remaining points:", allocation.balances)
print("Unlocked passives:", contribution.unlocked_passives)
print("Allocation abilities:", contribution.granted_abilities)
print("Resolved abilities:", resolved.abilities)
print("Effective attack:", stats.get("attack"))
print("Alternate branch preview:", blocked.reasons)
