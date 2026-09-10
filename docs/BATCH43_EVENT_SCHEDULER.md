# Phase 5 Batch 43 — Autorun / Parallel Event Scheduling Foundation

Version: `v0.43.0a43`

## Goal

Add explicit scheduling policy for automatically-running event programs while
keeping foreground interaction simple.

## Added

- `EventScheduleMode`
  - `AUTORUN`
  - `PARALLEL`
- `ScheduledEventSpec`
- `ScheduledEventInstance`
- `EventScheduler`
- automatic start while enabled
- autorun foreground-blocking policy
- parallel non-blocking policy
- stop / stop-all
- instance snapshot / restore
- next-update restart semantics for continuously enabled scheduled events

## Policy

### Foreground interaction
Still uses the normal single `EventRunner`.

### Autorun
- starts automatically
- blocks starting foreground interaction while busy
- completes normally
- if still enabled, may restart on the next scheduler update

### Parallel
- starts automatically
- runs independently
- does not block foreground interaction
- if still enabled, may restart after completion

This avoids forcing all event types into one mega-runner.

## Execution sketch

```text
Game/runtime tick
    ↓
EventScheduler.update(dt)
    ├─ AUTORUN runner(s)
    │    └─ foreground gate
    └─ PARALLEL runner(s)
         └─ independent
```

## Not included yet

- editor trigger authoring UI
- trigger conditions on ScheduledEventSpec
- scene lifecycle ownership
- dialogue presentation for background/parallel events
- debugger visualization

These belong in the next integration/editor batches.

## Next

Batch 44: scene/event binding + trigger condition model, then first Event
Editor GUI vertical slice.
