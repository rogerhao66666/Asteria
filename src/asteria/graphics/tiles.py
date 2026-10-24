from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from asteria.assets.types import AssetRef


@dataclass(frozen=True, slots=True)
class TileDef:
    frame_index: int
    collision: str = "none"
    terrain: str | None = None
    tags: tuple[str, ...] = ()
    animation: tuple[int, ...] = ()  # frame indices shown in turn (an animated tile)
    frame_ms: float = 0.0  # how long each animation frame shows

    def validate(self, frame_count):
        if self.frame_index < 0 or self.frame_index >= frame_count:
            raise ValueError("frame index")
        if any(f < 0 or f >= frame_count for f in self.animation):
            raise ValueError("animation frame index")
        if self.animation and self.frame_ms <= 0:
            raise ValueError("an animated tile needs frame_ms > 0")
        if self.collision not in {"none", "solid", "water", "one_way"}:
            raise ValueError("collision")


@dataclass(slots=True)
class Tileset:
    sprite_sheet: AssetRef
    tile_width: int
    tile_height: int
    tiles: dict[int, TileDef] = field(default_factory=dict)

    def validate(self, frame_count):
        if self.sprite_sheet.expected_kind not in (None, "sprite_sheet"):
            raise TypeError("sprite_sheet ref")
        if self.tile_width <= 0 or self.tile_height <= 0:
            raise ValueError("tile size")
        for i, t in self.tiles.items():
            if not isinstance(i, int) or i < 0:
                raise ValueError("tile id")
            t.validate(frame_count)
