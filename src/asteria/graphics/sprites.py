from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from asteria.assets.types import AssetRef


@dataclass(frozen=True, slots=True)
class SpriteFrame:
    x: int
    y: int
    width: int
    height: int
    pivot_x: float = 0.5
    pivot_y: float = 1.0

    def validate(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("positive frame size required")
        if self.x < 0 or self.y < 0:
            raise ValueError("non-negative coords required")
        if not (0 <= self.pivot_x <= 1 and 0 <= self.pivot_y <= 1):
            raise ValueError("pivot 0..1")


SCALING_PIXEL = "pixel"  # nearest neighbour: pixel art stays sharp (the default)
SCALING_SMOOTH = "smooth"  # bilinear: painted or rendered pictures keep their soft edges
SCALINGS = (SCALING_PIXEL, SCALING_SMOOTH)


@dataclass(slots=True)
class SpriteSheet:
    texture: AssetRef
    frames: list[SpriteFrame] = field(default_factory=list)
    # how the renderer resizes this sheet's frames (SCALINGS): a sheet's own choice, so pixel
    # art and smooth pictures can stand in the same scene
    scaling: str = SCALING_PIXEL

    def validate(self):
        if getattr(self.texture, "expected_kind", None) not in (None, "texture"):
            raise TypeError("texture ref required")
        if not self.frames:
            raise ValueError("frames required")
        if self.scaling not in SCALINGS:
            raise ValueError(f"scaling must be one of {SCALINGS}")
        for f in self.frames:
            f.validate()

    @property
    def smooth(self):
        return self.scaling == SCALING_SMOOTH


@dataclass(frozen=True, slots=True)
class SpriteKeyframe:
    frame_index: int
    duration: float
    # Names fired when playback enters this keyframe (footstep, hit, spawn_vfx, ...).
    events: tuple[str, ...] = ()

    def validate(self):
        if self.frame_index < 0 or self.duration <= 0:
            raise ValueError("invalid keyframe")


@dataclass(slots=True)
class SpriteClip:
    name: str
    keyframes: list[SpriteKeyframe]
    loop: bool = True

    def validate(self, sheet):
        if not self.name or not self.keyframes:
            raise ValueError("clip data required")
        for k in self.keyframes:
            k.validate()
            if k.frame_index >= len(sheet.frames):
                raise ValueError("missing frame")
