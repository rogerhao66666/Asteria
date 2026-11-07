# Phase 5 Batch 37 — Event Context / State

Version: `v0.37.0a37`

## Goal

Add deterministic event state on top of the Batch 36 VM without coupling
events to dialogue, quests, combat, rendering, or the Editor.

## Added

- `EventContext`
  - global switches
  - global variables
  - local/self-scoped state
  - JSON-compatible serialization
- `EventCondition`
  - switch / variable / local sources
  - ==, !=, <, <=, >, >=
- intrinsic Event VM state commands:
  - `SET_SWITCH`
  - `SET_VARIABLE`
  - `SET_LOCAL`
  - `IF_FALSE_SKIP`

## Why this design

The VM remains a small deterministic executor. State lives in an explicit
`EventContext`, so future NPC events, common events, save games, autorun
events, and tests can share or isolate state deliberately.

Local state is scoped by an external stable identifier instead of being tied
to Python object identity. This keeps save/load and reusable event programs
possible.

## Not included yet

- jump labels / general branching
- interaction/proximity/facing
- dialogue / choices
- common/parallel/autorun scheduling
- inventory/world commands
- quest/battle-specific logic

Next recommended batch: interaction foundation.
