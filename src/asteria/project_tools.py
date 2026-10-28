"""Project maintenance commands: upgrade to the current format and export a playable game.

asteria-upgrade path/to/project.asteria.json        # rewrites at the current version (.bak kept)
asteria-export  path/to/project.asteria.json OUT    # portable game folder with run_game.py
asteria-export  ... OUT --pyz --app "My Game"        # also a single-file .pyz and a macOS .app

An exported folder carries the engine (``engine/asteria``), so it runs with
only Python and pygame-ce installed — not from the Asteria repository. The
``.pyz`` is the same folder in one file: it unpacks once into the user cache
and keeps saves in a per-game data folder that survives updates.

From the standalone Asteria app (``asteria.frozen``) the macOS app / game folder is a copy of
the bundled AsteriaPlayer with the game inside, so players need no Python at all.

The engine copy carries the native (C++) kernel library, built first when it
is missing or out of date. When it cannot be built the export still succeeds
and its report warns that the game runs on the slower kernels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import shutil
import stat
import subprocess
import sys
import zipapp
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_FILE = "project.asteria.json"
RESOURCE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".ogg",
    ".wav",
    ".mp3",
    ".json",
    ".ttf",
    ".otf",
}
NOTICE_NAMES = ("CREDITS.md", "CREDITS.txt", "LICENSE", "LICENSE.txt", "LICENSE.md")
RESOURCE_DIRS = ("reference_data",)

LAUNCHER = '''"""Launch this exported Asteria game (needs Python 3.12+ with pygame-ce)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if (HERE / "engine").is_dir():  # the engine travels with the game
    sys.path.insert(0, str(HERE / "engine"))

from asteria.runtime.preview import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main([str(HERE / "{project}"), *sys.argv[1:]]))
'''

PYZ_MAIN = '''"""Packaged Asteria game: unpacks once into the user cache, keeps saves in the user
data folder."""
import os
import shutil
import sys
import zipfile
from pathlib import Path

NAME = {name!r}
BUILD = {build!r}


def _user_dir(kind):
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / ("Caches" if kind == "cache" else "Application Support")
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", home))
    if kind == "cache":
        return Path(os.environ.get("XDG_CACHE_HOME", home / ".cache"))
    return Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))


def unpack(archive):
    target = _user_dir("cache") / "Asteria" / f"{{NAME}}-{{BUILD}}"
    if not (target / ".complete").is_file():
        shutil.rmtree(target, ignore_errors=True)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(target, [n for n in bundle.namelist() if n.startswith(("engine/",
            "game/"))])
        (target / ".complete").write_text(BUILD)
    saves = _user_dir("data") / NAME / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    link = target / "game" / "saves"
    if not link.exists():
        try:
            link.symlink_to(saves, target_is_directory=True)
        except OSError:  # no symlinks (some Windows setups): saves stay with this build
            link.mkdir(parents=True, exist_ok=True)
    return target


