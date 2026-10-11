"""Field play on canonical TileMap scenes (W-18): imported RPG Maker MV maps and authored tile maps.

``TileMapField`` drives the normal ``GameSessionRuntime`` (events, action and
touch interactions, transfers between scenes, saves) and draws the current
scene from canonical project assets resolved through the asset registry:

* the scene's ``TileMap2D`` binding -> ``tilemap`` -> ``tileset`` -> ``sprite_sheet`` -> ``texture``
* every entity with a ``SpriteRenderer2D`` whose sheet resolves (the player animates
  with its ``Animator2D`` clip set's ``idle_*`` / ``walk_*`` clips)

Tile layers with ``order < 100`` draw under characters, ``order >= 100`` above them;
the player collides with every ``collision_enabled`` layer and with solid ``Collider2D``
entities; its box (``CharacterController2D`` half sizes) stands on its feet. Nothing here knows
where the data came from (no MV code is imported).
"""

from __future__ import annotations

from pathlib import Path

from asteria.core import Transform
from asteria.graphics import DirectionalClips
from asteria.reference_data import load_animation_set, load_sprite_sheet, load_tilemap, load_tileset

from .animation import AnimatorState
from .camera_factory import build_runtime_camera
from .character import CharacterController2D
from .character_animation import CharacterAnimationController
from .components2d import Animator2DComponent, Camera2DComponent, SpriteRenderer2D, TileMap2DComponent
from .draw import TextureDraw, sprite_draw
from .input import InputSnapshot
from .tile_draw import build_tile_draws
from .tilequery import TileMapQuery

ABOVE_CHARACTERS = 100
_LOADERS = {
    "tilemap": load_tilemap,
    "tileset": load_tileset,
    "sprite_sheet": load_sprite_sheet,
    "animation": load_animation_set,
}


class TileMapFieldError(RuntimeError):
    pass


class AssetResources:
    """Canonical project asset records -> loaded resources (cached), with clear errors for broken references."""

    def __init__(self, project, root):
        self.project = project
        self.root = Path(root)
        self._cache = {}

    def path(self, asset_id, kind):
        record = self.project.assets.get(str(asset_id))
        if record is None:
            raise TileMapFieldError(f"missing {kind} asset {asset_id}")
        if record.kind != kind:
            raise TileMapFieldError(f"asset {asset_id} is a {record.kind}, not a {kind}")
        path = self.root / record.source_path
        if not path.is_file():
            raise TileMapFieldError(f"{kind} asset {asset_id} file is missing: {record.source_path}")
        return path

    def get(self, asset_id, kind):
        key = (str(asset_id), kind)
        if key not in self._cache:
            self._cache[key] = _LOADERS[kind](self.path(asset_id, kind))
        return self._cache[key]

    def texture_path(self, asset_id):
        return str(self.path(asset_id, "texture"))


def tilemap_binding(scene):
    """The scene's first visible TileMap2D binding with an asset id, else None."""
    for entity in scene.entities():
        binding = entity.try_get(TileMap2DComponent)
        if binding is not None and binding.visible and binding.tilemap_asset_id:
            return binding
    return None


def can_play(project, root):
    """True when the project's start scene is a canonical tile map with a player entity."""
    start = project.game_start
    scene = project.scene(start.scene_id or project.startup_scene_id)
    if scene is None or not start.player_entity_id or scene.get_entity(start.player_entity_id) is None:
        return False
    binding = tilemap_binding(scene)
    if binding is None:
        return False
    try:
        AssetResources(project, root).path(binding.tilemap_asset_id, "tilemap")
    except TileMapFieldError:
        return False
    return True


