"""Running from the standalone app (AST-06): no Python install, the engine ships as source.

``scripts/build_app.py`` freezes two programs with PyInstaller:

- **Asteria** (the editor app). The interpreter, PySide6, pygame-ce and numpy are frozen; the
  engine itself sits beside them as plain ``.py`` files (``engine/src/asteria``, with
  ``engine/asset_library`` and the reference project the Full Verification template copies), so
  every path the engine finds from ``__file__`` works as in a source checkout and an export can
  copy the engine into a game. The editor starts the playtest and the local multiplayer server
  as ``sys.executable -m <module>``; in the frozen app ``sys.executable`` is the app itself, so
  :func:`run_python_style` takes those ``-m`` / ``-c`` command lines.
- **AsteriaPlayer** (no Qt), kept inside the editor app. An exported game is a copy of it with
  the game in ``game/`` (on macOS ``Name.app/Contents/Resources/game``), so players need no
  Python either. :func:`player_main` finds that game, puts its ``game/engine`` on ``sys.path``
  and runs it from a folder in the user's data where saves can be written (an app bundle is
  read-only once it is signed or moved to /Applications).
"""

from __future__ import annotations

import os
import runpy
import shutil
import sys
from pathlib import Path

PROJECT_FILE = "project.asteria.json"
PLAYER_NAME = "AsteriaPlayer"
# interpreter switches the editor (or a tool) may put before -m / -c; none changes anything here
_IGNORED_FLAGS = {"-I", "-u", "-B", "-E", "-s", "-S", "-O", "-OO", "-q"}


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def engine_root():
    """``engine/`` of the frozen app (``src/asteria``, ``asset_library``, ...), else ``None``."""
    if not is_frozen():
        return None
    return Path(__file__).resolve().parents[2]


def player_runtime():
    """The frozen player an export copies: ``$ASTERIA_PLAYER``, else the one inside the editor
    app (``AsteriaPlayer.app`` on macOS, the ``AsteriaPlayer`` folder elsewhere), else
    ``None`` (a source checkout: exports then run with the player's own python3)."""
    override = os.environ.get("ASTERIA_PLAYER")
    if override:
        path = Path(override).expanduser()
        return path if path.exists() else None
    root = engine_root()
    if root is None:
        return None
    for candidate in (
        root.parent / "player" / f"{PLAYER_NAME}.app",
        root.parent / "player" / PLAYER_NAME,
    ):
        if candidate.exists():
            return candidate
    return None


def player_executable(player):
    """The program inside a player (``.app`` bundle or folder)."""
    player = Path(player)
    if player.suffix == ".app":
        import plistlib

        with (player / "Contents" / "Info.plist").open("rb") as handle:
            name = plistlib.load(handle)["CFBundleExecutable"]
        return player / "Contents" / "MacOS" / name
    suffix = ".exe" if os.name == "nt" else ""
    return player / f"{PLAYER_NAME}{suffix}"


def run_python_style(argv):
    """Run ``[flags] -m module args``, ``[flags] -c code args`` or ``[flags] script.py args`` as
    ``python`` would.

    Returns ``None`` when ``argv`` is not such a command line (the caller starts its own
    program instead); otherwise the exit code. ``SystemExit`` from the module passes through.
    """
    argv = list(argv)
    while argv and argv[0] in _IGNORED_FLAGS:
        argv.pop(0)
    if argv and argv[0].endswith(".py") and Path(argv[0]).is_file():
        sys.argv = argv
        sys.path.insert(0, str(Path(argv[0]).resolve().parent))
        runpy.run_path(argv[0], run_name="__main__")
        return 0
    if len(argv) < 2 or argv[0] not in ("-m", "-c"):
        return None
    if argv[0] == "-m":
        module, rest = argv[1], argv[2:]
        sys.argv = [module, *rest]
        runpy.run_module(module, run_name="__main__", alter_sys=True)
        return 0
    code, rest = argv[1], argv[2:]
    sys.argv = ["-c", *rest]
    exec(compile(code, "<string>", "exec"), {"__name__": "__main__"})  # noqa: S102
    return 0


