# Asteria Phase 7B Batch 81 — Battle Resources / Gauges / Lifecycle

Version: `v0.81.0a81`

## Goal

Provide one generic combat-resource layer for MP-like persistent resources and battle-only gauges such as rage, boost, combo, guard, stagger, charge, morale, limit, or project-defined mechanics.

Asteria does **not** assign semantics to any resource name.

## Canonical definitions

`RpgDatabase` schema v9 now owns `BattleResourceDefinition` values.

Each definition supports:

- project-defined `resource_id`;
- optional binding to an existing `GameplaySubject.resources` entry with the same ID;
- combat-only resources when no subject resource exists;
- minimum / logical maximum;
- optional overflow limit;
- start policy: `fixed`, `current`, `minimum`, `maximum`;
- end policy: `persist`, `restore_initial`, `reset_to_start`;
- arbitrary lifecycle/custom string trigger rules.

RPG database v1-v8 remain readable. Loading an old database does not invent resource definitions.

## Runtime

`BattleResourceRuntime` owns combat-scoped values per `PartyMember`.

Operations:

- `current()` / `get()`
- `change()`
- atomic `spend()`
- `restore()`
- `apply_trigger()`
- snapshot / restore without replaying trigger rules
- finish/end-policy application

Existing subject resources are mirrored. Overflow beyond the logical maximum is intentionally combat-layer state and is not written above the persistent `ResourcePool` maximum.

## Battle lifecycle integration

`BattleRuntime` can receive `resource_definitions` and automatically drives rules for:

- `rpg.battle.started`
- `rpg.battle.round_started`
- `rpg.battle.turn_ready`
- `rpg.battle.turn_ended`
- `rpg.battle.round_ended`
- `rpg.battle.finished`

Calling `next_actor()` repeatedly does not duplicate the turn-ready resource tick. Battle finish policy is idempotent.

Custom trigger strings such as `demo.weakness_hit` or future `battle.outcome.critical` can be applied without editing a central enum. Later Interaction/Outcome, Status, Reaction, and Combo batches can drive the same seam.

## Lifecycle hooks

The resource runtime emits:

- `rpg.battle_resource.changed`
- `rpg.battle_resource.full`
- `rpg.battle_resource.empty`
- `rpg.battle_resource.overflowed`
- `rpg.battle_resource.finished`

Therefore battle-resource changes remain Event VM-connectable.

## Demo

Canonical engine-loadable project:

`AsteriaPhase7B_BattleResourcesDemo.asteria.json`

Functional verifier:

```bash
PYTHONPATH=src python demos/phase7b_batch81/verify_battle_resources_demo.py
```

It demonstrates bound MP plus Rage, Boost, Stagger, and Combo resource policies.

## Deliberately deferred

Batch 81 does not hardcode weakness, break, status, cast timing, or combo semantics. Those later systems will manipulate generic battle resources through explicit triggers/transactions.

Next: Batch 82 — Interaction / Weakness / Resistance / Generic Outcome Resolution.
