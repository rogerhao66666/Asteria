"""High-fidelity asset/presentation contract.
Defaults are presets, never hard engine limits.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class FrameTiming:
    duration_ms: float

    def __post_init__(self):
        if self.duration_ms <= 0:
            raise ValueError("duration must be positive")


@dataclass(frozen=True, slots=True)
class VisualLayer:
    asset_id: str
    z: int = 0
    blend_mode: str = "alpha"
    opacity: float = 1.0
    material: str | None = None

    def __post_init__(self):
        if not 0 <= self.opacity <= 1:
            raise ValueError("opacity")


@dataclass(frozen=True, slots=True)
class HighFidelityClip:
    id: str
    frame_size: tuple[int, int]
    frames: tuple[str, ...]
    timings: tuple[FrameTiming, ...]
    pivot: tuple[float, float] = (0.0, 0.0)
    layers: tuple[VisualLayer, ...] = ()
    loop: bool = False

    def __post_init__(self):
        if min(self.frame_size) <= 0 or not self.frames:
            raise ValueError("invalid clip")
        if len(self.timings) not in (1, len(self.frames)):
            raise ValueError("timing count")

    def duration_ms(self):
        return (
            sum(x.duration_ms for x in self.timings)
            if len(self.timings) > 1
            else self.timings[0].duration_ms * len(self.frames)
        )


@dataclass(frozen=True, slots=True)
class FidelityCapability:
    arbitrary_resolution: bool = True
    arbitrary_frame_count: bool = True
    per_frame_timing: bool = True
    alpha: bool = True
    layered_composition: bool = True
    blend_modes: bool = True
    materials: bool = True
    vfx: bool = True
    camera: bool = True
    audio_sync: bool = True
    frame_events: bool = True


CAPABILITIES = FidelityCapability()


def fidelity_warnings(clip: HighFidelityClip):
    w = []
    if clip.frame_size[0] > 4096 or clip.frame_size[1] > 4096:
        w.append("very_large_frame: profile runtime memory/GPU upload cost")
    if len(clip.frames) > 1000:
        w.append("very_large_clip: consider streaming/atlas strategy")
    return tuple(w)
