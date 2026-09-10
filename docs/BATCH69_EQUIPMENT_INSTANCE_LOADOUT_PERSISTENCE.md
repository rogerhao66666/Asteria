# Phase 7 Batch 69 — Unique Equipment Instances / Socketed Loadout Persistence

Version: `v0.69.0a69`

Equipment copies now have stable `instance_id` identity. Two copies of the same
`EquipmentDefinition` may therefore carry different attachment/socket state and
survive save/reopen without collapsing into one definition-level item.

`EquippedItem` schema v1 stores only stable references:

- instance ID
- equipment definition ID
- socket ID -> attachment definition ID

Definitions remain canonical in `RpgDatabase`; instance data does not duplicate
definition content.

`EquipmentLoadout` schema v1 persists slot definitions and equipped instances.

## No arbitrary engine caps

Asteria does not impose a fixed maximum number of sockets or attachments per
equipment definition. Socket count is project data and collections are
arbitrary-length.

Equipment slot capacity is also rule data. `capacity=None` explicitly means
unlimited. A finite capacity may still be chosen by a game/template where it is
part of that game's rules.

The same principle applies broadly: engine architecture should not introduce
arbitrary gameplay quantity caps where ordinary dynamic collections are
sufficient.

Next: Batch 70 — runtime RPG save-state container (inventory, loadout,
progression and party identity) and restore validation.
