"""Draw composition for RPG Maker MV tiles without leaking MV IDs into core."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from asteria.assets.local_reference import RPGMakerMVProjectLayout
from asteria.assets.rpg_maker_mv_catalog import RPGMakerMVCatalog
from asteria.assets.rpg_maker_mv_map import RPGMakerMVMap
from asteria.runtime.draw import TextureDraw


@dataclass(frozen=True, slots=True)
class MVTileRegion:
    tile_id: int
    source: Path | None
    asset_id: str
    quarters: tuple[tuple[int, int, int, int], ...]


def _autotile_table(js_path: Path, name: str):
    source = js_path.read_text(encoding="utf-8-sig")
    match = re.search(rf"Tilemap\.{name}\s*=\s*(\[.*?\]);", source, re.DOTALL)
    if match is None:
        raise ValueError(f"missing MV autotile table: {name}")
    return tuple(tuple(tuple(pair) for pair in row) for row in json.loads(match.group(1)))


class MVTileResolver:
    def __init__(self, layout: RPGMakerMVProjectLayout, catalog: RPGMakerMVCatalog, *, tileset_id: int):
        self.layout = layout
        self.catalog = catalog
        self.tileset_id = int(tileset_id)
        records = json.loads((layout.data / "Tilesets.json").read_text(encoding="utf-8-sig"))
        if self.tileset_id <= 0 or self.tileset_id >= len(records) or not isinstance(records[self.tileset_id], dict):
            raise ValueError(f"unknown MV tileset: {self.tileset_id}")
        self.names = tuple(records[self.tileset_id].get("tilesetNames", ()))
        js = (layout.js or layout.root / "js") / "rpg_core.js"
        self.floor = _autotile_table(js, "FLOOR_AUTOTILE_TABLE")
        self.wall = _autotile_table(js, "WALL_AUTOTILE_TABLE")
        self.waterfall = _autotile_table(js, "WATERFALL_AUTOTILE_TABLE")

    def _source(self, set_number: int) -> tuple[Path | None, str]:
        name = self.names[set_number] if set_number < len(self.names) else ""
        if not name:
            return None, ""
        source = self.catalog.resolve_image("tilesets", name)
        if source is None:
            return None, ""
        asset = next((item for item in self.catalog.assets if item.source.uri == str(source)), None)
        return source, "" if asset is None else asset.asset_id

    def resolve(self, tile_id: int) -> MVTileRegion | None:
        tile_id = int(tile_id)
        if tile_id == 0:
            return None
        if 0 < tile_id < 1024:
            set_number = tile_id // 256 + 5
            local = tile_id % 256
            source, asset_id = self._source(set_number)
            return MVTileRegion(tile_id, source, asset_id, ((local % 16 * 48, local // 16 * 48, 48, 48),))
        if 1536 <= tile_id < 2048:
            local = tile_id - 1536
            source, asset_id = self._source(4)
            return MVTileRegion(tile_id, source, asset_id, ((local % 8 * 48, local // 8 * 48, 48, 48),))
        if not 2048 <= tile_id < 8192:
            return MVTileRegion(tile_id, None, "", ())

        kind = (tile_id - 2048) // 48
        shape = (tile_id - 2048) % 48
        tx, ty = kind % 8, kind // 8
        table = self.floor
        if tile_id < 2816:  # A1, animation frame zero
            set_number = 0
            if kind == 0:
                bx, by = 0, 0
            elif kind == 1:
                bx, by = 0, 3
            elif kind == 2:
                bx, by = 6, 0
            elif kind == 3:
                bx, by = 6, 3
            else:
                bx = (tx // 4) * 8
                by = ty * 6 + ((tx // 2) % 2) * 3
                if kind % 2:
                    bx += 6
                    table = self.waterfall
                    shape %= len(table)
        elif tile_id < 4352:  # A2
            set_number, bx, by = 1, tx * 2, (ty - 2) * 3
        elif tile_id < 5888:  # A3
            set_number, bx, by, table = 2, tx * 2, (ty - 6) * 2, self.wall
            shape %= len(table)
        else:  # A4
            set_number, bx = 3, tx * 2
            by = int((ty - 10) * 2.5 + (0.5 if ty % 2 else 0))
            if ty % 2:
                table = self.wall
                shape %= len(table)
        source, asset_id = self._source(set_number)
        quarters = tuple(((bx * 2 + qx) * 24, (by * 2 + qy) * 24, 24, 24) for qx, qy in table[shape])
        return MVTileRegion(tile_id, source, asset_id, quarters)


def compose_mv_map_draws(
    mv_map: RPGMakerMVMap,
    resolver: MVTileResolver,
    viewport: tuple[float, float, float, float],
) -> tuple[TextureDraw, ...]:
    vx, vy, vw, vh = viewport
    draws = []
    for layer_index, layer in enumerate(mv_map.layers):
        for index, tile_id in enumerate(layer):
            if tile_id == 0:
                continue
            column, row = index % mv_map.width, index // mv_map.width
            x, y = column * 48, row * 48
            if x + 48 <= vx or y + 48 <= vy or x >= vx + vw or y >= vy + vh:
                continue
            region = resolver.resolve(tile_id)
            if region is None or region.source is None:
                continue
            for quarter_index, source_rect in enumerate(region.quarters):
                full = len(region.quarters) == 1
                qx = 0 if full else quarter_index % 2 * 24
                qy = 0 if full else quarter_index // 2 * 24
                size = 48 if full else 24
                draws.append(
                    TextureDraw(
                        region.asset_id,
                        source_rect,
                        x + qx,
                        y + qy,
                        size,
                        size,
                        layer=layer_index,
                    )
                )
    return tuple(draws)
