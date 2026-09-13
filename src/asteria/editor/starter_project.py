"""Starter assets bundled with the editor, copied into every new project.

Like RPG Maker's default resources: a new project is immediately paintable
because it arrives with a tileset and a first map, rather than an empty canvas
that needs art imported before anything can be drawn. The files are copied into
the project folder (not referenced from the editor install) so a project stays
self-contained and portable.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from asteria.assets import AssetRef
from asteria.assets.types import AssetRecord
from asteria.core import Entity, Scene, Transform
from asteria.core.ids import new_id
from asteria.graphics.serialization import tilemap_to_data
from asteria.graphics.sprites import SpriteFrame, SpriteSheet
from asteria.graphics.tiles import TileDef, Tileset
from asteria.graphics.tilemap import TileChunk, TileLayer, TileMap
from asteria.project import Project
from asteria.runtime import TileMap2DComponent

STARTER_ATLAS = Path(__file__).resolve().parent / "starter_assets" / "environment_atlas.png"
ASSET_DIR = "tiles"
TILE = 16
ATLAS_COLUMNS = 8

# Atlas cells, left-to-right, top-to-bottom.
GRASS, PATH, WATER, STONE_FLOOR, STONE_WALL, WOOD_FLOOR, FLOWERS, SAND = range(8)
BUSH, ROOF, FENCE, DOOR, LAMP, CRATE, DEEP_WATER, VOID = range(8, 16)

TILE_INFO = {
    GRASS: ("none", "grass"),
    PATH: ("none", "path"),
    WATER: ("water", "water"),
    STONE_FLOOR: ("none", "stone"),
    STONE_WALL: ("solid", "stone"),
    WOOD_FLOOR: ("none", "wood"),
    FLOWERS: ("none", "grass"),
    SAND: ("none", "sand"),
    BUSH: ("solid", "grass"),
    ROOF: ("solid", "roof"),
    FENCE: ("solid", "wood"),
    DOOR: ("none", "wood"),
    LAMP: ("solid", None),
    CRATE: ("solid", "wood"),
    DEEP_WATER: ("water", "water"),
    VOID: ("solid", None),
}

NEW_MAP_WIDTH = 20
NEW_MAP_HEIGHT = 15


def _starter_frames():
    return [
        {"x": (i % ATLAS_COLUMNS) * TILE, "y": (i // ATLAS_COLUMNS) * TILE,
         "width": TILE, "height": TILE}
        for i in range(len(TILE_INFO))
    ]


def starter_tileset_preview():
    """The bundled tiles as an in-memory (tileset, sprite_sheet, atlas_path).

    Lets the palette show the editor's built-in tiles before any project is
    open. Nothing is written to disk; a project still gets its own copy when
    it is created.
    """
    sheet = SpriteSheet(
        AssetRef(new_id(), "texture"),
        [SpriteFrame(**frame) for frame in _starter_frames()],
    )
    tileset = Tileset(
        AssetRef(new_id(), "sprite_sheet"), TILE, TILE,
        {
            tile_id: TileDef(tile_id, collision, terrain)
            for tile_id, (collision, terrain) in TILE_INFO.items()
        },
    )
    return tileset, sheet, STARTER_ATLAS


def _write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def install_starter_tileset(project, project_dir, asset_dir=ASSET_DIR):
    """Copy the starter atlas into the project and register its tileset chain.

    Returns the tileset AssetRecord id, for maps to reference.
    """
    project_dir = Path(project_dir)
    target = project_dir / asset_dir
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(STARTER_ATLAS, target / "environment_atlas.png")

    texture = AssetRecord.create(kind="texture", source_path=f"{asset_dir}/environment_atlas.png")
    sheet = AssetRecord.create(kind="sprite_sheet", source_path=f"{asset_dir}/environment.sprite_sheet.json")
    tileset = AssetRecord.create(kind="tileset", source_path=f"{asset_dir}/environment.tileset.json")
    for record in (texture, sheet, tileset):
        project.assets.add(record)

    _write_json(target / "environment.sprite_sheet.json", {
        "texture_asset_id": texture.id,
        "frames": _starter_frames(),
    })
    _write_json(target / "environment.tileset.json", {
        "sprite_sheet_asset_id": sheet.id,
        "tile_width": TILE,
        "tile_height": TILE,
        "tiles": {
            str(tile_id): {
                "frame_index": tile_id,
                "collision": collision,
                "terrain": terrain,
                "tags": [],
            }
            for tile_id, (collision, terrain) in TILE_INFO.items()
        },
    })
    return tileset.id


def build_layer(name, order, width, height, tile_for, collision=False):
    chunk = TileChunk.empty(0, 0, width, height)
    for y in range(height):
        for x in range(width):
            chunk.set(x, y, tile_for(x, y))
    return TileLayer(name, order, collision_enabled=collision, chunks={(0, 0): chunk})


def add_tilemap(project, scene, project_dir, tileset_id, layers, file_name,
                *, entity_name="Map", origin=(0.0, 0.0), asset_dir=ASSET_DIR):
    """Write a tilemap sidecar, register it, and bind it to the scene."""
    project_dir = Path(project_dir)
    record = AssetRecord.create(kind="tilemap", source_path=f"{asset_dir}/{file_name}")
    project.assets.add(record)
    tilemap = TileMap(AssetRef(tileset_id, "tileset"), TILE, TILE, layers=list(layers))
    _write_json(project_dir / asset_dir / file_name, tilemap_to_data(tilemap))

    entity = Entity(entity_name)
    entity.add_component(Transform())
    binding = entity.add_component(TileMap2DComponent())
    binding.tilemap_asset_id = record.id
    binding.origin_x, binding.origin_y = origin
    scene.add_entity(entity)
    return entity


def create_new_project(name, project_dir):
    """Create a self-contained, immediately paintable project on disk.

    Returns the path of the written project file.
    """
    project_dir = Path(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    project = Project(str(name).strip() or "New Project")
    scene = project.add_scene(Scene("Map001"))
    tileset_id = install_starter_tileset(project, project_dir)
    add_tilemap(
        project, scene, project_dir, tileset_id,
        [
            build_layer("Ground", 0, NEW_MAP_WIDTH, NEW_MAP_HEIGHT, lambda x, y: GRASS),
            build_layer("Decor", 1, NEW_MAP_WIDTH, NEW_MAP_HEIGHT, lambda x, y: -1, collision=True),
        ],
        "map001.tilemap.json",
    )
    path = project_dir / "project.asteria.json"
    project.save_json(path)
    return path
