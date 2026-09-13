# Batch 94 — Battle Presentation Foundation

Version: `v0.94.0a94`

## Purpose

Start Battle Presentation on top of the frozen Batch 93 Battle Core without creating a second combat model.

## Added

- `asteria.presentation` package.
- Canonical, serializable `BattlePresentationScene`.
- Per-member `BattleCombatantVisual` bindings for sprite sheet, animation clip-set, authored battle anchor/facing/depth, and semantic animation roles (`idle`, `attack`, `hit`, `ko`, plus project-defined roles).
- Backend-neutral `BattlePresentationCoordinator`.
- Deterministic presentation event queue.
- Direct ingestion of existing `PresentationCue` values emitted by `ActionTimelinePlayer`.
- Read-only bridge from existing Battle Core lifecycle hooks into presentation events.

## Boundary

The coordinator does not calculate damage, choose targets, decide weakness/break rules, spend resources, schedule turns, or decide battle results. Those remain owned by the frozen Battle Core. Presentation only observes resolved gameplay and translates it into data that later renderer/audio/UI adapters can consume.

No pygame-ce, PySide6, clock, texture renderer, or editor dependency was introduced into the presentation model.

## Next

Batch 95 should bind Battle Presentation combatants to the existing sprite/animation runtime and add the first coherent Asteria battle reference assets/scenario, including visible Idle/Attack/Hit/KO transitions. UI/VFX/camera layers then build on the same coordinator event stream.
