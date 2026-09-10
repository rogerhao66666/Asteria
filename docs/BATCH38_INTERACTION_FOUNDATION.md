# Phase 5 Batch 38 — Interaction Foundation

Version: `v0.38.0a38`

## Goal

Connect player action input to generic world interactables without hardcoding
NPC, chest, door, dialogue, quest, or battle behavior.

## Added

- persistent `Interaction2DComponent`
  - event program ID
  - interaction range
  - facing requirement
  - optional local-state scope
- `InteractionQuery`
  - canonical Transform-based distance checks
  - up/down/left/right facing cone
  - deterministic nearest-target selection
- `InteractionController`
  - action-button edge detection
  - avoids retriggering every frame while held
- `InteractionTrigger`
  - backend-neutral seam describing which event program should start
  - stable local state scope

## Execution path

```text
InputSnapshot(interact)
        ↓
InteractionController
        ↓
InteractionQuery
        ↓
Scene + Transform + Interaction2DComponent
        ↓
nearest eligible target
        ↓
InteractionTrigger
(event_program_id + local_scope_id)
        ↓
future Event Runner / Event VM
```

The interaction system does not execute dialogue or gameplay effects itself.

## Next

Batch 39 should connect `InteractionTrigger` to an Event Runner / program
registry so an interactable can start a real EventVM instance.
