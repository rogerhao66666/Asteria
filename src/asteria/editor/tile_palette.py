from __future__ import annotations
from dataclasses import dataclass
from asteria.graphics import EMPTY_TILE

@dataclass(frozen=True,slots=True)
class TilePaletteItem:
    tile_id:int
    frame_index:int
    collision:str
    terrain:str|None
    tags:tuple[str,...]

def build_tile_palette(tileset):
    return tuple(
        TilePaletteItem(tile_id,tile.frame_index,tile.collision,tile.terrain,tile.tags)
        for tile_id,tile in sorted(tileset.tiles.items())
    )

@dataclass(slots=True)
class TileToolState:
    mode:str="select"
    selected_tile_id:int|None=None
    active_layer:object|None=None

    def set_mode(self,mode):
        if mode not in {"select","paint","erase","fill","rectangle"}:
            raise ValueError("Unknown tile tool mode")
        self.mode=mode

    @property
    def effective_tile_id(self):
        if self.mode=="erase":
            return EMPTY_TILE
        if self.mode in {"paint","fill","rectangle"}:
            if self.selected_tile_id is None:
                raise ValueError("No tile selected")
            return self.selected_tile_id
        return None