def main(argv=None):
    target = unpack(Path(__file__).resolve().parent)
    sys.path.insert(0, str(target / "engine"))
    from asteria.runtime.preview import main as run

    return run([str(target / "game" / {project!r}), *(sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    raise SystemExit(main())
'''

APP_LAUNCHER = """#!/bin/sh
# {name}: runs the bundled game with ASTERIA_PYTHON, else python3 (needs pygame-ce).
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "${{ASTERIA_PYTHON:-python3}}" "$HERE/../Resources/{archive}" "$@"
"""


def _registry():
    from asteria.runtime.component_registry import default_component_registry

    return default_component_registry()


def load_project(path):
    from asteria.project import Project

    return Project.load_json(Path(path), _registry())


def upgrade_project(path, *, backup=True):
    """Rewrite a project file at the current format version; returns (old, new) versions."""
    path = Path(path)
    old_version = json.loads(path.read_text(encoding="utf-8")).get("version")
    project = load_project(path)
    if backup:
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    project.save_json(path)
    return old_version, project.to_data()["version"]


@dataclass
class ExportReport:
    output: Path
    files: list[Path] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _manifest_paths(value):
    if isinstance(value, str):
        if Path(value).suffix.lower() in RESOURCE_SUFFIXES and not Path(value).is_absolute():
            yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _manifest_paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from _manifest_paths(item)


def referenced_files(project, root):
    """Relative paths of every resource the project (and its playable manifest) uses."""
    root = Path(root)
    paths = set()
    for record in project.assets.records():
        paths.add(str(record.source_path))
    for asset in project.assets.snapshot():
        if not asset.source.uri:  # data-only assets (a particle effect) have no file
            continue
        uri = Path(asset.source.uri)
        if not uri.is_absolute():
            paths.add(str(uri))
    manifest = root / "playable_test_manifest.json"
    if manifest.is_file():
        paths.add(manifest.name)
        paths.update(_manifest_paths(json.loads(manifest.read_text(encoding="utf-8"))))
    for directory in RESOURCE_DIRS:
        base = root / directory
        if base.is_dir():
            paths.update(str(p.relative_to(root)) for p in base.rglob("*") if p.is_file())
    return sorted(paths)


def export_game(project_path, output, *, allow_missing=False, bundle_engine=True):
    """Copy a project and everything it references into ``output`` with a launcher."""
    project_path = Path(project_path)
    root = project_path.parent
    output = Path(output)
    project = load_project(project_path)
    report = ExportReport(output)
    files = referenced_files(project, root)
    report.missing = [p for p in files if not (root / p).is_file()]
    if report.missing and not allow_missing:
        raise FileNotFoundError("missing project resources: " + ", ".join(report.missing))
    output.mkdir(parents=True, exist_ok=True)
    project.save_json(output / PROJECT_FILE)
    report.files.append(output / PROJECT_FILE)
    notice_dirs = set()
    for relative in files:
        source = root / relative
        if not source.is_file():
            continue
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report.files.append(target)
        notice_dirs.update(
            parent for parent in source.parents if root in parent.parents or parent == root
        )
    for directory in notice_dirs:  # attribution / license files travel with the assets
        for name in NOTICE_NAMES:
            notice = directory / name
            if notice.is_file():
                target = output / notice.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(notice, target)
                report.files.append(target)
    if bundle_engine:
        library = _native_library(report)
        report.files.extend(_copy_engine(output / "engine", library))
    launcher = output / "run_game.py"
    launcher.write_text(LAUNCHER.format(project=PROJECT_FILE), encoding="utf-8")
    report.files.append(launcher)
    return report


def _native_library(report):
    """The native kernel library to ship (built now when missing or out of date), or ``None``.
    A problem becomes a report warning: the kernels are a speed-up, never a reason to fail."""
    from asteria.kernels import build_native

    try:
        usable, reason = build_native.ensure()
    except Exception as exc:  # whatever goes wrong here, the export goes on
        usable, reason = False, f"not checked ({exc})"
    if reason and usable:
        report.warnings.append(
            f"Native kernels: the library is {reason}. The game carries the older build."
        )
    elif reason:
        report.warnings.append(
            f"Native kernels not included: the library is {reason}. The game runs on the "
            "slower numpy or python kernels; install a C++ compiler (macOS: xcode-select "
            "--install) and export again."
        )
    return build_native.library_name() if usable else None


def _copy_engine(target, library=None):
    """The ``asteria`` package (sources only) so the export runs without an installed engine,
    plus ``library`` (the checked native kernel library) in its place."""
    import asteria

    source = Path(asteria.__file__).resolve().parent
    shutil.rmtree(target / "asteria", ignore_errors=True)
    shutil.copytree(
        source,
        target / "asteria",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "libasteria_kernels.*", ".*.tmp"),
    )
    if library is not None:
        shutil.copy2(library, target / "asteria" / "kernels" / "native" / Path(library).name)
    return sorted(p for p in (target / "asteria").rglob("*") if p.is_file())


def _slug(name):
    return (
        "".join(c if c.isalnum() or c in "-_" else "_" for c in str(name).strip()) or "AsteriaGame"
    )


def build_pyz(game_folder, output, *, name):
    """One-file build of an exported game folder (``python Game.pyz`` runs it)."""
    game_folder, output = Path(game_folder), Path(output)
    files = sorted(
        p for p in game_folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts
    )
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(game_folder)).encode())
        digest.update(path.read_bytes())
    build = digest.hexdigest()[:16]
    staging = output.parent / f".{output.name}.staging"
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(game_folder / "engine", staging / "engine")
    shutil.copytree(
        game_folder,
        staging / "game",
        ignore=shutil.ignore_patterns("engine", "run_game.py", "saves", "__pycache__"),
    )
    (staging / "__main__.py").write_text(
        PYZ_MAIN.format(name=_slug(name), build=build, project=PROJECT_FILE), encoding="utf-8"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    zipapp.create_archive(staging, output, interpreter="/usr/bin/env python3", compressed=True)
    shutil.rmtree(staging)
    return output


def build_macos_app(pyz, output_dir, *, name, identifier=None):
    """``Name.app`` around a ``.pyz``: double-clickable on macOS, runs with the user's python3 +
    pygame-ce."""
    pyz = Path(pyz)
    app = Path(output_dir) / f"{name}.app"
    shutil.rmtree(app, ignore_errors=True)
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "Resources").mkdir(parents=True)
    shutil.copy2(pyz, app / "Contents" / "Resources" / pyz.name)
    executable = app / "Contents" / "MacOS" / _slug(name)
    executable.write_text(APP_LAUNCHER.format(name=name, archive=pyz.name), encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    info = {
        "CFBundleName": name,
        "CFBundleDisplayName": name,
        "CFBundleIdentifier": identifier or f"com.asteria.{_slug(name).lower()}",
        "CFBundleExecutable": executable.name,
        "CFBundlePackageType": "APPL",
        "CFBundleVersion": "1",
        "CFBundleShortVersionString": "1.0",
        "NSHighResolutionCapable": True,
    }
    with (app / "Contents" / "Info.plist").open("wb") as handle:
        plistlib.dump(info, handle)
    return app


def build_player_game(game_folder, output_dir, *, name, player, identifier=None):
    """A game that needs no Python: a copy of the frozen ``player`` (``AsteriaPlayer.app`` or
    the ``AsteriaPlayer`` folder) named after the game, with the exported folder as its
    ``game`` (macOS: ``Name.app/Contents/Resources/game``; elsewhere: ``Name/game``)."""
    from asteria.frozen import PLAYER_NAME, player_executable

    player = Path(player)
    slug = _slug(name)
    skip = shutil.ignore_patterns("run_game.py", "saves", "__pycache__")
    if player.suffix != ".app":
        target = Path(output_dir) / slug
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(player, target, symlinks=True)
        program = player_executable(target)
        program.rename(program.with_name(program.name.replace(PLAYER_NAME, slug)))
        shutil.copytree(game_folder, target / "game", ignore=skip)
        return target
    app = Path(output_dir) / f"{name}.app"
    shutil.rmtree(app, ignore_errors=True)
    shutil.copytree(player, app, symlinks=True)
    contents = app / "Contents"
    with (contents / "Info.plist").open("rb") as handle:
        info = plistlib.load(handle)
    (contents / "MacOS" / info["CFBundleExecutable"]).rename(contents / "MacOS" / slug)
    info.update(
        CFBundleName=name,
        CFBundleDisplayName=name,
        CFBundleIdentifier=identifier or f"com.asteria.{slug.lower()}",
        CFBundleExecutable=slug,
    )
    with (contents / "Info.plist").open("wb") as handle:
        plistlib.dump(info, handle)
    shutil.copytree(game_folder, contents / "Resources" / "game", ignore=skip)
    _sign_ad_hoc(app)
    return app


def _sign_ad_hoc(app):
    """Seal ``app`` again after it was changed (ad-hoc: no developer identity). Unsealed, a
    downloaded copy is reported as damaged instead of from an unidentified developer."""
    codesign = shutil.which("codesign") if sys.platform == "darwin" else None
    if codesign is None:
        return False
    result = subprocess.run(
        [codesign, "--force", "--deep", "--sign", "-", str(app)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


class _Bundled:
    """Default of ``package_game(player=...)``: the player inside the standalone app, if any."""

    def __repr__(self):  # shown in signatures (the manual's API chapter)
        return "<bundled player>"


_BUNDLED = _Bundled()


def package_game(
    project_path,
    output,
    *,
    name=None,
    pyz=True,
    app=False,
    allow_missing=False,
    player=_BUNDLED,
):
    """Export a game folder, then the single-file build and (optionally) the macOS app next to it.

    With a frozen ``player`` (default: the one inside the standalone Asteria app, if any) the
    ``app`` is the player with the game inside - ``Name.app`` on macOS, a ``Name`` folder
    elsewhere - and runs without Python; otherwise it is a launcher around the ``.pyz``.

    Returns ``{"folder": Path, "pyz": Path | None, "app": Path | None, "report": ExportReport,
    "standalone": bool}`` (``standalone``: the app needs no Python).
    """
    if player is _BUNDLED:
        from asteria.frozen import player_runtime

        player = player_runtime()
    output = Path(output)
    name = name or load_project(project_path).name or "Asteria Game"
    folder = output / f"{_slug(name)}_folder"
    report = export_game(project_path, folder, allow_missing=allow_missing)
    standalone = bool(app and player is not None)
    result = {"folder": folder, "pyz": None, "app": None, "report": report}
    result["standalone"] = standalone
    if pyz or (app and player is None):
        result["pyz"] = build_pyz(folder, output / f"{_slug(name)}.pyz", name=name)
    if app and player is not None:
        result["app"] = build_player_game(folder, output, name=name, player=player)
    elif app:
        result["app"] = build_macos_app(result["pyz"], output, name=name)
    return result


def upgrade_main(argv=None):
    parser = argparse.ArgumentParser(
        description="Upgrade an Asteria project file to the current format"
    )
    parser.add_argument("project")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args(argv)
    old, new = upgrade_project(args.project, backup=not args.no_backup)
    print(f"{args.project}: version {old} -> {new}")
    return 0


def export_main(argv=None):
    parser = argparse.ArgumentParser(description="Export an Asteria project as a playable game")
    parser.add_argument("project")
    parser.add_argument("output")
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument(
        "--pyz", action="store_true", help="also build a single-file game (Name.pyz)"
    )
    parser.add_argument(
        "--app",
        action="store_true",
        help="also build a macOS app bundle (Name.app); from the standalone Asteria app, a game "
        "that runs without Python",
    )
    parser.add_argument("--name", help="game name (default: the project name)")
    args = parser.parse_args(argv)
    if not (args.pyz or args.app):
        report = export_game(args.project, args.output, allow_missing=args.allow_missing)
        print(f"Exported {len(report.files)} files to {report.output}")
        for missing in report.missing:
            print(f"  missing: {missing}")
        for warning in report.warnings:
            print(f"  warning: {warning}")
        print(f"Run: python {report.output / 'run_game.py'}")
        return 0
    result = package_game(
        args.project,
        args.output,
        name=args.name,
        pyz=args.pyz,
        app=args.app,
        allow_missing=args.allow_missing,
    )
    for missing in result["report"].missing:
        print(f"  missing: {missing}")
    for warning in result["report"].warnings:
        print(f"  warning: {warning}")
    print(f"Game folder: {result['folder']}  (python run_game.py)")
    if result["pyz"] is not None:
        print(f"Single file: {result['pyz']}  (python3 {result['pyz'].name})")
    if result["standalone"]:
        print(f"Standalone:  {result['app']}  (no Python needed)")
    elif result["app"] is not None:
        print(
            f"macOS app:   {result['app']}  (needs python3 with pygame-ce, or set ASTERIA_PYTHON)"
        )
    return 0
