# Phase 5 Batch 41 — Control Flow + World Command Service Boundary

Version: `v0.41.0a41`

## Added

### Control flow
- `LABEL`
- `JUMP`
- `JUMP_IF`
- deterministic label lookup in `EventProgram`
- duplicate/missing-label validation

This allows a `CHOICE` result stored in `EventContext` to select a later
event branch without encoding branch logic in dialogue UI.

### World command boundary
- `WorldCommand`
- `WorldCommandRouter`
- `WORLD` event instruction envelope

Example semantic commands that can be provided by services:
- `TRANSFER`
- `PLAY_ANIMATION`
- `PLAY_AUDIO`
- `SCREEN_EFFECT`
- `GIVE_ITEM`
- `REMOVE_ITEM`

These names are not hardcoded gameplay implementations. The router only
dispatches a backend-neutral command to an explicitly registered service.

## Execution path

```text
CHOICE
  ↓ writes EventContext value
JUMP_IF(condition, label)
  ↓
selected branch
  ↓
WORLD(command, args)
  ↓
WorldCommandRouter
  ↓
registered engine/game service
```

## Boundary

EventVM still owns orchestration only. It does not know scenes, inventories,
audio devices, renderers, quests, or combat rules.

Next recommended batch: common-event call stack / reusable event calls, before
parallel and autorun scheduling.
