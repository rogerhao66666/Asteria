"""Shared pytest configuration."""

import json
import shutil
from pathlib import Path

import pytest

from asteria.assets.local_reference import resolve_rpg_maker_mv_root

_REPO = Path(__file__).resolve().parents[1]
_MV_REFERENCE_AVAILABLE = resolve_rpg_maker_mv_root(_REPO) is not None


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "mv_reference: needs the git-ignored local RPG Maker MV reference "
        "(local_reference/rpg_maker_mv); skipped when it is absent",
    )


def pytest_collection_modifyitems(config, items):
    if _MV_REFERENCE_AVAILABLE:
        return
    skip = pytest.mark.skip(reason="local RPG Maker MV reference unavailable")
    for item in items:
        if item.get_closest_marker("mv_reference") is not None:
            item.add_marker(skip)


# --- shared playable-runtime fixtures ------------------------------------------------

REFERENCE_PROJECT = _REPO / "reference_projects" / "complex_reference_rpg"


def _image_paths(value):
    if isinstance(value, str) and value.endswith(".png"):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _image_paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from _image_paths(item)


@pytest.fixture
def resource_root(tmp_path):
    """Reference manifest plus flat-colour placeholder images; battle sheets are copied as-is."""
    from PIL import Image

    shutil.copy(REFERENCE_PROJECT / "playable_test_manifest.json", tmp_path / "playable_test_manifest.json")
    manifest = json.loads((tmp_path / "playable_test_manifest.json").read_text(encoding="utf-8"))
    for relative in set(_image_paths(manifest)):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (512, 512), (90, 120, 200, 255)).save(path)
    # Canonical battle presentation sheets (CC0) are real project assets; copy them as-is.
    shutil.copytree(REFERENCE_PROJECT / "playable_assets" / "battle", tmp_path / "playable_assets" / "battle")
    shutil.copy(REFERENCE_PROJECT / "playable_assets" / "fx_heal.png", tmp_path / "playable_assets" / "fx_heal.png")
    return tmp_path


@pytest.fixture
def runtime(resource_root, monkeypatch):
    """A headless PlayableTestRuntime on the reference project (blocking legacy effects disabled)."""
    pytest.importorskip("pygame")
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(REFERENCE_PROJECT / "project.asteria.json", EditorDocument().component_registry)
    value = PlayableTestRuntime(project, project.game_start.instantiate(project), resource_root, width=960, height=540)
    value.open()
    monkeypatch.setattr(value, "_play_fx", lambda *args, **kwargs: None)
    yield value
    value.close()
