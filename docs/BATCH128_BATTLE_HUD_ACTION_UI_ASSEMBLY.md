# Batch 128 — Battle HUD + Action UI Assembly

Batch 128 assembles the presentation systems from Batches 125–127 into one
renderer-ready battle UI view.

Inputs:
- Battle Interaction Architecture
- Battle Information Hierarchy
- Roster Density Policy
- Combatant Visual Runtime

Output:
- member cards with full/compact density
- reserve overflow IDs
- battlefield visual draw metadata
- root/action/overflow interaction surface
- persistent/compact/focused/contextual/overflow information channels

The assembly is intentionally presentation-only. It can be exercised without a
BattleRuntime because gameplay legality/execution remains in canonical systems.

The stress case uses twelve party members: four full cards, four compact cards,
and four overflow members. Twenty sample skills are paged through the existing
action-menu policy rather than rendered at once. Hidden battlefield bodies can
still retain HUD cards, allowing portrait-party layouts. Boss, add, and summon
all share the same battlefield visual pipeline.

This is the first batch where the interaction, information, and combatant visual
policies are combined into a single concrete battle UI frame suitable for a
renderer adapter.
