# Phase 7 Batch 68 — RPG Cross-reference Validation + Persistent Lifecycle Event Bindings

Version: `v0.68.0a68`

Project schema is now v5.

Lifecycle hook -> Event Program mappings are canonical project data through
`LifecycleEventBinding`. This means a future editor can expose event connections
for any named workflow without creating a battle-only or editor-only event path.

Project validation rejects lifecycle bindings that point to unknown Event
Programs.

`RpgDatabase.validate()` now checks references whose owning definitions are
already canonical inside the RPG database:

- Actor -> Class
- Encounter -> Enemy
- Enemy reward loot -> Item
- Enemy reward progression -> Progression Track

Ability IDs are deliberately not validated here yet because Phase 6
GameplayLibrary definitions are not yet part of canonical Project persistence.
Pretending otherwise would create a false validation boundary.

Project v2-v4 remain backward-readable. v4 projects load with no lifecycle
bindings.

Architectural invariant:

> Any meaningful workflow may expose a lifecycle hook, and hook-to-Event-Program
> connections are canonical project data rather than subsystem-specific glue.

Next: Batch 69 — unique equipment instances / socketed loadout persistence.
