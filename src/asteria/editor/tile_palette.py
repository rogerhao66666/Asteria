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
    # stamp: rows of tile ids picked as a block in the palette (None: the one selected tile);
    # brush_size: the side of the square a single tile paints or erases (1 = one cell)
    stamp: tuple | None = None
    brush_size: int = 1

    def set_stamp(self, rows):
        """Pick a block of tiles (rows of tile ids) as the brush; one tile is a plain pick."""
        rows = tuple(tuple(int(t) for t in row) for row in rows or () if row)
        if not rows:
            self.stamp = None
            return
        self.selected_tile_id = rows[0][0]
        self.stamp = rows if (len(rows) > 1 or len(rows[0]) > 1) else None

    def assignments(self, cells, origin=None):
        """``{cell: tile_id}`` a Paint / Erase / Fill / Rectangle puts on ``cells``. A stamp
        repeats as a pattern anchored at ``origin`` (the first cell), so dragging lays it
        seamlessly; a single tile (or Erase) covers a ``brush_size`` square around each cell."""
        cells = [(int(x), int(y)) for x, y in cells]
        if not cells:
            return {}
        ox, oy = origin if origin is not None else cells[0]
        stamp = self.stamp if self.mode != "erase" else None
        out = {}
        if stamp:
            h, w = len(stamp), len(stamp[0])
            spread = self.mode in {"paint"}  # a brush stroke lays the whole block at each cell
            for x, y in cells:
                for dy in range(h if spread else 1):
                    for dx in range(w if spread else 1):
                        cx, cy = x + dx, y + dy
                        out[(cx, cy)] = stamp[(cy - oy) % h][(cx - ox) % w]
            return out
        tile = self.effective_tile_id
        size = max(1, int(self.brush_size)) if self.mode in {"paint", "erase"} else 1
        lo = -((size - 1) // 2)
        for x, y in cells:
            for dy in range(lo, lo + size):
                for dx in range(lo, lo + size):
                    out[(x + dx, y + dy)] = tile
        return out

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
        from .tile_edit import build_assign_command

        if self.mode in {"paint", "erase", "fill", "rectangle"}:
            return build_assign_command(tilemap, self.active_layer, self.assignments(cells))
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
