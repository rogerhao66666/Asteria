# Batch 138 — UI + Renderer / Animation Stress Test

Batch 138 stress-tests the backend-neutral presentation path under deliberately
dense RPG battle load.

Reference load:
- 12 party members;
- boss + 4 adds + 1 summon;
- 80 action UI entries;
- 96 status/resource indicators;
- 3000 VFX draws;
- 1000 explicitly offscreen draws;
- 5000 authored motion beats;
- 512 reusable transient objects.

Evidence-backed tuning:
`BattleRenderVisibilityCuller.resolve()` and `BattleRenderBatcher.build()` were
materializing `tuple(draws)` on every call. Under several thousand draws this
creates an unnecessary full input-container copy in the per-frame hot path.
Batch 138 removes those copies and validates both APIs directly against
generators, preserving behavior while avoiding that allocation.

The stress harness verifies:
- culling occurs before batch planning;
- atlas/material/layer grouping substantially reduces planning groups;
- transient VFX/popups remain capacity-bounded and reusable;
- hot assets can be required/loaded before the scene becomes active;
- the event-driven motion clock releases 5000 authored beats even from one
  coarse host update;
- frame-budget accounting identifies over-budget synthetic frames.

Wall-clock planner time is recorded for diagnostics only and is deliberately not
used as a CI pass/fail threshold. Machine, Python build and backend differences
make such a threshold misleading.

This batch still does **not** claim real stable 60 FPS. GPU uploads, actual draw
calls, texture atlas effectiveness, driver behavior and asset costs require the
later concrete renderer/hardware validation.
