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

_STARTER_ASSETS = Path(__file__).resolve().parent / "starter_assets"
STARTER_ATLAS = _STARTER_ASSETS / "environment_atlas.png"
CHARACTER_ATLAS = _STARTER_ASSETS / "characters_atlas.png"
ASSET_DIR = "tiles"
CHARACTER_ASSET_DIR = "characters"
TILE = 48
CHARACTER_WIDTH = 48
CHARACTER_HEIGHT = 64
CHARACTER_FRAMES = 2
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


# Marks the records this module registers, so an unsaved project's bundled
# art can be located (before it has a folder) and written out (once it gets
# one) without guessing which of a project's assets came from the starter
# pack — see starter_asset_path() and materialize_starter_assets().
STARTER_METADATA_KEY = "asteria.starter_asset"


def _sprite_sheet_data(texture_id):
    return {"texture_asset_id": texture_id, "frames": _starter_frames()}


def _character_frames():
    return [
        {
            "x": index * CHARACTER_WIDTH, "y": 0,
            "width": CHARACTER_WIDTH, "height": CHARACTER_HEIGHT,
        }
        for index in range(CHARACTER_FRAMES)
    ]


def _character_sheet_data(texture_id):
    return {"texture_asset_id": texture_id, "frames": _character_frames()}


def _tileset_data(sheet_id):
    return {
        "sprite_sheet_asset_id": sheet_id,
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
    }


def _register_starter_records(project, asset_dir):
    texture = AssetRecord.create(
        kind="texture", source_path=f"{asset_dir}/environment_atlas.png",
        metadata={STARTER_METADATA_KEY: "texture"},
    )
    sheet = AssetRecord.create(
        kind="sprite_sheet", source_path=f"{asset_dir}/environment.sprite_sheet.json",
        metadata={STARTER_METADATA_KEY: "sprite_sheet"},
    )
    tileset = AssetRecord.create(
        kind="tileset", source_path=f"{asset_dir}/environment.tileset.json",
        metadata={STARTER_METADATA_KEY: "tileset"},
    )
    for record in (texture, sheet, tileset):
        project.assets.add(record)
    return texture, sheet, tileset


def _register_character_records(project, asset_dir=CHARACTER_ASSET_DIR):
    texture = AssetRecord.create(
        kind="texture", source_path=f"{asset_dir}/characters_atlas.png",
        metadata={STARTER_METADATA_KEY: "character_texture"},
    )
    sheet = AssetRecord.create(
        kind="sprite_sheet", source_path=f"{asset_dir}/characters.sprite_sheet.json",
        metadata={STARTER_METADATA_KEY: "character_sprite_sheet"},
    )
    for record in (texture, sheet):
        project.assets.add(record)
    return texture, sheet


_BUNDLED_TEXTURES = {
    "texture": STARTER_ATLAS,
    "character_texture": CHARACTER_ATLAS,
}


def starter_asset_path(record):
    """On-disk source for a starter record whose project has no folder yet."""
    metadata = record.metadata or {}
    return _BUNDLED_TEXTURES.get(metadata.get(STARTER_METADATA_KEY))


def install_starter_tileset(project, project_dir, asset_dir=ASSET_DIR):
    """Copy the starter atlas into the project and register its tileset chain.

    Returns the tileset AssetRecord id, for maps to reference.
    """
    project_dir = Path(project_dir)
    target = project_dir / asset_dir
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(STARTER_ATLAS, target / "environment_atlas.png")

    texture, sheet, tileset = _register_starter_records(project, asset_dir)
    _write_json(target / "environment.sprite_sheet.json", _sprite_sheet_data(texture.id))
    _write_json(target / "environment.tileset.json", _tileset_data(sheet.id))
    return tileset.id


def materialize_starter_assets(project, project_dir):
    """Write any bundled starter asset that has no file yet under project_dir.

    An untitled project carries its tileset only in memory; the first save
    is what gives it a folder to live in. Existing files are never touched,
    so this is a no-op for a project that was created on disk.
    """
    project_dir = Path(project_dir)
    by_role = {}
    for record in project.assets.records():
        role = (record.metadata or {}).get(STARTER_METADATA_KEY)
        if role is not None:
            by_role[role] = record
    if not by_role:
        return ()

    payloads = {}
    if "sprite_sheet" in by_role and "texture" in by_role:
        payloads["sprite_sheet"] = _sprite_sheet_data(by_role["texture"].id)
    if "tileset" in by_role and "sprite_sheet" in by_role:
        payloads["tileset"] = _tileset_data(by_role["sprite_sheet"].id)
    if "character_sprite_sheet" in by_role and "character_texture" in by_role:
        payloads["character_sprite_sheet"] = _character_sheet_data(
            by_role["character_texture"].id
        )

    written = []
    for role, record in by_role.items():
        destination = project_dir / record.source_path
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if role in _BUNDLED_TEXTURES:
            shutil.copyfile(_BUNDLED_TEXTURES[role], destination)
        elif role in payloads:
            _write_json(destination, payloads[role])
        else:
            continue
        written.append(destination)
    return tuple(written)


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


