# Phase 6 Batch 55 — Ability / Targeting Foundation

Version: `v0.55.0a55`

## Goal

Build a generic ability execution layer on top of Stats, Resources, Tags,
Formula, Effects, States and Conditions without hardcoding JRPG or ARPG combat.

## Core model

`AbilityDefinition`
- stable ability ID
- generic tags
- targeting rule
- resource costs
- activation condition
- effects

`TargetingRule`
- minimum / maximum target count
- whether self-targeting is allowed
- required target tags
- blocked target tags

`AbilityCost`
- generic resource key
- `ValueFormula` amount

`AbilityEffect`
- apply to source/self
- apply to selected targets

`AbilityRuntime`
- validates targets
- validates conditions
- evaluates and validates costs
- stages costs and effects
- commits atomically on success

## Important architecture boundary

Batch 55 does **not** make the ability system responsible for spatial queries,
input, animation timing, cooldown clocks or battle turns.

Those systems decide *which candidates are selected and when execution occurs*.
The Ability layer validates and executes canonical gameplay rules.

This keeps the same ability data usable by:

```text
Turn-based JRPG
Realtime ARPG
AI-controlled actor
Event/script invocation
Editor test tool
```

## Example

```python
AbilityDefinition(
    "spark",
    targeting=TargetingRule(required_tags=["enemy"]),
    costs=[AbilityCost("mp", 5)],
    effects=[
        AbilityEffect("selected", damage_effect),
    ],
)
```

No names such as enemy, mp, damage or magic are special to the engine. They are
ordinary authored keys/tags.

## Progressive GUI direction

Beginner:

```text
Skill: Spark
Cost: 5 MP
Target: One Enemy
Effect: Damage 12
```

Advanced:

```text
Targets
  min 1 / max 3
  required tag: enemy
  blocked tag: immune.arcane

Cost
  resource: mana
  formula: Base 8 + Focus × 0.2

Conditions
  Source state: overcharge

Effects
  Selected → arcane_burst
  Self     → recoil
```

Both edit the same canonical `AbilityDefinition`.

## Atomic execution

Costs and instantaneous effects execute against staged attribute copies.
If a later effect fails, resource cost and earlier effects are not committed.

## Next

Batch 56 should add an execution/timeline seam: ability phases or gameplay
actions that let turn-based battle flow and realtime animation/hit timing invoke
the same `AbilityRuntime` without putting frame scheduling into Ability itself.
