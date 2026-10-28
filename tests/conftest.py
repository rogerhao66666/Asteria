"""Shared pytest configuration."""

import json
import shutil
from pathlib import Path

import pytest

from asteria.assets.local_reference import resolve_rpg_maker_mv_root

_REPO = Path(__file__).resolve().parents[1]
_MV_REFERENCE_AVAILABLE = resolve_rpg_maker_mv_root(_REPO) is not None


def pytest_configure(config):
    import real_window

    if real_window.enabled():
        real_window.install()
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

    shutil.copy(
        REFERENCE_PROJECT / "playable_test_manifest.json", tmp_path / "playable_test_manifest.json"
    )
    manifest = json.loads((tmp_path / "playable_test_manifest.json").read_text(encoding="utf-8"))
    for relative in set(_image_paths(manifest)):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (512, 512), (90, 120, 200, 255)).save(path)
    # Canonical battle presentation sheets (CC0) are real project assets; copy them as-is.
    shutil.copytree(
        REFERENCE_PROJECT / "playable_assets" / "battle", tmp_path / "playable_assets" / "battle"
    )
    shutil.copytree(  # the Lucifer icons and UI skin the reference project names
        REFERENCE_PROJECT / "playable_assets" / "lucifer",
        tmp_path / "playable_assets" / "lucifer",
    )
    for name in ("fx_heal.png",):
        shutil.copy(
            REFERENCE_PROJECT / "playable_assets" / name, tmp_path / "playable_assets" / name
        )
    return tmp_path


@pytest.fixture
def runtime(resource_root, monkeypatch, request):
    """A headless PlayableTestRuntime on the reference project (blocking legacy effects
    disabled)."""
    pytest.importorskip("pygame")
    import real_window

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    if real_window.enabled():  # real-window replay (D19): a real playable window, no dummy driver
        monkeypatch.delenv("SDL_VIDEODRIVER", raising=False)
        monkeypatch.delenv("SDL_AUDIODRIVER", raising=False)
    else:
        monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
        monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(
        REFERENCE_PROJECT / "project.asteria.json", EditorDocument().component_registry
    )
    value = PlayableTestRuntime(
        project, project.game_start.instantiate(project), resource_root, width=960, height=540
    )
    value.open()
    if real_window.enabled():
        real_window.set_stage(value)
    yield value
    if real_window.enabled() and real_window.STATE["stage"] is value:
        real_window.save_screenshot(request.node.name)
        real_window.STATE["stage"] = None
    value.close()


# --- real-window replay (tests/real_window.py) ----------------------------------------

_REPLAY_RESULTS = {}


@pytest.fixture(autouse=True)
def _real_window_test_name(request):
    import real_window

    if not real_window.enabled():
        yield
        return
    real_window.STATE["test"] = request.node.nodeid
    yield
    stage = real_window.STATE["stage"]
    if (
        stage is not None
    ):  # a window opened by test_session_events._session (the runtime fixture closes its own)
        real_window.save_screenshot(request.node.name)
        real_window.STATE["stage"] = None
        if real_window._alive(stage):
            stage.close()


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        _REPLAY_RESULTS[report.nodeid] = report.outcome


def pytest_sessionfinish(session, exitstatus):
    import real_window

    if real_window.enabled():
        real_window.write_report(_REPLAY_RESULTS)


@pytest.fixture(autouse=True)
def _close_windows_the_test_opened():
    """Close and delete the root windows a test opened and left behind.

    They stayed alive until the session ended, so every later ``app.setStyleSheet`` restyled
    thousands of stale widgets: the theme tests took 16 minutes in a full run and pushed CI
    past its 30-minute limit. Windows that existed before the test (a module or session
    fixture's) are kept."""
    import sys

    qt = sys.modules.get("PySide6.QtWidgets")
    app = qt.QApplication.instance() if qt is not None else None
    before = set(_application_owned_top_level_widgets(app)) if app is not None else set()
    yield
    import real_window

    qt = sys.modules.get("PySide6.QtWidgets")
    app = qt.QApplication.instance() if qt is not None else None
    if app is None or real_window.enabled():  # a replay keeps its windows for screenshots
        return
    from PySide6.QtCore import QCoreApplication, QEvent

    left = [w for w in _application_owned_top_level_widgets(app) if w not in before]
    for widget in left:
        # hide, not close: closing an editor with unsaved changes asks to save and would wait
        # forever for an answer
        widget.hide()
        widget.deleteLater()
    if left:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _application_owned_top_level_widgets(app):
    """Return root windows; topLevelWidgets also includes parent-owned popups."""
    return [widget for widget in app.topLevelWidgets() if widget.parentWidget() is None]


def pytest_unconfigure(config):
    """Tear Qt and SDL down in a fixed order before the interpreter exits.

    A process that loaded both PySide6 and pygame crashed at exit (``malloc_consolidate`` /
    segfault) when their atexit/destructor hooks ran in an arbitrary order after tests passed."""
    import gc
    import sys

    gc.collect()
    qt = sys.modules.get("PySide6.QtWidgets")
    if qt is not None:
        app = qt.QApplication.instance()
        if app is not None:
            app.closeAllWindows()
            for widget in _application_owned_top_level_widgets(app):
                widget.deleteLater()
            app.processEvents()
            app.quit()
            del app
    pygame = sys.modules.get("pygame")
    if pygame is not None:
        try:
            pygame.quit()
        except Exception:
            pass
    gc.collect()
