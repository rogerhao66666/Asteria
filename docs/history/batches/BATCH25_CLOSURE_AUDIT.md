# Phase 3 / Batch 25 Closure Audit

## Scope
Editor session safety, save/load, and Play Current Scene boundary.

## Critical fixes
### Dirty-state branch bug
The old integer revision model could report a branched history as clean:
`execute A -> save -> undo -> execute B`.

`CommandStack` now assigns a unique state identity to each history branch.
`EditorDocument.dirty` compares the exact current history state with the saved state.

### Editor shell integrity
Accumulated incremental patches had left several Qt action methods outside
`AsteriaEditorWindow`. Headless subsystem tests did not exercise actual window
construction. Batch 25 rewrites the shell as one coherent class and adds a
surface regression test for all critical actions.

## Added
- exact history-state dirty tracking
- atomic editor save (`temp + fsync + os.replace`)
- project open/load through canonical Project serialization
- file path tracking in EditorDocument
- unsaved-change prompt on open/close
- Save / Save As / Open actions
- Play Current Scene / Stop toolbar actions
- backend-neutral `PlaySession`
- deep runtime snapshot made through canonical serialization
- runtime play mutation cannot modify the editor Project
- selected Scene/Entity/Component determines play scene; otherwise startup Scene
- built-in Transform registration in default Editor component registry

## Play architecture
Editor Project
→ canonical serialization snapshot
→ runtime Project clone
→ selected/startup Scene
→ PlaySession
→ future runtime/backend adapter

Play mode deliberately does not reuse mutable editor Scene objects.

## Deferred
- launch embedded/external pygame runtime window
- live edit while playing
- apply runtime changes back to editor
- crash recovery/autosave
- recent projects
- native macOS app packaging
- richer file/project browser
- final Phase 3 visual polish

## Closure
Batch 25: PASS if cumulative tests and compileall pass.
