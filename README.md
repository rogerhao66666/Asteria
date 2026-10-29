# Asteria

**English** | [繁體中文](README.zh-TW.md)

**A 2D RPG engine and editor in Python.** Turn-based party battles and real-time action combat
share one data-driven core. Every rule with more than one sensible answer is an option in the
editor, and the sample games are data, not rules written into the engine. The editor has an
English and a Traditional Chinese interface.

> **Status: alpha (developer preview).** It is feature-complete and well tested, but the data
> format and the API may still change, and it has not yet run on many people's machines. This is
> a personal hobby project: issues are welcome, but replies are not guaranteed.

![The editor: the Scene workspace](docs/manual/images/editor_en_scene.png)

![The game: a turn-based battle](docs/manual/images/game_en_battle.png)

---

## Features

- **Editor** (PySide6): seven workspaces - Scene, Database, Battle, Presentation, Events, Code and
  Multiplayer. Records are forms: a change applies at once, Ctrl+Z undoes it. Paint maps, draw
  skill-tree graphs, import into the asset library, start a new project from a template, and switch
  the interface between English and Traditional Chinese while it runs.
- **Turn-based battles:** turn order and boost points; weaknesses, shields and breaks; multi-hit
  attacks; several weapons; main and sub jobs; skill trees; states; reflect and absorb; multi-phase
  bosses; summons; pets and capture; mixing; escape; battle rewards. Side-view placement, HUD
  portraits, camera and effects are all adjustable.
- **Real-time combat:** top-down and side-view share one core - hitboxes (invincibility frames,
  knockback, hit stun), combos, dodges, lock-on, cooldowns, projectiles, behaviour-tree AI, and
  platformer feel (coyote time, jump buffering, slopes, ladders).
- **RPG data:** jobs, skill trees, equipment (slots, sockets, sets, growth, random affixes, rarity,
  refining), drops, quests, shops, reputation, achievements, a bestiary, pets (species, levels,
  evolution), save slots and New Game+.
- **World:** layered maps, four-direction characters, dialogue and event programs, NPC states,
  weather and lighting, parallax backgrounds, and translatable built-in words.
- **Performance:** ECS column arrays; the hot loops have Python, numpy and C++ kernels with the same
  results, so it runs without compiling the C++.
- **Export:** a game folder ready to release, a single-file game (`.pyz`), a macOS app, and a
  standalone build that needs no Python.
- **Multiplayer prototype:** TCP sessions and lobby, live input sync, a co-op boss example, and
  SQLite player data (on one machine or a trusted local network).
- **RPG Maker MV import:** maps, database and events come across (see the asset note below).

## Install

Python 3.12 or later (macOS, Linux, Windows).

```bash
git clone https://github.com/rogerhao66666/Asteria.git
cd Asteria
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
python -m pip install -U pip
python -m pip install -e ".[pygame,editor,mv,dev]"
```

Optional extras: `pygame` (running games), `editor` (the PySide6 editor), `mv` (RPG Maker MV import,
needs Pillow), `moderngl` (GPU backend), `fast` (numpy kernels), `dev` (pytest, ruff), `package`
(the standalone app). To play games without the editor, `".[pygame]"` is enough. The C++ kernels
are optional: `python -m asteria.kernels.build_native`.

## Getting started

```bash
asteria-editor                                   # open the editor
asteria-preview reference_projects/full_verification_demo/project.asteria.json   # play a sample
asteria-export PROJECT.json OUT_DIR              # export a game folder ready to release
asteria-export PROJECT.json OUT_DIR --pyz --app  # also a single-file game and a macOS app
asteria-import-mv MV_PROJECT_DIR OUT.json        # import an RPG Maker MV project
asteria-upgrade PROJECT.json                     # bring an older project up to the current format
```

The first time the editor opens, it opens a copy of the Full Verification sample (kept in your user
folder, so the sample in the repository is never changed). For a new project: **File > New
Project…** (Ctrl+N), then pick Full Verification (a whole game, recommended), Basic RPG, Party RPG,
Action RPG or Completely Empty. **Run Project** (F6) plays from the start of the game; **Run Current
Scene** (Ctrl+F6) plays from the map you are on.

Default game keys: WASD / arrow keys to move, E to interact, Q for quests, Esc to pause, F5 to save
(all can be changed in the settings). Menus, dialogue and battles also work with the mouse.

The full user manual: [English](docs/manual/USER_MANUAL.en.md) /
[繁體中文](docs/manual/USER_MANUAL.zh-TW.md).

## Sample projects (`reference_projects/`)

| Project | What it shows |
| --- | --- |
| `full_verification_demo` | A turn-based JRPG that **uses every system**: four maps, three bosses, four party members, skill trees, jobs, several weapons, equipment refining and sockets, pet capture and evolution, summons, mixing, shops, quests, save and load, New Game+ |
| `party_rpg_demo` | A party RPG: weaknesses / shields / breaks, boost, ultimate skills, several weapons, multi-hit attacks, pets, mixing |
| `arpg_demo` | An action RPG: a town, a top-down field, a side-view mine, skill-tree builds, affix equipment |
| `arpg_multiplayer_demo` | The multiplayer version of the one above |

The samples' art and music are in the repository (`playable_assets/`), so they play as they are. To
rebuild a sample:

```bash
python reference_projects/full_verification_demo/build_project.py
```

Art is read from `asset_library/`. The music came from a larger Foozle music pack that is not in the
repository; without `ASTERIA_MUSIC_ASSETS` set, a rebuild keeps the music files already in the
repository, so rebuilding from the repository needs no extra download.

## Assets and licences

- **Code:** [MIT License](LICENSE). Games made with Asteria may be released and sold freely, without
  opening their source.
- **Bundled assets** (`asset_library/`, the samples' `playable_assets/`): mostly CC0, fonts under the
  SIL OFL. The source and licence of each one are in [`THIRD_PARTY_ASSETS.md`](THIRD_PARTY_ASSETS.md);
  libraries are in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
- **Your own game's assets:** anything whose licence lets you use it. Note that RPG Maker's built-in
  assets (RTP) and most official DLC are usually licensed only for games made with RPG Maker; after
  importing an MV project, replace them with assets you have the right to use before releasing.

Asteria is not affiliated with RPG Maker or its owners.

## Development

```bash
python -m pytest -q                              # all tests (about 3,600; about 8 minutes)
ruff check src scripts tests reference_projects  # every line ≤ 99 characters
ruff format --check src scripts tests reference_projects
scripts/docker_tests.sh                          # the suite on a clean Linux in Docker
```

GitHub Actions runs the lint and format check and the whole test suite on Linux (Python 3.12 and
3.13) and macOS on every push and pull request. `scripts/docker_tests.sh` runs the suite on a clean
Linux in Docker on your own machine. To contribute, see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Documentation

- [`docs/manual/`](docs/manual/): the user manual for game authors (English and Traditional Chinese,
  with screenshots). **Start here** if you want to make a game.
- [`docs/ENGINE_HANDBOOK.md`](docs/ENGINE_HANDBOOK.md): install, layout, how each system works and
  the known limits (Traditional Chinese). Start here if you want to work on the engine.
- [`docs/audits/DECISION_LOG.md`](docs/audits/DECISION_LOG.md): the reason, tests and evidence for each
  design decision (Traditional Chinese).
- [`docs/spec/`](docs/spec/): product and asset specifications (design goals; the manual says what
  is implemented today).
- [`docs/README.md`](docs/README.md): an index of every document, marking which are current and
  which are history.
- [`docs/history/`](docs/history/): records and audits from development.
