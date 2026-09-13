# Batch 102 — Concrete Battle UI Renderer Adapter

Batch 102 adds the first concrete rendering seam for `BattleUiFrame`.

New presentation/runtime-facing pieces:
- `BattleUiTheme`: project-owned palette, font sizing, gauge and target styling.
- `BattleUiRenderer`: deterministic command executor over an adapter-ready `BattleUiFrame`.
- `HeadlessBattleUiBackend`: test backend that records presentation operations.
- `PygameBattleUiBackend`: concrete pygame-ce adapter for panels, gauges, icons, target markers, text, and flash-style screen FX.

The renderer receives presentation commands only. It has no Battle Core dependency and cannot resolve targets, mutate resources/states, advance turns, apply rewards, or decide outcomes.

The pygame adapter keeps authored VFX as a separate responsibility and accepts an optional icon resolver so project assets remain data-driven. Missing icons use a presentation fallback rather than crashing the battle.
