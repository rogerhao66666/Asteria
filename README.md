# Asteria v0.159.0 — Editor + Complex Reference RPG

This repository is the current working copy of the v0.159.0 Complex Reference
RPG acceptance baseline. Keep the checkout at:

`/Users/roger/Documents/Vscode/Asteria`

The Editor owns project authoring (`Project + Game Start Definition`). Player
progression and Player Save belong to the Runtime only.

## Start on macOS

```bash
cd "/Users/roger/Documents/Vscode/Asteria"
source .venv/bin/activate
python -m asteria.editor
```

In the Editor choose **File → Open Project…** and open:

`reference_projects/complex_reference_rpg/project.asteria.json`

Then choose **Run Project**. The normal flow is **New Game → play the field →
open the runtime Character menu with C → interact with the boss → complete the
battle → save in Runtime with F5 → restart → Load Game**. Use the arrow keys to
move, E/Enter/Space to interact or confirm, and Esc to quit the Runtime. The
Character menu separates Character, Skills, and Equipment tabs; mouse clicks
and arrow-key navigation are both supported.

## Install and verify

If the virtual environment does not exist:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[editor,pygame,dev]"
```

The current automated baseline is **1151 passed, 0 failed**. Compile checks
also pass:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
python -m compileall -q src tests
```

For the complete manual checklist and known managed-session limitation, see
[`REAL_MACHINE_ACCEPTANCE_REPORT.md`](REAL_MACHINE_ACCEPTANCE_REPORT.md) and
[`START_HERE_MAC.md`](START_HERE_MAC.md). Historical batch documents remain
provenance and are not assembly instructions for this checkout.
