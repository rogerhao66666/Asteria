# Phase 5 Batch 44 — Scene/Event Binding + Trigger Conditions

Version: `v0.44.0a44`

## Goal

Make event ownership and trigger policy canonical scene data so the future Event
Editor edits real engine data rather than an editor-only representation.

## Added

- `EventTriggerKind`
  - ACTION
  - AUTORUN
  - PARALLEL
- `EventTriggerCondition`
- `EventBinding`
- `SceneEventBindings`
- `SceneEventRuntime`
- conditional scheduled-binding refresh
- deterministic action-binding lookup per entity
- `Interaction2DComponent.event_binding_id`

## Canonical model

```text
Scene / Entity
   ↓
EventBinding
   ├─ stable binding_id
   ├─ entity_id
   ├─ program_id
   ├─ trigger
   ├─ enabled
   ├─ conditions[]
   └─ local_scope_id
```

Action bindings remain foreground interaction.
Autorun/Parallel bindings are converted to EventScheduler specs only while their
conditions are active.

## Why this matters for the editor

The first Event Editor can now edit:
- which entity owns the event
- which EventProgram it runs
- Action / Autorun / Parallel trigger
- enable state
- trigger conditions
- local/self state scope

without inventing a separate editor-only event-page model.

## Next

Batch 45: first Asteria Event Editor GUI vertical slice:
- event list for selected entity
- trigger/program/condition editing
- top-to-bottom EventProgram command list
- add basic commands
