# Phase 7 Batch 62 — Loadout / Consumable Integration

Version: `v0.62.0a62`

## Added

- `EquipmentSlotDefinition`
- `EquipmentLoadout`
- derived loadout modifiers / abilities / triggers / tags
- `ItemDefinition.use_effects`
- atomic `use_inventory_item()`
- `ItemUseResult`
- Item schema v2 with v1 backward read

## Design

Loadout does not permanently write equipment bonuses into an Actor's base
stats. It derives equipment contributions from equipped instances, preserving
the Phase 6 rule that modifiers affect evaluation rather than base state.

Equipment slots are data-driven. `weapon`, `body`, `accessory`, `ring`, or
project-specific names are toolkit/template conventions rather than engine
semantics. Slot compatibility uses tags and capacity.

Consumable items reuse Phase 6 `Effect`. All effects are staged; the target and
inventory are committed only when every item effect succeeds. A rejected use
does not consume the item and does not leave partial gameplay mutations.

The Simple RPG Potion now restores 30 `hp`, but `hp` is template data, not an
engine-reserved resource.

Next Batch 63: Enemy / encounter / loot-reward toolkit.
