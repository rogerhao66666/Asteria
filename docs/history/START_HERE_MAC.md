> **歷史文件**（v0.94 的首次驗收清單）。現在的安裝與使用方式見 [`README.md`](../../README.md) 與 [`docs/ENGINE_HANDBOOK.md`](../ENGINE_HANDBOOK.md)。

# Asteria — Mac First-Run Test

Optional setup and reference-world checks for the v0.94.0a94 full canonical review package.
Batch 94 battle presentation is a data/coordinator foundation; these checks do
not constitute a playable battle checkpoint. Batch 93 Battle Core remains frozen
at v0.93.0a93, Batch 95 is on hold, and no fresh GUI playtest is claimed.

## 1. Environment
Use Python 3.12+.

Create a virtual environment and install the project with editor/runtime extras:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[editor,pygame,dev]"
```

## 2. Run automated checks

```bash
python -m pytest -q
python -m compileall -q src tests
```

Expected for the current v0.94.0a94 source:
- all applicable tests pass; optional backend tests require their dependencies
- packaging verification: 523 passed, 4 skipped because PySide6 was absent
- compileall exits 0

## 3. Launch the Editor

```bash
python -m asteria.editor
```

Smoke-check:
- Asteria Editor opens
- docks render with Asteria Dark styling
- Project/Scene hierarchy is usable
- Inspector updates on selection
- Scene Viewport pans/zooms
- undo/redo works
- no default-Qt/prototype visual regression is obvious

## 4. Open the Reference World

Open:

`AsteriaReferenceWorld.asteria.json`

Expected:
- project loads without schema errors
- Hero and Game Camera exist in the Scene
- assets appear in Asset Browser
- no missing stable-ID references

## 5. Play Current Scene

Press **F6** or click **Play Current Scene**.

Expected:
- external runtime preview opens
- Reference World renders with actual Asteria pixel assets
- WASD / arrow keys move the Hero
- Hero cannot walk through collision areas
- bridge is passable
- directional animation changes while moving
- camera follows Hero
- Escape closes preview
- Shift+F6 stops preview from Editor

## 6. Tile-authoring smoke test

In the Editor:
- select a TileMap render source / active layer
- Paint several tiles
- Erase several tiles
- test Rectangle and Fill
- undo and redo each operation
- add/remove/reorder Layers
- toggle layer visibility
- toggle Collision layer and inspect overlay

## 7. Save/Open safety

- make an edit and verify the dirty indicator
- Save
- make another edit
- Undo back to saved state
- verify clean state
- branch from history and verify dirty state
- close with unsaved changes and confirm prompt appears

## Report useful failures
For each failure record:
- exact action sequence
- expected behavior
- actual behavior
- screenshot if visual
- terminal traceback if present
- whether it reproduces after restart
