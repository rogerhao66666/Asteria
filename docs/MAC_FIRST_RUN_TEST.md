# macOS first-run checklist — v0.159.0

Use only the current checkout at
`/Users/roger/Documents/Vscode/Asteria` and the project
`reference_projects/complex_reference_rpg/project.asteria.json`.

## Environment and automated checks

```bash
cd "/Users/roger/Documents/Vscode/Asteria"
source .venv/bin/activate
QT_QPA_PLATFORM=offscreen python -m pytest -q
python -m compileall -q src tests
```

Expected current result: **1151 passed, 0 failed**; compileall exits 0.

## Editor workflow

Start with `python -m asteria.editor`, then use **File → Open Project…**. Open
the Complex Reference RPG project and confirm the Scene, RPG, Battle, UI,
Events, and Code workspaces render. Use **Run Project** to launch the Runtime;
**Play Current Scene** is not the acceptance entry point.

## Runtime workflow

Select **New Game**. Test movement with **↑ ↓ ← →**, interaction/confirm with
**E**, **Enter**, or **Space**, the build menu with **C**, Runtime Player Save
with **F5**, and quit with **Esc**. Use mouse clicks or arrow-key navigation in
the Character, Skills, and Equipment tabs. Complete the boss battle, verify
rewards and progression, save, restart, choose **Load Game**, and compare the
state.

## Editor-only checks

Project Save remains an authoring action. Check scene selection, camera
viewport pan/zoom, tile paint/erase/fill, layer visibility and collision
overlays, undo/redo, and graph node selection/dragging/persistence. Do not use
Editor controls to create or edit a Player Save.

## Reporting

Record the exact action, expected result, actual result, screenshot, and
terminal traceback for each failure. The managed Codex desktop may not expose a
child Pygame window as an independently focusable surface; if so, report GUI
keyboard/F5 steps as environment-blocked rather than claiming a GUI PASS.
