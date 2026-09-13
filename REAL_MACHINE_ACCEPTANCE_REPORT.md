# Asteria v0.159.0 Real-machine acceptance

## Verified

- Editor starts through the VS Code `Asteria Editor` launch configuration on macOS.
- Complex Reference RPG opens through **File → Open Project**.
- Editor scene and RPG/battle workspace tabs render without a Qt traceback.
- Editor **Run Project** creates a live runtime subprocess from the canonical Game Start Definition.
- Automated playable validation completes New Game materialization, six-person party setup, boss interaction, battle actions, victory rewards, and exact save/reload state comparison.
- Final offscreen regression suite: **1150 passed**.
- `compileall src tests`: **pass**.

## Focused fix

The native pygame adapter now creates a resizable desktop window and handles `VIDEORESIZE` by updating the logical canvas dimensions. This keeps field, battle, and HUD layout usable after a real window resize without changing the frozen core/RPG/battle contracts.

The playable reference UI now uses arrow-key navigation with a visible selection. Enter applies the selected choice. Title choices, build rows, actor arrows, progression nodes, and battle skills also accept mouse clicks. Readable character names and labeled buttons replace the numbered engineering-test controls.

Changed files:

- `src/asteria/platform/pygame_backend.py`
- `src/asteria/runtime/playable_test_runtime.py`
- `reference_projects/complex_reference_rpg/PLAYTEST.md`
- `tests/test_playable_runtime_input.py`

## Remaining machine limitation

The current Codex managed desktop session can start the pygame subprocess, but does not expose that child window as an independently controllable accessibility surface. Consequently, keyboard movement, boss interaction, full GUI battle input, in-game F5 save/load, and direct FPS/input-latency measurement cannot be claimed as completed by this session. These are environment visibility limitations rather than automated runtime failures; the subprocess remains alive and the same path is covered by the playable validation harness.

## Verdict

**BLOCKED for independent GUI playable acceptance in this managed session.** The package is ready for a normal macOS desktop run where the pygame child window is visible and focusable.