def _starter_map_layers():
    return [
        build_layer("Ground", 0, NEW_MAP_WIDTH, NEW_MAP_HEIGHT, lambda x, y: GRASS),
        build_layer(
            "Decor", 1, NEW_MAP_WIDTH, NEW_MAP_HEIGHT, lambda x, y: -1, collision=True
        ),
    ]


DEMO_ACTOR_ID = "hero"
DEMO_ACTOR_NAME = "Hero"


def add_demo_character(project, scene, character_sheet_id, map_origin=(0.0, 0.0)):
    """Stand one character in the middle of the starter map.

    A brand-new project that shows only bare ground gives no hint that
    characters exist at all, let alone that they are entities rather than
    tiles — so the starter map ships with one, linked to a real Actor.
    """
    from asteria.rpg import ActorDefinition
    from asteria.runtime import ActorLinkComponent, SpriteRenderer2D

    if DEMO_ACTOR_ID not in project.rpg_database.actors:
        project.rpg_database.add_actor(
            ActorDefinition(DEMO_ACTOR_ID, DEMO_ACTOR_NAME)
        )
    entity = Entity(DEMO_ACTOR_NAME)
    transform = entity.add_component(Transform())
    # Centre column, bottom edge of the centre row: sprite frames pivot at
    # bottom-centre, so this reads as standing on that tile.
    transform.x = map_origin[0] + (NEW_MAP_WIDTH // 2 + 0.5) * TILE
    transform.y = map_origin[1] + (NEW_MAP_HEIGHT // 2 + 1) * TILE
    link = entity.add_component(ActorLinkComponent())
    link.actor_id = DEMO_ACTOR_ID
    sprite = entity.add_component(SpriteRenderer2D())
    sprite.sprite_sheet_asset_id = character_sheet_id
    sprite.frame_index = 0
    sprite.layer = 10
    scene.add_entity(entity)
    return entity


def build_untitled_project(name="Untitled"):
    """An immediately paintable project that has never touched the disk.

    The editor opens on one of these instead of an empty "No Project" shell,
    so a map can be drawn before anyone decides where — or whether — to save
    it. The tileset/tilemap resources live only in memory until the first
    save; seed_unsaved_views() resolves them and materialize_starter_assets()
    writes the sidecar files once the project has a folder.
    """
    project = Project(str(name).strip() or "Untitled")
    scene = project.add_scene(Scene("Map001"))
    _register_starter_records(project, ASSET_DIR)
    _, character_sheet = _register_character_records(project)
    tilemap_record = AssetRecord.create(
        kind="tilemap", source_path=f"{ASSET_DIR}/map001.tilemap.json",
    )
    project.assets.add(tilemap_record)

    entity = Entity("Map")
    entity.add_component(Transform())
    binding = entity.add_component(TileMap2DComponent())
    binding.tilemap_asset_id = tilemap_record.id
    scene.add_entity(entity)
    add_demo_character(project, scene, character_sheet.id)
    return project


def seed_unsaved_views(document):
    """Resolve an unsaved project's bundled resources without touching disk."""
    project = document.project
    if project is None:
        return document.asset_views
    roles = {
        (record.metadata or {}).get(STARTER_METADATA_KEY): record
        for record in project.assets.records()
    }
    sheet_record = roles.get("sprite_sheet")
    tileset_record = roles.get("tileset")
    texture_record = roles.get("texture")
    if sheet_record is None or tileset_record is None or texture_record is None:
        return document.asset_views
    document.asset_views.set_sprite_sheet(
        sheet_record.id,
        SpriteSheet(
            AssetRef(texture_record.id, "texture"),
            [SpriteFrame(**frame) for frame in _starter_frames()],
        ),
    )
    document.asset_views.set_tileset(
        tileset_record.id,
        Tileset(
            AssetRef(sheet_record.id, "sprite_sheet"), TILE, TILE,
            {
                tile_id: TileDef(tile_id, collision, terrain)
                for tile_id, (collision, terrain) in TILE_INFO.items()
            },
        ),
    )
    character_sheet = roles.get("character_sprite_sheet")
    character_texture = roles.get("character_texture")
    if character_sheet is not None and character_texture is not None:
        document.asset_views.set_sprite_sheet(
            character_sheet.id,
            SpriteSheet(
                AssetRef(character_texture.id, "texture"),
                [SpriteFrame(**frame) for frame in _character_frames()],
            ),
        )
    for record in project.assets.records():
        if record.kind != "tilemap":
            continue
        document.asset_views.set_tilemap(
            record.id,
            TileMap(
                AssetRef(tileset_record.id, "tileset"), TILE, TILE,
                layers=_starter_map_layers(),
            ),
        )
    return document.asset_views


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
        _starter_map_layers(),
        "map001.tilemap.json",
    )
    _, character_sheet = _register_character_records(project)
    materialize_starter_assets(project, project_dir)
    add_demo_character(project, scene, character_sheet.id)
    path = project_dir / "project.asteria.json"
    project.save_json(path)
    return path
