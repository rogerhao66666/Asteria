# Asteria Project Handoff

## Canonical baseline

`Asteria Battle Presentation v0.94.0a94`

Phase 7B Battle Core is **FROZEN** after Batch 93 cross-system closure.

## Do not redesign

Do not reopen Batches 75–93 speculatively. The current RPG/Battle Core already provides generic actor build composition, battle resources, interaction/outcome rules, status/state, targeting/formations, lifecycle/summon/transform, objectives/escape, continuous scheduling, advanced action timing, sequences/co-op actions, generic gauge composition, reactions, AI/boss phases/custom battle hooks, deterministic RNG/snapshot, and action cost transactions.

## Next phase

Battle Presentation has started. Batch 94 established the backend-neutral Battle Scene/presentation coordinator foundation. Next: sprite/animation runtime binding and coherent reference battle assets.

Remaining Battle Presentation:

- Battle Scene/presentation coordinator
- player/enemy sprites and Idle/Attack/Hit/KO animation
- Action/Ability Timeline presentation tracks
- VFX, damage numbers, status/weakness/break feedback
- camera impact feedback and screen effects
- HP/MP/gauge/status + timeline/turn UI
- targeting indicators
- battle result/reward presentation
- coherent original Asteria reference battle assets

Then build RPG GUI + playable vertical slice and perform the first broad user Mac interaction/playtest.

## Architecture invariants

- Simple things simple; complex things possible.
- Mechanism → policy → game-defined rules.
- Engine guarantees valid deterministic execution; authors own game-rule correctness/balance.
- No reference-game hardcoding.
- Any meaningful workflow remains lifecycle/event-connectable.
- Ability gameplay meaning and presentation Timeline remain separate.
- Editor/runtime/data/script APIs share canonical data rather than duplicate worlds.
- Backend-neutral gameplay/RPG/core; pygame-ce remains an implementation detail.
