# Batch 101 — Unified Battle UI Composition

Batch 101 introduces `BattleUiComposer`, a backend-neutral composition layer that turns the Battle Presentation view-state delivered by Batches 94–100 into one adapter-ready `BattleUiFrame`.

The composed frame contains:
- existing combatant `TextureDraw` values,
- HUD panels,
- text commands,
- gauge bars,
- status icons,
- timeline entries,
- cast progress text,
- floating resolved values,
- feedback labels,
- target markers,
- VFX/screen-FX metadata,
- battle-result overlay content.

`BattleUiComposer` owns layout only. It does not read or mutate Battle Core, advance turns, resolve targets, change resources, apply states/rewards, roll loot, or determine battle outcome. Side placement is caller-supplied presentation data rather than inferred gameplay semantics.

The output remains renderer-neutral so Pygame, Qt, or future render backends can consume the same frame model.
