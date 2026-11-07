# Phase 6 Batch 53 — Generic State / Status Lifecycle

Version: `v0.53.0a53`

## Goal

Provide lifecycle for temporary gameplay states without hardcoding names such as
poison, burn, stun, haste, buff or debuff.

## Core model

`StateDefinition`
- stable `state_id`
- duration
- stacking policy
- maximum stacks
- attached `StatModifier` values
- on-apply `Effect` values
- periodic effects
- on-remove `Effect` values

`StateRuntime`
- active-state ownership for one gameplay subject
- deterministic update
- stack/refresh/replace behavior
- periodic ticks
- effective modifier aggregation
- snapshot/restore

## Stacking policies

`REPLACE`
- replace the active instance with a fresh one.

`REFRESH`
- keep one stack and reset duration/tick phase.

`STACK`
- increase stack count up to `max_stacks`, refresh duration and tick phase.
- attached modifiers and periodic effects scale per active stack.

## Example

```python
burn = StateDefinition(
    "burning",
    5,
    periodic=[
        PeriodicEffect(
            1,
            Effect(
                "burn_tick",
                [
                    EffectOperation("resource_delta", "hp", -8),
                ],
            ),
        )
    ],
)
```

A different game can use the same system for:

```text
machine.overheated
weather.wet
stance.rage
blessing.moon
curse.glass
```

The engine does not distinguish these semantically.

## Architectural rule

A state owns **lifecycle**, not a fixed gameplay meaning.

```text
State
├─ duration / stacking
├─ modifiers
├─ on-apply effects
├─ periodic effects
└─ on-remove effects
```

This allows authored creativity without requiring engine changes.

## Snapshot / restore

Runtime snapshots preserve:

- state ID
- remaining duration
- stack count
- periodic tick progress

Definitions remain canonical registry data and are referenced by stable ID.

## Next

Batch 54 should introduce generic gameplay Conditions / Triggers that can read
stats, resources, tags and state presence, then dispatch Effects or other
gameplay actions. This will form the rule-composition seam needed by equipment,
abilities and passive mechanics.