class TileMapField:
    def __init__(self, session, root):
        self.session = session
        self.resources = AssetResources(session.project, root)
        self.viewport = (816, 624)
        self._scene_id = None
        self._confirm_down = False
        self._last_dt = 0.0
        self._load_scene()

    # -- scene binding ----------------------------------------------------------------------------
    def _load_scene(self):
        scene = self.session.scene
        binding = tilemap_binding(scene)
        if binding is None:
            raise TileMapFieldError(f"scene {scene.name} has no TileMap2D binding")
        self.tilemap = self.resources.get(binding.tilemap_asset_id, "tilemap")
        self.tileset = self.resources.get(self.tilemap.tileset.asset_id, "tileset")
        self.tile_sheet = self.resources.get(self.tileset.sprite_sheet.asset_id, "sprite_sheet")
        self.tilemap.validate()
        self.tileset.validate(len(self.tile_sheet.frames))
        self.query = TileMapQuery(self.tilemap)
        player = self.session.player
        t = player.get(Transform)
        speed, half_w, half_h = 72.0, 5.0, 7.0
        from .character_control import CharacterController2DComponent

        spec = player.try_get(CharacterController2DComponent)
        if spec is not None:
            speed, half_w, half_h = spec.speed, spec.half_width, spec.half_height
        self.controller = CharacterController2D(t.x, t.y, speed=speed, half_width=half_w, half_height=half_h)
        self.animation = None
        animator = player.try_get(Animator2DComponent)
        sprite = player.try_get(SpriteRenderer2D)
        if animator is not None and animator.clip_set_id and sprite is not None:
            clips = self.resources.get(animator.clip_set_id, "animation")
            directions = ("down", "left", "right", "up")
            if all(f"idle_{d}" in clips.clips and f"walk_{d}" in clips.clips for d in directions):
                directional = DirectionalClips(
                    idle={d: clips.get(f"idle_{d}") for d in directions},
                    walk={d: clips.get(f"walk_{d}") for d in directions},
                )
                self.animation = CharacterAnimationController(
                    directional, AnimatorState(directional.idle.get(self.session.facing, directional.idle["down"]))
                )
                self.animation.facing = self.session.facing
        camera_entity = next(
            (
                e
                for e in scene.entities()
                if e.try_get(Camera2DComponent) is not None and e.get(Camera2DComponent).active
            ),
            None,
        )
        self.camera_spec = None if camera_entity is None else camera_entity.get(Camera2DComponent)
        if camera_entity is not None:
            self.camera, self.follow = build_runtime_camera(camera_entity)
        else:
            from .camera import Camera2D

            self.camera, self.follow = Camera2D(width=self.viewport[0], height=self.viewport[1]), None
        self._scene_id = scene.id
        self._bounds = None
        self.prepare_viewport(*self.viewport)

    def prepare_viewport(self, width, height):
        self.viewport = (int(width), int(height))
        spec_w = self.camera_spec.width if self.camera_spec else width
        spec_h = self.camera_spec.height if self.camera_spec else height
        zoom = self.camera_spec.zoom if self.camera_spec else 1.0
        scale = min(width / spec_w, height / spec_h)
        self.camera.width, self.camera.height = width, height
        self.camera.zoom = zoom * scale
        bounds = self.world_bounds()
        if self.follow is not None:
            self.follow.world_bounds = (self.camera_spec.bounds if self.camera_spec else None) or bounds
        self._follow_player(0.0)

    def world_bounds(self):
        cached = getattr(self, "_bounds", None)
        if cached is not None and cached[0] == self._scene_id:
            return cached[1]
        self._bounds = (self._scene_id, self._compute_bounds())
        return self._bounds[1]

    def _compute_bounds(self):
        width = max(
            (c.chunk_x + 1) * self.tilemap.chunk_width for layer in self.tilemap.layers for c in layer.chunks.values()
        )
        height = max(
            (c.chunk_y + 1) * self.tilemap.chunk_height for layer in self.tilemap.layers for c in layer.chunks.values()
        )
        cells = [
            (c.chunk_x * self.tilemap.chunk_width + x, c.chunk_y * self.tilemap.chunk_height + y)
            for layer in self.tilemap.layers
            for c in layer.chunks.values()
            for y in range(c.height)
            for x in range(c.width)
            if c.get(x, y) != -1
        ]
        if cells:
            width = max(x for x, _ in cells) + 1
            height = max(y for _, y in cells) + 1
        return (0.0, 0.0, float(width * self.tilemap.tile_width), float(height * self.tilemap.tile_height))

    def _follow_player(self, dt, velocity=None):
        t = self.session.player.get(Transform)
        if self.follow is not None:
            self.follow.update(t.x, t.y, dt, velocity=velocity)
        else:
            self.camera.x = t.x - self.camera.width / (2 * self.camera.zoom)
            self.camera.y = t.y - self.camera.height / (2 * self.camera.zoom)

    # -- simulation -------------------------------------------------------------------------------
    @property
    def dialogue(self):
        request = self.session.pending_dialogue
        line = getattr(request, "line", None)
        if line is None:
            return None
        return f"{line.speaker}: {line.text}" if line.speaker else line.text

    def step(self, actions, dt):
        """One frame: dialogue / movement / interactions / events. Returns the player's (dx, dy)."""
        session = self.session
        self._last_dt = float(dt)
        actions = dict(actions)
        confirm = any(actions.get(a, 0.0) > 0 for a in ("confirm", "interact"))
        pressed = confirm and not self._confirm_down
        self._confirm_down = confirm
        moved = (0.0, 0.0)
        if session.pending_dialogue is not None:
            if pressed and getattr(session.pending_dialogue, "line", None) is not None:
                session.acknowledge_dialogue()
                session.interaction._was_down = True  # the same press must not talk to the NPC again
        elif session.mode == "field" and not session.event_busy:
            dx, dy = InputSnapshot(actions).movement_vector()
            t = session.player.get(Transform)
            hh = self.controller.half_height  # the collision box stands on the feet (bottom edge = feet)
            self.controller.x, self.controller.y = t.x, t.y - hh
            from .collision import CollisionWorld, CombinedQuery

            solids = CollisionWorld.from_scene(session.scene).blocking_query(exclude={session.player.id})
            moved = self.controller.move(dx, dy, dt, CombinedQuery(self.query, solids))  # tiles + solid entities
            x0, y0, x1, y1 = self.world_bounds()  # the map edge blocks like a wall
            self.controller.x = min(
                max(self.controller.x, x0 + self.controller.half_width), x1 - self.controller.half_width
            )
            self.controller.y = min(
                max(self.controller.y, y0 + self.controller.half_height), y1 - self.controller.half_height
            )
            moved = (self.controller.x - t.x, self.controller.y + hh - t.y)
            session.set_player_position(self.controller.x, self.controller.y + hh)
            if self.animation is not None:
                self.animation.update_motion(*moved)
                session.set_player_facing(self.animation.facing)
            session.field_step(actions)
        session.update_events(dt)
        if session.mode == "field":
            session.field_update(dt)
        if self.animation is not None:
            if session.event_busy:
                self.animation.update_motion(0.0, 0.0)
            self.animation.animator.update(dt)
        if session.scene.id != self._scene_id:
            self._load_scene()  # transferred
        velocity = (moved[0] / dt, moved[1] / dt) if dt > 0 else None
        self._follow_player(dt, velocity)
        return moved

    # -- drawing ----------------------------------------------------------------------------------
    def _sprite_draws(self):
        draws = []
        for entity in self.session.scene.entities():
            if not entity.enabled:
                continue
            sprite = entity.try_get(SpriteRenderer2D)
            t = entity.try_get(Transform)
            if sprite is None or t is None or not sprite.sprite_sheet_asset_id or not getattr(sprite, "visible", True):
                continue
            try:
                sheet = self.resources.get(sprite.sprite_sheet_asset_id, "sprite_sheet")
            except TileMapFieldError:
                continue
            frame = sprite.frame_index
            if entity is self.session.player and self.animation is not None:
                frame = self.animation.animator.frame_index
            if not 0 <= frame < len(sheet.frames):
                continue
            d = sprite_draw(
                sheet=sheet,
                frame_index=frame,
                world_x=t.x,
                world_y=t.y,
                camera=self.camera,
                opacity=getattr(sprite, "opacity", 1.0),
                flip_x=getattr(sprite, "flip_x", False),
            )
            draws.append(
                TextureDraw(
                    d.texture_asset_id,
                    d.source,
                    d.screen_x,
                    d.screen_y,
                    d.width,
                    d.height,
                    ABOVE_CHARACTERS - 1,
                    float(t.y),
                    d.opacity,
                    d.flip_x,
                )
            )
        return draws

    def draw_commands(self):
        width, height = self.viewport
        tiles = build_tile_draws(
            self.tilemap, self.tileset, self.tile_sheet, self.camera, viewport_width=width, viewport_height=height
        )
        return tuple(sorted((*tiles, *self._sprite_draws()), key=lambda d: (d.layer, d.depth, d.screen_y, d.screen_x)))

    def environment(self, time=0.0):
        """The current scene's Environment2D / lights / water projected through the field camera."""
        from .environment2d import resolve_environment

        def read_shader(asset_id):
            try:
                return self.resources.path(asset_id, "shader").read_text(encoding="utf-8")
            except TileMapFieldError:
                return None

        env = resolve_environment(
            self.session.scene, to_screen=self.camera.world_to_screen, scale=self.camera.zoom, read_shader=read_shader
        )
        if env.weather != "none":
            from .weather import WeatherSystem

            weather = self.__dict__.get("_weather")
            if weather is None or (weather.width, weather.height) != tuple(self.viewport):
                weather = self._weather = WeatherSystem(*self.viewport, seed=f"{self.session.scene.id}:weather")
            center = (self.camera.x + self.camera.width / (2 * self.camera.zoom), self.camera.y)
            weather.update(
                self._last_dt,
                env.weather,
                env.weather_intensity,
                env.weather_max_particles,
                env.weather_wind,
                camera=center,
                scale=self.camera.zoom,
            )
        return env

    def weather_rects(self):
        weather = self.__dict__.get("_weather")
        if weather is None or weather.kind == "none":
            return []
        from .weather import _KINDS

        color = _KINDS[weather.kind][2]
        if weather.kind == "rain":
            return [(x, y, 1, s * 2, color) for x, y, s in zip(weather.x, weather.y, weather.size, strict=True)]
        return [(x, y, s, s, color) for x, y, s in zip(weather.x, weather.y, weather.size, strict=True)]

    def texture_sources(self):
        ids = {self.tile_sheet.texture.asset_id}
        for entity in self.session.scene.entities():
            sprite = entity.try_get(SpriteRenderer2D)
            if sprite is not None and sprite.sprite_sheet_asset_id:
                try:
                    ids.add(self.resources.get(sprite.sprite_sheet_asset_id, "sprite_sheet").texture.asset_id)
                except TileMapFieldError:
                    pass
        return {asset_id: self.resources.texture_path(asset_id) for asset_id in ids}


