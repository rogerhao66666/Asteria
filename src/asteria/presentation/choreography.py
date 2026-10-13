"""Generic multi-track choreography clock.
Names such as impact/cast are project data, never engine semantics.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TrackEvent:
    time_ms: float
    track: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def __post_init__(self):
        if self.time_ms < 0 or self.duration_ms < 0:
            raise ValueError("negative time")


@dataclass(frozen=True, slots=True)
class TimeSegment:
    start_ms: float
    end_ms: float
    scale: float

    def __post_init__(self):
        if self.start_ms < 0 or self.end_ms < self.start_ms or self.scale < 0:
            raise ValueError("invalid time segment")


@dataclass(frozen=True, slots=True)
class ChoreographyFrame:
    real_time_ms: float
    presentation_time_ms: float
    events: tuple[TrackEvent, ...]
    active: tuple[TrackEvent, ...]


class ChoreographyTimeline:
    def __init__(self, events=(), time_segments=()):
        self.events = tuple(sorted(events, key=lambda x: x.time_ms))
        self.segments = tuple(sorted(time_segments, key=lambda x: x.start_ms))
        self.real_time_ms = 0.0
        self.presentation_time_ms = 0.0
        self._emitted = set()
        self.cancelled = False

    def reset(self):
        self.real_time_ms = self.presentation_time_ms = 0.0
        self._emitted.clear()
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def _scale_at(self, t):
        scale = 1.0
        for s in self.segments:
            if s.start_ms <= t < s.end_ms:
                scale *= s.scale
        return scale

    def advance(self, dt_ms):
        if dt_ms < 0:
            raise ValueError("negative dt")
        if self.cancelled:
            return ChoreographyFrame(self.real_time_ms, self.presentation_time_ms, (), ())
        # Integrate piecewise so hit-stop/slow-motion boundaries are deterministic.
        remain = dt_ms
        while remain > 1e-9:
            candidates = [s.start_ms for s in self.segments if s.start_ms > self.real_time_ms] + [
                s.end_ms for s in self.segments if s.end_ms > self.real_time_ms
            ]
            step = min(remain, min(candidates) - self.real_time_ms if candidates else remain)
            self.presentation_time_ms += step * self._scale_at(self.real_time_ms + 1e-9)
            self.real_time_ms += step
            remain -= step
        due = []
        for i, e in enumerate(self.events):
            if i not in self._emitted and e.time_ms <= self.presentation_time_ms:
                due.append(e)
                self._emitted.add(i)
        active = tuple(
            e
            for e in self.events
            if e.duration_ms > 0
            and e.time_ms <= self.presentation_time_ms < e.time_ms + e.duration_ms
        )
        return ChoreographyFrame(self.real_time_ms, self.presentation_time_ms, tuple(due), active)


def event(time_ms, track, action, **payload):
    return TrackEvent(float(time_ms), track, action, payload)


def hold(real_start_ms, real_duration_ms):
    return TimeSegment(float(real_start_ms), float(real_start_ms + real_duration_ms), 0.0)


def time_scale(real_start_ms, real_duration_ms, scale):
    return TimeSegment(float(real_start_ms), float(real_start_ms + real_duration_ms), float(scale))
