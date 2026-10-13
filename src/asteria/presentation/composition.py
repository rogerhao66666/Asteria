"""Generic high-fidelity layered composition + choreography primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .fidelity import HighFidelityClip


@dataclass(frozen=True, slots=True)
class LayerSample:
    asset_id: str
    z: int
    blend_mode: str
    opacity: float
    material: str | None
    frame_id: str | None = None


@dataclass(frozen=True, slots=True)
class SyncCue:
    time_ms: float
    channel: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CompositionFrame:
    time_ms: float
    frame_index: int
    layers: tuple[LayerSample, ...]
    cues: tuple[SyncCue, ...]


class ClipSampler:
    @staticmethod
    def frame_at(clip: HighFidelityClip, time_ms: float) -> tuple[int, float]:
        if time_ms < 0:
            raise ValueError("negative time")
        ds = [x.duration_ms for x in clip.timings]
        if len(ds) == 1:
            ds *= len(clip.frames)
        total = sum(ds)
        t = time_ms % total if clip.loop and total else min(time_ms, max(0, total - 1e-9))
        acc = 0.0
        for i, d in enumerate(ds):
            if t < acc + d:
                return i, t - acc
            acc += d
        return len(ds) - 1, ds[-1]

    @classmethod
    def sample(cls, clip, time_ms):
        i, _ = cls.frame_at(clip, time_ms)
        base = LayerSample(clip.frames[i], 0, "alpha", 1.0, None, clip.frames[i])
        extra = tuple(
            LayerSample(x.asset_id, x.z, x.blend_mode, x.opacity, x.material)
            for x in sorted(clip.layers, key=lambda q: q.z)
        )
        return i, (base,) + extra


class Choreography:
    def __init__(self, clip: HighFidelityClip, cues=()):
        self.clip = clip
        self.cues = tuple(sorted(cues, key=lambda x: x.time_ms))
        self.time_ms = 0.0
        self._emitted = set()

    def reset(self):
        self.time_ms = 0.0
        self._emitted.clear()

    def advance(self, dt_ms):
        if dt_ms < 0:
            raise ValueError("negative dt")
        old = self.time_ms
        self.time_ms += dt_ms
        idx, layers = ClipSampler.sample(self.clip, self.time_ms)
        due = []
        for n, c in enumerate(self.cues):
            if n not in self._emitted and old <= c.time_ms <= self.time_ms:
                due.append(c)
                self._emitted.add(n)
        return CompositionFrame(self.time_ms, idx, layers, tuple(due))


def presentation_cues(*items):
    """Convenience only: channels/actions remain project-defined strings."""
    return tuple(
        SyncCue(float(t), str(ch), str(act), dict(payload)) for t, ch, act, payload in items
    )
