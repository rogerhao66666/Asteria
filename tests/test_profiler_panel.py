"""EDT-19: Profiler panel in the editor, fed by the running game's RuntimeProfiler over the debug channel."""

import pytest

pygame = pytest.importorskip("pygame")

from asteria.runtime.debug_server import DebugClient  # noqa: E402


def _frames(runtime, count):
    for _ in range(count):
        runtime.profiler.begin_frame()
        runtime._frame([], 0.016)
        runtime._sample_counters()
        runtime.profiler.end_frame()


def test_profile_commands_start_report_and_reset(runtime):
    runtime._ui_mode = "field"
    server = runtime.enable_debugger(token="t")
    client = DebugClient(server.port, "t", pump=lambda: None)
    client.connect()
    try:
        server.poll()
        client.pump = server.poll
        assert client.request("profile_start") is True
        _frames(runtime, 30)
        report = client.request("profile")
        assert report["frames"] >= 29 and report["frame"]["mean_ms"] > 0
        assert "update" in report["sections"] and "entity_count" in report["counters"]
        assert set(report["unsupported"]) == {"draw_calls", "gpu_time"}
        client.request("profile_reset")
        assert client.request("profile")["frames"] == 0
    finally:
        client.close()


def test_profiler_dock_shows_the_live_profile(runtime):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.profiler_widget import ProfilerWidget

    QApplication.instance() or QApplication([])
    runtime._ui_mode = "field"
    server = runtime.enable_debugger(token="t")
    client = DebugClient(server.port, "t", pump=server.poll)
    widget = ProfilerWidget(lambda: client)
    assert widget.refresh() is not None  # starts the game's profiler on first request
    _frames(runtime, 30)
    report = widget.refresh()
    assert report["frames"] >= 29 and "fps" in widget.summary.text()
    names = [widget.sections.item(r, 0).text() for r in range(widget.sections.rowCount())]
    assert "update" in names and widget.counters.rowCount() >= 1
    assert widget.unsupported.count() == 2 and widget.unsupported.item(0).text().startswith("draw_calls")
    detached = ProfilerWidget(lambda: None)
    assert detached.refresh() is None and "not attached" in detached.summary.text()
    client.close()
