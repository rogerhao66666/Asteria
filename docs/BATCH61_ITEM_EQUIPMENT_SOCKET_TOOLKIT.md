# Phase 7 Batch 61 — Item / Equipment / Socket Toolkit

Version: `v0.61.0a61`

## Added

- `ItemDefinition`
- `Inventory`
- `EquipmentDefinition`
- `SocketDefinition`
- `AttachmentDefinition`
- `EquippedItem`
- RPG Database schema v2 with v1 backward read

## Equipment composition

Equipment and socketed attachments can contribute:

- tags
- stat modifiers
- granted abilities
- gameplay triggers

The socket system is tag-driven. Asteria does not hardcode Gem, Card, Rune,
Materia, Chip, Soul, or any other world-specific attachment type.

```text
Equipment
  ├─ own modifiers / abilities / triggers
  └─ sockets
       └─ Attachment
            ├─ tags
            ├─ modifiers
            ├─ abilities
            └─ triggers
```

A socket with no accepted tags is universal. A restricted socket accepts an
attachment when any accepted socket tag is present on that attachment.
Locked sockets reject attachments until some later game system unlocks them.

## Default-first content

The Simple RPG preset now includes:

- Potion
- Iron Sword (+10 attack)
- one weapon attachment socket
- Ruby (+5 attack)

These are editable template definitions, not engine rules.

## Boundary

Equipment composition is RPG toolkit data layered on frozen Phase 6
`StatModifier`, `GameplayTrigger`, tags, and ability IDs. The gameplay core
still has no weapon/gem/card semantics.

Next: Batch 62 — equipment loadout/contribution integration + consumable item
effects, followed by enemy/loot toolkit.
