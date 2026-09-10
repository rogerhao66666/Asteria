# Phase 6 Batch 58 — Gameplay Hardening

Version: `v0.58.0a58`

This batch closes several correctness/extensibility gaps discovered while
reviewing Batches 50–57.

## State lifecycle fixes

### STACK on-apply semantics

`StateRuntime.apply()` now executes `on_apply` exactly once for each application
event. Existing stacks are no longer replayed.

Previous problematic behavior:

```text
apply stack 1 → on_apply ×1
apply stack 2 → on_apply ×2
apply stack 3 → on_apply ×3
```

Correct behavior:

```text
apply stack 1 → on_apply ×1
apply stack 2 → on_apply ×1
apply stack 3 → on_apply ×1
```

Stack count still scales persistent modifiers and periodic effects where
appropriate.

### Periodic expiry boundary

A large runtime `dt` now advances periodic effects only for the portion of time
during which the state is alive. A 2.5 second state with a 1 second periodic
effect ticks at 1s and 2s, not at 3s...10s when a single `update(10)` occurs.

## Generic trigger event keys

Trigger events are now canonical strings. The old `TriggerEvent` enum remains
as a convenience list for common events, but the engine no longer restricts
projects to those names.

Valid project-defined examples:

```text
reactor.temperature.crossed
combat.perfect_guard
crafting.recipe.completed
world.weather.changed
```

Existing serialized v1 trigger data remains readable because its event field
was already a string.

## Formula-driven Effects

Numeric Effect operations now accept either:

- a fixed numeric value, or
- a canonical `ValueFormula`.

This finally closes the intended pipeline:

```text
Stats / Resources / Tags
        ↓
Formula / Scaling
        ↓
Effect
        ↓
Ability
```

Example:

```text
resource_delta hp =
    -(Source.attack × 1.0 - Target.defense × 0.5)
```

`AbilityRuntime` supplies source/target formula context independently for every
selected target. Existing numeric Effect data remains backward compatible.

## Still intentionally unresolved

State-owned tag contribution/reference-count semantics are not faked in this
batch. An `on_apply TAG_ADD` followed by `on_remove TAG_REMOVE` can still
conflict with independently-owned identical tags. This requires an explicit
contribution/ownership model and should be addressed before claiming state tag
ownership as production-safe.

## Next

Proceed to Phase 6 closure audit. The closure should verify Batches 50–58 as one
generic gameplay framework and decide whether tag contribution ownership must
be implemented before freeze or explicitly deferred with a safe-use boundary.
