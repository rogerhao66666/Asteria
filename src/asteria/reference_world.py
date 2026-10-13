import json
from dataclasses import dataclass
from pathlib import Path

from asteria.assets import AssetRecord, AssetRef
from asteria.core import Entity, Scene, Transform
from asteria.graphics import (
    SpriteClip,
    SpriteFrame,
    SpriteKeyframe,
    SpriteSheet,
    TileChunk,
    TileDef,
    TileLayer,
    TileMap,
    Tileset,
)
from asteria.graphics.serialization import tilemap_to_data
from asteria.project import Project
from asteria.reference_ids import (
    CAMERA_ENTITY_ID,
    ENV_SHEET_ID,
    ENV_TEXTURE_ID,
    HERO_ANIMATION_ID,
    HERO_ENTITY_ID,
    HERO_SHEET_ID,
    HERO_TEXTURE_ID,
    PROJECT_ID,
    PROPS_TEXTURE_ID,
    SCENE_ID,
    TILEMAP_ID,
    TILESET_ID,
    WORLD_ENTITY_ID,
)
from asteria.runtime import (
    AnimationClipSet,
    Animator2DComponent,
    Camera2DComponent,
    SpriteRenderer2D,
    TileMap2DComponent,
)


@dataclass(slots=True)
class ReferenceWorldBundle:
    project: Project
    scene: Scene
    tilemap: TileMap
    tileset: Tileset
    environment_sheet: SpriteSheet
    hero_sheet: SpriteSheet
    hero_clips: AnimationClipSet
    hero: Entity
    camera: Entity


def _record(asset_id, kind, path, name, metadata=None):
    return AssetRecord(
        asset_id, kind, path, name, "asteria.reference", 1, {}, dict(metadata or {})
    )


def _chunk_from_grid(grid, chunk_x, chunk_y, chunk_w, chunk_h):
    chunk = TileChunk.empty(chunk_x, chunk_y, chunk_w, chunk_h)
    base_x = chunk_x * chunk_w
    base_y = chunk_y * chunk_h
    for ly in range(chunk_h):
        for lx in range(chunk_w):
            gx = base_x + lx
            gy = base_y + ly
            if 0 <= gy < len(grid) and 0 <= gx < len(grid[0]):
                chunk.set(lx, ly, grid[gy][gx])
    return chunk


