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
from asteria.project_tools import export_game, load_project, upgrade_project

REF = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"


@component_schema(
    type_name="test.Lantern", version=3, fields=(Field("brightness", float, 1.0), Field("color", str, "white"))
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
    lantern = deserialize_component({"type": "test.Lantern", "version": 1, "fields": {"lumens": 250}}, _registry())
    assert (lantern.brightness, lantern.color) == (2.5, "amber")
    current = deserialize_component({"type": "test.Lantern", "version": 3, "fields": {"color": "red"}}, _registry())
    assert current.color == "red"
    with pytest.raises(ValueError):
        deserialize_component({"type": "test.Lantern", "version": 4, "fields": {}}, _registry())
    with pytest.raises(ValueError):
        deserialize_component({"type": "test.Lantern", "version": 0, "fields": {}}, _registry())


def test_upgrade_rewrites_an_old_project_at_the_current_version(tmp_path):
    path = tmp_path / "project.asteria.json"
    shutil.copy(REF / "project.asteria.json", path)
    old_version = json.loads(path.read_text())["version"]
    assert old_version < 10
    assert upgrade_project(path) == (old_version, 10)
    assert json.loads(path.read_text())["version"] == 10
    assert json.loads((tmp_path / "project.asteria.json.bak").read_text())["version"] == old_version
    assert load_project(path).name == load_project(REF / "project.asteria.json").name


def test_export_copies_every_resource_and_license_notice(tmp_path):
    report = export_game(REF / "project.asteria.json", tmp_path / "game")
    out = tmp_path / "game"
    assert report.missing == []
    manifest = json.loads((out / "playable_test_manifest.json").read_text())
    assert (out / manifest["field"]["background"]).is_file()
    assert (out / manifest["audio"]["battle_theme"]).is_file()
    assert (out / "playable_assets" / "CREDITS.md").is_file()  # credits / licence notices travel
    assert (out / "run_game.py").is_file()
    assert load_project(out / "project.asteria.json").to_data()["version"] == 10


def test_export_refuses_missing_resources_unless_allowed(tmp_path):
    source = tmp_path / "src"
    shutil.copytree(REF, source, ignore=shutil.ignore_patterns("saves", "__pycache__"))
    (source / "playable_assets" / "audio" / "hit.wav").unlink()
    with pytest.raises(FileNotFoundError):
        export_game(source / "project.asteria.json", tmp_path / "out")
    report = export_game(source / "project.asteria.json", tmp_path / "out2", allow_missing=True)
    assert report.missing == ["playable_assets/audio/hit.wav"]


def test_exported_game_launches_in_its_own_process(tmp_path):
    pytest.importorskip("pygame")
    export_game(REF / "project.asteria.json", tmp_path / "game")
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    result = subprocess.run(
        [sys.executable, str(tmp_path / "game" / "run_game.py"), "--frames", "5"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
