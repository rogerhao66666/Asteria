from __future__ import annotations

import json
from pathlib import Path

from asteria.core import Transform
from asteria.runtime.audio_mixer import AudioMixer
from asteria.runtime.battle_presentation_adapters import create_battle_presentation_adapter
from asteria.runtime.battle_visuals import vfx_rect
from asteria.runtime.collision import CollisionWorld
from asteria.runtime.field_camera import CAMERA_COMMANDS, FieldCameraError, FieldViewCamera
from asteria.runtime.field_presentation import (
    FIELD_EFFECT_COMMANDS,
    FieldEffectError,
    FieldEffects,
)
from asteria.runtime.game_menus import (
    GAME_OVER_OPTIONS,
    PAUSE_OPTIONS,
    CraftingScreen,
    GameSettings,
    MenuCursor,
    ShopScreen,
    achievement_rows,
    bestiary_rows,
    quest_rows,
)
from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.game_session import GameSessionRuntime
from asteria.runtime.input_map import InputActionTracker
from asteria.runtime.profiler import NullProfiler, RuntimeProfiler

WALK_ROW_BY_FACING = {"down": 0, "left": 1, "right": 2, "up": 3}
WALK_PATTERN_SEQUENCE = (0, 1, 2, 1)


def walking_row_index(facing: str) -> int:
    return WALK_ROW_BY_FACING.get(facing, 0)


