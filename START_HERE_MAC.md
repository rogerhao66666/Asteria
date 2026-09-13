# Asteria — macOS first run

These steps use the current v0.159.0 Complex Reference RPG checkout:

`/Users/roger/Documents/Vscode/Asteria`

## 1. Install dependencies

Use the project virtual environment and its declared extras.

```bash
cd "/Users/roger/Documents/Vscode/Asteria"
python3 -m venv .venv                 # only if .venv is missing
source .venv/bin/activate
python -m pip install -e ".[editor,pygame,dev]"
```

## 2. Verify the checkout

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
python -m compileall -q src tests
```

The current result is **1151 passed, 0 failed** and compileall exits 0.

## 3. Open the Editor and project

```bash
python -m asteria.editor
```

In the Editor:

1. Choose **File → Open Project…**.
2. Open `reference_projects/complex_reference_rpg/project.asteria.json`.
3. Confirm the Project / Scene tree, Scene viewport, RPG, Battle, UI, Events,
   and Code tabs render.
4. Choose **Run Project**. This starts the canonical Game Start Definition;
   do not use a Player Save or a midgame profile to start the acceptance run.

## 4. Runtime smoke test

Choose **New Game** in the Runtime. The primary controls are:

- **↑ ↓ ← →** — move the player
- **E**, **Enter**, or **Space** — interact / confirm
- **C** — open or close Character / Build
- **F5** — save Player Save inside the Runtime
- **Esc** — close the Runtime

In Character / Build, use the separate **Character**, **Skills**, and
**Equipment** tabs. Secondary class, skill-tree nodes, passives, weapons,
weapon growth, armor, accessories, party, and formation are selected with
arrow keys or mouse clicks. Save after making a build change, close the
Runtime, run the project again, choose **Load Game**, and compare the state.

## 5. If the preview is blank

Stop the preview and verify that the Editor opened the project path above and
that this file exists:

`reference_projects/complex_reference_rpg/playable_test_manifest.json`

Restart the Editor and use **Run Project** again. A generic grid-only preview
usually means an older project or the wrong preview route was opened.

## 6. Authoring smoke test

After the Runtime check, return to the Editor and verify scene selection,
mouse selection, arrow-key camera adjustment, viewport pan/zoom, tile paint,
layer visibility/collision toggles, undo/redo, and project Save. Editor project
Save is separate from Runtime Player Save.

Also switch between the **Scene / RPG / Battle / UI / Events / Code** toolbar
modes and confirm the **Tile Palette** and **Layers** docks are visible only
in Scene mode, and hidden in every other mode.
