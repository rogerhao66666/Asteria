# Phase 6 Batch 51 — Modifier + Effect Foundation

Version: `v0.51.0a51`

## Purpose

Separate two different gameplay concepts:

- **Modifier**: changes how a stat is evaluated.
- **Effect**: applies an instantaneous state change.

This prevents equipment, buffs, skills, damage, healing and statuses from
collapsing into one overloaded system.

## Modifier model

`StatModifier` supports:

- `ADD`
- `MULTIPLY`
- `OVERRIDE`
- priority
- stable modifier IDs
- required tags
- blocked tags

Evaluation is deterministic:

```text
base
 -> all ADD modifiers
 -> all MULTIPLY modifiers
 -> highest ordered applicable OVERRIDE
```

Ordering within an operation is `(priority, modifier_id)`.

Example:

```python
mods = ModifierSet(
    [
        StatModifier("sword", "power", "add", 10),
        StatModifier("rage", "power", "multiply", 1.5),
    ]
)

effective = mods.evaluate("power", 20)
# (20 + 10) * 1.5 = 45
```

No stat names are hardcoded by Asteria.

## Effect model

`Effect` contains deterministic `EffectOperation` values.

Batch 51 operations:

- `STAT_DELTA`
- `RESOURCE_DELTA`
- `RESOURCE_SET`
- `TAG_ADD`
- `TAG_REMOVE`

Effects can be gated by required/blocked tags.

Effect application is **atomic**: operations are applied to staged copies first.
If any operation fails, the original gameplay state is unchanged.

Example:

```python
heal = Effect(
    "heal",
    [
        EffectOperation("resource_delta", "hp", 30),
    ],
)

hero.gameplay.apply_effect(heal)
```

## Architectural boundary

Timed buffs/debuffs are not represented by mutating base stats directly.

Future State/Status systems will own lifecycle and duration, then contribute
`StatModifier` values or execute `Effect` values at defined times.

This keeps:

```text
base stats
 + active modifiers
 = effective stats
```

separate from:

```text
effect event
 -> mutate resource/stat/tag state once
```

## Python Authoring API

`AuthoringGameplayAttributes` now supports:

- `effective_stat(name, modifiers)`
- `apply_effect(effect)`

Mutations still travel through the authoring command path, so Editor script
transactions remain undoable/rollback-safe.

## Next

Batch 52 should add the generic **State / Status lifecycle** layer:

- active state instances
- duration
- stacking policy
- attached modifiers
- on-apply / periodic / on-remove effects
- deterministic update/snapshot/restore

without hardcoding poison, burn, stun, buff, or debuff names.