def editor_main(argv=None):
    """Entry of the frozen editor app: a python-style command line (playtest, server, probes,
    scripts), one of the tools (``preview``, ``export``, ``upgrade``) or the editor itself."""
    argv = list(sys.argv[1:] if argv is None else argv)
    argv = [a for a in argv if not a.startswith("-psn_")]  # Finder's process serial number
    os.environ.setdefault("ASTERIA_ASSET_LIBRARY", str(engine_root() / "asset_library"))
    code = run_python_style(argv)
    if code is not None:
        return code
    tools = {
        "preview": "asteria.runtime.preview:main",
        "export": "asteria.project_tools:export_main",
        "upgrade": "asteria.project_tools:upgrade_main",
    }
    if argv and argv[0] in tools:
        module, function = tools[argv[0]].split(":")
        return getattr(__import__(module, fromlist=[function]), function)(argv[1:])
    from asteria.editor.shell import launch_editor

    sys.argv = [sys.argv[0], *argv]
    return launch_editor()


def bundled_game(executable):
    """The game folder an exported player carries next to ``executable``, or ``None``."""
    here = Path(executable).resolve().parent
    for candidate in (here.parent / "Resources" / "game", here / "game"):
        if (candidate / PROJECT_FILE).is_file():
            return candidate
    return None


def _user_data():
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support"
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", home))
    return Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))


def _game_name(game):
    try:
        import json

        name = json.loads((game / PROJECT_FILE).read_text(encoding="utf-8")).get("name")
    except (OSError, ValueError, AttributeError):
        name = None
    name = str(name or game.parent.name or "Asteria Game")
    return "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip() or "Game"


def writable_game_folder(game, data_root=None):
    """A folder the game runs from whose ``saves`` can be written.

    A game folder that is writable and not inside an app bundle is used as it is. Otherwise a
    folder in the user's data mirrors it - each entry linked (copied where links are not
    allowed), ``saves`` kept there for good - and is refreshed on every start, since a
    downloaded app may run from a different place each time (macOS app translocation).
    """
    game = Path(game)
    inside_app = any(part.endswith(".app") for part in game.resolve().parts)
    if not inside_app and os.access(game, os.W_OK):
        return game
    target = Path(data_root or _user_data()) / "Asteria Games" / _game_name(game)
    target.mkdir(parents=True, exist_ok=True)
    (target / "saves").mkdir(exist_ok=True)
    for entry in target.iterdir():
        if entry.name == "saves":
            continue
        if entry.is_symlink() or entry.is_file():
            entry.unlink()
        else:
            shutil.rmtree(entry)
    for entry in game.iterdir():
        if entry.name in ("saves", "engine"):
            continue
        link = target / entry.name
        try:
            link.symlink_to(entry, target_is_directory=entry.is_dir())
        except OSError:  # no symlinks (some Windows setups)
            if entry.is_dir():
                shutil.copytree(entry, link)
            else:
                shutil.copy2(entry, link)
    return target


def player_main(argv=None, executable=None):
    """Entry of the frozen player: the game it carries, or a project file given first."""
    argv = list(sys.argv[1:] if argv is None else argv)
    argv = [a for a in argv if not a.startswith("-psn_")]
    if argv and argv[0].endswith(".json"):
        project = Path(argv.pop(0)).expanduser().resolve()
        game = project.parent
    else:
        game = bundled_game(executable or sys.executable)
        if game is None:
            print(f"usage: {PLAYER_NAME} PROJECT.asteria.json [options]", file=sys.stderr)
            return 2
        project = game / PROJECT_FILE
    engine = game / "engine"
    if (engine / "asteria").is_dir() and str(engine) not in sys.path:
        sys.path.insert(0, str(engine))
    root = writable_game_folder(game)
    from asteria.runtime.preview import main as run

    return run([str(project), "--resource-root", str(root), *argv])
