# Batch 105 Closure Audit — Adaptive Party / Combatant Layout

Status: COMPLETE

Scope:
- Added generic `BattlePartyLayoutPolicy`.
- Added expanded/compact/minimal density selection from available UI space.
- Added presentation-only overflow handling.
- Keeps focused/current member visible during overflow.
- Added per-density resource/status detail policies.
- Added explicit presentation placement zones.
- Removed new-code dependency on side-name semantics.
- Preserved older `side_by_member` behavior as compatibility only.
- Integrated placement/focus metadata into `BattleScreenRuntime`.
- No RPG/Battle Core gameplay source changes.

Boundary:
- No canonical member is removed because of UI capacity.
- No gameplay party-size cap was introduced.
- No target, formation, turn, scheduler, resource, state, or action rule is inferred from layout.

Verification:
- Batch 105 focused adaptive-layout tests: 21 passed.
- Full regression: 590 passed, 4 skipped, 0 failed.
- Python compile: PASS.
- JSON parse: PASS.
- ZIP integrity: PASS.
