# Phase 5 Batch 47 — Python Authoring API v1

Version: `v0.47.0a47`

The Code workspace now runs trusted local Python through a formal, Qt-free
Asteria authoring facade.

```python
scene = project.scene("Town")
hero = scene.entity("Hero")
hero.transform.position = (120, 88)

npc = scene.create_entity("Lina", x=160, y=96)
npc.event("Greeting").dialogue("Lina", "Hello").end()
```

## Invariant

GUI authoring and Python authoring mutate the same canonical
Project / Scene / Entity / Component / Event data.

Python scripts do not manipulate Qt widgets.

## Editor transaction policy

A script run applies authoring commands through one transaction.

- success -> recorded as one Undo/Redo step
- exception -> already-applied script changes are rolled back
- stdout / traceback -> Console

## API v1

- project scene lookup by stable ID or unique display name
- scene entity lookup by stable ID or unique display name
- create entity
- entity name / enabled
- transform position / x / y / rotation / scale
- create canonical EventProgram + EventBinding
- dialogue
- set switch
- set variable
- wait
- world command
- transfer convenience command
- end

Name lookup is a convenience only; persistent references remain stable IDs.

## Trust model

Project scripts are normal trusted local Python code. The Batch 47 runner is
not a security sandbox.

## Next

Batch 48 — Code workspace integration/polish:
script ergonomics, diagnostics, current selection context, and authoring API
discoverability before Phase 5 closure.
