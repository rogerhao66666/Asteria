# Phase 7 Batch 66 — Universal Lifecycle Hooks + Battle Outcome / Reward Handoff

Version: `v0.66.0a66`

## Core architecture

Asteria now has a generic `LifecycleHookBus` in Core.

This is intentionally **not battle-specific**. Any subsystem can publish a
named lifecycle seam:

- `world.door.opened`
- `rpg.item.before_use`
- `rpg.equipment.after_equip`
- `rpg.progression.rank_changed`
- `rpg.party.after_add`
- `rpg.battle.after_action`
- `rpg.battle.finished`
- `rpg.reward.after_apply`
- future quest/dialogue/crafting/shop/map/save/custom-plugin hooks

Hook names are strings rather than a closed enum. New tools/plugins can add
their own lifecycle points without editing engine core.

`LifecycleEventBridge` optionally maps any lifecycle hook to a Phase 5
`EventProgram`. Producers do not depend on Event VM. If the EventRunner is
busy, bridge requests queue instead of replacing active dialogue/cutscenes.

## Batch 66 RPG integration

Battle now emits lifecycle notifications for battle start, round boundaries,
turn readiness/end, before/after action, outcome resolution, and finish.

Battle outcome has no built-in HP/death semantics. The project injects an
`is_active(member)` predicate. A Simple RPG may use HP > 0; another project may
use tags, lives, capture state, scripted conditions, or custom rules.

`RewardRuntime` hands rolled reward data into caller-owned currency storage,
Inventory, and ProgressionRuntime. Reward and progression each emit their own
before/after lifecycle hooks.

Item use, equipment loadout changes, party membership changes, and progression
advancement now expose lifecycle seams too.

## Architectural rule

> Any meaningful Asteria workflow must remain event-connectable.

Subsystems should expose stable lifecycle seams around meaningful transitions
rather than requiring the Event VM to be hard-wired into every runtime class.

Next Batch 67: Project persistence integration for the Phase 7 RPG database and
runtime-facing toolkit data.
