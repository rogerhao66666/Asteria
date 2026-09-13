# Game Start + Skill Tree Editor — v0.158.3

## Canonical New Game / save boundary

Asteria Project schema v8 owns `game_start` (`asteria.game_start` v1). This is authored game-design data, not a Player Save. Normal Editor **Run Project (F6)** clones the Project and materializes a fresh `GameRuntimeSave` from `Project.game_start`. **Run Current Scene (Ctrl+F6)** remains a local developer preview. Player Save JSON remains runtime persistence after the game has started.

The authored start definition can initialize scene/spawn/facing/position, RPG runtime starting state (party, classes, levels/EXP, skills/passives, progression allocations, loadouts, inventory/currencies) and initial event context. Complex Reference RPG now embeds its New Game state directly in `project.asteria.json`.

Developer Playtest Profiles remain supported for automated/stress validation but are removed from the primary Run toolbar/workflow.

## Skill tree authoring

`ProgressionGraphDefinition` v2 keeps gameplay prerequisites canonical while adding editor-only presentation metadata: `editor_view` (`list` or `graph`) and `node_positions`. Existing v1 graphs remain readable.

The Qt RPG authoring surface now provides a functional no-icon Graph View for Skill Trees. It renders prerequisite connections, supports movable nodes, and can persist designer node positions with **Save Graph Layout**. List/data editing remains available against the same canonical graph; there is no second skill-tree model.

The Complex Reference RPG intentionally contains both linear/list-oriented and branching/graph-oriented progression definitions so both styles are exercised.
