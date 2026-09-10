# Phase 5 Batch 39 — Event Runner / Program Registry

Version: `v0.39.0a39`

## Goal

Connect world interaction triggers to real EventProgram/EventVM instances
without introducing dialogue, quests, or parallel scheduling prematurely.

## Added

- `EventProgramRegistry`
  - stable-ID registration
  - lookup / require / replace / unregister
- `EventRunner`
  - single foreground event lifecycle
  - start by program ID
  - start directly from `InteractionTrigger`
  - update wait/resume
  - surface host instructions
  - completion cleanup
  - stop / replace seam
  - active-event snapshot / restore
- `ActiveEvent`
  - program ID
  - source entity ID
  - local state scope

## Execution path

```text
Player presses interact
        ↓
InteractionController
        ↓
InteractionTrigger
        ↓
EventRunner.start_trigger()
        ↓
EventProgramRegistry.require(program_id)
        ↓
EventVM(program, shared EventContext, local scope)
        ↓
EventRunner.update(dt)
        ├─ state intrinsics
        ├─ WAIT / resume
        ├─ host command yield
        └─ complete
```

## Important boundary

Batch 39 supports one foreground event only. This is deliberate.

Parallel events, autorun, common events, cancellation policy, and scheduling
will be added later after dialogue/world command semantics are stable.

The EventRunner itself does not know what `CUSTOM`, dialogue, inventory,
transfer, or audiovisual commands mean. It only orchestrates execution.

## Next

Batch 40: Dialogue command/runtime boundary and choice-state foundation.
