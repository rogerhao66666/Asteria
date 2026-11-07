# Batch 116 — Ability / Passive Collections and Loadouts

Batch 116 adds the generic ability/passive presentation layer for Runtime RPG UI.

## Read-only projection

`AbilityScreenRuntime` consumes canonical `ResolvedActorBuild`, optional
`ActorAbilityState`, canonical `AbilityDefinition` catalog, and canonical
`PassiveDefinition` catalog.

It projects:
- resolved abilities
- learned-but-not-currently-resolved abilities
- ability provenance
- arbitrary ability/passive categories
- active passives
- passive loadout capacity summary
- project-owned labels/categories
- search/filter metadata
- presentation-only tab/category/selection state
- adaptive per-category overflow

## Genericity

There is no required Attack / Skill / Item / Defend taxonomy and no fixed
ability slot count. Projects may define categories such as techniques,
formulas, arcana, movement, stances, summons, craft, guard, traits, or any
other vocabulary.

## Passive loadout

The screen mirrors active passive IDs from the already-resolved actor build.
`passive_capacity` is presentation/controller-supplied metadata. Presentation
does not equip or unequip passives and does not decide whether a passive is
legal.

## Provenance

Ability source labels come from canonical `ability_grants`, for example:
- intrinsic
- class assignment
- progression
- allocation
- learned
- equipment
- evolution

The UI never recomputes ownership or ability resolution.

## Large collections

`visible_limits` are presentation limits only. Full collection IDs remain in
the view and gameplay capability is never capped.
