# Complex Reference RPG Acceptance — v0.159

The reference project is a short end-to-end acceptance game, not a simple battle demo and not a midgame-save shortcut.

Coverage includes Project Game Start, six-character party, dual-class runtime switching, mixed list/branching ProgressionGraph content, AP allocation, ability-point persistence, passive loadout, multiple weapons, accessories, weapon growth, formation changes, field interaction, weakness, generic Shield/Break composition, generic boost-like Momentum, buffs/debuff/status tags, boss phases, adds, victory rewards, actor EXP/level gains, AP/ability-point gains, in-game Player Save, and in-game Load.

Octopath-like concepts are used only as complexity targets. Engine mechanisms remain generic (`BattleResourceDefinition`, `GaugeCompositionDefinition`, class composition, progression graph, etc.).

## Current run instructions

Open `reference_projects/complex_reference_rpg/project.asteria.json` from the
Editor with **File → Open Project**, then press **Run Project**. Start with
Runtime **New Game**; do not load a test profile as the acceptance entry point.
The Runtime uses **↑ ↓ ← →** for movement, **E/Enter/Space** for interaction
and confirmation, **C** for Character / Build, **F5** for Player Save, and
**Esc** to quit. Character, Skills, and Equipment are separate tabs and accept
mouse clicks as well as arrow-key navigation.

The current automated baseline is **1151 passed, 0 failed**. GUI acceptance
results and the managed macOS child-window limitation are recorded in
[`REAL_MACHINE_ACCEPTANCE_REPORT.md`](../REAL_MACHINE_ACCEPTANCE_REPORT.md).
