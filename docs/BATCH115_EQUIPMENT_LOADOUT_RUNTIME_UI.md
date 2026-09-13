# Batch 115 — Equipment / Loadout Runtime UI

Batch 115 adds the generic equipment/loadout presentation layer for Runtime RPG UI.

## Read-only projection

`EquipmentScreenRuntime` consumes canonical `EquipmentLoadout` plus a project equipment catalog.

It projects:
- arbitrary equipment slot IDs
- arbitrary per-slot capacity, including unlimited
- equipped item instances
- equipment tags and granted abilities
- sockets and current attachments
- growth runtime summary
- evolution target metadata
- candidate equipment browsing
- capability eligibility reasons
- query/filter/paging
- presentation-only slot/item selection

The runtime never equips or unequips items, attaches or detaches sockets, unlocks growth nodes, evolves equipment, or consumes inventory.

## Generic slot model

There are no required `weapon`, `armor`, `head`, `body`, or `accessory` semantics. A project may define slots such as:
- main
- accessory
- relic_matrix
- sigil_array
- drone_bay

Slot compatibility remains canonical RPG data.

## Candidate eligibility

The screen may use existing canonical `EquipmentDefinition.eligibility()` capability rules or receive already-resolved eligibility from a controller.

Presentation never invents its own capability requirements.

## Adaptive browsing

Candidate search and paging are presentation-only. `EquipmentScreenProfile.page_size` changes visible browsing density, not inventory/equipment limits.
