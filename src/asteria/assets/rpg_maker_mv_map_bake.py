"""Bake RPG Maker MV maps into canonical Asteria tile assets (W-18).

MV tile knowledge ends in this module. Each imported map becomes ordinary
project assets that the runtime already understands:

* ``texture``      — a PNG atlas of every tile the map uses (autotiles composed
  from their 24 px quarters, A1 water at its first animation frame)
* ``sprite_sheet`` — one 48 x 48 frame per atlas cell
* ``tileset``      — one tile per atlas cell; MV "star" tiles are tagged ``above``
* ``tilemap``      — MV layers 0–3 as tile layers (star tiles on separate layers
  drawn above characters) plus a hidden ``Walkability`` collision layer baked
  from the MV passage flags

Characters (the party leader, events with a character image) become a 3 x 4
walking ``sprite_sheet`` and an ``animation`` clip set. Nothing written here
needs MV code at runtime, and no MV file is read after the import.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid5

from PIL import Image

from asteria.graphics import EMPTY_TILE, TileChunk, TileLayer, TileMap
from asteria.graphics.serialization import tilemap_to_data

from .rpg_maker_mv import RPGMakerMVImporter
from .rpg_maker_mv_map_render import MVTileResolver, cached_json
from .types import AssetRecord, AssetRef

TILE = 48
STAR = 0x10
BLOCKED = 0x0F
ATLAS_COLUMNS = 16
CHUNK = 32
WALK_DIRECTIONS = ("down", "left", "right", "up")
_NAMESPACE = UUID("3b8a3f8e-61a5-4c2c-9f0b-6c1f7a4d2e10")


def stable_id(*parts) -> str:
    return str(uuid5(_NAMESPACE, ":".join(str(p) for p in parts)))


@dataclass
class BakedMap:
    tilemap_id: str
    width: int
    height: int
    records: list = field(default_factory=list)
    unsupported_tiles: tuple[int, ...] = ()
    blocked_cells: int = 0


@dataclass
class BakedCharacter:
    sprite_sheet_id: str
    animation_id: str
    records: list = field(default_factory=list)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _record(asset_id, kind, source_path, name, provenance) -> AssetRecord:
    return AssetRecord(asset_id, kind, source_path, name, "rpg_maker_mv", 1, {}, dict(provenance))


def _sheet_data(texture_id, frames):
    return {
        "texture_asset_id": texture_id,
        "frames": [
            {"x": x, "y": y, "width": w, "height": h, "pivot_x": px, "pivot_y": py}
            for x, y, w, h, px, py in frames
        ],
    }


def _tileset_flags(layout, tileset_id):
    records = cached_json(layout.data / "Tilesets.json")  # parsed once per import
    return tuple(records[tileset_id].get("flags") or ())


def passable(flags, tiles_top_to_bottom) -> bool:
    """RPG Maker MV cell passage (Game_Map.checkPassage with all four directions)."""
    for tile_id in tiles_top_to_bottom:
        flag = flags[tile_id] if 0 <= tile_id < len(flags) else 0
        if flag & STAR:
            continue
        if flag & BLOCKED == 0:
            return True
        if flag & BLOCKED == BLOCKED:
            return False
        return True  # partially passable (directional): the cell stays walkable
    return False


def _layer(name, order, cells, width, height, *, visible=True, collision=False):
    layer = TileLayer(name, order, visible, 1.0, collision)
    for index, tile_id in enumerate(cells):
        if tile_id == EMPTY_TILE:
            continue
        x, y = index % width, index // width
        key = (x // CHUNK, y // CHUNK)
        chunk = layer.chunks.get(key)
        if chunk is None:
            chunk = layer.chunks[key] = TileChunk.empty(key[0], key[1], CHUNK, CHUNK)
        chunk.set(x % CHUNK, y % CHUNK, tile_id)
    return layer


def bake_map(layout, catalog, mv_map, out_root) -> BakedMap:
    """Write the map's atlas, sprite sheet, tileset and tilemap under ``out_root``; return their
    records."""
    out_root = Path(out_root)
    folder = f"imported/mv/map_{mv_map.map_id:03d}"
    resolver = MVTileResolver(layout, catalog, tileset_id=mv_map.tileset_id)
    flags = _tileset_flags(layout, mv_map.tileset_id)
    sources: dict[Path, Image.Image] = {}
    local: dict[int, int] = {}
    images: list[Image.Image] = []
    unsupported: set[int] = set()
    # tile id -> the catalog issues composing it reported, for a tile that cannot be composed:
    # each later use reports them again instead of composing it again
    failed: dict[int, tuple] = {}

    def compose(tile_id):
        region = resolver.resolve(tile_id)
        if region is None or region.source is None or not region.quarters:
            return None
        if region.source not in sources:
            with Image.open(region.source) as source:
                sources[region.source] = source.convert("RGBA")
        sheet = sources[region.source]
        tile = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
        whole = len(region.quarters) == 1
        for index, (x, y, w, h) in enumerate(region.quarters):
            piece = sheet.crop((x, y, x + w, y + h))
            tile.paste(piece, (0, 0) if whole else (index % 2 * 24, index // 2 * 24))
        return tile

    width, height = mv_map.width, mv_map.height
    layers = []
    for z in range(4):
        below = [EMPTY_TILE] * (width * height)
        above = [EMPTY_TILE] * (width * height)
        for index, tile_id in enumerate(mv_map.layers[z]):
            if tile_id == 0:
                continue
            if tile_id not in local:
                if tile_id in failed:
                    catalog.issues.extend(failed[tile_id])
                    continue
                before = len(catalog.issues)
                image = compose(tile_id)
                if image is None:
                    failed[tile_id] = tuple(catalog.issues[before:])
                    unsupported.add(tile_id)
                    continue
                local[tile_id] = len(images)
                images.append(image)
            flag = flags[tile_id] if tile_id < len(flags) else 0
            (above if flag & STAR else below)[index] = local[tile_id]
        if any(t != EMPTY_TILE for t in below):
            layers.append(_layer(f"Layer {z + 1}", z, below, width, height))
        if any(t != EMPTY_TILE for t in above):
            layers.append(
                _layer(f"Layer {z + 1} (above characters)", 200 + z, above, width, height)
            )

    blocked_tile = len(images)
    walk = [EMPTY_TILE] * (width * height)
    for index in range(width * height):
        stack = [mv_map.layers[z][index] for z in (3, 2, 1, 0)]
        if not passable(flags, stack):
            walk[index] = blocked_tile
    layers.append(_layer("Walkability", 500, walk, width, height, visible=False, collision=True))

    rows = max(1, -(-max(1, len(images)) // ATLAS_COLUMNS))
    atlas = Image.new("RGBA", (ATLAS_COLUMNS * TILE, rows * TILE), (0, 0, 0, 0))
    frames = []
    for index, image in enumerate(images or [Image.new("RGBA", (TILE, TILE))]):
        x, y = index % ATLAS_COLUMNS * TILE, index // ATLAS_COLUMNS * TILE
        atlas.paste(image, (x, y))
        frames.append((x, y, TILE, TILE, 0.0, 0.0))
    (out_root / folder).mkdir(parents=True, exist_ok=True)
    atlas.save(out_root / folder / "tiles.png")

    ids = {
        kind: stable_id("mv-map", mv_map.map_id, kind)
        for kind in ("texture", "sheet", "tileset", "tilemap")
    }
    tiles = {
        str(i): {"frame_index": i, "collision": "none", "terrain": None, "tags": []}
        for i in range(len(images))
    }
    for tile_id, index in local.items():
        flag = flags[tile_id] if tile_id < len(flags) else 0
        tiles[str(index)]["tags"] = ["above"] if flag & STAR else []
    tiles[str(blocked_tile)] = {
        "frame_index": 0,
        "collision": "solid",
        "terrain": None,
        "tags": ["walkability"],
    }
    _write_json(out_root / folder / "tiles_sheet.json", _sheet_data(ids["texture"], frames))
    _write_json(
        out_root / folder / "tileset.json",
        {
            "sprite_sheet_asset_id": ids["sheet"],
            "tile_width": TILE,
            "tile_height": TILE,
            "tiles": tiles,
        },
    )
    tilemap = TileMap(AssetRef(ids["tileset"], "tileset"), TILE, TILE, CHUNK, CHUNK, layers)
    tilemap.validate()
    _write_json(out_root / folder / "tilemap.json", tilemap_to_data(tilemap))
    provenance = {
        "source": "rpg_maker_mv",
        "map_id": mv_map.map_id,
        "tileset_id": mv_map.tileset_id,
    }
    name = mv_map.display_name or mv_map.name
    records = [
        _record(ids["texture"], "texture", f"{folder}/tiles.png", f"{name} Tiles", provenance),
        _record(
            ids["sheet"],
            "sprite_sheet",
            f"{folder}/tiles_sheet.json",
            f"{name} Tile Sheet",
            provenance,
        ),
        _record(
            ids["tileset"], "tileset", f"{folder}/tileset.json", f"{name} Tileset", provenance
        ),
        _record(
            ids["tilemap"], "tilemap", f"{folder}/tilemap.json", f"{name} TileMap", provenance
        ),
    ]
    return BakedMap(
        ids["tilemap"],
        width,
        height,
        records,
        tuple(sorted(unsupported)),
        sum(1 for t in walk if t != EMPTY_TILE),
    )


def bake_character(catalog, character_name, character_index, out_root) -> BakedCharacter | None:
    """A 3 x 4 MV walking character as a canonical sprite sheet + idle/walk clip set (None when not
    found)."""
    source = catalog.resolve_image("characters", character_name)
    if source is None:
        return None
    imported = RPGMakerMVImporter().inspect(source)
    if not imported.character_count or character_index >= imported.character_count:
        return None
    fw, fh = imported.frame_size
    folder = f"imported/mv/characters/{Path(character_name).name}_{character_index}"
    sheet = Image.new("RGBA", (fw * 3, fh * 4), (0, 0, 0, 0))
    with Image.open(source) as image:
        image = image.convert("RGBA")
        for row, direction in enumerate(WALK_DIRECTIONS):
            boxes = RPGMakerMVImporter.walk_clip_boxes(
                imported, character_index=character_index, direction=direction
            )
            for column, box in enumerate(boxes):
                sheet.paste(image.crop(box), (column * fw, row * fh))
    out = Path(out_root) / folder
    out.mkdir(parents=True, exist_ok=True)
    sheet.save(out / "walk.png")
    key = f"{character_name}:{character_index}"
    texture_id = stable_id("mv-character", key, "texture")
    sheet_id = stable_id("mv-character", key, "sheet")
    animation_id = stable_id("mv-character", key, "animation")
    frames = [(c * fw, r * fh, fw, fh, 0.5, 1.0) for r in range(4) for c in range(3)]
    _write_json(out / "walk_sheet.json", _sheet_data(texture_id, frames))
    clips = {}
    for row, direction in enumerate(WALK_DIRECTIONS):
        base = row * 3
        clips[f"idle_{direction}"] = {
            "keyframes": [{"frame_index": base + 1, "duration": 0.4}],
            "loop": True,
        }
        clips[f"walk_{direction}"] = {
            "keyframes": [{"frame_index": base + i, "duration": 0.15} for i in (0, 1, 2, 1)],
            "loop": True,
        }
    _write_json(out / "walk_animation.json", {"clips": clips})
    provenance = {
        "source": "rpg_maker_mv",
        "character": character_name,
        "character_index": character_index,
    }
    label = f"{Path(character_name).name} {character_index}"
    records = [
        _record(texture_id, "texture", f"{folder}/walk.png", f"{label} Walk", provenance),
        _record(
            sheet_id,
            "sprite_sheet",
            f"{folder}/walk_sheet.json",
            f"{label} Walk Sheet",
            provenance,
        ),
        _record(
            animation_id,
            "animation",
            f"{folder}/walk_animation.json",
            f"{label} Walk Animation",
            provenance,
        ),
    ]
    return BakedCharacter(sheet_id, animation_id, records)
