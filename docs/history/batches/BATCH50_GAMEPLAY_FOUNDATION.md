# Phase 6 Batch 50 — Generic Gameplay Foundation

Version: `v0.50.0a50`

## Scope

Phase 6 starts from the lowest reusable gameplay layer:

- `StatBlock`
- `ResourceValue`
- `ResourcePool`
- `TagSet`
- canonical persistent `GameplayAttributesComponent`
- Python Authoring API access to gameplay attributes

No RPG-specific stat names are built into the engine.

Examples of valid game-defined stats/resources/tags:

```text
power
speed
temperature
combo_meter
hp
mana
stamina
guard
actor.player
enemy.boss
element.fire
state.poisoned
```

## Why this layer comes first

Abilities, effects, modifiers, states, conditions and targeting all need a stable
way to read/write numeric attributes, bounded resources and classification tags.
They should depend on this small generic layer rather than hardcoding RPG rules.

## Runtime model

`StatBlock`
- named finite numeric values
- set/add/get/require
- deterministic JSON data

`ResourcePool`
- named bounded resources
- minimum/current/maximum
- clamp
- spend without partial failure
- restore
- optional ratio preservation when maximum changes

`TagSet`
- normalized lowercase tags
- deterministic sorted serialization
- contains / all / any

## Persistent component

`GameplayAttributesComponent` stores JSON-native canonical fields:

- `stats`
- `resources`
- `tags`

This keeps Project serialization, Inspector metadata and scripting on one source
of truth.

## Python Authoring API

```python
hero = project.scene("Town").entity("Hero")

hero.gameplay.set_stat("power", 15)
hero.gameplay.define_resource("hp", 100, current=80)
hero.gameplay.add_tag("actor.player")
```

The same command/transaction path used by Batch 47 remains available in the
Editor, so script-driven gameplay edits remain undoable.

## Next

Batch 51 should add the generic Modifier / Effect evaluation layer on top of
Stats, Resources and Tags. It must remain deterministic and game-agnostic.
