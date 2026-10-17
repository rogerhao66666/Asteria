"""CB12: component migrations, project upgrade and playable game export (ASTERIA_SPEC §33)."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from asteria.core import Component, ComponentRegistry, Field, component_schema
from asteria.core.migration import component_migration
from asteria.core.serialization import deserialize_component
from asteria.project_tools import export_game, load_project, package_game, upgrade_project

OLD_PROJECT = (  # a project saved by an older build
    Path(__file__).resolve().parents[1] / "AsteriaPhase7B_AbilityPassiveDemo.asteria.json"
)
REF = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"


@component_schema(
    type_name="test.Lantern",
    version=3,
    fields=(Field("brightness", float, 1.0), Field("color", str, "white")),
)
class Lantern(Component):
    def __init__(self):
        super().__init__()
        self.brightness = 1.0
        self.color = "white"


@component_migration("test.Lantern", from_version=1)
def _lantern_v1(fields):
    fields["brightness"] = float(fields.pop("lumens")) / 100.0
    return fields


@component_migration("test.Lantern", from_version=2)
def _lantern_v2(fields):
    fields.setdefault("color", "amber")
    return fields


def _registry():
    registry = ComponentRegistry()
    registry.register(Lantern)
    return registry


def test_old_component_versions_are_migrated_step_by_step():
    lantern = deserialize_component(
        {"type": "test.Lantern", "version": 1, "fields": {"lumens": 250}}, _registry()
    )
    assert (lantern.brightness, lantern.color) == (2.5, "amber")
    current = deserialize_component(
        {"type": "test.Lantern", "version": 3, "fields": {"color": "red"}}, _registry()
    )
    assert current.color == "red"
    with pytest.raises(ValueError):
        deserialize_component({"type": "test.Lantern", "version": 4, "fields": {}}, _registry())
    with pytest.raises(ValueError):
        deserialize_component({"type": "test.Lantern", "version": 0, "fields": {}}, _registry())


def test_upgrade_rewrites_an_old_project_at_the_current_version(tmp_path):
    path = tmp_path / "project.asteria.json"
    shutil.copy(OLD_PROJECT, path)
    old_version = json.loads(path.read_text())["version"]
    assert old_version < 10
    assert upgrade_project(path) == (old_version, 11)
    assert json.loads(path.read_text())["version"] == 11
    assert (
        json.loads((tmp_path / "project.asteria.json.bak").read_text())["version"] == old_version
    )
    assert load_project(path).name == load_project(OLD_PROJECT).name


def test_export_copies_every_resource_and_license_notice(tmp_path):
    report = export_game(REF / "project.asteria.json", tmp_path / "game")
    out = tmp_path / "game"
    assert report.missing == []
    manifest = json.loads((out / "playable_test_manifest.json").read_text())
    assert (out / manifest["field"]["background"]).is_file()
    assert (out / manifest["audio"]["battle_theme"]).is_file()
    assert (out / "playable_assets" / "CREDITS.md").is_file()  # credits / licence notices travel
    assert (out / "run_game.py").is_file()
    assert load_project(out / "project.asteria.json").to_data()["version"] == 11


def test_export_refuses_missing_resources_unless_allowed(tmp_path):
    source = tmp_path / "src"
    shutil.copytree(REF, source, ignore=shutil.ignore_patterns("saves", "__pycache__"))
    (source / "playable_assets" / "audio" / "hit.wav").unlink()
    with pytest.raises(FileNotFoundError):
        export_game(source / "project.asteria.json", tmp_path / "out")
    report = export_game(source / "project.asteria.json", tmp_path / "out2", allow_missing=True)
    assert report.missing == ["playable_assets/audio/hit.wav"]


def _run_isolated(tmp_path, *command, home=None):
    """Run outside the repo: ``python -I`` (no PYTHONPATH, no cwd on sys.path), reporting the
    engine it imported."""
    env = dict(
        os.environ,
        SDL_VIDEODRIVER="dummy",
        SDL_AUDIODRIVER="dummy",
        HOME=str(home or tmp_path / "home"),
    )
    probe = (
        "import runpy, sys\n"
        "target = sys.argv[1]; sys.argv = [target, '--frames', '5']\n"
        "try:\n    runpy.run_path(target, run_name='__main__')\n"
        "except SystemExit as exc:\n    assert not exc.code, exc.code\n"
        "import asteria; print('ENGINE', asteria.__file__)\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", probe, *command],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return Path(result.stdout.split("ENGINE ")[-1].strip())


def test_exported_game_launches_in_its_own_process_with_its_own_engine(tmp_path):
    pytest.importorskip("pygame")
    export_game(REF / "project.asteria.json", tmp_path / "game")
    assert (tmp_path / "game" / "engine" / "asteria" / "runtime" / "preview.py").is_file()
    assert not list((tmp_path / "game" / "engine").rglob("__pycache__"))
    engine = _run_isolated(tmp_path, str(tmp_path / "game" / "run_game.py"))
    assert engine.is_relative_to(tmp_path / "game" / "engine")  # not the repository's copy


def test_single_file_build_unpacks_once_and_keeps_saves_in_the_user_data_folder(tmp_path):
    pytest.importorskip("pygame")
    result = package_game(
        REF / "project.asteria.json", tmp_path / "dist", name="Ref Game", app=True
    )
    pyz = result["pyz"]
    assert pyz.name == "Ref_Game.pyz" and pyz.read_bytes().startswith(b"#!/usr/bin/env python3")
    engine = _run_isolated(tmp_path, str(pyz))
    cache = tmp_path / "home" / "Library" / "Caches" / "Asteria"
    if sys.platform != "darwin":
        cache = tmp_path / "home" / ".cache" / "Asteria"
    (build,) = cache.iterdir()
    assert engine.is_relative_to(build / "engine") and (build / ".complete").is_file()
    saves = build / "game" / "saves"
    assert (
        saves.is_symlink()
        and saves.resolve().name == "saves"
        and "Ref_Game" in str(saves.resolve())
    )
    stamp = (build / ".complete").stat().st_mtime_ns
    _run_isolated(tmp_path, str(pyz))  # the second start reuses the unpacked build
    assert (build / ".complete").stat().st_mtime_ns == stamp
    app = result["app"]
    import plistlib

    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    executable = app / "Contents" / "MacOS" / info["CFBundleExecutable"]
    assert info["CFBundlePackageType"] == "APPL" and os.access(executable, os.X_OK)
    assert (app / "Contents" / "Resources" / pyz.name).read_bytes() == pyz.read_bytes()


@pytest.mark.skipif(sys.platform == "win32", reason="the .app launcher is a POSIX shell script")
def test_macos_app_launcher_starts_the_game(tmp_path):
    pytest.importorskip("pygame")
    app = package_game(REF / "project.asteria.json", tmp_path / "dist", name="Ref Game", app=True)[
        "app"
    ]
    env = dict(
        os.environ,
        SDL_VIDEODRIVER="dummy",
        SDL_AUDIODRIVER="dummy",
        HOME=str(tmp_path / "home"),
        ASTERIA_PYTHON=sys.executable,
    )
    result = subprocess.run(
        [str(app / "Contents" / "MacOS" / "Ref_Game"), "--frames", "5"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]


def test_editor_export_game_saves_and_packages(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    source = tmp_path / "project"
    shutil.copytree(REF, source, ignore=shutil.ignore_patterns("saves", "__pycache__"))
    window = AsteriaEditorWindow(None)
    window.document.set_project(
        load_project(source / "project.asteria.json"), file_path=source / "project.asteria.json"
    )
    from asteria.editor.commands import SetAttributeCommand

    window.document.execute(
        SetAttributeCommand(
            window.document.project, "name", "Exported From Editor", window.document.project.name
        )
    )
    assert window.document.dirty
    assert window.export_action.text() == "Export Game…"
    result = window.export_game(tmp_path / "dist", pyz=True, app=False)
    assert result["pyz"].name == "Exported_From_Editor.pyz" and result["app"] is None
    assert (
        load_project(result["folder"] / "project.asteria.json").name == "Exported From Editor"
    )  # saved first
    window.close()
    app.processEvents()