def _layer_from_grid(name, order, grid, chunk_w=16, chunk_h=16, **kwargs):
    width = len(grid[0])
    height = len(grid)
    chunks = {}
    for cy in range((height + chunk_h - 1) // chunk_h):
        for cx in range((width + chunk_w - 1) // chunk_w):
            chunk = _chunk_from_grid(grid, cx, cy, chunk_w, chunk_h)
            if any(v != -1 for v in chunk.tiles):
                chunks[(cx, cy)] = chunk
    return TileLayer(name, order=order, chunks=chunks, **kwargs)


def _make_map():
    width, height = 40, 24
    ground = [[0 for _ in range(width)] for _ in range(height)]
    props = [[-1 for _ in range(width)] for _ in range(height)]
    collision = [[-1 for _ in range(width)] for _ in range(height)]

    # Town road and plaza.
    for y in range(3, 21):
        for x in range(17, 23):
            ground[y][x] = 1
    for y in range(8, 16):
        for x in range(10, 31):
            ground[y][x] = 1

    # River / bridge.
    for y in range(height):
        for x in range(32, 36):
            ground[y][x] = 2
            collision[y][x] = 15
    for y in range(11, 14):
        for x in range(32, 36):
            ground[y][x] = 10
            collision[y][x] = -1

    # Forest boundary and flowers.
    for x in range(width):
        props[0][x] = 8
        props[height - 1][x] = 8
        collision[0][x] = 15
        collision[height - 1][x] = 15
    for y in range(height):
        props[y][0] = 8
        props[y][width - 1] = 8
        collision[y][0] = 15
        collision[y][width - 1] = 15
    for x, y in ((4, 4), (6, 7), (9, 18), (27, 5), (29, 19), (4, 15), (13, 4)):
        ground[y][x] = 6

    # Small town buildings represented as roof/wall blocks.
    buildings = ((6, 6, 6, 5), (25, 4, 5, 5), (5, 16, 7, 5), (24, 16, 7, 5))
    for bx, by, bw, bh in buildings:
        for y in range(by, by + bh):
            for x in range(bx, bx + bw):
                props[y][x] = 9 if y == by else 4
                collision[y][x] = 15
        door_x = bx + bw // 2
        props[by + bh - 1][door_x] = 11
        collision[by + bh - 1][door_x] = -1

    # Plaza props.
    for x, y, tile in (
        (15, 10, 12),
        (24, 10, 12),
        (15, 15, 12),
        (24, 15, 12),
        (13, 12, 13),
    ):
        props[y][x] = tile
        collision[y][x] = 15

    return TileMap(
        AssetRef(TILESET_ID, "tileset"),
        16,
        16,
        16,
        16,
        [
            _layer_from_grid("Ground", 0, ground),
            _layer_from_grid("Props", 1, props),
            _layer_from_grid("Collision", 2, collision, visible=False, collision_enabled=True),
        ],
    )


def build_reference_world():
    project = Project("Asteria Reference World", project_id=PROJECT_ID)
    scene = project.add_scene(Scene("Town & River", scene_id=SCENE_ID))

    for record in (
        _record(
            ENV_TEXTURE_ID,
            "texture",
            "reference_assets/asteria_environment_atlas_1x.png",
            "Environment Atlas",
            {"license": "Asteria original reference art", "pixel_scale": 1},
        ),
        _record(
            HERO_TEXTURE_ID,
            "texture",
            "reference_assets/asteria_hero_sheet_1x.png",
            "Hero Sheet",
            {"license": "Asteria original reference art", "pixel_scale": 1},
        ),
        _record(
            PROPS_TEXTURE_ID,
            "texture",
            "reference_assets/asteria_props_1x.png",
            "Props",
            {"license": "Asteria original reference art", "pixel_scale": 1},
        ),
        _record(
            ENV_SHEET_ID,
            "sprite_sheet",
            "reference_data/environment_sheet.json",
            "Environment Sprite Sheet",
        ),
        _record(
            HERO_SHEET_ID,
            "sprite_sheet",
            "reference_data/hero_sheet.json",
            "Hero Sprite Sheet",
        ),
        _record(
            TILESET_ID,
            "tileset",
            "reference_data/environment_tileset.json",
            "Environment Tileset",
        ),
        _record(
            HERO_ANIMATION_ID,
            "animation",
            "reference_data/hero_animation.json",
            "Hero Animation",
        ),
        _record(
            TILEMAP_ID,
            "tilemap",
            "reference_data/tilemap.json",
            "Town & River TileMap",
        ),
    ):
        project.assets.add(record)

    env_frames = [SpriteFrame((i % 8) * 16, (i // 8) * 16, 16, 16, 0.0, 0.0) for i in range(16)]
    environment_sheet = SpriteSheet(AssetRef(ENV_TEXTURE_ID, "texture"), env_frames)
    tileset = Tileset(
        AssetRef(ENV_SHEET_ID, "sprite_sheet"),
        16,
        16,
        {i: TileDef(i, collision="solid" if i in {4, 8, 15} else "none") for i in range(16)},
    )

    hero_frames = []
    for row in range(4):
        for col in range(4):
            hero_frames.append(SpriteFrame(col * 16, row * 24, 16, 24, 0.5, 1.0))
    hero_sheet = SpriteSheet(AssetRef(HERO_TEXTURE_ID, "texture"), hero_frames)

    directions = {"down": 0, "left": 1, "right": 2, "up": 3}
    clips = {}
    for name, row in directions.items():
        base = row * 4
        clips[f"idle_{name}"] = SpriteClip(f"idle_{name}", [SpriteKeyframe(base, 0.4)], True)
        clips[f"walk_{name}"] = SpriteClip(
            f"walk_{name}", [SpriteKeyframe(base + i, 0.12) for i in (0, 1, 2, 3)], True
        )
    hero_clips = AnimationClipSet(clips)

    world = scene.add_entity(Entity("World Map", entity_id=WORLD_ENTITY_ID))
    world_map = world.add_component(TileMap2DComponent())
    world_map.tilemap_asset_id = TILEMAP_ID

    hero = scene.add_entity(Entity("Hero", entity_id=HERO_ENTITY_ID))
    hero.add_component(Transform(20 * 16, 13 * 16))
    sprite = hero.add_component(SpriteRenderer2D())
    sprite.sprite_sheet_asset_id = HERO_SHEET_ID
    sprite.layer = 5
    animator = hero.add_component(Animator2DComponent())
    animator.clip_set_id = HERO_ANIMATION_ID
    animator.default_clip = "idle_down"

    camera = scene.add_entity(Entity("Game Camera", entity_id=CAMERA_ENTITY_ID))
    camera.add_component(Transform(15 * 16, 8 * 16))
    cam = camera.add_component(Camera2DComponent())
    cam.width = 480
    cam.height = 270
    cam.zoom = 1.0
    cam.follow_entity_id = hero.id
    cam.deadzone_x = 0.0
    cam.deadzone_y = 0.0
    cam.smoothing = 12.0

    tilemap = _make_map()
    return ReferenceWorldBundle(
        project,
        scene,
        tilemap,
        tileset,
        environment_sheet,
        hero_sheet,
        hero_clips,
        hero,
        camera,
    )


def write_reference_world(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    data = root / "reference_data"
    data.mkdir(parents=True, exist_ok=True)
    bundle = build_reference_world()
    bundle.project.save_json(root / "AsteriaReferenceWorld.asteria.json")
    (data / "tilemap.json").write_text(
        json.dumps(tilemap_to_data(bundle.tilemap), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (data / "environment_sheet.json").write_text(
        json.dumps(
            {
                "texture_asset_id": ENV_TEXTURE_ID,
                "frames": [
                    {
                        "x": f.x,
                        "y": f.y,
                        "width": f.width,
                        "height": f.height,
                        "pivot_x": f.pivot_x,
                        "pivot_y": f.pivot_y,
                    }
                    for f in bundle.environment_sheet.frames
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (data / "hero_sheet.json").write_text(
        json.dumps(
            {
                "texture_asset_id": HERO_TEXTURE_ID,
                "frames": [
                    {
                        "x": f.x,
                        "y": f.y,
                        "width": f.width,
                        "height": f.height,
                        "pivot_x": f.pivot_x,
                        "pivot_y": f.pivot_y,
                    }
                    for f in bundle.hero_sheet.frames
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (data / "environment_tileset.json").write_text(
        json.dumps(
            {
                "sprite_sheet_asset_id": ENV_SHEET_ID,
                "tile_width": 16,
                "tile_height": 16,
                "tiles": {
                    str(i): {
                        "frame_index": t.frame_index,
                        "collision": t.collision,
                        "terrain": t.terrain,
                        "tags": list(t.tags),
                    }
                    for i, t in bundle.tileset.tiles.items()
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (data / "hero_animation.json").write_text(
        json.dumps(
            {
                "clips": {
                    name: {
                        "loop": clip.loop,
                        "keyframes": [
                            {"frame_index": k.frame_index, "duration": k.duration}
                            for k in clip.keyframes
                        ],
                    }
                    for name, clip in bundle.hero_clips.clips.items()
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return bundle
