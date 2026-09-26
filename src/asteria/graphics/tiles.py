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

    def validate(self, frame_count):
        if self.frame_index < 0 or self.frame_index >= frame_count:
            raise ValueError("frame index")
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
