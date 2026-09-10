# Phase 5 Batch 46 — Central Authoring Workspace

Version: `v0.46.0a46`

## Goal

Make visual authoring and code authoring first-class peers inside the same
Asteria Editor rather than adding scripting later as an escape hatch.

## Added

The main central workspace now has four switchable authoring modes:

- **Scene** — existing world/TileMap/entity viewport
- **Code** — Python project-script workspace
- **Event** — Batch 45 Event Editor
- **Animation** — existing animation authoring/preview view

They are available both as central tabs and Run-toolbar mode actions.

## Code workspace foundation

The first Code workspace includes:

- fixed-width Python editor
- canonical current-project context indicator
- project-relative `scripts/main.py`
- load existing script when a project opens
- save script into the project directory
- independent code-buffer dirty state
- Run control reserved for Batch 47 Authoring API integration

The Run button is deliberately disabled in Batch 46. Executing arbitrary code
before a stable canonical authoring API exists would encourage scripts to reach
into editor/Qt internals and create an architecture we would later need to
break.

## Architecture invariant

```text
Scene GUI ─────┐
Event GUI ─────┼──> canonical Asteria Project / Scene / Entity / Component / Event data
Python Code ───┘
```

The Code workspace is not a second world model. Batch 47 will expose a narrow
Python Authoring API over the same canonical data edited by the GUI.

## Important separation

- Project JSON owns canonical game data.
- Project scripts live as normal source files under `scripts/`.
- Editor workspace selection is presentation state, not game data.
- Runtime/Event/Core remain independent of Qt.

## Next

Batch 47 — Asteria Python Authoring API v1:

- project / scene / entity lookup helpers
- canonical Transform/Component authoring
- Event authoring helpers
- transactional mutation boundary for Editor undo/refresh
- safe Code workspace Run integration
