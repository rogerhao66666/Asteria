# Asteria Phase 7B Batch 75 — Multi-Class / Job Composition

Version: `v0.75.0a75`

## Purpose

Batch 75 replaces the Phase 7A single-class assumption with arbitrary, project-defined class/job composition while preserving backward compatibility with existing single-class actor data.

## Added

- `ClassAssignment`
  - `class_id`
  - stable `assignment_id`
  - opaque project-defined `role`
  - `enabled`
  - deterministic `priority`
  - per-assignment `progression_track_ids`
  - assignment-level tags
- `ActorDefinition.class_assignments`
- deterministic enabled assignment ordering
- arbitrary simultaneous job/class layers
- actor v2 serialization
- actor v1 backward migration
- RPG database schema v5
- database validation for class and job progression references
- `RpgActorRuntime` support for multiple class definitions
- per-job progression scoping when assignments explicitly declare progression tracks
- legacy Phase 7A progression behavior retained when no assignment declares tracks

## Important semantics

`primary`, `secondary`, `special`, and similar role strings are ordinary project data. The engine does not assign fixed gameplay meaning to them.

There is no two-job engine limit. A project can use one, two, three, or any number of class assignments.

Lower `priority` values contribute first. Ties are resolved deterministically by `assignment_id` and `class_id`.

Class/job contributions remain composed into runtime build state; later Phase 7B batches will formalize complete provenance and resolved build output.

## Demo / playable project

`AsteriaPhase7B_MultiClassDemo.asteria.json`

This is a canonical Asteria project based on the Mac-verified reference world, so it can be opened in the Editor and played normally. The project also contains the Batch 75 RPG database.

Companion runtime save:

`reference_data/phase7b_batch75_multiclass_demo.save.json`

Demo actor Aria uses three simultaneous jobs:
- Warrior — primary
- Scholar — secondary
- Hunter — special

Each job has its own progression track.

Functional verification:

```bash
PYTHONPATH=src python demos/phase7b_batch75/verify_multiclass_demo.py
```

The script loads the same canonical project and runtime save, resolves the actor, and validates the job contributions.

## Validation

- pytest: 340 passed, 4 skipped
- compileall: PASS
- PySide6 leakage into RPG/gameplay/core/events: 0
- pygame leakage into RPG/gameplay/core/events: 0
- demo verification: PASS

## Deferred to following Phase 7B batches

- learned/passive ability provenance and loadout
- weapon proficiency/equipment capability rules
- canonical `ResolvedActorBuild`
- advanced battle rules and scheduling
- dedicated RPG authoring GUI
