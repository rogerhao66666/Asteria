# Batch 129A — Animation Runtime Closure Review

## Scope

Focused architecture/performance review of the Battle Presentation animation path.
No Battle Core or RPG gameplay changes.

## Findings and fixes

### 1. Fixed: built-in animation-role enum leaked into runtime
The old BattleCombatantAnimator accepted only the convenience roles
idle/attack/hit/ko. That contradicted the project requirement that animation
vocabulary is project-defined.

The animator now accepts arbitrary role strings such as:
- ritual.cast.long
- weapon.swap
- summon.enter
- locomotion.hover
- project.custom.pose

The old BattleAnimationRole enum remains as backward-compatible convenience
constants only. Snapshot/restore preserves arbitrary role IDs.

### 2. Fixed: sub-frame runtime had avoidable O(substeps × total beats) scanning
Batch 129 used a fixed quantum and scanned the entire beat list on every
sub-step. Correct, but undesirable for dense choreography.

BattleMotionRuntime is now event-driven:
- advances exactly to authored beat boundaries;
- releases all beats sharing a timestamp;
- consumes presentation-only hit stop in wall-clock dt;
- keeps a next-beat cursor;
- tracks only currently active duration beats.

Correctness no longer depends on rendering at 240 Hz. `quantum` remains a
compatibility/performance-policy hint for adapters.

### 3. Added lightweight motion metrics
BattleMotionRuntime exposes:
- update_calls
- released_beats
- peak_active_beats
- current_active_beats

These are instrumentation seams for later frame-budget/stress profiling without
mixing profiling into gameplay.

### 4. Fixed: repeated sprite-sheet resolution in build_frame
Sprite sheets are resolved/validated once during BattlePresentationRuntime
construction and then cached by member. Per-frame build no longer calls the
external sprite-sheet resolver.

### 5. Fixed: repeated combatant sorting and animation timing-rule lookup
Stable scene member order is cached once. Animation timing rules are cached per
role per combatant instead of linearly re-resolving the timing profile every
frame.

## Architecture assessment

PASS:
- gameplay and presentation clocks remain separate;
- hit stop affects presentation only;
- arbitrary project-defined animation roles are supported;
- choreography channels remain generic;
- animation/VFX/camera/audio/UI timing can be synchronized;
- asset resolution has a preload-friendly boundary;
- renderer-facing draw construction remains outside gameplay;
- future batching/culling/pooling can be implemented in renderer adapters
  without changing Battle Core.

## Important boundary

"Never stutter" cannot be guaranteed by a backend-neutral Python presentation
layer alone. Final frame stability also depends on the renderer backend, GPU,
asset sizes, shader/VFX cost, texture uploads, audio backend, and project content.

Asteria's engine-side acceptance target is therefore:
- no avoidable repeated asset loading in hot paths;
- no choreography algorithm whose cost scales with virtual sub-frame frequency;
- no gameplay dependency on render cadence;
- provide batching/culling/pooling/preload seams;
- measure real frame time and dropped frames once a concrete renderer and real
  assets are present.

## Deferred to renderer/performance validation

These are intentionally not implemented as fake backend-neutral abstractions:
- GPU texture batching / atlas strategy
- draw-call batching
- particle/VFX object pools
- visibility/frustum culling
- asynchronous asset streaming
- GPU upload scheduling
- renderer frame-time/dropped-frame counters

Those belong in the concrete renderer/backend phase and will be stress-tested
with the final presentation templates and real/representative assets.
