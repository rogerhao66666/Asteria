# Phase 7 Batch 60 — RPG Actor / Class Toolkit

Version: `v0.60.0a60`

Phase 7 begins above the frozen Phase 6 generic gameplay framework.

## Added

- `ActorDefinition`
- `ClassDefinition`
- `RpgActorRuntime`
- `RpgDatabase`
- beginner-ready `simple_rpg_database()`

Actor/Class are RPG convenience concepts. They compose generic `StatBlock`,
`ResourcePool`, `TagSet`, and ability IDs rather than changing Phase 6.

## Default-first UX

The Simple RPG preset contains a ready Hero + Adventurer class with HP/MP,
common starter stats, and Basic Attack. These values are editable template
content and have no special engine semantics.

## Boundary

`asteria.gameplay` remains generic. RPG vocabulary lives under `asteria.rpg`.

Next Batch 61: Item / Equipment toolkit.
