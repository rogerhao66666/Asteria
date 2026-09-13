# Batch 84 — Advanced Targeting / Formation / Position

## Goal

Add a battle-level targeting layer that remains data-driven and formation-aware without hardcoding JRPG concepts such as front row, back row, lane, flying, or boss body parts into the engine.

## Canonical model

- `FormationDefinition` owns an ordered set of logical `FormationSlotDefinition` values.
- Slots have stable IDs, optional editor/presentation coordinates, arbitrary tags, and explicit adjacency edges.
- `BattleFormationRuntime` maps combatant instance IDs to slots and supports runtime movement.
- `BattleTargetingDefinition` is keyed by ability ID and filters candidates by relation, subject tags, slot tags, active state, metric conditions, and optional actor adjacency.
- `BattleTargetingRuntime` resolves candidates and selected targets deterministically.

The engine never interprets tags such as `row.front`, `row.back`, `part.core`, or `airborne`. Those are project vocabulary.

## Selection modes

- `manual`
- `all`
- `random_n`
- `first_n`

`random_n` accepts a supplied RNG so later deterministic battle snapshots can reproduce selection exactly.

## Candidate relations

- `self`
- `ally`
- `opponent`
- `any`

Side names themselves remain project-defined strings.

## Generic metric filters

`TargetMetricCondition` supports project-defined stat/resource constraints without embedding game-specific targeting rules. Examples:

- HP fraction <= 0.25
- threat >= 10
- mana > 30

## Boss parts

Boss parts require no special boss-targeting system. A project may model body parts as combatants/targets placed in tagged formation slots, for example `part.core` or `part.shell`. Abilities select them through the normal target filter path.

## BattleRuntime integration

`BattleRuntime.resolve_targets()` exposes preview/candidate resolution. `BattleRuntime.execute()` validates manual targets and substitutes auto-selected targets before delegating to the existing Phase 6 `AbilityRuntime`.

Existing projects with no `BattleTargetingDefinition` retain the previous ability-targeting behavior.

## Canonical data

`RpgDatabase` schema is now v12 and owns:

- `formations`
- `battle_targeting`

v1-v11 remain readable.

## Developer Battle Test Harness

Batch 84 introduces `demos/phase7b_batch84/run_battle_test_harness.py`.

It is intentionally a developer sandbox, not final RPG presentation. It provides an actual interactive window for validating:

- formation placement
- candidate highlighting
- manual target rejection
- all-opponent targeting
- random-N targeting
- back-row targeting
- turn-to-turn interaction

This harness will be extended through the remaining Battle Core batches so architecture problems can be detected in real interaction before final battle presentation/UI work.
