# Phase 5 Batch 42 — Reusable/Common Event Calls

Version: `v0.42.0a42`

## Goal

Allow one EventProgram to call another reusable EventProgram and then return
to the exact next instruction.

## Added

- `EventCallFrame`
- runner-owned event call stack
- `CALL`
- `RETURN`
- automatic return when a callee reaches `END`
- nested calls
- inherited or callee-specific local/self scope
- call-stack snapshot / restore
- backward-compatible restore of Batch 39–41 active-event snapshot v1

## Execution path

```text
Root EventProgram
    ↓
CALL common_event
    ↓
push EventCallFrame(root VM state)
    ↓
run Common EventProgram
    ↓
END / RETURN
    ↓
pop frame
    ↓
restore root VM
    ↓
continue exact next instruction
```

## Design choice

The EventVM remains a deterministic single-program interpreter.

Cross-program orchestration belongs to EventRunner, which already owns program
lookup, active-event identity, dialogue blocking, and runtime host boundaries.
This avoids turning the VM into a project/database-aware object.

## Scope semantics

`CALL` defaults to `scope="inherit"`, so a reusable common event can operate on
the caller's self/local state.

A caller may request `scope="callee"` with an explicit `local_scope_id` when
the reusable event needs its own persistent scope.

## Next

Batch 43: event scheduling foundation for autorun / parallel / common runtime
instances, with explicit policies so foreground interaction remains simple.
