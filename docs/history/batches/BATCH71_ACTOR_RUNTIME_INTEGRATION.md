# Phase 7 Batch 71 — Actor Runtime Integration + Snapshot Hardening

Version: `v0.71.0a71`

`RpgActorRuntime` now separates three concerns cleanly:

1. definition/class build data,
2. mutable intrinsic runtime state (`stats`, `resources`, `tags`),
3. derived progression/equipment contributions.

Equipment and progression are evaluated on demand. They are never permanently
written into intrinsic actor state, so removing equipment or changing
progression cannot leave stale stats, tags or granted abilities.

New effective views:
- `effective_stats(progression=..., loadout=...)`
- `effective_tags(...)`
- `effective_abilities(...)`

Progression milestone bonuses are cumulative for reached milestones. Equipment
continues to use the generic Phase 6 `ModifierSet`; no RPG stat names are
hardcoded.

`RpgActorSnapshot` v1 stores mutable actor stat/resource/tag state and validates
actor identity on restore.

`RpgRuntimeState` advances to schema v2 and can persist per-actor snapshots.
Runtime-state v1 remains backward readable.

Next: Batch 72 — Phase 7 integration hardening: reward atomicity, item-use
commit seam, lifecycle consistency and save/restore edge cases.
