# Asteria Phase 7B Batch 76 — Ability Ownership, Passives & Evolution

Version: `v0.76.0a76`

## Goal

Separate ability ownership/provenance from temporary grants, add persistent learned abilities and passive loadout state, and establish a generic ability-evolution seam without hardcoding a skill-tree model.

## Added

- `ActorAbilityState`
  - learned abilities
  - active passives
  - selected evolution branches
- `PassiveDefinition`
  - tags
  - stat modifiers
  - granted abilities
  - triggers
- `AbilityEvolutionRule`
  - source/result ability
  - optional progression requirement
  - priority
  - source-retention policy
- `AbilityGrant` / `AbilityResolution` provenance
- `RpgActorRuntime.resolve_abilities(...)`
- passive stat/tag contribution seams
- actor snapshot schema v2 with ability state; v1 remains readable
- RPG database schema v6 with passives/evolution rules; v1–v5 remain readable
- Project gameplay-reference validation includes passive and evolution ability refs
- runtime-state validation checks passive/evolution references stored in actor snapshots

## Semantics

A learned ability is mutable actor/save state and survives job changes unless project rules explicitly remove it.
A class/equipment/passive/state grant is derived from its current source and therefore disappears when that source disappears.

Evolution is generic replacement/variant resolution. `fireball -> firestorm` is demo data, not an engine mechanic. Multiple equal-priority branches can be selected explicitly by actor ability state.

Passive capacity is caller/project policy. The engine provides a capacity argument but does not define a global hard cap.

## Demo

- `AsteriaPhase7B_AbilityPassiveDemo.asteria.json`
- `reference_data/phase7b_batch76_ability_passive_demo.save.json`
- `demos/phase7b_batch76/verify_ability_passive_demo.py`

The project remains a normal playable Reference World while its canonical RPG data/save demonstrates learned skills, passive loadout, stat/tag grants and skill evolution.
