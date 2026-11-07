# Phase 6 Batch 52 — Formula / Scaling Foundation

Version: `v0.52.0a52`

## Product invariant

> Easy by default, progressively powerful, no dead-end beginner mode.

Asteria provides gameplay primitives and rule composition; concrete game rules
belong to the game, not to the engine.

## Canonical ValueFormula

The engine does not hardcode damage, attack, defense, strength, magic, element,
healing, critical chance or any other RPG-specific formula.

`ValueFormula` is a small typed data model consisting of:

- additive `FormulaTerm` values
- optional conditional multipliers
- optional minimum / maximum clamp

Supported term sources in Batch 52:

- constant
- source stat
- target stat
- source resource current / maximum
- target resource current / maximum

Example:

```text
40
+ Source.strength * 1.5
+ Source.dexterity * 0.3
- Target.armor * 0.7
```

Conditional multipliers use generic tags:

```text
if Target has weak.slash:
    final value * 1.5
```

There is no built-in `Fire > Ice` table. A game may represent that rule through
tags and conditions, or define a completely different combat model.

## Progressive authoring

Beginner:

```python
ValueFormula.constant(25)
```

Standard:

```python
FormulaBuilder().constant(25).source_stat("attack", 1.0).build()
```

Advanced:

```python
(
    FormulaBuilder()
    .constant(40)
    .source_stat("strength", 1.5)
    .target_stat("armor", -0.7)
    .multiply_when(
        1.5,
        FormulaCondition(required_target_tags=["weak.slash"]),
    )
    .build()
)
```

All three produce the same canonical `ValueFormula` type. There is no separate
beginner gameplay system.

## Why no arbitrary expression language yet

A free-form expression parser would make simple GUI authoring, validation,
migration, inspection and safe refactoring harder.

The canonical representation is intentionally structured so future editor modes
can show:

```text
Beginner -> Standard -> Advanced
```

without converting to another gameplay model.

Expert Python/plugin code remains available when a game genuinely needs rules
outside the structured model.

## Generality

The same formula can later drive:

- damage
- healing
- shields
- skill costs
- status strength/duration
- knockback
- rewards
- movement modifiers
- crafting values

Formula itself does not know which one it is calculating.

## Next

Batch 53 — Generic State / Status lifecycle:
duration, stacking, attached modifiers, on-apply/periodic/on-remove effects,
snapshot/restore, using the same Stats/Resources/Tags/Modifier/Effect/Formula
foundation.
