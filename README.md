# Asteria — Python-first 2D RPG engine and editor

**Canonical specification** (authority order, see `audit/FIVE_DOC_CONSISTENCY_AUDIT.md`):
[`ASTERIA_SPEC.md`](ASTERIA_SPEC.md), [`ASTERIA_ASSET_SPEC.md`](ASTERIA_ASSET_SPEC.md),
[`ASTERIA_ASSET_PIPELINE.md`](ASTERIA_ASSET_PIPELINE.md),
[`ASTERIA_ART_DIRECTION.md`](ASTERIA_ART_DIRECTION.md); implementation state lives in
[`ASTERIA_PROGRESS.md`](ASTERIA_PROGRESS.md). `docs/CANONICAL_SPEC.md` and the batch
documents are historical.

**Current state (2026-10-15):** the engine, the editor and the reference demos are described in
[`docs/ENGINE_HANDBOOK.md`](docs/ENGINE_HANDBOOK.md) (start there); decisions and evidence are in
[`docs/audits/DECISION_LOG.md`](docs/audits/DECISION_LOG.md). The generic multiplayer prototype, including Counter, Movement and a four-player cooperative
Boss adapter, lives in `src/asteria/multiplayer`; its editor workflow and known limits are
documented in [`docs/audits/MULTIPLAYER_DESIGN.md`](docs/audits/MULTIPLAYER_DESIGN.md). It has
project-owned SQLite player state, editable reward templates, and a separate
`reference_projects/diablo_multiplayer_demo` copy. Its opt-in **Run Project** profile uses the project-backed authoritative adapter: original
ECS combat, skills, monsters, NPCs, inventory, equipment and character saves are synchronized.
The four-player sample remains for local/trusted-LAN development. See the
[gameplay template](docs/audits/MULTIPLAYER_GAMEPLAY_TEMPLATE.md) for load steps and editable rules.
The sections below are historical. To continue the work, see [`docs/NEXT_STEPS.md`](docs/NEXT_STEPS.md).

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
