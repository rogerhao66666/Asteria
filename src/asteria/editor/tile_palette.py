from __future__ import annotations

from dataclasses import dataclass

from asteria.graphics import EMPTY_TILE


@dataclass(frozen=True, slots=True)
class TilePaletteItem:
    tile_id: int
    frame_index: int
    collision: str
    terrain: str | None
    tags: tuple[str, ...]


def build_tile_palette(tileset):
    return tuple(
        TilePaletteItem(tile_id, tile.frame_index, tile.collision, tile.terrain, tile.tags)
        for tile_id, tile in sorted(tileset.tiles.items())
    )


MODES = {"select", "paint", "erase", "fill", "rectangle", "terrain", "region", "doodad"}
STROKE_MODES = {"paint", "erase", "terrain", "region"}


def terrain_ids(tileset):
    """Terrain ids a tileset can autotile: those with at least one ``mask:<n>`` tile."""
    found = set()
    for definition in tileset.tiles.values():
        if definition.terrain and any(
            tag.startswith("mask:") and tag[5:].isdigit() for tag in definition.tags
        ):
            found.add(definition.terrain)
    return tuple(sorted(found))


@dataclass(slots=True)
class TileToolState:
    mode: str = "select"
    selected_tile_id: int | None = None
    active_layer: object | None = None
    tileset: object | None = None
    terrain_id: str | None = None
    terrain_mode: str = "edge4"
    region_id: int = 1
    region_layer_name: str = "regions"
    region_erase: bool = False
    doodad: object | None = None

    def set_mode(self, mode):
        if mode not in MODES:
            raise ValueError("Unknown tile tool mode")
        self.mode = mode

    def autotile(self):
        from asteria.graphics.autotile import build_autotile_set

        if self.tileset is None or not self.terrain_id:
            raise ValueError("No terrain selected")
        return build_autotile_set(self.tileset, self.terrain_id, self.terrain_mode)

    def build_command(self, tilemap, cells):
        """The undoable command painting ``cells`` with the current tool."""
        from .tile_edit import build_paint_command, build_region_command, build_terrain_command

        if self.mode == "terrain":
            return build_terrain_command(
                tilemap, self.active_layer, self.tileset, self.autotile(), cells
            )
        if self.mode == "region":
            return build_region_command(
                tilemap, self.region_layer_name, cells, self.region_id, erase=self.region_erase
            )
        return build_paint_command(tilemap, self.active_layer, cells, self.effective_tile_id)

    @property
    def effective_tile_id(self):
        if self.mode == "erase":
            return EMPTY_TILE
        if self.mode in {"paint", "fill", "rectangle"}:
            if self.selected_tile_id is None:
                raise ValueError("No tile selected")
            return self.selected_tile_id
        return None
