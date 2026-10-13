"""Runtime profiler (ASTERIA_SPEC §34 "Profiling", CB13).

Measures what the running game can actually measure:

* timed sections per frame (``with profiler.section("update"):``) such as
  input, events, update, AI, collision, animation, VFX, render, present and
  asset loading;
* frame time and frame pacing (interval between frame starts, jitter, frames
  over budget);
* counters sampled per frame (entities, particles, assets loaded, ...);
* process memory (peak resident set size) and Python heap (tracemalloc).

A backend that cannot provide a metric declares it with :meth:`unsupported`;
reports list such metrics under ``"unsupported"`` instead of inventing a
number. Nothing here is estimated or synthesized.
"""

from __future__ import annotations

import json
import resource
import sys
import time
import tracemalloc
from contextlib import contextmanager
from pathlib import Path
from statistics import mean, pstdev

SPEC_METRICS = (
    "frame",
    "update",
    "render",
    "ai",
    "collision",
    "animation",
    "vfx",
    "asset_loading",
    "entity_count",
    "particles",
    "draw_calls",
    "memory",
    "asset_usage",
)


def _percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def _summary_ms(samples):
    if not samples:
        return None
    ms = [s * 1000.0 for s in samples]
    return {
        "count": len(ms),
        "mean_ms": round(mean(ms), 4),
        "p50_ms": round(_percentile(ms, 0.50), 4),
        "p95_ms": round(_percentile(ms, 0.95), 4),
        "p99_ms": round(_percentile(ms, 0.99), 4),
        "max_ms": round(max(ms), 4),
        "total_ms": round(sum(ms), 4),
    }


class RuntimeProfiler:
    """Per-frame section timings, pacing, counters and memory for a running game."""

    def __init__(self, *, target_fps=60.0, clock=time.perf_counter, track_python_heap=True):
        self.target_fps = float(target_fps)
        self.clock = clock
        self.sections: dict[str, list[float]] = {}
        self.counters: dict[str, list[float]] = {}
        self.frame_times: list[float] = []
        self.frame_intervals: list[float] = []
        self._unsupported: dict[str, str] = {}
        self._frame_start = None
        self._last_frame_start = None
        self._frame_sections: dict[str, float] = {}
        self.track_python_heap = bool(track_python_heap)
        self._started_tracemalloc = False
        if self.track_python_heap and not tracemalloc.is_tracing():
            tracemalloc.start()
            self._started_tracemalloc = True

    # -- recording ------------------------------------------------------------
    def unsupported(self, metric, reason):
        """Declare that the current backend cannot measure ``metric``."""
        self._unsupported[str(metric)] = str(reason)

    def begin_frame(self):
        now = self.clock()
        if self._last_frame_start is not None:
            self.frame_intervals.append(now - self._last_frame_start)
        self._last_frame_start = now
        self._frame_start = now
        self._frame_sections = {}

    def end_frame(self):
        if self._frame_start is None:
            return
        self.frame_times.append(self.clock() - self._frame_start)
        for name, elapsed in self._frame_sections.items():
            self.sections.setdefault(name, []).append(elapsed)
        self._frame_start = None

    @contextmanager
    def section(self, name):
        start = self.clock()
        try:
            yield
        finally:
            self.add_time(name, self.clock() - start)

    def add_time(self, name, seconds):
        """Accumulate ``seconds`` into section ``name`` for the current frame."""
        if self._frame_start is None:  # outside a frame (e.g. loading): record directly
            self.sections.setdefault(name, []).append(float(seconds))
        else:
            self._frame_sections[name] = self._frame_sections.get(name, 0.0) + float(seconds)

    def count(self, name, value):
        self.counters.setdefault(str(name), []).append(float(value))

    # -- reporting -------------------------------------------------------------
    def pacing(self):
        if not self.frame_intervals:
            return None
        budget = 1.0 / self.target_fps
        intervals_ms = [x * 1000.0 for x in self.frame_intervals]
        return {
            "target_fps": self.target_fps,
            "measured_fps": round(len(self.frame_intervals) / sum(self.frame_intervals), 3),
            "interval_mean_ms": round(mean(intervals_ms), 4),
            "interval_jitter_ms": round(pstdev(intervals_ms), 4),
            "interval_p99_ms": round(_percentile(intervals_ms, 0.99), 4),
            "frames_over_budget": sum(1 for x in self.frame_intervals if x > budget * 1.5),
        }

    def memory(self):
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # ru_maxrss is bytes on macOS and kilobytes on Linux.
        peak_rss = rss if sys.platform == "darwin" else rss * 1024
        result = {"peak_rss_bytes": int(peak_rss)}
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            result.update(python_heap_current_bytes=current, python_heap_peak_bytes=peak)
        return result

    def report(self):
        counters = {
            k: {"last": v[-1], "max": max(v), "mean": round(mean(v), 4)}
            for k, v in sorted(self.counters.items())
            if v
        }
        measured = set(self.sections) | set(counters) | {"frame", "memory"}
        missing = [m for m in SPEC_METRICS if m not in measured and m not in self._unsupported]
        return {
            "schema": "asteria.runtime_profile",
            "version": 1,
            "frames": len(self.frame_times),
            "frame": _summary_ms(self.frame_times),
            "pacing": self.pacing(),
            "sections": {k: _summary_ms(v) for k, v in sorted(self.sections.items())},
            "counters": counters,
            "memory": self.memory(),
            "unsupported": dict(sorted(self._unsupported.items())),
            "not_recorded": missing,
        }

    def write(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.report(), indent=2), encoding="utf-8")
        return path

    def close(self):
        if self._started_tracemalloc and tracemalloc.is_tracing():
            tracemalloc.stop()
            self._started_tracemalloc = False


class NullProfiler:
    """Drop-in profiler that records nothing (used when profiling is off)."""

    def begin_frame(self):
        pass

    def end_frame(self):
        pass

    @contextmanager
    def section(self, name):
        yield

    def add_time(self, name, seconds):
        pass

    def count(self, name, value):
        pass

    def unsupported(self, metric, reason):
        pass

    def close(self):
        pass
