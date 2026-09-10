# Phase 7 Batch 70 — RPG Runtime Save State

Version: `v0.70.0a70`

Adds `RpgRuntimeState`, a canonical JSON-native container for mutable,
player-facing RPG state while immutable definitions remain in the Project's
`RpgDatabase`.

Persisted runtime state:
- inventory counts
- progression totals
- per-actor equipment loadouts
- stable equipment instance IDs and socket attachments
- party actor identity/order
- generic currency balances

Restore resolves equipment/attachment references against the canonical
`RpgDatabase` and validates inventory, party, loadout and progression
references. Missing definitions fail loudly rather than silently corrupting a
save.

The party identity collection has no arbitrary engine size cap. A particular
game may impose party rules through project/toolkit policy later.

This is runtime/save data, not Project definition data: Project answers "what
exists"; RpgRuntimeState answers "what has changed during play".

Next: Batch 71 — actor mutable runtime snapshots and derived equipment /
progression integration.
