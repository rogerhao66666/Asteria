# Batch 103 — Battle Screen Orchestration / Runnable Reference Presentation

Batch 103 adds `BattleScreenRuntime`, the presentation-only execution path that connects the Battle Presentation systems delivered in Batches 94–102.

Flow:

`BattlePresentationCoordinator events`
→ animation / feedback / camera presentation runtimes
→ HUD + scheduler/timing canonical mirrors
→ `BattleUiComposer`
→ `BattleUiFrame`
→ world `TextureRenderer` + `BattleUiRenderer`
→ one-shot audio cues.

`sync_battle()` mirrors canonical Battle Core state without calling `next_actor()`, advancing scheduler time, resolving actions, changing resources/states, or applying rewards. The canonical current member is supplied by the caller rather than inferred by presentation.

`render()` supports the existing texture renderer for combatants and the new Battle UI renderer for screen-space presentation. Audio cues are drained exactly once.

The runtime also provides deterministic presentation snapshot/restore across animation, feedback, camera/target, HUD, timeline, result and screen-level presentation state.
