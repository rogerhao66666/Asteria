"""D22 A11: the playable runtime's frame limiter keeps a steady schedule (no whole-millisecond
drift) and never reports more than 0.05 s per frame."""

import os
import sys
import time
from types import SimpleNamespace

import pytest


class _FakeClock:
    """``time.perf_counter`` and ``time.sleep`` on a clock the test drives: each sleep wakes
    ``late`` seconds after it was asked to, and each reading moves time on a little (so the
    limiter's short spin ends)."""

    def __init__(self, late=0.0):
        self.now, self.late = 100.0, late

    def perf_counter(self):
        self.now += 0.00005
        return self.now

    def sleep(self, seconds):
        self.now += seconds + self.late


def _ticks(monkeypatch, late=0.0):
    pytest.importorskip("pygame")
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    fake = _FakeClock(late)
    monkeypatch.setattr(time, "perf_counter", fake.perf_counter)
    monkeypatch.setattr(time, "sleep", fake.sleep)
    clock = SimpleNamespace()
    return fake, (lambda: PlayableTestRuntime.tick(clock, 60))


@pytest.mark.parametrize("late", [0.0, 0.001, 0.010])
def test_the_schedule_does_not_drift_when_sleeps_wake_late(monkeypatch, late):
    """Deadlines advance by exactly one period, so a sleep that wakes late (up to a frame)
    delays that frame only: 30 frames still take 30/60 s."""
    fake, tick = _ticks(monkeypatch, late)
    tick()
    start = fake.now
    dts = [tick() for _ in range(30)]
    assert 0.5 <= fake.now - start < 0.5 + late + 0.005
    assert all(0 < dt <= 0.05 for dt in dts)


def test_a_long_stall_restarts_the_schedule_instead_of_rushing(monkeypatch):
    fake, tick = _ticks(monkeypatch)
    tick()
    tick()
    fake.now += 0.2  # the game stood still for 0.2 s
    assert tick() == 0.05  # dt is capped
    start = fake.now
    tick()
    assert fake.now - start == pytest.approx(1 / 60, abs=0.002)  # one frame, not a burst


@pytest.mark.skipif(
    sys.platform == "darwin" and bool(os.environ.get("CI")),
    reason="a macOS CI runner wakes background sleeps tens of ms late (timer coalescing); "
    "the schedule itself is covered by the fake-clock tests above",
)
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
