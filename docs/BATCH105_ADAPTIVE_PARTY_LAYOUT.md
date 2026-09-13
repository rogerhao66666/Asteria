# Batch 105 — Adaptive Party / Combatant Layout

Batch 105 makes arbitrary party/combatant counts a first-class presentation concern without adding gameplay caps.

## New presentation policy

`BattlePartyLayoutPolicy` controls visual density only:

- expanded rows for small groups,
- compact rows when screen space becomes tighter,
- minimal rows for large groups,
- overflow summaries when even minimal rows cannot fit,
- focused/current combatant retention during overflow,
- per-density resource/status detail limits.

The complete canonical member list remains untouched. Hidden members are hidden only from the current HUD viewport.

## Generic placement

The new path accepts explicit `placement_by_member` metadata such as `left`, `right`, or `center`. These are presentation zones, not gameplay sides.

`BattleScreenRuntime` accepts optional `placement_by_side` project configuration. If a project does not configure it, distinct canonical side IDs are assigned to left/right zones deterministically without interpreting names such as `heroes` or `enemies`.

The old `side_by_member` behavior remains as a compatibility path for older Batch 101–104 callers.

## Adaptive detail

When density decreases, presentation reduces information rather than modifying gameplay:

- expanded: full configured resource/status detail,
- compact: highest-priority configured resources/statuses,
- minimal: only the most important resource plus member identity,
- overflow: a `+N` summary while preserving the focused member.

Resource priority comes from the generic Batch 104 presentation policy.

No Battle Core party size, side model, resource count, action count, or formation rule is changed.
