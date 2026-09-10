# Phase 5 Batch 40 — Dialogue Runtime Boundary + Choice State

Version: `v0.40.0a40`

## Goal

Add RPG dialogue/choice semantics without coupling Event VM to Qt, pygame,
or a specific dialogue-window implementation.

## Added

- `DialogueLine`
- `DialogueChoice`
- `DialogueRequest`
- `ChoiceRequest`
- `DialogueRuntimeState`
- EventRunner handling for:
  - `DIALOGUE`
  - `CHOICE`
- dialogue acknowledgement
- indexed choice selection
- choice result → EventContext variable
- choice result → local/self state
- runner blocking while UI response is pending

## Runtime contract

```text
EventVM
  ↓ yields DIALOGUE / CHOICE
EventRunner
  ↓ converts to request object
DialogueRuntimeState
  ↓ exposed to presentation/UI layer
UI presents content
  ↓
acknowledge_dialogue() / choose(index)
  ↓
EventRunner resumes EventVM
```

The Event VM does not know about fonts, windows, widgets, input devices,
portraits rendering, or screen layout.

## Why this matters

The same dialogue runtime can later be presented by:
- pygame runtime UI
- PySide6 preview/editor tools
- automated tests
- alternate rendering backends

without changing event program semantics.

## Next

Batch 41: richer branch/control-flow support around dialogue choices and
world-command service boundaries.
