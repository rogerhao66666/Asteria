from dataclasses import dataclass
from pathlib import Path

from asteria.assets import TextureResourceCache
from asteria.core import Transform
from asteria.graphics import EMPTY_TILE, DirectionalClips
from asteria.reference_data import (
    load_animation_set,
    load_sprite_sheet,
    load_tilemap,
    load_tileset,
)
from asteria.reference_ids import (
    CAMERA_ENTITY_ID,
    ENV_TEXTURE_ID,
    HERO_ENTITY_ID,
    HERO_TEXTURE_ID,
)

from .animation import AnimatorState
from .camera_factory import build_runtime_camera
from .character import CharacterController2D
from .character_animation import CharacterAnimationController
from .components2d import Camera2DComponent
from .draw import sprite_draw
from .input import InputSnapshot
from .player_slice import PlayerCameraSlice
from .texture_renderer import TextureRenderer
from .tile_draw import build_tile_draws
from .tilequery import TileMapQuery


@dataclass(slots=True)
class ReferenceRuntime:
    project: object
    scene: object
    project_root: Path
    tilemap: object
    tileset: object
    environment_sheet: object
    hero_sheet: object
    animation_set: object
    hero: object
    game_camera_entity: object
    camera: object
    camera_follow: object
    player: PlayerCameraSlice

    @classmethod
    def load(cls, project, scene, project_root):
        root = Path(project_root)
        tilemap = load_tilemap(root / "reference_data/tilemap.json")
        tileset = load_tileset(root / "reference_data/environment_tileset.json")
        env_sheet = load_sprite_sheet(root / "reference_data/environment_sheet.json")
        hero_sheet = load_sprite_sheet(root / "reference_data/hero_sheet.json")
        animations = load_animation_set(root / "reference_data/hero_animation.json")
        hero = next((e for e in scene.entities() if e.id == HERO_ENTITY_ID), None)
        camera_entity = next((e for e in scene.entities() if e.id == CAMERA_ENTITY_ID), None)
        if hero is None or camera_entity is None:
            raise ValueError("Reference World requires Hero and Game Camera")
        transform = hero.get(Transform)
        camera, follow = build_runtime_camera(camera_entity)
        camera_target = None
        if follow is not None:
            follow_id = camera_entity.get(Camera2DComponent).follow_entity_id
            camera_target = scene.get_entity(follow_id)
            if camera_target is None:
                raise ValueError(f"Camera follow entity does not exist: {follow_id}")
            if camera_target.try_get(Transform) is None:
                raise ValueError("Camera follow entity requires a Transform")
        clips = DirectionalClips(
            idle={d: animations.get(f"idle_{d}") for d in ("down", "left", "right", "up")},
            walk={d: animations.get(f"walk_{d}") for d in ("down", "left", "right", "up")},
        )
        clips.validate(hero_sheet)
        animator = AnimatorState(clips.idle["down"])
        animation = CharacterAnimationController(clips, animator)
        controller = CharacterController2D(transform.x, transform.y, speed=72.0, half_width=5.0, half_height=7.0)
        player = PlayerCameraSlice(
            hero,
            controller,
            animation,
            follow,
            hero.get(__import__("asteria.runtime.components2d", fromlist=["SpriteRenderer2D"]).SpriteRenderer2D),
            camera_target,
        )
        # Follow cameras begin centered on their target. Fixed cameras retain
        # the authored Camera entity Transform as their world-space top-left.
        if follow is not None:
            target_transform = camera_target.get(Transform)
            follow.update(target_transform.x, target_transform.y, 0.0)
        return cls(
            project,
            scene,
            root,
            tilemap,
            tileset,
            env_sheet,
            hero_sheet,
            animations,
            hero,
            camera_entity,
            camera,
            follow,
            player,
        )

    def step(self, actions, dt):
        return self.player.step(InputSnapshot(dict(actions)), dt, TileMapQuery(self.tilemap))

    def prepare_viewport(self, viewport_width, viewport_height):
        """Fit the authored camera to the output while preserving its world bounds."""
        viewport_width = int(viewport_width)
        viewport_height = int(viewport_height)
        if viewport_width <= 0 or viewport_height <= 0:
            raise ValueError("viewport dimensions must be positive")

        spec = self.game_camera_entity.get(Camera2DComponent)
        output_scale = min(
            viewport_width / spec.width,
            viewport_height / spec.height,
        )
        self.camera.width = viewport_width
        self.camera.height = viewport_height
        self.camera.zoom = spec.zoom * output_scale
        if self.camera_follow is not None:
            self.camera_follow.world_bounds = spec.bounds or self._tilemap_world_bounds()
            target_transform = self.player.camera_target.get(Transform)
            self.camera_follow.update(target_transform.x, target_transform.y, 0.0)

    def _tilemap_world_bounds(self):
        cells = []
        for layer in self.tilemap.layers:
            for chunk in layer.chunks.values():
                base_x = chunk.chunk_x * self.tilemap.chunk_width
                base_y = chunk.chunk_y * self.tilemap.chunk_height
                for local_y in range(chunk.height):
                    for local_x in range(chunk.width):
                        if chunk.get(local_x, local_y) != EMPTY_TILE:
                            cells.append((base_x + local_x, base_y + local_y))
        if not cells:
            return (0.0, 0.0, 0.0, 0.0)
        min_x = min(cell[0] for cell in cells) * self.tilemap.tile_width
        min_y = min(cell[1] for cell in cells) * self.tilemap.tile_height
        max_x = (max(cell[0] for cell in cells) + 1) * self.tilemap.tile_width
        max_y = (max(cell[1] for cell in cells) + 1) * self.tilemap.tile_height
        return (float(min_x), float(min_y), float(max_x), float(max_y))

    def draw_commands(self, viewport_width, viewport_height):
        tile_draws = build_tile_draws(
            self.tilemap,
            self.tileset,
            self.environment_sheet,
            self.camera,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
        transform = self.hero.get(Transform)
        sprite = self.player.sprite
        hero_draw = sprite_draw(
            sheet=self.hero_sheet,
            frame_index=sprite.frame_index,
            world_x=transform.x,
            world_y=transform.y,
            camera=self.camera,
            opacity=sprite.opacity,
            flip_x=sprite.flip_x,
        )
        # Hero should draw above the map in this vertical slice.
        hero_draw = type(hero_draw)(
            hero_draw.texture_asset_id,
            hero_draw.source,
            hero_draw.screen_x,
            hero_draw.screen_y,
            hero_draw.width,
            hero_draw.height,
            100,
            float(transform.y),
            hero_draw.opacity,
            hero_draw.flip_x,
        )
        return tuple(
            sorted(
                (*tile_draws, hero_draw),
                key=lambda d: (d.layer, d.depth, d.screen_y, d.screen_x),
            )
        )

    def texture_sources(self):
        paths = {}
        for texture_id in (ENV_TEXTURE_ID, HERO_TEXTURE_ID):
            record = self.project.assets.get(texture_id)
            if record is None:
                raise KeyError(f"missing texture asset {texture_id}")
            paths[texture_id] = str(self.project_root / record.source_path)
        return paths


def run_reference_runtime(runtime, backend, width, height, target_fps=60, max_frames=None):
    runtime.prepare_viewport(width, height)
    cache = TextureResourceCache(backend.load_texture)
    renderer = TextureRenderer(backend, cache, runtime.texture_sources())
    frames = 0
    while not backend.should_close():
        dt = backend.tick(target_fps) if hasattr(backend, "tick") else 1.0 / target_fps
        actions = backend.poll_actions() if hasattr(backend, "poll_actions") else {}
        runtime.step(actions, dt)
        backend.begin_frame()
        renderer.render(runtime.draw_commands(width, height))
        backend.end_frame()
        frames += 1
        if max_frames is not None and frames >= max_frames:
            break
    return frames