def run_tilemap_field(field, backend, width, height, target_fps=60, max_frames=None, on_frame=None):
    """Window loop: input -> step -> draw (textures reloaded when a transfer changes the scene)."""
    from asteria.assets import TextureResourceCache

    from .texture_renderer import TextureRenderer

    field.prepare_viewport(width, height)
    cache = TextureResourceCache(backend.load_texture)
    scene_id, renderer = None, None
    frames, clock = 0, 0.0
    while not backend.should_close():
        dt = backend.tick(target_fps) if hasattr(backend, "tick") else 1.0 / target_fps
        actions = backend.poll_actions() if hasattr(backend, "poll_actions") else {}
        field.step(actions, dt)
        if field.session.scene.id != scene_id:
            field.prepare_viewport(width, height)
            renderer = TextureRenderer(backend, cache, field.texture_sources())
            scene_id = field.session.scene.id
        clock += dt
        if hasattr(backend, "set_environment"):
            env = field.environment(clock)
            backend.set_environment(env if env.active else None, clock)
        backend.begin_frame()
        renderer.render(field.draw_commands())
        if hasattr(backend, "draw_rects"):
            backend.draw_rects(field.weather_rects())
        if field.dialogue and hasattr(backend, "draw_text_box"):
            backend.draw_text_box(field.dialogue)
        backend.end_frame()
        frames += 1
        if on_frame is not None:
            on_frame(frames)
        if max_frames is not None and frames >= max_frames:
            break
    return frames
