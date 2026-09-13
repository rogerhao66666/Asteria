# Asteria Next Phase Plan

## Current checkpoint

Sole canonical input: `Asteria_BattlePresentation_Batch94_v0.94.0a94.zip`.
This is a documentation consistency revision at `v0.94.0a94`, not Batch 95.

| Area | Current status | Evidence available here |
| --- | --- | --- |
| Phase 5 Event VM / Dialogue | Recorded FROZEN at v0.49.0a49 | Prior plan only; implementation absent |
| Phase 6 Generic Gameplay | Recorded FROZEN at v0.59.0a59 | Prior plan only; implementation absent |
| Phase 7 RPG Toolkit | Recorded CLOSURE PASS / FROZEN at v0.73.0a73 | Prior plan only; implementation absent |
| Phase 7B Battle Core | Recorded Batch 93 closure PASS / FROZEN at v0.93.0a93 | Supplied handoff and Batch 94 records; implementation absent |
| Batch 94 Battle Presentation | Data/coordinator foundation implemented | Included presentation source and five test definitions; execution blocked |
| Batch 95 | ON HOLD — not started | Current user instruction |

Earlier batch-by-batch “Next” instructions are superseded in this active plan.
No Phase 5, 6, or 7 implementation work is restarted. Phase 8 ARPG is not the
immediate next phase. See [current spec](CANONICAL_SPEC.md) for RPG milestones.

## Foundation already delivered in Batch 94

- Scene schema version 1 with background/camera identifiers and combatant visuals.
- Sprite-sheet/clip-set identifiers, anchors/facing/depth and semantic role mapping.
- Backend-neutral ordered event queue with scene start/finish and custom events.
- Ingestion of supplied presentation cues and observation of selected battle hooks.

These are data and integration seams. They are not a renderer, automatic
Idle/Attack/Hit/KO playback, full timeline runtime integration, or a playable battle.
Do not list the scene/coordinator foundation as unimplemented remaining work.

## Immediate closure gate

Audit the files actually supplied and preserve source/tests and historical batch
records. The archive omits core/gameplay dependencies and earlier specs/tests;
full-system verification requires a complete user-supplied canonical input.
Do not merge in a different baseline, fabricate missing systems, or use test
stubs to claim closure. See [audit](CONSISTENCY_AUDIT.md) for exact checks.

## Deferred roadmap — requires a later instruction

Batch 95 remains on hold. The historical candidate is sprite/animation runtime
binding plus coherent original Asteria battle reference assets/scenario and
visible Idle/Attack/Hit/KO transitions. Its implementation has not begun here.

Subsequent presentation work may include runtime Action/Ability Timeline track
integration; VFX and damage/status/weakness/break feedback; camera/screen effects;
target indicators; HP/MP/gauge/status and turn/timeline UI; result/reward displays.
All adapters must consume resolved gameplay without duplicating Battle Core.

After presentation, the recorded direction is RPG GUI plus a playable vertical
slice and the first broad user Mac interaction/playtest. These remain future
work, not completed or verified features. Do not redesign completed RPG systems
or change frozen Battle Core semantics during this documentation revision.
