# Phase 5 Batch 36 — Event VM Core

Version: `v0.36.0a36`

## Goal

Create the smallest deterministic event execution foundation required by
Asteria RPG behavior without coupling the VM to Editor, rendering, dialogue,
quests, combat, or platform APIs.

## Added

- `EventInstruction`
- `EventProgram`
- `EventVMStatus`
- `EventVMState`
- `EventVM`
- `EventStepResult`
- deterministic program counter semantics
- intrinsic `WAIT`
- intrinsic `END`
- host-opcode yielding
- wait/update/resume behavior
- stop/resume behavior
- JSON-compatible program serialization
- JSON-compatible VM state serialization
- snapshot / restore seam
- execution safety guard

## Execution model

```text
EventProgram
    ↓
EventVMState(pc/status/wait_remaining)
    ↓
EventVM.step()
    ├─ host opcode → yield instruction to caller
    ├─ WAIT        → advance PC, enter WAITING
    └─ END         → COMPLETED

WAITING
    ↓
update_wait(dt)
    ↓
RUNNING
    ↓
continue from exact saved PC
```

## Architectural boundary

Batch 36 deliberately does **not** implement:
- switches/variables
- conditions/branches
- dialogue/choices
- NPC interaction
- quests
- inventory/world commands
- autorun/parallel/common events

Those belong to later Phase 5 batches and consume this VM contract.

The VM imports neither Qt nor pygame and has no knowledge of Scene rendering
or Editor widgets.
