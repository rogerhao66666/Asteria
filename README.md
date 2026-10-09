# Asteria — Python-first 2D RPG engine and editor

**Canonical specification** (authority order, see `audit/FIVE_DOC_CONSISTENCY_AUDIT.md`):
[`ASTERIA_SPEC.md`](ASTERIA_SPEC.md), [`ASTERIA_ASSET_SPEC.md`](ASTERIA_ASSET_SPEC.md),
[`ASTERIA_ASSET_PIPELINE.md`](ASTERIA_ASSET_PIPELINE.md),
[`ASTERIA_ART_DIRECTION.md`](ASTERIA_ART_DIRECTION.md); implementation state lives in
[`ASTERIA_PROGRESS.md`](ASTERIA_PROGRESS.md). `docs/CANONICAL_SPEC.md` and the batch
documents are historical.

**Current state (2026-10-09):** SPEC-to-code gap audit and closure plan in
[`docs/audits/`](docs/audits/README.md) — start with
[`AUDIT_EXECUTIVE_SUMMARY.md`](docs/audits/AUDIT_EXECUTIVE_SUMMARY.md). The Character
Generator is cancelled and no art assets are bundled; ARPG and demo work are deferred
until the original SPEC is closed.

```bash
python -m pip install -e ".[pygame,editor,mv,dev]"
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

Tests marked `mv_reference` need the git-ignored `local_reference/rpg_maker_mv` and
skip without it.

## Historical Batch 98 state

Current cumulative base: `Asteria_v0.94.0a94_FULL_CANONICAL_REVIEW_DOCS_CONSISTENCY.zip`. Apply Batch 95, Batch 96, Batch 97, and then Batch 98 incremental packages for the current development tree. Phase 7 RPG Toolkit remains frozen at v0.73.0a73; Phase 7B Battle Core remains **FROZEN at Batch 93 / v0.93.0a93**.

Battle Presentation status:

- Batch 94: backend-neutral battle presentation scene/bindings/coordinator.
- Batch 95: combatant Idle/Attack/Hit/KO animation runtime and existing `TextureDraw` integration.
- Batch 96: deterministic resolved combat-feedback state, data-driven interaction/threshold labels, VFX cue queue and audio cue queue.
- Batch 97: presentation-only camera/screen hit feedback plus canonical target-indicator state.
- Batch 98: read-only HP/MP/arbitrary gauge HUD view-state plus project-mapped status icons.

Batch 98 does not recompute or mutate battle resources/states. HUD values mirror canonical `BattleResourceRuntime` and active gameplay states through project-owned presentation profiles. Final bar/icon/text rendering, turn/timeline UI and battle result/reward presentation remain future work.

Historical regression result at Batch 98: 554 passed, 4 skipped.

See [current specification](docs/CANONICAL_SPEC.md), [architecture](docs/ARCHITECTURE.md), [handoff](PROJECT_HANDOFF.md), [next-phase plan](docs/NEXT_PHASE_PLAN.md), and [Batch 98 closure](docs/BATCH98_CLOSURE_AUDIT.md). Historical batch/closure documents remain provenance only and do not reopen frozen ownership boundaries.
