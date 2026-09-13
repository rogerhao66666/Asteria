# Batch 85 Closure Audit — Combatant Lifecycle / Objectives / Escape

## Closure status

**PASS**

## Implemented

- generic battle-local combatant participation state
- incapacitate/revive/remove with open project state vocabulary
- targetable-but-inactive revival seam
- removed/non-targetable distinction
- compatibility with caller-defined dynamic activity predicates
- runtime summon with owner/generation provenance
- explicit policy for same-round vs next-round summon participation
- atomic formation-slot summon validation
- runtime transform/revert preserving stable identity
- generic objective success/failure composition
- eliminate, survive, protect, and scripted-flag objective primitives
- explicit objectives override legacy elimination fallback
- seeded project-stat-driven escape checks
- escaped-side reporting in `BattleOutcome`
- RpgDatabase schema v13 persistence, v1-v12 backward readability
- combatant lifecycle snapshot seam
- Batch 85 real-window developer harness

## Explicitly deferred

- continuous speed/timeline scheduler: Batch 86
- cast/delay/recovery/priority/interrupt: Batch 87
- multi-hit/combo/cooperative actions: Batch 88
- break/stagger composition: Batch 89
- reaction queue/counter/cover/follow-up: Batch 90
- enemy AI/boss phase runtime: Batch 91
- whole-battle deterministic snapshot/RNG restore: Batch 92
- final battle-core cross-system closure: Batch 93
- polished battle sprites/animations/VFX and RPG GUI: after Battle Core

## Architecture checks

- no HP=0 hardcoded as universal KO rule
- no fixed `KO` state enum
- no fixed victory-only-by-elimination rule when authored objectives exist
- no fixed speed/agility escape stat
- summon/transform use stable battle member identity
- Battle Core remains independent of PySide6 and pygame-ce
- pygame-ce remains confined to the developer harness under `demos/`

## Validation

- full pytest: **444 passed, 4 skipped**
- `compileall`: **PASS**
- deterministic lifecycle/objective/escape demo: **PASS**
- canonical Batch 85 project load + RPG database roundtrip: **PASS**
- backend AST dependency audit (`rpg`, `gameplay`, `core`, `events`): **0 PySide6 / 0 pygame-ce imports**
