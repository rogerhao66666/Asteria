# Phase 7 Batch 72 — Integration Hardening

Version: `v0.72.0a72`

This batch closes the main transactional and integration seams discovered
during Phase 7.

## Transactional reward application

`RewardRuntime.apply()` now validates the whole reward before mutation and
keeps rollback snapshots of currency, progression and inventory state. A
failure during commit, including an exception from a lifecycle subscriber,
restores all three stores before propagating the error.

The new failure hook is `rpg.reward.apply_failed`.

## Public mutable-state replacement seams

Phase 6 primitives gain additive, backward-compatible public replacement APIs:

- `StatBlock.replace_from()/replace_from_data()`
- `ResourcePool.replace_from()/replace_from_data()`
- `TagSet.replace_from()/replace_from_data()`

Phase 7 adds equivalent replacement APIs to `Inventory` and
`ProgressionRuntime`.

`use_inventory_item()` therefore no longer commits through private `_values`
or `_tags` implementation details.

## Lifecycle identity

Equipment equip/unequip lifecycle payloads now include stable
`instance_id` and definition-level `equipment_id` in addition to the item
object. Event VM / tooling can react to a unique equipped copy without
depending on Python object identity.

## No arbitrary collection caps

Regression coverage includes a 256-socket equipment instance. This is a
scalability test, not a limit. Project/game rules may impose limits where
meaningful; Asteria's generic data model does not.

Next: Phase 7 pre-closure audit. The audit must explicitly decide the remaining
GameplayLibrary / ability-definition ownership gap before Phase 7 can freeze.
