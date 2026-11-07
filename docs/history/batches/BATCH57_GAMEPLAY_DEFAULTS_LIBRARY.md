# Phase 6 Batch 57 — Gameplay Defaults / Presets / Canonical Library

Version: `v0.57.0a57`

## Product rule

**If Asteria can provide a sensible ready-to-use default, it should.**

A beginner should be able to create a project and start making a game before
learning every gameplay primitive.

Defaults are **template data, never hardcoded engine rules**.

```text
Asteria Presets
      ↓
Canonical Gameplay Data
      ↓
Beginner GUI / Advanced GUI / Python
      ↓
Generic Runtime
```

## Starter RPG attributes

The Simple RPG starter currently provides editable example values:

- HP 100
- MP 30
- Attack 10
- Defense 10
- Magic 10
- Resistance 10
- Speed 10
- `actor.player` starter tag

None of these names has engine semantics.

## Formula presets

- Standard Physical: `Base + Attack × 1.0 - Defense × 0.5`
- Standard Magic: `Base + Magic × 1.2 - Resistance × 0.5`
- Flat value

These all produce ordinary `ValueFormula` objects.

## Ability presets

- Basic Attack
- Simple Heal

They produce ordinary `AbilityDefinition` values and can immediately be opened
in future Advanced editors or modified through Python.

## Presentation preset

`basic_melee` demonstrates a ready-to-use sequence:

```text
attack animation
→ slash VFX
→ gameplay hit
→ impact audio
→ hit stop
→ small camera impact
```

Again this is ordinary `ActionTimeline` data.

## Canonical GameplayLibrary

Batch 57 adds a versioned canonical container for:

- formulas
- abilities
- states
- triggers
- action timelines

Preset-generated definitions use exactly the same library as custom content.

## Beginner/advanced invariant

There is no beginner-only runtime representation.

```text
Preset / Beginner GUI ─┐
Advanced GUI ──────────┼→ canonical definition
Python ────────────────┘
```

A project can also use an empty `GameplayLibrary` for advanced/blank workflows.

## Next

Batch 58 should harden Phase 6 integration and address lifecycle/serialization
edge cases before the Phase 6 closure audit.
