# Asteria Project Handoff

## Canonical baseline and verification scope

The sole canonical input is `Asteria_BattlePresentation_Batch94_v0.94.0a94.zip`.
Project version remains `0.94.0a94`. This revision changes documentation only;
Batch 95 is on hold and has not started.

This archive contains only presentation source, five presentation tests,
package metadata, this handoff, and three original documents. It does not contain
core/gameplay/RPG implementations, earlier tests, assets, or original SPEC and
architecture documents. Do not substitute another baseline or reconstruct those
systems. Full-project closure remains blocked until a complete canonical input
is supplied. See [consistency audit](docs/CONSISTENCY_AUDIT.md).

## Current phase status

- Phase 7 RPG Toolkit: historically recorded CLOSURE PASS / FROZEN at
  `v0.73.0a73`. Its systems and persistence milestones are summarized in the
  [current spec](docs/CANONICAL_SPEC.md); their implementations are absent here.
- Phase 7B Battle Core: historically recorded Batch 93 cross-system closure PASS
  and **FROZEN at `v0.93.0a93`**. This freeze checkpoint is not the current archive
  baseline. No frozen semantics may be changed or completed systems redesigned.
- Batch 94 Battle Presentation foundation: scene/combatant visual data,
  backend-neutral coordinator, cue ingestion and lifecycle observation are
  implemented in the included source. Runtime rendering and playable integration
  are not demonstrated by this archive. Historical Batch 94 PASS is not a fresh
  test result for this incomplete distribution.

## Implementation boundaries

Keep mechanism → policy → game-defined rules; no reference-game hardcoding.
Engine validity/determinism and author-owned game rules/balance remain distinct.
Meaningful workflows remain lifecycle/event-connectable. Gameplay meaning and
presentation timelines stay separate. Editor/runtime/data/script APIs should
share canonical data. Gameplay/RPG/core remain backend-neutral.

Do not reopen the recorded Battle Core systems: actor build composition,
battle resources, interaction/outcome rules, statuses, targeting/formations,
lifecycle/summon/transform, objectives/escape, continuous scheduling, advanced
action timing, sequences/co-op actions, gauges, reactions, AI/boss phases/custom
hooks, deterministic RNG/snapshots, or action cost transactions.

See [architecture](docs/ARCHITECTURE.md) for the actual presentation dependency
and event boundaries, and [next-phase plan](docs/NEXT_PHASE_PLAN.md) for deferred
work. Historical `BATCH94_*` documents are preserved verbatim, including their
then-current next-step recommendations; they do not authorize Batch 95.
