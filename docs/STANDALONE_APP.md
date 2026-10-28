# The standalone Asteria app

[繁體中文](STANDALONE_APP.zh-TW.md)

The standalone app is the whole engine in one download: the editor, playtesting and game export.
You do not install Python, PySide6 or pygame, and you compile nothing. Games you export from it
run on players' machines without Python too.

## For game makers: download and run

### macOS (Apple silicon, macOS 11 or newer)

1. Download `Asteria-<version>-macos-arm64.dmg` (or the `.zip`).
2. Open the `.dmg` and drag **Asteria** onto **Applications**.
3. The first time only: the app is not signed by an Apple developer, so macOS stops a
   double-click. **Right-click (or Control-click) Asteria ▸ Open**, then **Open** in the dialog.
   On macOS 15 and later, if no **Open** button appears: open **System Settings ▸ Privacy &
   Security**, scroll to *"Asteria" was blocked*, click **Open Anyway**.
4. After that Asteria opens with a normal double-click.

The first start opens your own copy of the **Full Verification** demo, as in a source install.
**File ▸ New from Template…** starts a new project; the asset library is inside the app.

### What works the same as a source install

| | Standalone app |
| --- | --- |
| Editor, every page | yes |
| Playtest (▶) and the debugger | yes: the app starts itself as the game |
| Local multiplayer server | yes |
| C++ speed-ups (native kernels) | yes, already built inside (no compiler needed) |
| Your project's own Python code | yes: the whole Python standard library is inside; extra pip packages are not |
| **File ▸ Export Game…** | yes, see below |
| Web export (`asteria-export-web`) | no: it needs `pygbag`, use a source install |

### Exporting a game players can run without Python

**File ▸ Export Game…** with **macOS app (.app)** ticked makes `Your Game.app`. It contains a
small player (no editor, no Qt) and your game, so players just double-click it (the same
right-click ▸ Open the first time applies). Saves go to
`~/Library/Application Support/Asteria Games/<Game name>/saves`, so they survive replacing the
app with a newer build. The `.pyz` and the game folder are still made on request; those two need
Python 3.12+ with pygame-ce.

### Command line

The app's program takes the same commands as a source install:

```bash
/Applications/Asteria.app/Contents/MacOS/Asteria                       # the editor
/Applications/Asteria.app/Contents/MacOS/Asteria preview path/to/project.asteria.json
/Applications/Asteria.app/Contents/MacOS/Asteria export path/to/project.asteria.json OUT --app
```

## For maintainers: building it

On the platform you build for (PyInstaller does not cross-compile):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[pygame,moderngl,editor,mv,fast,package]"
.venv/bin/python scripts/build_app.py
```

It writes `dist/Asteria.app` (Windows / Linux: `dist/Asteria/`), `dist/Asteria-<version>-
<platform>.zip` and on macOS a `.dmg`. `build/` and `dist/` are git-ignored; never commit them.
Options: `--sign "Developer ID Application: …"` signs with your identity (default: ad-hoc),
`--skip-player` and `--no-archive` make a quicker build while working on the script.

How it is put together (`scripts/build_app.py`, `src/asteria/frozen.py`):

- PyInstaller freezes the interpreter, the standard library, PySide6, pygame-ce, numpy and
  ModernGL. The engine itself is **not** frozen: it is copied as source to
  `Contents/Resources/engine/src/asteria` (precompiled), with `engine/asset_library` and
  `engine/reference_projects/full_verification_demo`. Every path the engine finds from
  `__file__` therefore works as in a checkout, and an export copies the engine into the game.
- The editor starts the playtest and the multiplayer server as `sys.executable -m <module>`. In
  the app `sys.executable` is the app itself; `asteria.frozen.editor_main` runs those `-m` / `-c`
  command lines as Python would.
- `AsteriaPlayer.app` (no Qt) sits in `Contents/Resources/player/`. An export copies it, renames
  it after the game, puts the game in `Contents/Resources/game` and seals it again (ad-hoc).
- The C++ kernel library is built (universal arm64 + x86_64) before it is copied; without a
  compiler the app still works on the numpy kernels.

Before a release, check the frozen app by hand in real windows: open the Full Verification demo,
playtest it, export a game and start the exported game.

Not done yet: Developer ID signing with notarization (needs an Apple Developer account), and
Windows / Linux builds in CI (the script already makes a folder build there; it has not been
run on those systems).
