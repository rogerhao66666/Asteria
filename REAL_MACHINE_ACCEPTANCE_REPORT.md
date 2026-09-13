# Asteria v0.159.0 real-machine acceptance report

This report describes the current checkout at
`/Users/roger/Documents/Vscode/Asteria`, based on the v0.159.0 Complex
Reference RPG package.

## Environment and automated baseline

- macOS with the project virtual environment and declared editor/pygame/dev extras.
- Editor source imports from this checkout; the older ChatGPT and acceptance-clean copies are not part of the current workflow.
- `QT_QPA_PLATFORM=offscreen python -m pytest -q`: **1151 passed, 0 failed**.
- `python -m compileall -q src tests`: **pass**.

## Verified in the current package

- Editor starts and opens the Complex Reference RPG through **File → Open Project**.
- **Run Project** routes to the playable Runtime and uses the canonical Game Start Definition.
- Reference scene, RPG data, battle data, and playable manifest are present.
- Runtime UI presents named data with separate Character, Skills, and Equipment tabs, mouse selection, visible arrow controls, and no tofu/engineering-ID labels.
- Reference data covers the six-person party, secondary class, progression graph, passives, multiple weapons, weapon growth, equipment/accessories, formation, boss interaction, battle rewards, and save/load state.
- Equipment instances reject duplicate equip operations without corrupting the loadout.

## Focused fixes included

- Preview routing now selects the playable Runtime before the generic preview backend, preventing a blank/grid-only window when the Complex Reference RPG is run from the Editor.
- Runtime build menu labels and controls were rewritten for readable names and separate tabs; mouse clicks and arrow-key controls share the same selection path.
- Equipment instance identity is checked at the loadout boundary so repeated clicks produce a clear validation result instead of duplicated state.
- macOS Pygame window resize handling keeps the logical canvas and HUD layout in sync.

## GUI acceptance status

Automated playable validation covers New Game materialization, party/build
changes, boss interaction, battle resolution, victory rewards, and exact
save/reload comparison. In the Codex managed desktop session, the Pygame child
window can start but is not exposed as an independently focusable accessibility
surface. Therefore this session cannot honestly claim independent GUI PASS for
keyboard movement, boss Interact, full battle input, in-game F5 Save/Load,
window resize, FPS, or input-latency measurements. A normal macOS desktop run
with the child window focused is the remaining verification step.

## Final verdict

**BLOCKED for independent GUI playable acceptance in the managed session.**
The repository and documented workflow are ready for a normal macOS desktop
acceptance run; automated regression remains green.
