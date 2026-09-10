# Phase 5 Batch 45 — Asteria Event Editor GUI Vertical Slice

Version: `v0.45.0a45`

## Goal

Expose the Phase 5 event runtime through a first real authoring UI without
copying RPG Maker's event-page UX and without creating editor-only event data.

## Added

### Canonical project persistence
Project schema v3 now stores:
- `EventProgramRegistry`
- per-scene `SceneEventBindings`

Project schema v2 remains readable for backward compatibility.

### Event Editor dock
For the selected Entity:
- list/create event bindings
- choose Trigger:
  - Action
  - Autorun
  - Parallel
- choose EventProgram
- show/add trigger conditions
- top-to-bottom command list
- insert basic commands:
  - Dialogue
  - Choice
  - If / branch
  - Set Switch
  - Set Variable
  - World Command
- delete command
- move command up/down

All edits use canonical `EventProgram` / `EventBinding` objects and the normal
Editor `CommandStack`, so undo/redo and dirty tracking continue to work.

## Current UX philosophy

The first vertical slice deliberately uses a readable top-to-bottom command
list rather than event pages or a mandatory node graph.

Simple content should remain simple. Advanced branching remains possible
through the same canonical event representation.

## Important limitation

This is the first authoring slice, not the polished final Event Editor.

The next UI passes should add:
- structured command property editors instead of repeated text dialogs
- ELSE/branch indentation visualization
- direct editing/removal of conditions
- event rename/duplicate/delete
- validation badges and unresolved-label warnings
- command search/palette
- runtime current-instruction highlight/debugger

## Next

Batch 46: central Editor workspace architecture for switching
`Scene ↔ Code ↔ Event ↔ Animation`, preparing the first-class Python authoring
workflow.
