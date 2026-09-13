# Asteria Phase 7B Batch 79 — Equipment Progression / Item Growth

Version: `v0.79.0a79`

## Goal

Make equipment growth a first-class, data-driven RPG capability without hardcoding a universal weapon-level system.

Asteria treats growth vocabulary as project data. A game may advance equipment through XP, usage, kill counts, materials, bond, quest/boss flags, or any other numeric counter supplied by game rules.

## Added

- `EquipmentGrowthDefinition`
- `EquipmentGrowthNodeDefinition`
- `EquipmentGrowthReward`
- `EquipmentGrowthRuntime`
- `EquipmentGrowthContribution`
- `EquipmentGrowthUnlockPreview`
- per-instance equipment growth persistence
- automatic ranked growth nodes
- manual branch nodes
- prerequisite nodes
- exclusive branch groups
- arbitrary progress counters
- growth-provided stat modifiers
- growth-provided abilities
- growth-provided tags/capabilities
- growth-provided triggers
- growth-unlocked sockets
- equipment evolution target seam
- lifecycle hooks for growth progress and unlocks

## Important semantics

There is no engine-defined `weapon_level`, `weapon_xp`, maximum level, weapon-only restriction, or fixed growth source.

A project can define counters such as:

- `xp`
- `kills`
- `usage_mastery`
- `material_invested`
- `bond`
- `boss_mark`

Nodes can auto-unlock when their requirements become true or remain manual choices for branching progression.

Growth is attached to a stable `EquippedItem.instance_id`, so two copies of the same equipment definition can grow independently.

## Equipment evolution

A growth reward may expose `evolution_equipment_id`. Batch 79 deliberately keeps this as an explicit target seam rather than silently replacing the equipment definition. Later authoring/gameplay code can decide whether evolution is automatic, confirmed by the player, consumes materials, preserves sockets, or follows other project rules.

## Persistence

- `EquipmentDefinition` schema: v3 (`growth_id`)
- `EquipmentInstance` schema: v2 (`growth` runtime state)
- `AttachmentDefinition` schema: v2 (`growth_id` reserved seam)
- `RpgDatabase` schema: v8 (`equipment_growth`)
- older equipment/database saves remain readable

## Lifecycle hooks

- `rpg.equipment_growth.progressed`
- `rpg.equipment_growth.node_unlocked`

## Demo

Project:

`AsteriaPhase7B_EquipmentGrowthDemo.asteria.json`

Runtime save:

`reference_data/phase7b_batch79_equipment_growth_demo.save.json`

Verification:

```bash
PYTHONPATH=src python demos/phase7b_batch79/verify_equipment_growth_demo.py
```

The demo contains a unique Blood Blade instance that:

1. gains three automatic weapon-growth ranks from XP,
2. receives cumulative attack modifiers,
3. unlocks a previously locked socket,
4. preserves a socketed Growth Ruby,
5. selects one of two mutually exclusive awakening paths,
6. grants a capability and ability,
7. exposes `crimson_fang` as its evolution target,
8. round-trips through the canonical RPG runtime save.

The demo remains an engine-loadable Reference World project. Interactive RPG GUI is intentionally deferred until the Phase 7B backend contract is complete.

## Validation

- pytest: 373 passed, 4 skipped
- compileall: PASS
- PySide6 imports in RPG/gameplay/core/events: 0
- pygame imports in RPG/gameplay/core/events: 0
- Batch 79 canonical demo verification: PASS

## Next

Batch 80 — Canonical Resolved Actor Build.
