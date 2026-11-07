# Batch 82 — Interaction / Weakness / Resistance / Generic Outcome Resolution

Batch 82 adds a mutation-free, explainable battle resolution layer between an action's semantic tags and the eventual battle transaction/presentation layer.

## Design boundary

The engine does **not** own an elemental chart, weapon table, fixed `hit/crit/block` formula, or `if fire then ...` branches. Projects define interaction rules using arbitrary action/source tags, target tags, project stat names, coefficients, multipliers, routing dispositions, and outcome tags.

The same rule shape can represent elemental weakness/resistance, armor mitigation, species bonuses, airborne interactions, temporary guard states, boss mechanics, or game-specific relationships.

## `InteractionRule`

A rule may match all/any required source/action tags and target tags, reject blocked tags, add flat/stat terms, apply a multiplier, emit outcome tags, and choose a routing disposition.

Routing dispositions are:

- `normal` — ordinary target-directed magnitude.
- `nullify` — value resolves to zero.
- `absorb` — positive magnitude is preserved but routing says the target absorbs it. Batch 82 deliberately does not invent HP/healing semantics.
- `reflect` — positive magnitude is preserved but routing says a later transaction layer should route it back toward the source.

Rules are deterministic: priority descending, then stable rule ID. Resolution returns matched rule IDs and a before/after trace for debugging/UI explainability.

## Generic probability checks

`OutcomeCheckDefinition` is a project-defined probability check. `check_id` is an open string, so the same primitive can express `hit`, `critical`, `block`, `parry`, `proc.poison`, `lucky_break`, or another game's mechanic.

Chance is composed from a base chance plus arbitrary source/target stat coefficients, clamped by project-defined bounds. Checks can require source/target tags and emit success/failure tags.

`InteractionResolver.resolve(...)` runs checks first and feeds their emitted tags back into normal interaction rules. Therefore a failed project-defined `hit` check can emit `outcome.evade`, which a normal rule maps to `nullify`; a `critical` check can emit a tag matched by a multiplier rule; a `block` check can emit a tag matched by a reduction rule. There is no second special-case damage pipeline.

## Battle integration seam

`BattleRuntime.resolve_interaction(...)` resolves an action using the canonical ability tags from `AbilityDefinition`. It is intentionally mutation-free in this batch. Later action-transaction work will own application/routing so absorb/reflect, resource mutation, reaction ordering, interruption, and rollback remain atomic rather than being partially committed here.

## Canonical project data

`RpgDatabase` schema is v10 and now stores:

- `interaction_rules`
- `outcome_checks`

v1–v9 remain readable. Older projects receive empty collections rather than invented combat rules.

## Explicit non-goals

Batch 82 does not yet implement status application/resistance, formation targeting, KO, timeline scheduling, reactions, or final battle transaction mutation. Those remain subsequent battle-core batches. It also does not hardcode names such as Fire/Ice/Sword/Undead/Hit/Crit/Block.
