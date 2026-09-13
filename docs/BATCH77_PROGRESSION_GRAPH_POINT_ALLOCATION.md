# Asteria Phase 7B Batch 77 — Progression Graph / Skill Tree / Point Allocation

Version: `v0.77.0a77`

## Purpose

Batch 77 makes skill trees, stat allocation boards, job boards and mastery grids ordinary project-defined progression graphs instead of hardcoded RPG systems.

The engine does **not** require a tree shape and does not hardcode Skill Point, Job Point, Strength, or a fixed number of branches.

## Canonical definitions

- `ProgressionGraphDefinition`
- `ProgressionNodeDefinition`
- `ProgressionNodeRequirement`
- `ProgressionNodeReward`

A node can have arbitrary ranks. Each rank has its own costs and rewards.

Supported reward contributions in this batch:

- stat bonuses
- resource bonuses
- tags
- abilities
- passive unlocks
- capability tags

These rewards are derived contributions; allocating a node does not mutate the actor's intrinsic stats.

## Runtime allocation state

`ProgressionAllocationRuntime` owns mutable allocation state:

- arbitrary point/currency balances (`ap`, `jp`, `mastery`, or project-defined IDs)
- graph/node ranks
- preview before spending
- deterministic allocation
- prerequisite checking
- ALL prerequisites plus an optional ANY prerequisite set
- mutually exclusive branch groups
- rank-dependent costs
- refund/respec with project-selected refund ratio
- dependency protection when refunding a prerequisite
- serialization / restoration
- lifecycle hooks

The runtime exposes explainable rejection reasons such as:

```text
requires core_training rank 2
insufficient ap: requires 2, current 1
exclusive with warrior_focus
```

## Save integration

- `RpgDatabase` schema: v7
- `RpgRuntimeState` schema: v3
- v1/v2 runtime saves remain readable
- RPG database v1-v6 remain readable
- allocation states are scoped by arbitrary save-state keys such as `actor:aria`; the engine does not assume every graph belongs to exactly one actor

## Actor integration

`RpgActorRuntime` can consume an allocation runtime when resolving:

- effective stats
- effective tags/capabilities
- available abilities and provenance

The formal all-source `ResolvedActorBuild` remains scheduled for a later Phase 7B batch.

## Demo

Playable project:

`AsteriaPhase7B_ProgressionAllocationDemo.asteria.json`

Companion RPG save:

`reference_data/phase7b_batch77_progression_allocation_demo.save.json`

Verification:

```bash
PYTHONPATH=src python demos/phase7b_batch77/verify_progression_allocation_demo.py
```

The demo includes:

- 10 AP and 4 JP initial allocation budget
- a 3-rank stat node with increasing cost
- a prerequisite-gated Heal unlock
- a Warrior/Arcane exclusive branch
- Battle Instinct passive unlock
- remaining point persistence
- actor derived stat/ability resolution
- save/load round trip

The same `.asteria.json` remains a normal playable Reference World project and can be opened in the Editor and run with Play.

## Architecture invariants preserved

- no fixed skill-tree topology
- no fixed point currency
- no arbitrary node/rank count cap imposed globally
- no reference-game mechanic hardcoding
- allocation state is save data; graph definitions are project data
- derived rewards do not mutate intrinsic actor state
- meaningful allocation/refund operations emit lifecycle hooks
- backend-neutral; no Qt/pygame dependency in RPG/gameplay/core