def walking_pattern_index(field_step: int) -> int:
    """Use MV's 0-1-2-1 walk loop; never jump directly from stride to stride."""
    return WALK_PATTERN_SEQUENCE[(max(0, int(field_step)) // 8) % len(WALK_PATTERN_SEQUENCE)]


FIELD_BODY_HEIGHT = 24.0  # world units a field character stands tall (VFX anchors)


def field_player_render_size(frame_size, render_width=64) -> tuple[int, int]:
    """Scale field sprites to ``render_width`` while preserving each source frame's ratio."""
    frame_w, frame_h = (int(frame_size[0]), int(frame_size[1]))
    if frame_w <= 0 or frame_h <= 0:
        raise ValueError("player frame dimensions must be positive")
    render_w = int(render_width)
    render_h = max(1, round(frame_h * render_w / frame_w))
    return render_w, render_h


def _load_manifest(resource_root):
    path = Path(resource_root) / "playable_test_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "asteria.playable_test_content" or data.get("version") != 1:
        raise ValueError("unsupported playable test manifest")
    return data


class PlayableTestRuntime:
    """Small human-operable pygame adapter for serialized Asteria reference games.

    This module is intentionally adapter/test-content code. Game rules remain in
    Project + GameRuntimeSave + GameSessionRuntime. The adapter only handles
    input, pixels, simple menu navigation and VFX playback.
    """

    def __init__(
        self, project, runtime_save, resource_root, *, width=960, height=540, backend=None
    ):
        try:
            import pygame
        except ImportError as exc:
            raise RuntimeError(
                "Playable reference game requires pygame-ce. Install with: pip install "
                "'pygame-ce>=2.5'"
            ) from exc

        self.pg = pygame
        self.project = project
        self.resource_root = Path(resource_root)
        self.manifest = _load_manifest(self.resource_root)
        self.game = GameSessionRuntime(project, runtime_save)
        self.save = runtime_save
        self.width = int(width)
        self.height = int(height)
        # ENG-12: "pygame" (default) or "moderngl" (GPU presentation + post-processing); manifest
        # render.backend
        self.backend_kind = backend or self.manifest.get("render", {}).get("backend", "pygame")
        self.gpu = None
        self.gpu_fallback_reason = ""
        self._world_layer = None
        self._ui_layer = None
        self._frame_env = None
        self._frame_dt = 0.0
        self._clock_seconds = 0.0
        self._weather = None
        self._l0 = None
        self.environment_errors = []
        self.environment_unsupported = []
        self.screen = None
        self.clock = None
        self.running = True
        self.message = ""
        self.message_until = 0
        self._field_step = 0
        self._held_interact = False
        self._battle_skill_index = 0
        self._last_action_name = ""
        self._victory = False
        self._defeat = False
        self._loaded = {}
        self._icon_cache = {}  # (icon id, size) -> scaled menu icon
        # Resource lifetime (ENG-10): images first loaded during a battle belong to
        # the "battle" scope and are released when play returns to the field.
        self._image_scope = {}
        self.released_images = 0
        self.debug_server = None
        self._ui_mode = "title"
        self._menu_actor_index = 0
        self._turn_actor = None
        self._victory_summary = []
        self._fonts = {}
        self._glyphs = {}  # (font, char) -> the font can draw it
        self._battle_presentation = create_battle_presentation_adapter(self)
        self.profiler = NullProfiler()
        self._drawing = False
        self._wrap_draw_methods()
        options = list(PAUSE_OPTIONS)
        if getattr(self.project.rpg_database, "pet_species", None):  # a game with pets
            options.insert(2, ("pets", "Pets"))
        self._pause_menu = MenuCursor(options)
        self._pets_screen = None
        self._game_over_menu = MenuCursor(GAME_OVER_OPTIONS)
        self._shop_screen = None
        self._quest_return = "field"
        self._capture_menu = False
        self._crafting_screen = None
        self._list_scroll = 0
        self.settings = GameSettings.load(self._settings_path())
        self._settings_menu = MenuCursor(GameSettings.OPTIONS)

    def path(self, rel):
        return self.resource_root / str(rel)

    def load_image(self, rel):
        rel = str(rel)
        if rel not in self._loaded:
            with self.profiler.section("asset_loading"):
                self._loaded[rel] = self.pg.image.load(self.path(rel)).convert_alpha()
            in_battle = self.game.mode == "battle" or self._victory or self._defeat
            self._image_scope[rel] = "battle" if in_battle else "field"
        return self._loaded[rel]

    def icon_image(self, icon_id, size=24):
        """The menu icon ``icon_id`` (see ``menu_icons``) scaled to fit ``size`` pixels, or
        None."""
        from .menu_icons import icon_source

        cache = self._icon_cache
        key = (str(icon_id or ""), int(size))
        if key in cache:
            return cache[key]
        icon = None
        source = icon_source(self.project, icon_id)
        if source is not None:
            uri, region = source
            try:
                image = self.load_image(uri)
                if region is not None:
                    image = image.subsurface(self.pg.Rect(region).clip(image.get_rect()))
                w, h = image.get_size()
                scale = min(size / max(1, w), size / max(1, h))
                target = (max(1, round(w * scale)), max(1, round(h * scale)))
                pixel_art = scale >= 1 and float(scale).is_integer()
                icon = (self.pg.transform.scale if pixel_art else self.pg.transform.smoothscale)(
                    image, target
                )
            except (OSError, ValueError, self.pg.error):
                icon = None  # a missing or broken icon shows the name only
        cache[key] = icon
        return icon

    @property
    def particle_drawer(self):
        from .particle_draw import ParticleDrawer

        drawer = getattr(self, "_particle_drawer", None)
        if drawer is None:
            drawer = self._particle_drawer = ParticleDrawer(self.pg)
        return drawer

    def particle_image(self, image_id):
        """The image of image particles (VFX-01): any id ``menu_icons`` resolves (icon cell, image,
        path)."""
        from .menu_icons import icon_source

        source = icon_source(self.project, image_id)
        if source is None:
            return None
        uri, region = source
        try:
            image = self.load_image(uri)
            return (
                image.subsurface(self.pg.Rect(region).clip(image.get_rect())) if region else image
            )
        except (OSError, ValueError, self.pg.error):
            return None

    def _draw_icon(self, icon_id, x, y, size=22):
        """Draw the icon centred in a ``size`` box at (x, y); True when one was drawn."""
        icon = self.icon_image(icon_id, size) if icon_id else None
        if icon is None:
            return False
        w, h = icon.get_size()
        self.screen.blit(icon, (x + (size - w) // 2, y + (size - h) // 2))
        return True

    def release_resource_scope(self, scope):
        """Drop every cached image owned by ``scope``; returns how many were released."""
        self._icon_cache.clear()  # icons are cut from cached images: rebuild them on demand
        names = [rel for rel, owner in self._image_scope.items() if owner == scope]
        for rel in names:
            self._loaded.pop(rel, None)
            self._image_scope.pop(rel, None)
        self.released_images += len(names)
        return len(names)

    def enable_debugger(self, *, port=0, token=None):
        """Start the editor debug channel (EDT-10); returns the DebugServer."""
        from asteria.runtime.debug_server import DebugServer
        from asteria.runtime.debugger import RuntimeDebugger

        self.debug_server = DebugServer(RuntimeDebugger(self.game, self), port=port, token=token)
        return self.debug_server

    def _update_resource_scope(self):
        in_battle = self.game.mode == "battle" or self._victory or self._defeat
        if not in_battle and "battle" in self._image_scope.values():
            self.release_resource_scope("battle")

    # Top-level drawing entry points; nested calls are timed once.
    _DRAW_METHODS = (
        "_draw_field",
        "_draw_title",
        "_draw_build_menu",
        "_draw_overlay_menu",
        "_draw_quests",
        "_draw_shop",
        "_draw_crafting",
        "_draw_list_screen",
        "_draw_settings",
        "_draw_capture_menu",
    )

    def _wrap_draw_methods(self):
        for name in self._DRAW_METHODS:
            method = getattr(self, name)

            def timed(*args, _method=method, **kwargs):
                if self._drawing:
                    return _method(*args, **kwargs)
                self._drawing = True
                try:
                    with self.profiler.section("render"):
                        return _method(*args, **kwargs)
                finally:
                    self._drawing = False

            setattr(self, name, timed)

    def enable_profiling(self, profiler=None, *, target_fps=60.0):
        """Attach a RuntimeProfiler (also to the game session) and declare what pygame cannot
        measure."""
        self.profiler = profiler or RuntimeProfiler(target_fps=target_fps)
        self.game.profiler = self.profiler
        if self.gpu is None:
            self.profiler.unsupported(
                "draw_calls", "pygame software blitting exposes no draw-call counter"
            )
            self.profiler.unsupported(
                "gpu_time", "pygame backend renders on the CPU; no GPU timer"
            )
        return self.profiler

    def _sample_counters(self):
        p = self.profiler
        p.count("entity_count", len(self.game.scene.entities()))
        p.count("asset_usage", len(self._loaded))
        particles = getattr(self._battle_presentation, "particle_count", None)
        if callable(particles):
            p.count("particles", particles())

    def open(self):
        self.pg.init()
        title = self.manifest.get("title", "Asteria Playable Test")
        self.screen = None
        if self.backend_kind == "moderngl":
            from asteria.platform.gpu_presenter import GpuPresenter, GpuPresenterError

            try:
                self.gpu = GpuPresenter.open_window(self.pg, (self.width, self.height), title)
                self.screen = self.pg.Surface(
                    (self.width, self.height), 0, 32
                )  # composed here, shown by the GPU
            except GpuPresenterError as exc:
                self.gpu, self.gpu_fallback_reason = (
                    None,
                    str(exc),
                )  # keep playing on the pygame window
        if self.screen is None:
            self.screen = self.pg.display.set_mode((self.width, self.height))
        self.pg.display.set_caption(title)
        self.clock = self.pg.time.Clock()
        from asteria.platform.pygame_input import PygameInputSource

        self.input_source = PygameInputSource(self.pg)
        from asteria.runtime.input_rebinding import effective_input_map

        # ENG-15: the player's rebinding (settings) over the project's default bindings
        input_map = effective_input_map(self.project.input_map, self.settings.input_overrides)
        from asteria.runtime.action_play import missing_action_bindings

        for action, bindings in missing_action_bindings(
            input_map
        ).items():  # action-scene controls (not saved)
            input_map.set_bindings(action, bindings)
        self.input = InputActionTracker(input_map)
        from asteria.platform.pygame_audio import open_audio_device

        self.audio = AudioMixer(open_audio_device(self.pg), self._audio_path)
        self.settings.apply(self.audio)
        return self

    def _settings_path(self):
        return self.resource_root / "saves" / "settings.json"

    def _audio_path(self, asset_id):
        """Manifest audio map first, then a canonical project asset; None when missing."""
        rel = self.manifest.get("audio", {}).get(asset_id)
        if rel is not None:
            path = self.path(rel)
        else:
            try:
                path = Path(self.project.assets.resolve(asset_id).source.uri)
            except KeyError:
                return None
            if not path.is_absolute():
                path = self.resource_root / path
        return path if path.is_file() else None

    # -- scene environment: lighting, fog, weather, post-processing (VFX-02 / VFX-03) -------------
    def _resolve_environment(self, kind):
        from asteria.runtime.environment2d import resolve_environment

        defaults = self.manifest.get("render", {}).get("environment")
        if kind == "field":
            scale = (
                float(self.manifest["field"].get("world_to_screen_scale", 3.0))
                * self.field_camera.zoom
            )
            return resolve_environment(
                self.game.scene,
                defaults=defaults,
                to_screen=self.field_camera.world_to_screen,
                scale=scale,
                read_shader=self._read_shader,
            )
        env = resolve_environment(
            self.game.scene, defaults=defaults, read_shader=self._read_shader
        )
        # scene lights are placed in the field; battles keep fog, weather and post effects
        env.lighting = False
        return env

    def _read_shader(self, asset_id):
        """A project ``shader`` asset's GLSL source (asset registry), or None."""
        record = self.project.assets.get(str(asset_id))
        if record is None or record.kind != "shader":
            return None
        path = self.resource_root / record.source_path
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def world_done(self, kind):
        """The world layer for this frame is drawn: weather goes on it, and what follows (HUD,
        menus,
        dialogue, fades) is drawn on a separate UI layer so lighting and post effects never touch
        it."""
        env = self._resolve_environment(kind)
        self._frame_env = env
        if env is None or not env.active:
            return
        if env.weather != "none" or self._weather is not None:
            from asteria.runtime.weather import WeatherSystem

            if self._weather is None:
                self._weather = WeatherSystem(
                    self.width, self.height, seed=f"{self.game.scene.id}:weather"
                )
            camera = self.field_camera.view[:2] if kind == "field" else None
            scale = (
                float(self.manifest["field"].get("world_to_screen_scale", 3.0))
                * self.field_camera.zoom
            )
            self._weather.update(
                self._frame_dt,
                env.weather,
                env.weather_intensity,
                env.weather_max_particles,
                env.weather_wind,
                camera=camera,
                scale=scale,
            )
            with self.profiler.section("vfx"):
                self.profiler.count(
                    "particles", self._weather.draw(self.pg, self.screen, env.weather_wind)
                )
        self._world_layer = self.screen
        if self._ui_layer is None or self._ui_layer.get_size() != self.screen.get_size():
            self._ui_layer = self.pg.Surface(self.screen.get_size(), self.pg.SRCALPHA, 32)
        self._ui_layer.fill((0, 0, 0, 0))
        self.screen = self._ui_layer

    def drawing_world(self):
        """Context manager: draw into the world layer even after ``world_done`` (e.g. battle
        VFX)."""
        from contextlib import contextmanager

        @contextmanager
        def scope():
            if self._world_layer is None:
                yield
                return
            ui, self.screen = self.screen, self._world_layer
            try:
                yield
            finally:
                self.screen = ui

        return scope()

    def present(self):
        """Show the composed frame: GPU presenter (upload + effect chain) or the pygame window
        flip."""
        world, ui = self.screen, None
        if self._world_layer is not None:
            world, ui = self._world_layer, self.screen
            self.screen = world
            self._world_layer = None
        env, self._frame_env = self._frame_env, None
        self._lit_last_frame = bool(env is not None and env.lighting)
        normals = self._normal_layer if getattr(self, "_normal_layer_active", False) else None
        self._normal_layer_active = False
        if self.gpu is not None:
            with self.profiler.section("gpu_present"):
                self.gpu.present_layers(
                    world, ui, self.pg, environment=env, normals=normals, time=self._clock_seconds
                )
            if self.gpu.post is not None and self.gpu.post.errors:
                self.environment_errors = list(self.gpu.post.errors)
        else:
            if env is not None and env.active:
                from asteria.runtime.environment_fallback import (
                    PygameEnvironmentRenderer,
                    unsupported,
                )

                if self._l0 is None:
                    self._l0 = PygameEnvironmentRenderer(self.pg)
                self._l0.time = self._clock_seconds
                self._l0.apply(world, env)
                self.environment_unsupported = unsupported(env)
            if ui is not None:
                world.blit(ui, (0, 0))
        if self.gpu is not None:
            self.profiler.count(
                "draw_calls", self.gpu.last_draw_calls
            )  # presenter + effect passes
            if self.gpu.last_gpu_ms is not None:
                self.profiler.add_time("gpu_time", self.gpu.last_gpu_ms / 1000.0)
        self.pg.display.flip()

    def capture(self):
        """The frame as the player sees it (after GPU post-processing when active)."""
        return self.gpu.read(self.pg) if self.gpu is not None else self.screen.copy()

    def close(self):
        if self.gpu is not None:
            self.gpu.release()
            self.gpu = None
        if self.debug_server is not None:
            self.debug_server.close()
            self.debug_server = None
        audio = getattr(self, "audio", None)
        if audio is not None:
            audio.stop_music()
        if self.pg.get_init():
            self.pg.quit()

    def text(self, value, x, y, *, size=20, color=(245, 245, 250), center=False, anchor=None):
        """Draw text at ``(x, y)``: top-left by default, ``center=True`` centres it, ``anchor`` is
        any pygame rect attribute (``"midleft"``, ``"midright"``, ``"bottomright"``...) placed at
        the point - so a label can sit on the same horizontal line as a bar."""
        f = self._fonts.get(int(size))
        if f is None:
            f = self._fonts[int(size)] = self.pg.font.Font(None, int(size))
        from asteria.platform.pygame_battle_ui import renderable_text

        # rendered text is cached: HUD labels and damage numbers repeat every frame
        key = (str(value), int(size), tuple(color))
        cache = self.__dict__.setdefault("_text_cache", {})
        surf = cache.get(key)
        if surf is None:
            if len(cache) > 2048:
                cache.clear()
            surf = cache[key] = f.render(
                renderable_text(self.pg, f, value, self._glyphs), True, color
            )
        rect = surf.get_rect()
        if anchor:
            setattr(rect, anchor, (int(x), int(y)))
        elif center:
            rect.center = (int(x), int(y))
        else:
            rect.topleft = (int(x), int(y))
        self.screen.blit(surf, rect)
        return rect

    def panel(self, rect, fill=(13, 17, 28, 220), border=(124, 145, 190)):
        s = self.pg.Surface((rect[2], rect[3]), self.pg.SRCALPHA)
        s.fill(fill)
        self.screen.blit(s, (rect[0], rect[1]))
        self.pg.draw.rect(self.screen, border, rect, 2, border_radius=6)

    def bar(self, x, y, w, h, current, maximum, *, fill=(90, 203, 130), bg=(48, 53, 66)):
        maximum = max(float(maximum), 1.0)
        ratio = max(0.0, min(1.0, float(current) / maximum))
        self.pg.draw.rect(self.screen, bg, (x, y, w, h), border_radius=4)
        self.pg.draw.rect(self.screen, fill, (x, y, int(w * ratio), h), border_radius=4)
        self.pg.draw.rect(self.screen, (220, 225, 235), (x, y, w, h), 1, border_radius=4)

    @property
    def field_camera(self):
        """Field view camera (CAM-02); identity unless an event focuses or shakes it."""
        camera = getattr(self, "_field_camera", None)
        if camera is None:
            scale = float(self.manifest["field"].get("world_to_screen_scale", 3.0))
            camera = self._field_camera = FieldViewCamera(
                self.width,
                self.height,
                scale,
                follow=self.manifest["field"].get("camera", {}).get("follow"),
            )
        return camera

    @property
    def field_effects(self):
        """Screen fades and field VFX started by event programs (EVT-02 / EVT-04)."""
        effects = getattr(self, "_field_effects", None)
        if effects is None:
            effects = self._field_effects = FieldEffects()
        return effects

    def _draw_field_effects(self):
        scale = float(self.manifest["field"].get("world_to_screen_scale", 3.0))
        tiles = self.tile_view
        # screen pixels per world unit, and the world -> screen mapping of the scene being shown
        # (a tile scene has its own camera)
        pixels = tiles.camera.zoom if tiles is not None else scale * self.field_camera.zoom
        to_screen = self._field_screen_xy
        for effect in self.field_effects.vfx:
            asset = self.game.project.assets.resolve(effect.asset_id)
            meta = asset.meta()
            frames = meta["clips"]["play"]["frames"]
            fw, fh = meta["frame_size"]
            sheet = self.load_image(asset.source.uri)
            columns = max(1, sheet.get_width() // fw)
            index = frames[FieldEffects.keyframe(effect, len(frames))]
            if effect.entity_id is not None:
                entity = self.game.scene.get_entity(effect.entity_id)
                if entity is None:
                    continue
                t = entity.get(Transform)
                ax, ay = t.x, t.y
            else:
                ax, ay = effect.x, effect.y
            x, y, w, h = vfx_rect(
                effect.placement, ax, ay, FIELD_BODY_HEIGHT, fw / scale, fh / scale
            )
            sx, sy = to_screen(x, y)
            size = (max(1, round(w * pixels)), max(1, round(h * pixels)))
            image = self.pg.transform.scale(
                sheet.subsurface(((index % columns) * fw, (index // columns) * fh, fw, fh)), size
            )
            if effect.placement["opacity"] < 1.0:
                image.set_alpha(int(effect.placement["opacity"] * 255))
            flags = self.pg.BLEND_RGB_ADD if effect.placement["blend"] == "add" else 0
            self.screen.blit(
                image, (round(sx - size[0] / 2), round(sy - size[1] / 2)), special_flags=flags
            )
        systems = [p.system for p in self.field_effects.all_particles()]
        if systems:
            with self.profiler.section("vfx"):
                self.particles_drawn = self.particle_drawer.draw(
                    self.screen,
                    systems,
                    to_screen,
                    pixels,
                    image=self.particle_image,
                )
        self.world_done("field")
        alpha = self.field_effects.fade_alpha
        if alpha > 0:
            shade = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
            shade.fill((*self.field_effects.fade_color, int(alpha * 255)))
            self.screen.blit(shade, (0, 0))
        if self.game.cutscene_active:  # letterbox while a cutscene runs
            bar = int(self.height * 0.09)
            self.pg.draw.rect(self.screen, (0, 0, 0), (0, 0, self.width, bar))
            self.pg.draw.rect(self.screen, (0, 0, 0), (0, self.height - bar, self.width, bar))
            if self.game.cutscene_skippable:
                self.text(
                    "Esc: skip",
                    self.width - 130,
                    self.height - bar + 8,
                    size=18,
                    color=(190, 200, 215),
                )

    @property
    def tile_view(self):
        """The tile-map scene view (D22 A10) when the current scene is bound to a TileMap2D,
        else None."""
        from asteria.runtime.tile_scene_view import TileSceneView

        scene = self.game.scene
        # whether a scene is a tile scene is looked up once per scene, not per entity per frame
        known = self.__dict__.get("_tile_scene")
        if known is None or known[0] is not scene:
            known = self._tile_scene = (scene, TileSceneView.available(scene))
        if not known[1]:
            return None
        view = getattr(self, "_tile_view", None)
        if view is None:
            view = self._tile_view = TileSceneView(
                self.game, self.resource_root, self.width, self.height, self.pg
            )
        elif view.scene_id != scene.id:
            view.load()
        return view

    def _field_screen_xy(self, world_x, world_y):
        view = self.tile_view
        if view is not None:
            return view.world_to_screen(world_x, world_y)
        return self.field_camera.world_to_screen(world_x, world_y)

    def _player_frame(self, facing, moving):
        sheet = self.load_image(self.manifest["field"]["player_sheet"])
        fw, fh = self.manifest["field"]["player_frame_size"]
        row = walking_row_index(facing)
        col = walking_pattern_index(self._field_step) if moving else 1
        return sheet.subsurface((col * fw, row * fh, fw, fh))

    def _interaction_candidate(self):
        try:
            return self.game.interaction.query.nearest(
                self.game.scene, self.game.player, self.game.facing
            )
        except Exception:
            return None

    def _normal_image(self, image_path):
        """The normal map for an image, from its canonical asset's ``material.normal_asset_id`` (or
        None)."""
        cache = self.__dict__.setdefault("_normal_images", {})
        if image_path not in cache:
            normal = None
            for asset in self.project.assets.snapshot():
                if asset.source.uri != image_path:
                    continue
                normal_id = dict(asset.meta().get("material") or {}).get("normal_asset_id")
                if normal_id:
                    try:
                        normal = self.load_image(self.project.assets.resolve(normal_id).source.uri)
                    except KeyError:
                        normal = None
                break
            cache[image_path] = normal
        return cache[image_path]

    def _begin_normals(self):
        """Prepare a flat normal layer when last frame's environment lit the world on the GPU."""
        if self.gpu is None or not getattr(self, "_lit_last_frame", False):
            self._normal_layer_active = False
            return
        if getattr(self, "_normal_layer", None) is None or self._normal_layer.get_size() != (
            self.width,
            self.height,
        ):
            self._normal_layer = self.pg.Surface((self.width, self.height), 0, 32)
        self._normal_layer.fill((128, 128, 255))
        self._normal_layer_active = True

    def _blit_normal(self, image_path, source_rect, size, position):
        """Draw the normal-map frame matching a world sprite blit (same source rect, size and
        place)."""
        if not getattr(self, "_normal_layer_active", False):
            return
        normal = self._normal_image(image_path)
        if normal is None:
            return
        frame = normal.subsurface(source_rect) if source_rect is not None else normal
        if frame.get_size() != tuple(size):
            frame = self.pg.transform.scale(frame, tuple(size))
        self._normal_layer.blit(frame, position)

    def _blit_with_trail(self, entity, image, position):
        """Blit a field sprite; with MotionTrail2D, fading echoes of earlier positions go behind it
        (VFX-03)."""
        from asteria.presentation.motion_fx import EchoSettings, MotionEchoes
        from asteria.runtime.environment2d import MotionTrail2DComponent

        trail = entity.try_get(MotionTrail2DComponent)
        if trail is not None and trail.enabled:
            echoes = self.__dict__.setdefault("_field_echoes", MotionEchoes())
            settings = EchoSettings.of(
                trail.kind,
                interval=trail.interval,
                count=trail.count,
                fade=trail.fade,
                lifetime=trail.lifetime,
            )
            echo = echoes.get(entity.id, settings)
            t = entity.get(Transform)
            last = self.__dict__.setdefault("_trail_last_xy", {}).get(entity.id)
            moving = last is not None and (abs(t.x - last[0]) + abs(t.y - last[1])) > 1e-3
            self._trail_last_xy[entity.id] = (t.x, t.y)
            for ghost_image, ghost_position, opacity in (
                (img, pos, a) for (img, pos), a in echo.ghosts(self._clock_seconds)
            ):
                ghost = ghost_image.copy()
                ghost.set_alpha(int(200 * opacity))
                self.screen.blit(ghost, ghost_position)
            echo.record(
                self._clock_seconds,
                (image, position),
                moving=moving or not trail.only_while_moving,
            )
        self.screen.blit(image, position)

    def _field_composition(self, image_path):
        """CharacterComposition of the canonical sprite-sheet asset whose image is ``image_path``
        (CMP-01)."""
        cache = self.__dict__.setdefault("_field_compositions", {})
        if image_path not in cache:
            from asteria.presentation.character_composition import CharacterComposition

            composition = None
            for asset in self.project.assets.snapshot():
                if asset.source.uri == image_path and asset.kind == "sprite_sheet":
                    composition = CharacterComposition.from_meta(asset.meta())
                    break
            cache[image_path] = composition
        return cache[image_path]

    def _composition_parts(self, image_path, frame_index, clip, frame_size, render_size, position):
        """``(behind, front)`` lists of ``(surface, position)`` for a field sprite's layers and
        attachments."""
        composition = self._field_composition(image_path)
        if composition is None:
            return (), ()
        scale = render_size[0] / frame_size[0]
        pivot = (
            position[0] + render_size[0] / 2,
            position[1] + render_size[1],
        )  # feet: bottom centre
        behind, front = [], []
        for part in composition.parts(clip, frame_index):
            try:
                asset = self.project.assets.resolve(part.asset_id)
            except KeyError:
                continue
            meta = asset.meta()
            fw, fh = meta.get("frame_size", frame_size)
            sheet = self.load_image(asset.source.uri)
            columns = max(1, sheet.get_width() // fw)
            index = part.frame_index % max(1, columns * max(1, sheet.get_height() // fh))
            image = sheet.subsurface(((index % columns) * fw, (index // columns) * fh, fw, fh))
            size = (
                max(1, round(fw * part.scale_x * scale)),
                max(1, round(fh * part.scale_y * scale)),
            )
            image = self.pg.transform.scale(image, size)
            if part.rotation_deg:
                image = self.pg.transform.rotate(image, -part.rotation_deg)
            if part.opacity < 1.0:
                image.set_alpha(int(part.opacity * 255))
            if part.kind == "layer":
                x, y = position[0] + part.x * scale, position[1] + part.y * scale
            else:
                x, y = pivot[0] + part.x * scale, pivot[1] + part.y * scale
            (behind if part.behind else front).append((image, (round(x), round(y))))
        return behind, front

    def _prune_field_echoes(self):
        echoes = self.__dict__.get("_field_echoes")
        if echoes is None:
            return
        alive = {e.id for e in self.game.scene.entities() if e.enabled}
        echoes.prune(alive)  # entity removed / hidden / another scene: its echoes go too

    def _draw_field(self, moving=False):
        self._begin_normals()
        self._prune_field_echoes()
        zoom = self.field_camera.zoom
        settings = self.game.combat_scene
        tiles = self.tile_view
        if tiles is not None:
            hud = self.action_hud if self.game.action_scene else None
            tiles.draw(self.screen, flash=hud.flash if hud is not None else ())
            self._draw_field_overlays()
            return
        if (
            settings is not None and settings.background_color
        ):  # a block-out level: a flat colour, no field image
            color = settings.background_color.lstrip("#")
            self.screen.fill(tuple(int(color[i : i + 2], 16) for i in (0, 2, 4)))
        else:
            bg = self.load_image(self.manifest["field"]["background"])
            bx, by, bw, bh = self.field_camera.background_rect()
            self.screen.blit(
                self.pg.transform.smoothscale(bg, (round(bw), round(bh))), (round(bx), round(by))
            )

        sprites = self.manifest["field"].get("entity_sprites", {})
        from asteria.runtime.field_ai import FieldAIComponent, VisibleEncounterComponent

        for entity in self.game.scene.entities():
            if not entity.enabled:
                continue  # hidden / relocated NPCs (WLD-02) and disabled entities are not drawn
            spec = sprites.get(entity.name)
            if (
                spec is None
                and entity is not self.game.player
                and entity.has(Transform)
                and (entity.has(FieldAIComponent) or entity.has(VisibleEncounterComponent))
            ):
                # Field enemies without a manifest sprite still need to be visible.
                et = entity.get(Transform)
                ex, ey = self._field_screen_xy(et.x, et.y)
                self.pg.draw.circle(self.screen, (200, 70, 80), (int(ex), int(ey)), int(14 * zoom))
                self.pg.draw.circle(
                    self.screen, (255, 230, 230), (int(ex), int(ey)), int(14 * zoom), 2
                )
                continue
            if spec is None or entity is self.game.player:
                continue
            et = entity.get(Transform)
            ex, ey = self._field_screen_xy(et.x, et.y)
            w, h = (v * zoom for v in spec.get("size", (96, 112)))
            image = self.pg.transform.scale(self.load_image(spec["sprite"]), (int(w), int(h)))
            position = (int(ex - w / 2), int(ey - h + 12 * zoom))
            self._blit_with_trail(entity, image, position)
            self._blit_normal(spec["sprite"], None, (int(w), int(h)), position)

        pt = self.game.player.get(Transform)
        px, py = self._field_screen_xy(pt.x, pt.y)
        pf = self._player_frame(self.game.facing, moving)
        render_w, render_h = field_player_render_size(
            pf.get_size(), self.manifest["field"].get("player_render_width", 64) * zoom
        )
        pf = self.pg.transform.scale(pf, (render_w, render_h))
        position = (int(px - render_w / 2), int(py - render_h + 10 * zoom))
        sheet_path = self.manifest["field"]["player_sheet"]
        fw, fh = self.manifest["field"]["player_frame_size"]
        sheet_columns = max(1, self.load_image(sheet_path).get_width() // fw)
        frame_index = walking_row_index(self.game.facing) * sheet_columns + (
            walking_pattern_index(self._field_step) if moving else 1
        )
        clip = f"{'walk' if moving else 'idle'}_{self.game.facing}"
        behind, front = self._composition_parts(
            sheet_path, frame_index, clip, (fw, fh), (render_w, render_h), position
        )
        for image, at in behind:
            self.screen.blit(image, at)
        self._blit_with_trail(self.game.player, pf, position)
        for image, at in front:
            self.screen.blit(image, at)
        if (
            getattr(self, "_normal_layer_active", False)
            and self._normal_image(sheet_path) is not None
        ):
            fw, fh = self.manifest["field"]["player_frame_size"]
            row = walking_row_index(self.game.facing)
            col = walking_pattern_index(self._field_step) if moving else 1
            self._blit_normal(
                sheet_path, (col * fw, row * fh, fw, fh), (render_w, render_h), position
            )
        self._draw_field_overlays()

    def _draw_field_overlays(self):
        """Everything drawn over the field's world: HUD, effects, popups, dialogue, help."""
        if self.game.action_scene:
            self.action_hud.draw_world(self)
        self._draw_field_effects()
        self._draw_popups()
        if self.game.cutscene_active:
            self._draw_dialogue()
            return
        if self.game.action_scene:
            self.action_hud.draw_overlay(self)
            if self.message and self.pg.time.get_ticks() < self.message_until:
                self.text(
                    self.message, self.width / 2, 92, size=22, color=(175, 235, 255), center=True
                )
            self._draw_dialogue()
            return

        self.panel((18, self.height - 92, self.width - 36, 72))
        self.text("Field Test", 34, self.height - 82, size=24, color=(255, 220, 124))
        self.text(
            "Move: WASD / Arrows   C: Build   Q: Quests   E: Interact   F5: Save   Esc: Pause",
            34,
            self.height - 52,
            size=19,
        )
        candidate = self._interaction_candidate()
        if candidate is not None and not self.game.event_busy:
            self.text(
                f"E  Interact — {candidate.entity.name}",
                self.width / 2,
                55,
                size=26,
                color=(255, 226, 129),
                center=True,
            )
        if self.message and self.pg.time.get_ticks() < self.message_until:
            self.text(
                self.message, self.width / 2, 92, size=22, color=(175, 235, 255), center=True
            )
        self._draw_dialogue()

    # -- popups (CMP-03: generic animated text above field characters) ----------------------------
    POPUP_COLORS = {"item": (170, 240, 170), "warning": (255, 170, 150), "info": (230, 232, 240)}

    def _update_popups(self, dt):
        from asteria.presentation.animated_text import (
            AnimatedTextRuntime,
            AnimatedTextSpec,
            TextKey,
            TextTransform,
        )

        if getattr(self, "popups", None) is None:
            self.popups, self._popup_serial = AnimatedTextRuntime(), 0
        for notice in self.game.drain_notices():
            self._popup_serial += 1
            rise = TextTransform(y=-34.0, opacity=0.0, scale=1.0)
            spec = AnimatedTextSpec(
                notice["text"],
                duration_ms=notice["duration_ms"],
                space="world",
                anchor_id=notice["entity"] or "player",
                keys=(
                    TextKey(0.0, TextTransform(y=0.0, opacity=0.0, scale=0.8)),
                    TextKey(0.15, TextTransform(y=-8.0, opacity=1.0, scale=1.0)),
                    TextKey(0.7, TextTransform(y=-22.0, opacity=1.0)),
                    TextKey(1.0, rise),
                ),
                metadata={"kind": notice["kind"]},
            )
            self.popups.spawn(f"popup.{self._popup_serial}", spec)
        self.popup_frame = self.popups.update(dt * 1000.0)

    def _popup_anchor(self, anchor_id):
        if anchor_id == "player":
            entity = self.game.player
        else:
            entity = next(
                (
                    e
                    for e in self.game.scene.entities()
                    if e.name == anchor_id or e.id == anchor_id
                ),
                None,
            )
        transform = entity.get(Transform) if entity is not None else None
        if transform is None:
            return None
        x, y = self._field_screen_xy(transform.x, transform.y)
        return x, y - 48 * self.field_camera.zoom  # above the head

    def _draw_popups(self):
        from asteria.presentation.text_render_integration import AnimatedTextRenderComposer

        resolved = getattr(self, "popup_frame", ())
        if not resolved:
            return
        composer = AnimatedTextRenderComposer(anchor_resolver=self._popup_anchor)
        packets = []
        for item in resolved:
            try:
                packets.extend(composer.compose((item,)))
            except ValueError:
                continue  # the anchor left the scene
        font = self.pg.font.Font(None, 30)
        for packet in packets:
            color = self.POPUP_COLORS.get(packet.metadata.get("kind"), self.POPUP_COLORS["info"])
            image = font.render(packet.text, True, color)
            if packet.scale != 1.0:
                size = (
                    max(1, round(image.get_width() * packet.scale)),
                    max(1, round(image.get_height() * packet.scale)),
                )
                image = self.pg.transform.smoothscale(image, size)
            shadow = font.render(packet.text, True, (10, 12, 20))
            shadow.set_alpha(round(160 * packet.opacity))
            image.set_alpha(round(255 * packet.opacity))
            at = (
                round(packet.x - image.get_width() / 2),
                round(packet.y - image.get_height() / 2),
            )
            self.screen.blit(shadow, (at[0] + 2, at[1] + 2))
            self.screen.blit(image, at)

    def _draw_dialogue(self):
        request = self.game.pending_dialogue
        if request is None:
            return
        self.panel(
            (60, self.height - 230, self.width - 120, 130),
            fill=(10, 14, 24, 235),
            border=(240, 201, 93),
        )
        line = getattr(request, "line", None)
        if line is not None:
            if line.speaker:
                self.text(line.speaker, 84, self.height - 218, size=24, color=(255, 220, 124))
            self.text(line.text, 84, self.height - 184, size=22)
            self.text(
                "Enter / E: continue",
                self.width - 250,
                self.height - 128,
                size=18,
                color=(170, 210, 240),
            )
            return
        self.text(
            request.prompt or "Choose", 84, self.height - 218, size=22, color=(255, 220, 124)
        )
        for i, choice in enumerate(request.choices[:9], 1):
            self.text(
                f"{i}. {choice.text}",
                84 + ((i - 1) % 3) * 270,
                self.height - 184 + ((i - 1) // 3) * 26,
                size=20,
            )

    def _dialogue_input(self, events):
        """Route keys to a waiting dialogue/choice. Returns True when one is open."""
        request = self.game.pending_dialogue
        if request is None:
            return False
        if getattr(request, "line", None) is not None:
            if self.input.just_pressed("confirm") or self.input.just_pressed("interact"):
                self.game.acknowledge_dialogue()
                self._sound(self.manifest.get("dialogue_confirm_sfx"))
            return True
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            if getattr(request, "choices", None) and self.pg.K_1 <= event.key <= self.pg.K_9:
                index = event.key - self.pg.K_1
                if index < len(request.choices):
                    self.game.choose(index)
                    break
        return True

    def _field_input(self, events, dt):
        if self.game.cutscene_active:
            if self.game.cutscene_skippable and self.input.just_pressed("cancel"):
                self.game.skip_cutscene()
                return False
            self._dialogue_input(events)
            return False
        if self._dialogue_input(events) or self.game.event_busy:
            self.game.set_field_input(None)
            return False
        if self.game.action_scene:
            return self._action_input(events)
        # Project input map: keyboard and gamepad (stick / d-pad) both drive movement.
        dx, dy = self.input.current.movement_vector()
        moving = bool(dx or dy)
        if moving:
            mag = max(1.0, (dx * dx + dy * dy) ** 0.5)
            speed = 36.0
            pt = self.game.player.get(Transform)
            blocked = CollisionWorld.from_scene(self.game.scene).blocking_query(
                exclude={self.game.player.id}
            )
            nx = max(-120.0, min(120.0, pt.x + dx / mag * speed * dt))
            if not blocked.collides_world_point(nx, pt.y):
                pt.x = nx
            ny = max(-52.0, min(52.0, pt.y + dy / mag * speed * dt))
            if not blocked.collides_world_point(pt.x, ny):
                pt.y = ny
            self.game.save.player_position = (pt.x, pt.y)
            if abs(dx) > abs(dy):
                self.game.set_player_facing("right" if dx > 0 else "left")
            else:
                self.game.set_player_facing("down" if dy > 0 else "up")
            self._field_step += 1

        if self.input.just_pressed("menu"):
            self._ui_mode = "build"
        if self.input.just_pressed("cancel"):
            self._pause_menu.index = 0
            self._ui_mode = "pause"
            return moving
        if any(e.type == self.pg.KEYDOWN and e.key == self.pg.K_i for e in events):
            self.open_status_menu(back="field")
            return moving
        if any(e.type == self.pg.KEYDOWN and e.key == self.pg.K_q for e in events):
            self._quest_return = "field"
            self._ui_mode = "quests"
            return moving
        # GameSessionRuntime interaction is edge-triggered. Emit release after press.
        if self.input.just_pressed("interact"):
            self.game.field_step({"interact": 1.0})
            if self.game.mode == "field":
                self.game.field_step({"interact": 0.0})
        return moving

    # -- action scenes (ASTERIA_SPEC §20; D22 A8) -------------------------------------------------
    @property
    def action_hud(self):
        hud = getattr(self, "_action_hud", None)
        if hud is None:
            from asteria.runtime.action_play import ActionHud

            hud = self._action_hud = ActionHud()
        return hud

    def _action_input(self, events):
        """Real-time control: the input actions drive the player's controller and abilities through
        the session."""
        self.game.prepare_action_player()
        self.game.set_field_input(dict(self.input.current.actions))
        if self.input.just_pressed("pickup"):
            self.game.loot.pick_up_nearest(self.game.scene, self.game.player)
        if self.input.just_pressed("bag"):
            from asteria.runtime.bag_screen import BagScreen

            self._bag_screen = BagScreen(self)
            self._ui_mode = "bag"
        if self.input.just_pressed("menu"):  # the skill tree (D22 A10)
            from asteria.runtime.skill_tree_screen import SkillTreeScreen

            self._skill_tree = SkillTreeScreen(self)
            self._ui_mode = "skills"
        if self.input.just_pressed("cancel"):
            self._pause_menu.index = 0
            self._ui_mode = "pause"
        if self.input.just_pressed("interact") and not self.input.just_pressed("jump"):
            self.game.field_step({"interact": 1.0})
            if self.game.mode == "field":
                self.game.field_step({"interact": 0.0})
        from asteria.runtime.character_control import CharacterController2DComponent

        controller = self.game.player.try_get(CharacterController2DComponent)
        moving = controller is not None and bool(controller.intent_x or controller.intent_y)
        if controller is not None:
            self.game.set_player_facing(controller.facing)
        if moving:
            self._field_step += 1
        return moving

    def _draw_title(self):
        bg = self.load_image(self.manifest["field"]["background"])
        self.screen.blit(self.pg.transform.smoothscale(bg, (self.width, self.height)), (0, 0))
        shade = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
        shade.fill((5, 8, 16, 150))
        self.screen.blit(shade, (0, 0))
        self.text("ASTERIA", self.width / 2, 120, size=64, color=(255, 220, 120), center=True)
        # the game's own name (manifest "subtitle"); the reference project keeps its old text
        subtitle = self.manifest.get("subtitle") or "Complex Reference RPG"
        self.text(subtitle, self.width / 2, 180, size=36, center=True)
        self.panel((280, 250, 400, 150))
        self.text("N   New Game", 330, 282, size=28)
        self.text("L   Load Game", 330, 330, size=28)
        from asteria.runtime.save_slots import SaveSlots

        used = sum(
            1
            for s in SaveSlots(self.resource_root / "saves", self.project).slots()
            if self._slot_exists(s)
        )
        self.text(
            f"{used} save(s) found" if used else "No saves yet",
            330,
            372,
            size=18,
            color=(170, 210, 240),
        )

    def _load_player_save(self):
        path = self.resource_root / "saves" / "playtest_autosave.asteria-save.json"
        if not path.exists():
            self.message = "No player save exists yet"
            self.message_until = self.pg.time.get_ticks() + 1800
            return False
        loaded = GameRuntimeSave.load_json(path, self.project)
        self.save = loaded
        self.game = GameSessionRuntime(self.project, loaded)
        self._victory = False
        self._defeat = False
        self._ui_mode = "field"
        self.message = "Loaded player save"
        self.message_until = self.pg.time.get_ticks() + 1800
        return True

    def _menu_actor_ids(self):
        return tuple(self.save.rpg_state.party_actor_ids)

    def _menu_actor(self):
        ids = self._menu_actor_ids()
        if not ids:
            return None
        self._menu_actor_index %= len(ids)
        return ids[self._menu_actor_index]

    def _current_weapon(self, actor_id):
        loadout = self.save.rpg_state.loadouts[actor_id]
        values = loadout.equipped("weapon")
        return values[0] if values else None

    def _draw_build_menu(self):
        self._draw_field(False)
        overlay = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
        overlay.fill((6, 9, 18, 210))
        self.screen.blit(overlay, (0, 0))
        actor_id = self._menu_actor()
        if actor_id is None:
            return
        db = self.project.rpg_database
        state = self.save.rpg_state.actor_progression[actor_id]
        ability = self.game._ability_state(actor_id)
        weapon = self._current_weapon(actor_id)
        allocation = self.save.rpg_state.progression_allocations[actor_id]
        self.panel((24, 22, 912, 496), fill=(11, 15, 25, 242))
        self.text("Character / Build Acceptance Menu", 44, 38, size=30, color=(255, 220, 120))
        self.text(f"Q/E Actor   C Close     Current: {actor_id}", 44, 76, size=19)
        self.text(
            f"Level {state.level}   EXP {int(state.experience)}   AP "
            f"{int(allocation.balance('ap'))}"
            f"   Ability Pts {int(state.points.get('ability_points', 0))}",
            44,
            106,
            size=20,
            color=(170, 220, 255),
        )
        classes = " + ".join(state.active_class_ids) or "—"
        self.text(f"1 Secondary Class: {classes}", 44, 148, size=20)
        self.text(f"3 Passives: {', '.join(ability.active_passives[:4]) or '—'}", 44, 178, size=20)
        self.text(
            f"4 Weapon: {weapon.equipment.display_name if weapon else '—'}", 44, 208, size=20
        )
        growth = (
            "—"
            if weapon is None or weapon.growth is None
            else ", ".join(f"{k}:{v}" for k, v in sorted(weapon.growth.ranks.items())) or "base"
        )
        self.text(f"5 Weapon Upgrade: {growth}", 44, 238, size=20)
        accessories = self.save.rpg_state.loadouts[actor_id].equipped("accessory")
        self.text(
            f"6 Accessories: {', '.join(x.equipment.display_name for x in accessories) or '—'}",
            44,
            268,
            size=20,
        )
        active = self.save.rpg_state.party_active_actor_ids
        self.text(f"7 Party / Formation: {', '.join(active)}", 44, 298, size=20)
        self.text("2 Skill Tree: allocate next available node", 44, 328, size=20)
        graph_id = (
            state.active_class_ids[-1] if state.active_class_ids else next(iter(db.classes))
        ) + "_tree"
        graph = db.progression_graphs.get(graph_id)
        if graph is not None:
            ox, oy = 485, 150
            self.text(graph.display_name, ox, 116, size=22, color=(255, 220, 120))
            if graph.node_positions:
                ranks = allocation.allocations.get(graph.graph_id, {})
                for node in graph.nodes:
                    x, y = graph.node_positions.get(node.node_id, (0, 0))
                    x = ox + x * 0.55
                    y = oy + y * 0.65
                    for req in node.prerequisites:
                        px, py = graph.node_positions.get(req.node_id, (0, 0))
                        px = ox + px * 0.55
                        py = oy + py * 0.65
                        self.pg.draw.line(
                            self.screen,
                            (100, 120, 155),
                            (int(px + 38), int(py + 12)),
                            (int(x + 38), int(y + 12)),
                            2,
                        )
                    rect = (int(x), int(y), 78, 25)
                    self.pg.draw.rect(
                        self.screen,
                        (45, 70, 60) if ranks.get(node.node_id, 0) else (40, 46, 62),
                        rect,
                        border_radius=4,
                    )
                    self.pg.draw.rect(self.screen, (190, 200, 225), rect, 1, border_radius=4)
                    self.text(
                        node.display_name.replace(graph.display_name.split()[0], "")[:10],
                        x + 4,
                        y + 5,
                        size=14,
                    )
            else:
                ranks = allocation.allocations.get(graph.graph_id, {})
                for i, node in enumerate(graph.nodes[:6]):
                    self.text(
                        ("[x] " if ranks.get(node.node_id, 0) else "[ ] ") + node.display_name,
                        ox,
                        155 + i * 38,
                        size=18,
                    )
        self.text(
            "All changes are Runtime State and are verified again after Save/Load.",
            44,
            480,
            size=18,
            color=(170, 210, 240),
        )

    def _cycle_secondary_class(self, actor_id):
        state = self.save.rpg_state.actor_progression[actor_id]
        current = state.active_class_ids[-1] if len(state.active_class_ids) > 1 else None
        choices = [x for x in state.unlocked_class_ids if x != state.active_class_ids[0]]
        if not choices:
            return
        idx = -1 if current not in choices else choices.index(current)
        self.game.set_secondary_class(actor_id, choices[(idx + 1) % len(choices)])

    def _allocate_next_tree_node(self, actor_id):
        state = self.save.rpg_state.actor_progression[actor_id]
        cls = state.active_class_ids[-1] if state.active_class_ids else None
        if not cls:
            return
        graph_id = f"{cls}_tree"
        allocation = self.save.rpg_state.progression_allocations[actor_id]
        graph = self.project.rpg_database.progression_graphs[graph_id]
        for node in graph.nodes:
            preview = allocation.preview_allocate(graph_id, node.node_id, 1)
            if preview.allowed:
                allocation.allocate(graph_id, node.node_id, 1)
                self.message = f"Learned {node.display_name}"
                self.message_until = self.pg.time.get_ticks() + 1400
                return
        self.message = "No affordable/unlocked node"
        self.message_until = self.pg.time.get_ticks() + 1400

    def _cycle_passive(self, actor_id):
        ids = sorted(self.project.rpg_database.passives)
        state = self.game._ability_state(actor_id)
        current = list(state.active_passives)
        candidate = next((x for x in ids if x not in current), ids[0] if ids else None)
        if candidate is None:
            return
        values = (current + [candidate])[-4:]
        self.game.set_passives(actor_id, values, capacity=4)

    def _cycle_weapon(self, actor_id):
        ids = sorted(
            k for k, v in self.project.rpg_database.equipment.items() if v.slot == "weapon"
        )
        current = self._current_weapon(actor_id)
        cur = None if current is None else current.equipment.equipment_id
        idx = -1 if cur not in ids else ids.index(cur)
        self.game.equip_definition(actor_id, ids[(idx + 1) % len(ids)], slot_id="weapon")

    def _upgrade_weapon(self, actor_id):
        item = self._current_weapon(actor_id)
        if item is None:
            return
        growth = item.ensure_growth(self.project.rpg_database.equipment_growth)
        for node in growth.definition.nodes:
            if growth.preview_unlock(node.node_id).allowed:
                growth.unlock(node.node_id)
                self.message = f"Weapon upgraded: {node.display_name}"
                self.message_until = self.pg.time.get_ticks() + 1400
                return
        self.message = "Weapon growth maxed or blocked"
        self.message_until = self.pg.time.get_ticks() + 1400

    def _cycle_accessory(self, actor_id):
        ids = sorted(
            k for k, v in self.project.rpg_database.equipment.items() if v.slot == "accessory"
        )
        loadout = self.save.rpg_state.loadouts[actor_id]
        if loadout.equipped("accessory"):
            loadout.unequip("accessory", 0)
        self.game.equip_definition(
            actor_id, ids[(self._menu_actor_index) % len(ids)], slot_id="accessory", replace=False
        )

    def _rotate_party(self):
        roster = list(self.save.rpg_state.party_actor_ids)
        if len(roster) <= 1:
            return
        rotated = roster[1:] + roster[:1]
        chosen = rotated[: min(6, len(rotated))]
        self.game.set_active_party(
            chosen, {actor_id: f"slot_{i + 1}" for i, actor_id in enumerate(chosen)}
        )

    def _build_menu_input(self, events):
        actor = self._menu_actor()
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            if event.key == self.pg.K_c:
                self._ui_mode = "field"
            elif event.key == self.pg.K_q:
                self._menu_actor_index -= 1
            elif event.key == self.pg.K_e:
                self._menu_actor_index += 1
            elif actor is not None and event.key == self.pg.K_1:
                self._cycle_secondary_class(actor)
            elif actor is not None and event.key == self.pg.K_2:
                self._allocate_next_tree_node(actor)
            elif actor is not None and event.key == self.pg.K_3:
                self._cycle_passive(actor)
            elif actor is not None and event.key == self.pg.K_4:
                self._cycle_weapon(actor)
            elif actor is not None and event.key == self.pg.K_5:
                self._upgrade_weapon(actor)
            elif actor is not None and event.key == self.pg.K_6:
                self._cycle_accessory(actor)
            elif event.key == self.pg.K_7:
                self._rotate_party()

    def _battle_actor(self):
        return None if self.game.battle is None else self._turn_actor

    def _advance_to_hero_turn(self):
        """Let the battle scheduler run enemy turns until a hero must act."""
        hero, log = self.game.run_enemy_turns()
        if log:
            member_id, outcome = log[-1]
            name = member_id.split(":", 1)[0].replace("_", " ").title()
            self._last_action_name = (
                f"Enemy AI: {outcome}" if isinstance(outcome, Exception) else f"{name} acts"
            )
        self._turn_actor = hero
        self._boost_level = 0
        if not self.game.active_hero_ids():
            self._defeat = True

    @property
    def battle_commands(self):
        """The player's battle command menu for the current game (skills, items, concoct, boost,
        targets)."""
        from .battle_commands import BattleCommands

        commands = getattr(self, "_battle_commands", None)
        if commands is None or commands.game is not self.game:
            labels = self.manifest.get("battle", {}).get("skills", {})
            style = self.manifest.get("battle", {}).get("command_style", "categories")
            commands = self._battle_commands = BattleCommands(
                self.game, labels=labels, style=style
            )
        return commands

    @property
    def _boost_level(self):
        commands = getattr(self, "_battle_commands", None)
        return commands.boost if commands is not None and commands.game is self.game else 0

    @_boost_level.setter
    def _boost_level(self, value):
        self.battle_commands.boost = int(value)

    def _skills_for_actor(self, actor_id):
        if actor_id is None:
            return []
        member = self.game.battle.member(actor_id)
        authored = self.manifest["battle"].get("skills", {})
        values = []
        for ability_id in authored:
            if ability_id in member.ability_ids:
                values.append((ability_id, authored[ability_id]))
            if len(values) >= 4:
                break
        # Ensure at least some menu entries if a custom save changed build.
        for ability_id in member.ability_ids:
            if ability_id not in {x[0] for x in values}:
                values.append((ability_id, {"label": ability_id.replace("_", " ").title()}))
            if len(values) >= 4:
                break
        return values[:4]

    def _enemy_layout(self, member_id):
        enemy_id = str(member_id).split(":", 1)[0]
        return self.manifest["battle"].get("enemy_layouts", {}).get(enemy_id)

    def _draw_battle(self):
        self._battle_presentation.draw()
        if self._capture_menu and self.game.mode == "battle":
            self._draw_capture_menu()

    def _presentation_busy(self):
        busy = getattr(self._battle_presentation, "busy", None)
        return bool(callable(busy) and busy())

    def _flush_victory_audio(self):
        pending_cues = getattr(self._battle_presentation, "audio_cues", ())
        if (
            getattr(self, "_victory_audio_pending", False)
            and not self._presentation_busy()
            and not pending_cues
        ):
            self._victory_audio_pending = False
            self.audio.stop_music(fade_out=0.3)
            self._sound(self.manifest["battle"].get("victory_jingle"))

    def _present_battle(self, dt):
        """Feed new canonical battle facts to the active presentation adapter and draw."""
        with self.profiler.section("update"):
            self._battle_presentation.consume(self.game.drain_battle_log())
        with self.profiler.section("animation"):
            self._battle_presentation.update(dt)
        with self.profiler.section("render"):
            self._battle_presentation.draw()
            self._draw_battle_extras()
        self._flush_victory_audio()

    def _draw_battle_extras(self):
        """Shield and weaknesses under each enemy, boost points under each hero (unless the
        party panel has them), the chosen boost level (runtime/battle_extras.py)."""
        from .battle_extras import draw_blocks, extras_layout

        game, adapter = self.game, self._battle_presentation
        box = getattr(adapter, "member_screen_box", None)
        if game.battle is None or box is None or self._victory or self._defeat:
            return
        pg, battle = self.pg, game.battle
        scale = getattr(getattr(adapter, "textures", None), "scale", 3.0)
        blocks = extras_layout(game, box, scale, self.width)
        draw_blocks(self, blocks, scale)
        self.battle_extras_blocks = blocks  # what was drawn (tests check it for overlaps)
        bp = game.rules.boost_resource_id if game.rules.boost_enabled else ""
        layout = getattr(getattr(adapter, "screen", None), "composer", None)
        panel_has_bp = (
            layout is not None and getattr(layout.layout, "party_hud", "") == "side_list"
        )
        for member in battle.members.values():
            if member.side != "heroes" or not battle.is_active(member):
                continue
            where = box(member.member_id)
            if where is None:
                continue
            x, _top, feet = where
            y = feet + 6
            if (
                bp
                and not panel_has_bp
                and battle.battle_resources.get(member.member_id, bp) is not None
            ):
                value = battle.battle_resources.current(member.member_id, bp)
                top = battle.battle_resources.get(member.member_id, bp).maximum
                for i in range(int(top)):
                    filled = i < value
                    centre = (round(x - (top - 1) * 5 + i * 10), round(y + 4))
                    pg.draw.circle(
                        self.screen, (255, 196, 70) if filled else (60, 66, 84), centre, 4
                    )
            states = member.subject.states
            names = []
            for active in states.active_states() if states is not None else ():
                definition = states.registry.get(active.state_id)
                shown = getattr(definition, "display_name", "") or active.state_id
                names.append(shown.replace("_", " "))
            if names and not panel_has_bp:  # the side panel shows them as chips
                label = " ".join(names)[:28]
                self.text(label, x, y + 20, size=15, color=(220, 180, 255), center=True)
        actor = self._battle_actor()
        commands = getattr(self, "_battle_commands", None)
        if actor is not None and commands is not None and commands.game is game:
            where = box(actor)
            if where is not None and commands.boost:
                self.text(
                    f"BOOST x{commands.boost + 1}",
                    where[0],
                    where[1] - 22,
                    size=22,
                    color=(255, 210, 90),
                    center=True,
                )
            if commands.message:
                self.text(
                    commands.message,
                    self.width / 2,
                    70,
                    size=20,
                    color=(255, 170, 150),
                    center=True,
                )

    def _use_skill(self, slot):
        actor = self._battle_actor()
        skills = self._skills_for_actor(actor)
        if actor is None or slot < 0 or slot >= len(skills):
            return
        ability_id, meta = skills[slot]
        boost = self._boost_level
        try:
            self.game.use_ability(actor, ability_id, boost_level=boost)
            self._last_action_name = f"{actor}: {meta.get('label', ability_id)} x{boost + 1}"
            self._boost_level = 0
            # Sound and VFX belong to the battle screen's choreography (motion sequence, or the
            # manifest skill's sfx / fx in the default cues), timed to the impact.
        except Exception as exc:
            self._last_action_name = f"Action failed: {exc}"
            return
        self._after_hero_action()

    def _after_hero_action(self):
        """End the hero's turn; finish the battle or run enemies until a hero acts."""
        self.game.end_turn()
        if not self.game.active_enemy_ids():
            try:
                self.game.finish_victory()
                self._victory_summary = []
                rewards = self.manifest.get("progression_rewards", {})
                for hero_id in self.save.rpg_state.party_active_actor_ids:
                    info = self.game.grant_actor_experience(
                        hero_id,
                        rewards.get("experience", 1600),
                        level_threshold=rewards.get("level_threshold", 1000),
                        ap_per_level=rewards.get("ap_per_level", 2),
                        ability_points_per_level=rewards.get("ability_points_per_level", 1),
                    )
                    self._victory_summary.append(
                        f"{hero_id}: Lv {info['old_level']}→{info['new_level']} "
                        f"+{info['levels_gained'] * 2:g} AP +{info['levels_gained']:g} ability pts"
                    )
                self._victory = True
                # The jingle waits for the presentation to finish showing the final blows.
                self._victory_audio_pending = (
                    True  # played by _present_battle once the screen is idle
                )
                self._last_action_name = "Victory — rewards + progression applied"
            except Exception as exc:
                self._last_action_name = f"Victory finalize failed: {exc}"
            return
        self._advance_to_hero_turn()

    @property
    def _COMMAND_KEYS(self):  # noqa: N802 - a key table
        pg = self.pg
        return {
            pg.K_UP: "up",
            pg.K_w: "up",
            pg.K_DOWN: "down",
            pg.K_s: "down",
            pg.K_LEFT: "left",
            pg.K_a: "left",
            pg.K_RIGHT: "right",
            pg.K_d: "right",
            pg.K_RETURN: "confirm",
            pg.K_SPACE: "confirm",
            pg.K_e: "confirm",
            pg.K_ESCAPE: "cancel",
            pg.K_BACKSPACE: "cancel",
            pg.K_TAB: "category",
            pg.K_q: "boost_down",
            pg.K_r: "boost_up",
        }

    def _battle_input(self, events):
        if self._victory:
            if self._presentation_busy():
                return  # the result is still being presented
            for event in events:
                if event.type == self.pg.KEYDOWN and event.key in (
                    self.pg.K_RETURN,
                    self.pg.K_e,
                    self.pg.K_SPACE,
                ):
                    self._victory = False
                    self.game.mode = "field"
                    self._last_action_name = ""
            return
        if self._defeat:
            return
        if self._capture_menu:
            self._capture_input(events)
            return
        busy = getattr(self._battle_presentation, "busy", None)
        if callable(busy) and busy():
            return  # the previous action's choreography is still playing
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            if event.key == self.pg.K_x and self._battle_actor() and self.game.capture_targets():
                self._capture_menu = True
            elif event.key == self.pg.K_b:
                actor = self._battle_actor()
                if actor:
                    self._boost_level = (self._boost_level + 1) % (
                        self.game.max_boost_level(actor) + 1
                    )
            elif event.key in self._COMMAND_KEYS:
                actor = self._battle_actor()
                commands = self.battle_commands
                if commands.press(self._COMMAND_KEYS[event.key], actor):
                    self._last_action_name = f"{actor} acts"
                    self._after_hero_action()
                    return
                if commands.message == "capture":
                    commands.message = ""
                    self._capture_menu = bool(self.game.capture_targets())
            elif event.key in (self.pg.K_1, self.pg.K_KP1):
                self._use_skill(0)
            elif event.key in (self.pg.K_2, self.pg.K_KP2):
                self._use_skill(1)
            elif event.key in (self.pg.K_3, self.pg.K_KP3):
                self._use_skill(2)
            elif event.key in (self.pg.K_4, self.pg.K_KP4):
                self._use_skill(3)

    # --- pause, quests, shop and game over (UI-02) --------------------------

    def _menu_step(self, cursor):
        if self.input.just_pressed("move_up"):
            cursor.move(-1)
        if self.input.just_pressed("move_down"):
            cursor.move(1)
        return self.input.just_pressed("confirm")

    def _restart_to_title(self):
        if self.project.game_start is not None:
            self.save = self.project.game_start.instantiate(self.project)
            self.game = GameSessionRuntime(self.project, self.save)
        self._victory = False
        self._defeat = False
        self._shop_screen = None
        self.audio.stop_music(fade_out=0.3)
        self._ui_mode = "title"

    # -- status menu (UI-01) ----------------------------------------------------------------------
    def open_status_menu(self, back="field"):
        from asteria.runtime.status_menu import StatusMenu

        self.status_menu = StatusMenu(self.game)
        self._status_back = back
        self._ui_mode = "status"

    def _status_input(self, events):
        menu = self.status_menu
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            if event.key in (self.pg.K_ESCAPE, self.pg.K_i):
                self._ui_mode = self._status_back
            elif event.key == self.pg.K_TAB:
                menu.next_tab(-1 if getattr(event, "mod", 0) & self.pg.KMOD_SHIFT else 1)
            elif event.key in (self.pg.K_q, self.pg.K_PAGEUP):
                menu.next_actor(-1)
            elif event.key in (self.pg.K_e, self.pg.K_PAGEDOWN):
                menu.next_actor(1)
            elif event.key in (self.pg.K_UP, self.pg.K_w):
                menu.move(-1)
            elif event.key in (self.pg.K_DOWN, self.pg.K_s):
                menu.move(1)
            elif event.key in (self.pg.K_RETURN, self.pg.K_SPACE):
                try:
                    menu.activate()
                except Exception as exc:  # noqa: BLE001 - shown to the player, the game keeps running
                    menu.message = str(exc)

    def _draw_status_menu(self):
        from asteria.runtime.status_menu import TABS

        self._draw_field(False)
        shade = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
        shade.fill((6, 9, 18, 215))
        self.screen.blit(shade, (0, 0))
        menu = self.status_menu
        self.panel((24, 22, self.width - 48, self.height - 44), fill=(11, 15, 25, 242))
        x = 44
        for tab in TABS:
            label = tab.title()
            active = tab == menu.tab
            self.text(label, x, 36, size=24, color=(255, 220, 120) if active else (150, 160, 180))
            x += 150
        actor = menu.actor_id or "—"
        name = getattr(self.project.rpg_database.actors.get(actor), "display_name", actor)
        self.text(f"Q / E  {name}", self.width - 330, 40, size=20, color=(170, 220, 255))
        rows = menu.rows()
        icons = menu.row_icons() if menu.tab in ("items", "equipment") else [""] * len(rows)
        label_x = 56 + (30 if any(icons) else 0)
        start = max(0, menu.row - 13)
        for i, (_kind, _key, label, detail) in enumerate(rows[start : start + 14]):
            y = 92 + i * 28
            selected = start + i == menu.row
            if selected:
                self.pg.draw.rect(
                    self.screen, (40, 52, 78), (40, y - 4, self.width - 80, 26), border_radius=4
                )
            self._draw_icon(icons[start + i], 56, y - 3)
            self.text(
                label, label_x, y, size=20, color=(255, 255, 255) if selected else (210, 215, 225)
            )
            self.text(detail, self.width - 420, y, size=20, color=(170, 210, 240))
        if not rows:
            self.text("Nothing here yet.", 56, 92, size=20, color=(150, 160, 180))
        hint = "Tab: next tab   Up/Down: choose   Enter: use / equip / unequip   Esc: back"
        self.text(hint, 44, self.height - 60, size=18, color=(170, 210, 240))
        if menu.message:
            self.text(menu.message, 44, self.height - 88, size=19, color=(255, 226, 129))

    def _pause_input(self):
        if self.input.just_pressed("cancel"):
            self._ui_mode = "field"
            return
        if not self._menu_step(self._pause_menu):
            return
        choice = self._pause_menu.selected
        if choice == "resume":
            self._ui_mode = "field"
        elif choice == "status":
            self.open_status_menu(back="pause")
        elif choice == "pets":
            from asteria.runtime.pets_screen import PetsScreen

            self._pets_screen = PetsScreen(self)
            self._ui_mode = "pets"
        elif choice == "quests":
            self._quest_return = "pause"
            self._ui_mode = "quests"
        elif choice == "crafting":
            self._open_crafting("", back="pause")
        elif choice in ("achievements", "bestiary"):
            self._list_scroll = 0
            self._ui_mode = choice
        elif choice == "settings":
            self._settings_menu.index = 0
            self._ui_mode = "settings"
        elif choice == "save":
            self.open_slots("save", back="pause")
        elif choice == "load":
            self.open_slots("load", back="pause")
        elif choice == "title":
            self._restart_to_title()
        elif choice == "quit":
            self.running = False

    def _game_over_input(self):
        if not self._menu_step(self._game_over_menu):
            return
        if self._game_over_menu.selected == "load":
            self._load_player_save()
        else:
            self._restart_to_title()

    def _quests_input(self):
        if self.input.just_pressed("cancel") or self.input.just_pressed("confirm"):
            self._ui_mode = self._quest_return

    def _shop_input(self):
        screen = self._shop_screen
        if screen is None or screen.shop is None or self.input.just_pressed("cancel"):
            if screen is not None:
                screen.close()
            self._shop_screen = None
            self._ui_mode = "field"
            return
        if self.input.just_pressed("move_up"):
            screen.move(-1)
        if self.input.just_pressed("move_down"):
            screen.move(1)
        if self.input.just_pressed("move_left") or self.input.just_pressed("move_right"):
            screen.switch_tab()
        if self.input.just_pressed("confirm") and screen.confirm() is not None:
            self._sound(self.manifest.get("dialogue_confirm_sfx"))

    def _open_crafting(self, station, back="field"):
        self._crafting_screen = CraftingScreen(self.game, station)
        self._crafting_back = back
        self._ui_mode = "crafting"

    def _crafting_input(self):
        screen = self._crafting_screen
        if screen is None or self.input.just_pressed("cancel"):
            if screen is not None:
                screen.close()
            self._crafting_screen = None
            self._ui_mode = getattr(self, "_crafting_back", "field")
            return
        if self.input.just_pressed("move_up"):
            screen.move(-1)
        if self.input.just_pressed("move_down"):
            screen.move(1)
        if self.input.just_pressed("confirm") and screen.confirm() is not None:
            self._sound(self.manifest.get("dialogue_confirm_sfx"))

    def _list_screen_input(self):
        if self.input.just_pressed("cancel") or self.input.just_pressed("confirm"):
            self._ui_mode = "pause"
            return
        if self.input.just_pressed("move_down"):
            self._list_scroll += 1
        if self.input.just_pressed("move_up"):
            self._list_scroll = max(0, self._list_scroll - 1)

    def _settings_input(self):
        cursor = self._settings_menu
        if self.input.just_pressed("cancel"):
            self.settings.save(self._settings_path())
            self._ui_mode = "pause"
            return
        if self.input.just_pressed("move_up"):
            cursor.move(-1)
        if self.input.just_pressed("move_down"):
            cursor.move(1)
        key = cursor.selected
        if key == "back":
            if self.input.just_pressed("confirm"):
                self.settings.save(self._settings_path())
                self._ui_mode = "pause"
            return
        if key == "controls":
            if self.input.just_pressed("confirm"):
                from asteria.runtime.input_rebinding import ControlsMenu

                self.controls_menu = ControlsMenu(
                    self.project.input_map, self.settings.input_overrides
                )
                self._ui_mode = "controls"
            return
        delta = (1 if self.input.just_pressed("move_right") else 0) - (
            1 if self.input.just_pressed("move_left") else 0
        )
        if self.input.just_pressed("confirm") and key == "show_battle_log":
            delta = 1
        if delta:
            self.settings.adjust(key, delta)
            self.settings.apply(self.audio)

    # -- save slots (ENG-21) ----------------------------------------------------------------------
    def _slot_exists(self, slot):
        from asteria.runtime.save_slots import SaveSlots

        return SaveSlots(self.resource_root / "saves", self.project).path(slot).exists()

    def open_slots(self, mode, back="pause"):
        from asteria.runtime.save_slots import SaveSlots, SlotMenu

        self.slot_menu = SlotMenu(SaveSlots(self.resource_root / "saves", self.project), mode)
        self._slots_back = back
        self._ui_mode = "slots"

    def _slots_input(self, events):
        menu = self.slot_menu
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            if event.key == self.pg.K_ESCAPE:
                self._ui_mode = self._slots_back
            elif event.key in (self.pg.K_UP, self.pg.K_w):
                menu.move(-1)
            elif event.key in (self.pg.K_DOWN, self.pg.K_s):
                menu.move(1)
            elif event.key in (self.pg.K_DELETE, self.pg.K_BACKSPACE):
                menu.delete()
            elif event.key in (self.pg.K_RETURN, self.pg.K_SPACE):
                outcome, value = menu.activate(self.game)
                if outcome == "loaded":
                    self.save = value
                    self.game = GameSessionRuntime(self.project, value)
                    self._victory = self._defeat = False
                    self._ui_mode = "field"
                    self.message = f"Loaded slot {menu.slot}"
                    self.message_until = self.pg.time.get_ticks() + 1800
                elif outcome == "saved":
                    self.message = menu.message
                    self.message_until = self.pg.time.get_ticks() + 1800

    def _draw_slots(self):
        self._draw_backdrop()
        menu = self.slot_menu
        self.panel((100, 60, self.width - 200, self.height - 120))
        title = "Save Game" if menu.mode == "save" else "Load Game"
        self.text(title, self.width / 2, 76, size=32, color=(255, 220, 124), center=True)
        for i, info in enumerate(menu.rows()):
            y = 140 + i * 64
            selected = i == menu.row
            if selected:
                self.pg.draw.rect(
                    self.screen, (40, 52, 78), (120, y - 8, self.width - 240, 54), border_radius=6
                )
            name = "Autosave (F5)" if info.slot == "autosave" else f"Slot {info.slot}"
            self.text(
                name, 140, y, size=24, color=(255, 226, 129) if selected else (235, 238, 245)
            )
            self.text(info.summary, 140, y + 24, size=18, color=(170, 210, 240))
        hint = menu.message or "Enter: choose   Delete: erase   Esc: back"
        self.text(
            hint, self.width / 2, self.height - 96, size=19, color=(255, 226, 129), center=True
        )

    # -- controls / rebinding (ENG-15) ------------------------------------------------------------
    def _controls_input(self, events):
        from asteria.runtime.input_map import InputBinding

        menu = self.controls_menu
        for event in events:
            if menu.capturing is not None:
                if event.type == self.pg.KEYDOWN and event.key == self.pg.K_ESCAPE:
                    menu.cancel_capture()
                elif event.type == self.pg.KEYDOWN:
                    menu.capture(InputBinding("key", self.pg.key.name(event.key)))
                    self._apply_controls()
                elif event.type == getattr(self.pg, "JOYBUTTONDOWN", -1):
                    menu.capture(InputBinding("gamepad_button", str(event.button)))
                    self._apply_controls()
                continue
            if event.type != self.pg.KEYDOWN:
                continue
            if event.key == self.pg.K_ESCAPE:
                self.settings.save(self._settings_path())
                self._ui_mode = "settings"
            elif event.key in (self.pg.K_UP, self.pg.K_w):
                menu.move(-1)
            elif event.key in (self.pg.K_DOWN, self.pg.K_s):
                menu.move(1)
            elif event.key in (self.pg.K_RETURN, self.pg.K_SPACE):
                menu.select()
                if menu.capturing is None:  # reset all
                    self._apply_controls()
            elif event.key in (self.pg.K_BACKSPACE, self.pg.K_DELETE):
                menu.reset(menu.rows()[menu.row][0])
                self._apply_controls()

    def _apply_controls(self):
        from asteria.runtime.input_rebinding import effective_input_map

        self.settings.input_overrides = dict(self.controls_menu.overrides)
        self.input = InputActionTracker(
            effective_input_map(self.project.input_map, self.settings.input_overrides)
        )
        self.settings.save(self._settings_path())

    def _draw_controls(self):
        self._draw_backdrop()
        menu = self.controls_menu
        self.panel((60, 30, self.width - 120, self.height - 60))
        self.text("Controls", self.width / 2, 44, size=32, color=(255, 220, 124), center=True)
        for i, (action, bindings) in enumerate(menu.rows()):
            y = 92 + i * 30
            selected = i == menu.row
            color = (255, 226, 129) if selected else (235, 238, 245)
            self.text(("> " if selected else "   ") + action, 90, y, size=21, color=color)
            self.text(bindings, self.width / 2, y, size=21, color=(170, 210, 240))
        hint = menu.message or "Enter: rebind   Backspace: reset action   Esc: save and back"
        self.text(
            hint, self.width / 2, self.height - 58, size=19, color=(255, 226, 129), center=True
        )

    def _draw_crafting(self):
        screen = self._crafting_screen
        self._draw_backdrop()
        if screen is None:
            return
        self.panel((60, 40, self.width - 120, self.height - 80))
        title = "Crafting" + (
            f" — {screen.station.replace('_', ' ').title()}" if screen.station else ""
        )
        self.text(title, 90, 54, size=30, color=(255, 220, 124))
        rows = screen.rows()
        if not rows:
            self.text("No known recipes here.", 90, 110, size=22, color=(170, 210, 240))
        y = 104
        for i, row in enumerate(rows):
            if y > self.height - 150:
                break
            selected = i == screen.index
            color = (
                (255, 226, 129)
                if selected
                else (235, 238, 245)
                if row.craftable
                else (130, 135, 150)
            )
            self.text(
                ("> " if selected else "   ") + f"{row.name}  ->  {row.outputs}",
                90,
                y,
                size=22,
                color=color,
            )
            y += 26
            materials = "   ".join(f"{name} {have}/{need}" for name, need, have in row.materials)
            self.text(
                materials,
                120,
                y,
                size=17,
                color=(170, 210, 240) if row.craftable else (200, 130, 130),
            )
            y += 30
        hidden = screen.undiscovered()
        if hidden:
            self.text(
                f"??? {hidden} recipe(s) not yet discovered",
                90,
                self.height - 128,
                size=18,
                color=(150, 155, 175),
            )
        if screen.message:
            self.text(screen.message, 90, self.height - 100, size=20, color=(255, 220, 124))
        self.text(
            "Up/Down: select   Enter: craft   Esc: back",
            90,
            self.height - 72,
            size=18,
            color=(170, 210, 240),
        )

    def _draw_list_screen(self, kind):
        self._draw_backdrop()
        self.panel((60, 40, self.width - 120, self.height - 80))
        if kind == "achievements":
            rows = achievement_rows(self.game)
            done = sum(1 for r in rows if r[2])
            self.text(
                f"Achievements  {done}/{len(rows)}",
                self.width / 2,
                56,
                size=30,
                color=(255, 220, 124),
                center=True,
            )
            lines = [
                (
                    (("[x] " if unlocked else "[ ] ") + name),
                    description,
                    (130, 220, 150) if unlocked else (150, 155, 175),
                )
                for name, description, unlocked in rows
            ]
        else:
            rows = bestiary_rows(self.game)
            seen = sum(1 for r in rows if r[1])
            self.text(
                f"Bestiary  {seen}/{len(rows)} seen",
                self.width / 2,
                56,
                size=30,
                color=(255, 220, 124),
                center=True,
            )
            lines = [
                (
                    name,
                    (
                        ""
                        if not s
                        else f"seen {s}   defeated {d}   captured {c}"
                        + (f"   {', '.join(tags)}" if tags else "")
                    ),
                    (235, 238, 245) if s else (150, 155, 175),
                )
                for name, s, d, c, tags in rows
            ]
        if not lines:
            self.text("Nothing here yet.", 90, 110, size=22, color=(170, 210, 240))
        self._list_scroll = min(self._list_scroll, max(0, len(lines) - 1))
        y = 104
        for title, detail, color in lines[self._list_scroll :]:
            if y > self.height - 110:
                break
            self.text(title, 90, y, size=22, color=color)
            y += 24
            if detail:
                self.text(detail, 120, y, size=17, color=(170, 210, 240))
                y += 24
            y += 6
        self.text(
            "Up/Down: scroll   Enter / Esc: back",
            self.width - 360,
            self.height - 72,
            size=18,
            color=(170, 210, 240),
        )

    def _draw_settings(self):
        self._draw_backdrop()
        cursor = self._settings_menu
        x, y = self.width / 2 - 220, self.height / 2 - 130
        self.panel((x, y, 440, 260))
        self.text("Settings", self.width / 2, y + 18, size=34, color=(255, 220, 124), center=True)
        for i, (key, label) in enumerate(cursor.options):
            selected = i == cursor.index
            color = (255, 226, 129) if selected else (235, 238, 245)
            self.text(
                ("> " if selected else "   ") + label,
                x + 40,
                y + 76 + i * 38,
                size=24,
                color=color,
            )
            value = self.settings.value_text(key)
            if value:
                self.text(
                    f"< {value} >" if selected else value,
                    x + 300,
                    y + 76 + i * 38,
                    size=24,
                    color=color,
                )
        self.text(
            "Left/Right: change   Esc: save and back",
            self.width / 2,
            y + 236,
            size=16,
            color=(170, 210, 240),
            center=True,
        )

    def _draw_backdrop(self, base="field"):
        if base == "battle":
            self._battle_presentation.draw()  # the canonical battle screen as it was left
        else:
            self._draw_field(False)
        shade = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
        shade.fill((5, 8, 16, 170))
        self.screen.blit(shade, (0, 0))

    def _draw_overlay_menu(self, title, cursor, base="field"):
        self._draw_backdrop(base)
        height = 90 + 34 * len(cursor.options)
        x, y = self.width / 2 - 170, self.height / 2 - height / 2
        self.panel((x, y, 340, height))
        self.text(title, self.width / 2, y + 18, size=34, color=(255, 220, 124), center=True)
        for i, (_, label) in enumerate(cursor.options):
            selected = i == cursor.index
            self.text(
                ("> " if selected else "   ") + label,
                x + 40,
                y + 70 + i * 34,
                size=24,
                color=(255, 226, 129) if selected else (235, 238, 245),
            )
        if self.message and self.pg.time.get_ticks() < self.message_until:
            self.text(
                self.message,
                self.width / 2,
                y + height + 14,
                size=20,
                color=(175, 235, 255),
                center=True,
            )

    def _draw_quests(self):
        self._draw_backdrop()
        self.panel((60, 40, self.width - 120, self.height - 80))
        self.text("Quest Log", self.width / 2, 56, size=32, color=(255, 220, 124), center=True)
        rows = quest_rows(self.game)
        if not rows:
            self.text("No quests yet.", 90, 110, size=22, color=(170, 210, 240))
        y = 104
        colors = {
            "active": (235, 238, 245),
            "completed": (130, 220, 150),
            "failed": (230, 120, 120),
        }
        for row in rows:
            if y > self.height - 110:
                break
            self.text(f"{row.name}  [{row.status}]", 90, y, size=24, color=colors[row.status])
            y += 30
            for description, value, required, done in row.objectives:
                self.text(
                    f"{'[x]' if done else '[ ]'} {description}  {value}/{required}",
                    120,
                    y,
                    size=19,
                    color=(170, 210, 240),
                )
                y += 24
            y += 8
        self.text(
            "Enter / Esc: back", self.width - 260, self.height - 72, size=18, color=(170, 210, 240)
        )

    def _draw_shop(self):
        screen = self._shop_screen
        self._draw_backdrop()
        if screen is None or screen.shop is None:
            return
        self.panel((60, 40, self.width - 120, self.height - 80))
        self.text(screen.shop.display_name, 90, 54, size=30, color=(255, 220, 124))
        for i, tab in enumerate(("buy", "sell")):
            self.text(
                tab.title(),
                self.width - 300 + i * 100,
                60,
                size=24,
                color=(255, 226, 129) if screen.tab == tab else (130, 140, 160),
            )
        self.text("Item", 90, 104, size=19, color=(170, 210, 240))
        self.text("Price", 420, 104, size=19, color=(170, 210, 240))
        self.text("Stock", 640, 104, size=19, color=(170, 210, 240))
        self.text("Owned", 740, 104, size=19, color=(170, 210, 240))
        from .menu_icons import record_icon_id

        rows = screen.rows()
        icons = [record_icon_id(self.project, "item", r.item_id) for r in rows]
        name_x = 90 + (30 if any(icons) else 0)
        for i, row in enumerate(rows):
            y = 134 + i * 30
            if y > self.height - 130:
                break
            color = (
                (255, 226, 129)
                if i == screen.index
                else (235, 238, 245)
                if row.available
                else (120, 125, 140)
            )
            self.text("> " if i == screen.index else "", 72, y, size=22, color=color)
            self._draw_icon(icons[i], 90, y - 2)
            self.text(row.name, name_x, y, size=22, color=color)
            self.text(row.price, 420, y, size=22, color=color)
            self.text(row.stock, 640, y, size=22, color=color)
            self.text(str(row.owned), 740, y, size=22, color=color)
        self.text(screen.wallet(), 90, self.height - 100, size=20, color=(175, 235, 255))
        if screen.message:
            self.text(
                screen.message, self.width / 2, self.height - 100, size=20, color=(255, 220, 124)
            )
        self.text(
            "Up/Down: select   Left/Right: buy/sell   Enter: confirm   Esc: leave",
            90,
            self.height - 72,
            size=18,
            color=(170, 210, 240),
        )

    # --- capture (RPG-08) ----------------------------------------------------

    def _capture_input(self, events):
        targets = self.game.capture_targets()
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            if event.key in (self.pg.K_ESCAPE, self.pg.K_x, self.pg.K_BACKSPACE):
                self._capture_menu = False
                return
            if self.pg.K_1 <= event.key <= self.pg.K_9 and event.key - self.pg.K_1 < len(targets):
                self._attempt_capture(targets[event.key - self.pg.K_1][0])
                return

    def _attempt_capture(self, target_id):
        actor = self._battle_actor()
        self._capture_menu = False
        if actor is None:
            return False
        name = target_id.split(":", 1)[0].replace("_", " ").title()
        try:
            captured = self.game.attempt_capture(actor, target_id)
        except Exception as exc:
            self._last_action_name = f"Capture failed: {exc}"
            return False
        self._last_action_name = f"Captured {name}!" if captured else f"{name} broke free"
        self._sound(self.manifest.get("dialogue_confirm_sfx") if captured else None)
        self._after_hero_action()
        return captured

    def _draw_capture_menu(self):
        targets = self.game.capture_targets()
        height = 70 + 30 * max(1, len(targets))
        self.panel((300, 190, 360, height), fill=(12, 18, 28, 240), border=(130, 200, 255))
        self.text("Capture", 480, 200, size=28, color=(175, 235, 255), center=True)
        inventory = self.save.rpg_state.inventory
        for i, (member_id, chance, item_id) in enumerate(targets, 1):
            name = member_id.split(":", 1)[0].replace("_", " ").title()
            need = f"  (uses {item_id}: {inventory.count(item_id)})" if item_id else ""
            self.text(f"{i}. {name}  {chance * 100:.0f}%{need}", 320, 236 + (i - 1) * 30, size=20)
        self.text(
            "Esc: cancel", 480, 190 + height - 24, size=16, color=(170, 210, 240), center=True
        )

    def save_playtest(self):
        self.game.sync_world_state()
        out = self.resource_root / "saves" / "playtest_autosave.asteria-save.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        self.save.save_json(out)
        self.message = f"Saved: {out.name}"
        self.message_until = self.pg.time.get_ticks() + 1800
        self._last_action_name = self.message
        return out

    def tick(self, target_fps=60):
        """Wait for the next frame of a steady ``target_fps`` schedule; returns dt in seconds
        (capped at 0.05). Deadlines advance by exactly one period (sleep, then a short spin), so
        frames do not drift the way whole-millisecond waits plus a vsynced present do (A11)."""
        import time

        period = 1.0 / max(1, int(target_fps))
        now = time.perf_counter()
        deadline = getattr(self, "_frame_deadline", None)
        if deadline is None or now - deadline > period:  # first frame, or far behind: restart
            deadline = now
        else:
            if deadline - now > 0.002:
                time.sleep(deadline - now - 0.0015)
            while time.perf_counter() < deadline:
                pass
            now = time.perf_counter()
        self._frame_deadline = deadline + period
        last = getattr(self, "_frame_last", None)
        self._frame_last = now
        return min(now - last, 0.05) if last is not None else period

    def run(self, target_fps=60, max_frames=None, *, profile_path=None):
        self.open()
        if profile_path is not None:
            self.enable_profiling(target_fps=target_fps)
        frames = 0
        try:
            while self.running:
                dt = self.tick(target_fps)
                self.profiler.begin_frame()
                self._frame(self.pg.event.get(), dt)
                with self.profiler.section("present"):
                    self.present()
                self._sample_counters()
                self.profiler.end_frame()
                frames += 1
                if max_frames is not None and frames >= max_frames:
                    break
        finally:
            if profile_path is not None:
                self.profiler.write(profile_path)
                self.profiler.close()
            self.close()
        return 0

    def _sound(self, asset_id):
        if asset_id:
            self.audio.play_effect(asset_id)

    def _music(self, asset_id, fade=0.5):
        if asset_id:
            self.audio.play_music(asset_id, fade_in=fade)

    def _frame(self, events, dt):
        """Process one frame of input, event programs and drawing (no flip)."""
        self._frame_dt = float(dt)
        self._clock_seconds += float(dt)
        self._update_resource_scope()
        self._update_popups(float(dt))
        if self.debug_server is not None:
            self.debug_server.poll()
        with self.profiler.section("input"):
            self.input_source.handle_events(events)
            self.input.update(self.input_source.raw_state())
        while self.game.presentation_requests:
            request = self.game.presentation_requests.pop(0)
            if request.name in CAMERA_COMMANDS:
                try:
                    self.field_camera.handle(request, self.game.scene)
                except (FieldCameraError, ValueError) as exc:
                    self.game.event_errors.append(exc)
            elif request.name in FIELD_EFFECT_COMMANDS:
                try:
                    self.field_effects.handle(
                        request, self.game.scene, self.game.project.assets, player=self.game.player
                    )
                except (FieldEffectError, ValueError) as exc:
                    self.game.event_errors.append(exc)
            else:
                self.audio.handle_world_request(request)
        for cue in getattr(self._battle_presentation, "audio_cues", ()):
            self._sound(dict(cue.payload).get("asset_id"))
        if hasattr(self._battle_presentation, "audio_cues"):
            self._battle_presentation.audio_cues.clear()
        for event in events:
            if event.type == self.pg.QUIT:
                self.running = False
            elif event.type == self.pg.KEYDOWN and event.key == self.pg.K_ESCAPE:
                if self._ui_mode == "build":
                    self._ui_mode = "field"
                elif self._ui_mode == "title":
                    self.running = False
            elif (
                event.type == self.pg.KEYDOWN
                and event.key == self.pg.K_F5
                and self._ui_mode != "title"
            ):
                self.save_playtest()

        if self._ui_mode == "title":
            for event in events:
                if event.type == self.pg.KEYDOWN and event.key == self.pg.K_n:
                    self._ui_mode = "field"
                elif event.type == self.pg.KEYDOWN and event.key == self.pg.K_l:
                    self.open_slots("load", back="title")
            self._draw_title()
        elif self._ui_mode == "build":
            self._build_menu_input(events)
            self._draw_build_menu()
        elif self._ui_mode == "pause":
            self._pause_input()
            self._draw_overlay_menu("Paused", self._pause_menu)
        elif self._ui_mode == "slots":
            self._slots_input(events)
            self._draw_slots()
        elif self._ui_mode == "controls":
            self._controls_input(events)
            self._draw_controls()
        elif self._ui_mode == "status":
            self._status_input(events)
            self._draw_status_menu()
        elif self._ui_mode == "quests":
            self._quests_input()
            self._draw_quests()
        elif self._ui_mode == "shop":
            self._shop_input()
            self._draw_shop()
        elif self._ui_mode == "crafting":
            self._crafting_input()
            self._draw_crafting()
        elif self._ui_mode in ("achievements", "bestiary"):
            self._list_screen_input()
            self._draw_list_screen(self._ui_mode)
        elif self._ui_mode == "settings":
            self._settings_input()
            self._draw_settings()
        elif self._ui_mode == "bag":
            self._bag_screen.handle(dt)
            if self._bag_screen.closed:
                self._ui_mode = "field"
            else:
                self._bag_screen.draw()
        elif self._ui_mode == "pets":
            self._pets_screen.handle(dt, events)
            if self._pets_screen.closed:
                self._ui_mode = "pause"
            else:
                self._pets_screen.draw()
        elif self._ui_mode == "skills":
            self._skill_tree.handle(dt)
            if self._skill_tree.closed:
                self._ui_mode = "field"
            else:
                self._skill_tree.draw()
        elif self._ui_mode == "game_over":
            self._game_over_input()
            self._draw_overlay_menu("Game Over", self._game_over_menu, base="battle")
        elif self.game.mode == "battle" or self._victory:
            if self.game.mode == "battle":
                with self.profiler.section("events"):
                    self.game.update_events(dt)  # battle events (EVT-03)
            if not (
                self._dialogue_input(events)
                or (self.game.mode == "battle" and self.game.event_busy)
            ):
                self._battle_input(events)
            self._present_battle(dt)
            self._draw_dialogue()
            if self._defeat:
                self._game_over_menu.index = 0
                self._ui_mode = "game_over"
                self.audio.stop_music(fade_out=0.5)
        elif self.game.mode == "field":
            moving = self._field_input(events, dt)
            with self.profiler.section("events"):
                self.game.update_events(dt)
            if self._ui_mode == "field" and self.game.open_shop_id and not self.game.event_busy:
                self._shop_screen = ShopScreen(self.game)
                self._ui_mode = "shop"
            if (
                self._ui_mode == "field"
                and self.game.open_crafting_station is not None
                and not self.game.event_busy
            ):
                self._open_crafting(self.game.open_crafting_station, back="field")
            if self.game.mode == "field" and self._ui_mode == "field":
                with self.profiler.section("update"):
                    self.game.field_update(dt)
                if self.game.action_scene:
                    self.action_hud.observe(self.game, dt)
                    if getattr(self.game, "player_defeated", False):
                        self.game.player_defeated = False
                        self._game_over_menu.index = 0
                        self._ui_mode = "game_over"
            pt = self.game.player.get(Transform)
            last = getattr(self, "_last_player_xy", None)
            velocity = (
                ((pt.x - last[0]) / dt, (pt.y - last[1]) / dt)
                if last is not None and dt > 0
                else None
            )
            self._last_player_xy = (pt.x, pt.y)
            self.field_camera.update(dt, (pt.x, pt.y), velocity)
            tiles = self.tile_view
            if tiles is not None:
                tiles.update(dt)
            self.field_effects.sync_emitters(
                self.game.scene, self.game.project.assets
            )  # VFX-01 emitters
            self.field_effects.update(dt)
            if self.game.mode == "battle":
                self._turn_actor = None
                self._battle_presentation.begin()
                self._music(self.manifest["battle"].get("bgm"))
                self._advance_to_hero_turn()
                self._present_battle(dt)
            else:
                self._music(self.manifest["field"].get("bgm"))
                self._draw_field(moving)


def run_playable_test_runtime(
    project,
    resource_root,
    *,
    runtime_save=None,
    save_path=None,
    width=960,
    height=540,
    target_fps=60,
    max_frames=None,
    profile_path=None,
    battle_presentation=None,
    debug_port=None,
    debug_token=None,
    spawn=None,
    backend=None,
):
    resource_root = Path(resource_root)
    if runtime_save is None:
        if save_path is not None:
            runtime_save = GameRuntimeSave.load_json(save_path, project)
        else:
            raise ValueError(
                "playable test content requires Project Game Start runtime state or an explicit "
                "Player Save"
            )
    runtime = PlayableTestRuntime(
        project, runtime_save, resource_root, width=width, height=height, backend=backend
    )
    if battle_presentation:
        runtime.manifest.setdefault("battle", {})["presentation"] = {
            **runtime.manifest.get("battle", {}).get("presentation", {}),
            "adapter": battle_presentation,
        }
        runtime._battle_presentation = create_battle_presentation_adapter(runtime)
    if spawn is not None:
        runtime.game.set_player_position(float(spawn[0]), float(spawn[1]))
        runtime._ui_mode = "field"  # play-test from the chosen point skips the title screen
    if debug_port is not None:
        runtime.enable_debugger(port=debug_port, token=debug_token)
        print(f"asteria-debug: listening on 127.0.0.1:{runtime.debug_server.port}", flush=True)
    return runtime.run(target_fps, max_frames, profile_path=profile_path)
