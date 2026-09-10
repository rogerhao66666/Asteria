# Phase 6 Batch 54 — Generic Conditions / Triggers Foundation

Version: `v0.54.0a54`

## Goal

Allow game authors to compose mechanics such as:

- low-HP passives
- on-hit effects
- target-tag weaknesses
- equipment passives
- state-dependent behavior
- conditional healing or damage

without adding new engine code for each mechanic.

## Gameplay conditions

Batch 54 supports:

- source/target stat comparisons
- source/target resource current/max/ratio comparisons
- tag presence/absence
- active state presence/minimum stacks
- nested ALL / ANY / NONE groups

Examples:

```text
Source HP ratio <= 0.25
Target has enemy.boss
Target does NOT have immune.fire
Source has rage with at least 2 stacks
```

## Trigger model

`GameplayTrigger` contains:

- stable trigger ID
- event kind
- condition tree
- effects

Initial trigger events:

```text
manual
on_hit
on_damaged
on_defeat
on_resource_changed
on_state_applied
on_state_removed
on_equip
on_unequip
```

These are semantic gameplay events, not frame/update callbacks.

## Example

```python
GameplayTrigger(
    "desperation_hit",
    "on_hit",
    conditions=NumericCondition(
        "source",
        "resource_ratio",
        "hp",
        "<=",
        0.25,
    ),
    effects=[bonus_damage],
)
```

This expresses:

```text
When I hit
AND my HP <= 25%
THEN apply bonus effect
```

## Rule composition invariant

Asteria supplies primitives:

```text
Stats / Resources / Tags / States
          ↓
      Conditions
          ↓
       Triggers
          ↓
       Effects
```

Specific game ideas belong to authored data.

## GUI direction

The same canonical structure can later drive a beginner-friendly rule editor:

```text
When      [ On Hit ▼ ]
If        [ My HP ] [ <= ] [ 25% ]
Then      [ Apply Effect ] [ Bonus Damage ]
```

Advanced mode can expose nested groups and source/target selection without
changing the underlying rule model.

## Next

Batch 55 should build **Ability / Targeting foundation** on top of Formula,
Effect, State and Trigger primitives, while keeping turn-based and real-time
combat on the same generic model.
