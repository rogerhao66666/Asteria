# Batch 80 — Canonical Resolved Actor Build

Version `v0.80.0a80`.

Batch 80 introduces a single resolved actor-build contract for battle, AI, editor inspection and future GUI/runtime menus.

## Canonical inputs

Actor runtime + multi-class assignments + progression + allocation graphs + learned abilities/passives + equipment + attachments + equipment growth + ability evolution.

## Canonical outputs

`ResolvedActorBuild` contains effective stats/resources/tags/capabilities/abilities, active passives, class assignment IDs, equipped instance IDs, gameplay triggers, ability provenance and generic contribution provenance.

The result is derived. Resolving a build never bakes equipment/progression/passive values into the actor's mutable intrinsic state.

## Explainability

`ability_sources(ability_id)` and `sources_for(category, key)` expose provenance usable by future inspector/character/equipment-comparison UI.

## Important hardening

Equipment-growth granted abilities are now included in actor ability resolution with `equipment_growth` provenance. Allocation resource bonuses are represented in the canonical resolved resource view.

## Demo

`AsteriaPhase7B_ResolvedBuildDemo.asteria.json` + `reference_data/phase7b_batch80_resolved_build_demo.save.json`.
