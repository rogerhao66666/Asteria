# Asteria v0.158.0a158 — Editor + RPG Runtime Milestone

Current canonical state: **Batch 158 FROZEN / FINAL CLOSURE PASS**. See
[`docs/BATCH158_EDITOR_RPG_RUNTIME_FINAL_CLOSURE_AUDIT.md`](docs/BATCH158_EDITOR_RPG_RUNTIME_FINAL_CLOSURE_AUDIT.md)
for the verified architecture, schema, editor, runtime, save-state, and full-play
coverage.

## Historical Batch 98 state

Current cumulative base: `Asteria_v0.94.0a94_FULL_CANONICAL_REVIEW_DOCS_CONSISTENCY.zip`. Apply Batch 95, Batch 96, Batch 97, and then Batch 98 incremental packages for the current development tree. Phase 7 RPG Toolkit remains frozen at v0.73.0a73; Phase 7B Battle Core remains **FROZEN at Batch 93 / v0.93.0a93**.

Battle Presentation status:

- Batch 94: backend-neutral battle presentation scene/bindings/coordinator.
- Batch 95: combatant Idle/Attack/Hit/KO animation runtime and existing `TextureDraw` integration.
- Batch 96: deterministic resolved combat-feedback state, data-driven interaction/threshold labels, VFX cue queue and audio cue queue.
- Batch 97: presentation-only camera/screen hit feedback plus canonical target-indicator state.
- Batch 98: read-only HP/MP/arbitrary gauge HUD view-state plus project-mapped status icons.

Batch 98 does not recompute or mutate battle resources/states. HUD values mirror canonical `BattleResourceRuntime` and active gameplay states through project-owned presentation profiles. Final bar/icon/text rendering, turn/timeline UI and battle result/reward presentation remain future work.

Current regression result: **554 passed, 4 skipped, 0 failed**. The four skips are optional PySide6 editor UI tests unavailable in this environment.

See [current specification](docs/CANONICAL_SPEC.md), [architecture](docs/ARCHITECTURE.md), [handoff](PROJECT_HANDOFF.md), [next-phase plan](docs/NEXT_PHASE_PLAN.md), and [Batch 98 closure](docs/BATCH98_CLOSURE_AUDIT.md). Historical batch/closure documents remain provenance only and do not reopen frozen ownership boundaries.
