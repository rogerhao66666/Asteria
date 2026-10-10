"""CB13: runtime profiler — measured sections, pacing, counters, memory, explicit Unsupported."""

import json

import pytest

from asteria.runtime.profiler import SPEC_METRICS, NullProfiler, RuntimeProfiler


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_sections_frames_pacing_and_unsupported_are_reported_from_measurements():
    clock = FakeClock()
    profiler = RuntimeProfiler(target_fps=40, clock=clock, track_python_heap=False)
    profiler.unsupported("draw_calls", "no counter")
    for frame in range(4):
        profiler.begin_frame()
        with profiler.section("update"):
            clock.now += 0.004
        with profiler.section("render"):
            clock.now += 0.006
        with profiler.section("update"):            # accumulates within one frame
            clock.now += 0.001
        profiler.count("entity_count", 10 + frame)
        profiler.end_frame()
        clock.now += 0.020 if frame != 2 else 0.040  # one long gap
    report = profiler.report()
    assert report["frames"] == 4
    assert report["sections"]["update"]["mean_ms"] == pytest.approx(5.0)
    assert report["sections"]["render"]["max_ms"] == pytest.approx(6.0)
    assert report["frame"]["mean_ms"] == pytest.approx(11.0)
    pacing = report["pacing"]
    assert pacing["interval_mean_ms"] == pytest.approx((31 + 31 + 51) / 3)
    assert pacing["frames_over_budget"] == 1                      # only 51 ms > 1.5 x 25 ms
    assert report["counters"]["entity_count"] == {"last": 13.0, "max": 13.0, "mean": 11.5}
    assert report["unsupported"] == {"draw_calls": "no counter"}
    # Metrics neither measured nor declared unsupported are listed, never invented.
    assert set(report["not_recorded"]) == set(SPEC_METRICS) - {"frame", "update", "render", "entity_count", "memory", "draw_calls"}
    assert report["memory"]["peak_rss_bytes"] > 0


def test_null_profiler_is_a_no_op():
    profiler = NullProfiler()
    profiler.begin_frame()
    with profiler.section("x"):
        pass
    profiler.count("y", 1)
    profiler.end_frame()


pygame = pytest.importorskip("pygame")


def test_playable_runtime_writes_a_profile_with_real_measurements(tmp_path, monkeypatch):
    from test_playable_battle_loop import _image_paths  # noqa: F401  (fixture helpers)
    import shutil

    from PIL import Image

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime
    from test_playable_battle_loop import ROOT

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    shutil.copy(ROOT / "playable_test_manifest.json", tmp_path / "playable_test_manifest.json")
    manifest = json.loads((tmp_path / "playable_test_manifest.json").read_text())
    for relative in set(_image_paths(manifest)):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (512, 512), (90, 120, 200, 255)).save(path)
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(project, project.game_start.instantiate(project), tmp_path)
    runtime._ui_mode = "field"
    out = tmp_path / "profile.json"
    assert runtime.run(target_fps=240, max_frames=30, profile_path=out) == 0
    report = json.loads(out.read_text())
    assert report["frames"] == 30
    for name in ("input", "events", "update", "render", "present", "asset_loading", "ai", "spawn"):
        assert report["sections"][name]["count"] >= 1, name
    assert report["counters"]["entity_count"]["last"] > 0
    assert report["pacing"]["measured_fps"] > 0
    assert "draw_calls" in report["unsupported"]
