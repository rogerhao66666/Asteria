"""D22 A11: the playable runtime's frame limiter keeps a steady schedule (no whole-millisecond
drift) and never reports more than 0.05 s per frame."""

import time
from types import SimpleNamespace

import pytest


def test_tick_keeps_a_steady_sixty_frames_per_second():
    pytest.importorskip("pygame")
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    clock = SimpleNamespace()
    tick = PlayableTestRuntime.tick
    tick(clock, 60)
    start = time.perf_counter()
    dts = [tick(clock, 60) for _ in range(30)]
    elapsed = time.perf_counter() - start
    assert 0.48 < elapsed < 0.56  # 30 frames of 1/60 s
    assert all(0 < dt <= 0.05 for dt in dts)
    time.sleep(0.2)  # a long stall restarts the schedule instead of rushing to catch up
    assert tick(clock, 60) == 0.05
    start = time.perf_counter()
    tick(clock, 60)
    assert time.perf_counter() - start < 0.03
