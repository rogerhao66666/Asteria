from __future__ import annotations

import json
import math
from pathlib import Path

from asteria.core import Transform
from asteria.presentation.motion_fx import EchoSettings, MotionEchoes
from asteria.rpg.built_in_text import translated
from asteria.runtime.audio_mixer import AudioMixer
from asteria.runtime.battle_commands import BattleCommands
from asteria.runtime.battle_extras import draw_blocks, extras_layout
from asteria.runtime.battle_presentation_adapters import create_battle_presentation_adapter
from asteria.runtime.battle_visuals import vfx_rect
from asteria.runtime.collision import CollisionWorld
from asteria.runtime.field_camera import (
    CAMERA_COMMANDS,
    FieldCameraError,
    FieldViewCamera,
    scene_camera_follow,
)
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
    text_keys,
)
from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.game_session import GameSessionRuntime
from asteria.runtime.input_map import InputActionTracker
from asteria.runtime.particle_draw import ParticleDrawer
from asteria.runtime.profiler import NullProfiler, RuntimeProfiler
from asteria.runtime.skeleton_component import SkeletonSceneRuntime

WALK_ROW_BY_FACING = {"down": 0, "left": 1, "right": 2, "up": 3}
WALK_PATTERN_SEQUENCE = (0, 1, 2, 1)
# enemy tag kinds the bestiary groups by (``weak.fire``): the word drawn for each is a built-in
# text (``bestiary.tag.<kind>``); any other kind shows as written
BESTIARY_TAG_KINDS = ("weak", "resist", "immune", "absorb", "reflect", "trait")


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
        from asteria.runtime.multiplayer_preview import (
            MultiplayerPreviewBridge,
            load_runtime_multiplayer_profile,
        )

        self.multiplayer_profile_error = ""
        try:
            self.multiplayer_profile = load_runtime_multiplayer_profile(self.resource_root)
        except ValueError as exc:
            self.multiplayer_profile = None
            self.multiplayer_profile_error = str(exc)
        self.multiplayer_bridge = (
            MultiplayerPreviewBridge(self.multiplayer_profile)
            if self.multiplayer_profile is not None
            else None
        )
        self._authoritative_project_mode = bool(
            self.multiplayer_profile
            and str(self.multiplayer_profile.get("adapter_factory", "")).endswith(
                "build_project_adapter"
            )
        )
        self._multiplayer_error = self.multiplayer_profile_error
        self._network_origin = None
        self._network_revision = -1
        self._network_scale = float(self.manifest.get("field", {}).get("network_world_scale", 16))
        self._network_predictor = None
        self._network_prediction_sequence = 0
        self._network_input_prediction_sequences = {}
        self._network_prediction_reconciled_revision = -1
        self.game = GameSessionRuntime(project, runtime_save)
        self._skeleton_scene_runtime = SkeletonSceneRuntime()
        self._skeleton_sheet_cache = {}
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
        self._portrait_cache = {}  # (portrait id, width, height) -> fitted dialogue portrait
        # Resource lifetime (ENG-10): images first loaded during a battle belong to
        # the "battle" scope and are released when play returns to the field.
        self._image_scope = {}
        self.released_images = 0
        # Battle pictures decoded ahead in the field (image_preloader.py). None: only in a real
        # window (off-screen runs and tests skip it); True / False: always / never.
        self.preload_battle_images = None
        self._preloader = None
        self._preload_frames = 0
        self._preload_scene = ""
        self.debug_server = None
        self._ui_mode = "title"
        self._menu_actor_index = 0
        self._turn_actor = None
        self._victory_summary = []
        self._fonts = {}
        self._glyphs = {}  # (font, char) -> the font can draw it
        self._cjk_fonts = {}
        self._battle_presentation = create_battle_presentation_adapter(self)
        self.profiler = NullProfiler()
        self._drawing = False
        self._wrap_draw_methods()
        options = list(PAUSE_OPTIONS)
        if getattr(self.project.rpg_database, "pet_species", None):  # a game with pets
            options.insert(2, ("pets", "Pets"))
        db = self.project.rpg_database
        extras = []
        if self.game.message_settings is not None and self.game.message_settings.backlog_limit:
            extras.append(("backlog", "Message Log"))
        if db.ability_loadout_rules:
            extras.append(("skill_slots", "Skill Slots"))
        if db.music_tracks:
            extras.append(("music", "Music Room"))
        if db.credits_pages:
            extras.append(("credits", "Credits"))
        for entry in sorted(db.menu_entries.values(), key=lambda e: (e.order, e.entry_id)):
            extras.append((f"entry:{entry.entry_id}", entry.label))
        for entry in extras:  # in order, before Settings
            options.insert(next(i for i, o in enumerate(options) if o[0] == "settings"), entry)
        icons = {
            f"entry:{e.entry_id}": e.icon_id for e in db.menu_entries.values() if e.icon_id
        }  # project-defined entries may carry an icon
        built_in = [o for o in options if not o[0].startswith("entry:")]
        keys = text_keys("pause", built_in)
        # the project's own entries keep their label unless a table words it (pause.entry.<id>)
        keys.update({f"entry:{e}": f"pause.entry.{e}" for e in db.menu_entries})
        self._pause_menu = MenuCursor(options, icons, keys=keys)
        self._extra_screen = None
        self._pets_screen = None
        self._game_over_menu = MenuCursor(
            GAME_OVER_OPTIONS, keys=text_keys("game_over", GAME_OVER_OPTIONS)
        )
        self._shop_screen = None
        self._quest_return = "field"
        self._capture_menu = False
        self._crafting_screen = None
        self._list_scroll = 0
        self.settings = GameSettings.load(self._settings_path())
        settings_options = list(GameSettings.OPTIONS)
        if len(self.game.localizer.locales()) > 1:  # a translated game: the player picks one
            settings_options.insert(-2, ("language", "Language"))
        self._settings_menu = MenuCursor(
            settings_options, keys=text_keys("settings", settings_options)
        )

    def path(self, rel):
        return self.resource_root / str(rel)

    def load_image(self, rel):
        rel = str(rel)
        if rel not in self._loaded:
            with self.profiler.section("asset_loading"):
                ready = None if self._preloader is None else self._preloader.take(rel)
                if ready is None:
                    ready = self.pg.image.load(self.path(rel)).convert_alpha()
                self._loaded[rel] = ready
            in_battle = self.game.mode == "battle" or self._victory or self._defeat
            self._image_scope[rel] = "battle" if in_battle else "field"
        return self._loaded[rel]

    def skin_image(self, asset_id):
        """A skin picture (nine-patch source) at its own size, or ``None`` when it is missing."""
        from .menu_icons import icon_source

        source = icon_source(self.project, asset_id)
        if source is None:
            return None
        uri, region = source
        try:
            image = self.load_image(uri)
            if region is not None:
                image = image.subsurface(self.pg.Rect(region).clip(image.get_rect()))
        except Exception as exc:  # noqa: BLE001 - pygame.error / a missing file: plain colours
            if type(exc).__name__ not in ("error", "FileNotFoundError"):
                raise
            return None
        return image

    def skin_font(self, asset_id):
        """The file path of the skin's font asset, or ``None`` (the built-in font)."""
        from .menu_icons import icon_source

        if not asset_id:
            return None
        source = icon_source(self.project, asset_id) or (
            (str(asset_id), None) if str(asset_id).lower().endswith((".ttf", ".otf")) else None
        )
        if source is None:
            return None
        try:
            path = Path(self.path(source[0]))
        except Exception:  # noqa: BLE001 - a font that is not there: the built-in one
            return None
        return str(path) if path.is_file() else None

    def icon_image(self, icon_id, size=24):
        """The menu icon ``icon_id`` (see ``menu_icons``) scaled to fit ``size`` pixels, or
        None."""
        from .menu_icons import forged_surface, icon_source

        cache = self._icon_cache
        key = (str(icon_id or ""), int(size))
        if key in cache:
            return cache[key]
        icon = None
        built_in = forged_surface(icon_id, int(size))
        if built_in is not None:  # a code-drawn icon of the engine's own library
            cache[key] = built_in
            return built_in
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

    PRELOAD_REFRESH_FRAMES = 120  # field frames between looks at what the next fight may show

    def _preload_battle_images(self):
        """Decode the next fight's pictures in the background while the player is in the field
        (a battle used to load them all in its first frame). The manifest's
        ``battle.preload_mb`` caps the memory held (0: off)."""
        preloader = self._preloader
        if preloader is None:
            budget = float(self.manifest.get("battle", {}).get("preload_mb", 64))
            upcoming = getattr(self._battle_presentation, "upcoming_images", None)
            enabled = self.preload_battle_images
            if enabled is None:
                driver = self.pg.display.get_driver() if self.pg.display.get_init() else "dummy"
                enabled = driver not in ("dummy", "offscreen")
            if budget <= 0 or upcoming is None or not enabled:
                return
            from asteria.runtime.image_preloader import ImagePreloader

            preloader = self._preloader = ImagePreloader(
                self.pg, self.path, self._loaded, budget_bytes=int(budget * (1 << 20))
            )
            self._preload_frames = 0
        if self._preload_frames <= 0 or self.game.scene.id != self._preload_scene:
            self._preload_scene = self.game.scene.id
            self._preload_frames = self.PRELOAD_REFRESH_FRAMES
            preloader.want(self._battle_presentation.upcoming_images())
        self._preload_frames -= 1
        preloader.step()

    def release_resource_scope(self, scope):
        """Drop every cached image owned by ``scope``; returns how many were released."""
        self._icon_cache.clear()  # icons are cut from cached images: rebuild them on demand
        self._portrait_cache.clear()
        names = [rel for rel, owner in self._image_scope.items() if owner == scope]
        for rel in names:
            image = self._loaded.pop(rel, None)
            self._image_scope.pop(rel, None)
            if image is not None and self._preloader is not None:
                self._preloader.keep(rel, image)  # ready for the next fight
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
        self._network_legacy_attack_injected = False
        if (
            self.multiplayer_profile is not None
            and not self._authoritative_project_mode
            and "attack" not in input_map.actions()
        ):
            from asteria.runtime.input_map import InputBinding

            input_map.set_bindings("attack", [InputBinding("key", "f")])
            self._network_legacy_attack_injected = True
        from asteria.runtime.action_play import missing_action_bindings

        for action, bindings in missing_action_bindings(
            input_map
        ).items():  # action-scene controls (not saved)
            input_map.set_bindings(action, bindings)
        self.input = InputActionTracker(input_map)
        from asteria.platform.pygame_audio import open_audio_device

        self.audio = AudioMixer(open_audio_device(self.pg), self._audio_path)
        self.settings.apply(self.audio)
        if self.multiplayer_bridge is not None:
            from asteria.core import Transform

            transform = self.game.player.get(Transform)
            self._network_origin = (float(transform.x), float(transform.y))
            if self.multiplayer_bridge.connect():
                if (
                    self.multiplayer_bridge.state.get("schema")
                    == "asteria.multiplayer.project_state"
                ):
                    self._enable_authoritative_project_controls()
                self.multiplayer_bridge.send_input(
                    {"move_x": 0.0, "move_y": 0.0, "attack": False}, force=True
                )
                self.message = (
                    self.game.tr(
                        "coop.connected_project",
                        "Co-op connected · WASD / arrows · J attack · F pickup",
                    )
                    if self._authoritative_project_mode
                    else self.game.tr(
                        "coop.connected",
                        "Co-op connected · move with WASD / arrows · attack with F",
                    )
                )
                self.message_until = self.pg.time.get_ticks() + 6000
            else:
                self._multiplayer_error = self.multiplayer_bridge.error
                self.message = self.game.tr(
                    "coop.offline", "Co-op offline: {error}", error=self.multiplayer_bridge.error
                )
                self.message_until = self.pg.time.get_ticks() + 8000
        self._warm_start()
        return self

    # modules the field imports on first use; open() imports them before the first frame
    FIELD_MODULES = (
        "asteria.presentation.animated_text",
        "asteria.presentation.text_render_integration",
        "asteria.runtime.behavior_tree",
        "asteria.runtime.entity_actions",
        "asteria.runtime.hud_bottom",
        "asteria.runtime.image_preloader",
        "asteria.runtime.map_rules_field",
        "asteria.runtime.menu_icons",
        "asteria.runtime.preview",
        "asteria.runtime.projectiles",
        "asteria.runtime.tile_scene_view",
        "asteria.runtime.tilemap_field",
    )

    def _warm_start(self):
        """Load now what the first field frame would load mid-frame (70-90 ms): the kernel set
        (numpy, the native library), chosen on first use, and the field's modules."""
        import importlib

        from asteria import kernels

        kernels.active()
        for name in self.FIELD_MODULES:
            importlib.import_module(name)

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
        battle_weather = self.game.battle_weather()
        if battle_weather is not None:  # the battle's own weather replaces the map's
            env.weather, env.weather_intensity, env.weather_wind = battle_weather
            env.weather_max_particles = env.weather_max_particles or 900
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
        if self._preloader is not None:
            self._preloader.close()
            self._preloader = None
        if self.multiplayer_bridge is not None:
            self.multiplayer_bridge.close()
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

    def text_width(self, value, size=20):
        """The width in pixels of ``value`` drawn at ``size`` (the face ``text`` uses)."""
        return self.text_size(value, size)[0]

    def text_size(self, value, size=20):
        """``(width, height)`` in pixels of ``value`` drawn at ``size``, in the face ``text``
        draws it with (a system CJK face for Chinese, Japanese or Korean)."""
        from asteria.platform.pygame_battle_ui import cjk_size, font_for_text

        f = self._menu_font(size)
        return font_for_text(self.pg, f, value, self._cjk_fonts, cjk_size(f)).size(str(value))

    def text(self, value, x, y, *, size=20, color=(245, 245, 250), center=False, anchor=None):
        """Draw text at ``(x, y)``: top-left by default, ``center=True`` centres it, ``anchor`` is
        any pygame rect attribute (``"midleft"``, ``"midright"``, ``"bottomright"``...) placed at
        the point - so a label can sit on the same horizontal line as a bar. Text drawn in the
        CJK face (Chinese...) is placed where the built-in face's line would be, centred on the
        same height as its capitals, so menu cursors and mixed rows stay level."""
        f = self._fonts.get(int(size))
        if f is None:
            f = self._fonts[int(size)] = self.pg.font.Font(None, int(size))
        from asteria.platform.pygame_battle_ui import (
            cjk_size,
            font_for_text,
            glyph_shift,
            renderable_text,
        )

        # rendered text is cached: HUD labels and damage numbers repeat every frame
        key = (str(value), int(size), tuple(color))
        cache = self.__dict__.setdefault("_text_cache", {})
        entry = cache.get(key)
        if entry is None:
            if len(cache) > 2048:
                cache.clear()
            text_font = font_for_text(self.pg, f, value, self._cjk_fonts, cjk_size(f))
            surf = text_font.render(
                renderable_text(self.pg, text_font, value, self._glyphs), True, color
            )
            shift = None  # the built-in face: placed as it is
            if text_font is not f:
                metrics = text_font.metrics("中")
                ink = text_font.get_ascent() - metrics[0][3] if metrics and metrics[0] else 0
                level = glyph_shift(self.pg, f, text_font, self._glyphs)
                shift = (f.get_height(), level, ink)  # line, move to level, top of the ink
            entry = cache[key] = (surf, shift)
        surf, shift = entry
        rect = surf.get_rect()
        if shift is not None:  # where the built-in face's line would go, then level with it
            rect.height = shift[0]
        if anchor:
            setattr(rect, anchor, (int(x), int(y)))
        elif center:
            rect.center = (int(x), int(y))
        else:
            rect.topleft = (int(x), int(y))
        if shift is not None:
            top = rect.y + shift[1]
            if anchor or center:  # a title or hint keeps inside its line (no cursor beside it)
                top = max(top, rect.y - shift[2])
            rect = self.pg.Rect(rect.x, top, *surf.get_size())
        self.screen.blit(surf, rect)
        return rect

    def _menu_font(self, size):
        f = self._fonts.get(int(size))
        if f is None:
            f = self._fonts[int(size)] = self.pg.font.Font(None, int(size))
        return f

    def menu_mark_room(self, size):
        """Room a menu row keeps before its label for the cursor (pixels): every row's label
        starts at the same place, the selected one or not."""
        return round(int(size) * 0.75)

    def menu_mark(self, x, y, *, size=20, color=(255, 226, 129)):
        """A menu cursor at ``x``, centred on the capitals of ``size`` text drawn from ``y``
        (its top): a drawn arrow, so it sits level with the row whatever the font (a ``>``
        sat low beside the letters)."""
        font = self._menu_font(size)
        metrics = font.metrics("H")
        if metrics and metrics[0] is not None:
            _, _, low, high, _ = metrics[0]
            centre, height = y + font.get_ascent() - (high + low) / 2, max(4, high - low)
        else:
            centre, height = y + font.get_height() / 2, max(4, font.get_height() // 2)
        width = max(3, round(height * 0.7))
        half = height / 2
        points = ((x, centre - half), (x + width, centre), (x, centre + half))
        self.pg.draw.polygon(self.screen, color, [(round(a), round(b)) for a, b in points])

    def menu_row(self, label, x, y, *, selected, size=20, color=(245, 245, 250)):
        """One menu row: the cursor when ``selected``, the label after the cursor's room."""
        if selected:
            self.menu_mark(x, y, size=size, color=color)
        return self.text(label, x + self.menu_mark_room(size), y, size=size, color=color)

    def _skin_theme(self):
        """The project's battle UI theme (its skin also frames the host's own menus)."""
        library = self.project.battle_presentation_library
        ids = library.ids("ui_theme")
        return (
            library.require("ui_theme", "default" if "default" in ids else ids[0]) if ids else None
        )

    def panel(self, rect, fill=(13, 17, 28, 220), border=(124, 145, 190)):
        theme = self._skin_theme()
        skin = None if theme is None else theme.panel_skin("host:panel")
        image = None if skin is None else self.skin_image(skin.asset_id)
        if image is not None:
            from asteria.presentation.ui_skin import draw_nine_patch

            draw_nine_patch(self.pg, self.screen, image, tuple(int(v) for v in rect), skin)
            return
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
            follow = self.manifest["field"].get("camera", {}).get("follow")
            from asteria.runtime.tile_scene_view import TileSceneView

            scene = self.game.scene
            if not follow and not TileSceneView.available(scene):
                # a picture field follows the scene's own Camera entity, as authored in the
                # editor (a tile scene has a camera of its own)
                follow = scene_camera_follow(scene, self.width / scale)
            camera = self._field_camera = FieldViewCamera(
                self.width, self.height, scale, follow=follow
            )
        return camera

    @property
    def field_effects(self):
        """Screen fades and field VFX started by event programs (EVT-02 / EVT-04)."""
        effects = getattr(self, "_field_effects", None)
        if effects is None:
            effects = self._field_effects = FieldEffects()
        return effects

    def _field_vfx_content(self, asset_id, sheet, frames, fw, fh, columns):
        """Where a field VFX clip's picture sits inside its frames (source pixels), once."""
        from asteria.runtime.battle_visuals import vfx_content_center

        cache = self.__dict__.setdefault("_field_vfx_content_cache", {})
        if asset_id not in cache:
            boxes = []
            for index in frames:
                area = ((index % columns) * fw, (index // columns) * fh, fw, fh)
                try:
                    rect = sheet.subsurface(area).get_bounding_rect()
                except ValueError:  # a frame outside the sheet
                    continue
                if rect.width and rect.height:
                    boxes.append((rect.left, rect.top, rect.right, rect.bottom))
            cache[asset_id] = vfx_content_center(boxes, fw, fh)
        return cache[asset_id]

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
            cx, cy = self._field_vfx_content(effect.asset_id, sheet, frames, fw, fh, columns)
            x, y, w, h = vfx_rect(
                effect.placement,
                ax,
                ay,
                FIELD_BODY_HEIGHT,
                fw / scale,
                fh / scale,
                (cx / scale, cy / scale),
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
                    self.game.tr("field.skip_cutscene", "Esc: skip"),
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
        if view is not None and view.session is not self.game:
            view = None  # a loaded save is a new session: the old view still holds the old one
        if view is None:
            view = self._tile_view = TileSceneView(
                self.game, self.resource_root, self.width, self.height, self.pg
            )
        elif view.scene_id != scene.id:
            view.load()
        if self._multiplayer_connected():
            # Network snapshots already choose each guest's own class appearance.
            if not hasattr(view, "_offline_class_looks"):
                view._offline_class_looks = view._apply_class_looks
                view._apply_class_looks = lambda: None
        elif not getattr(self, "_authoritative_project_mode", False) and hasattr(
            view, "_offline_class_looks"
        ):
            view._apply_class_looks = view._offline_class_looks
            del view._offline_class_looks
        return view

    def _field_screen_xy(self, world_x, world_y):
        view = self.tile_view
        if view is not None:
            return view.world_to_screen(world_x, world_y)
        return self.field_camera.world_to_screen(world_x, world_y)

    def _field_world_xy(self, screen_x, screen_y):
        """The world point under a screen pixel (inverse of the field's affine view)."""
        ox, oy = self._field_screen_xy(0.0, 0.0)
        ax, ay = self._field_screen_xy(1.0, 0.0)
        bx, by = self._field_screen_xy(0.0, 1.0)
        a, c, b, d = ax - ox, ay - oy, bx - ox, by - oy  # screen = origin + x*(a, c) + y*(b, d)
        det = a * d - b * c
        if abs(det) < 1e-12:
            return screen_x - ox, screen_y - oy
        dx, dy = screen_x - ox, screen_y - oy
        return (d * dx - b * dy) / det, (a * dy - c * dx) / det

    def _asset_source_path(self, asset_id, kind):
        record = self.project.assets.get(str(asset_id))
        if record is not None:
            if record.kind != kind:
                return None
            uri = record.source_path
        else:
            try:
                asset = self.project.assets.resolve(str(asset_id))
            except KeyError:
                return None
            if asset.kind != kind:
                return None
            uri = asset.source.uri
        path = Path(uri)
        return path if path.is_absolute() else self.resource_root / path

    def _skeleton_sheet(self, asset_id):
        from asteria.reference_data import load_sprite_sheet

        if asset_id not in self._skeleton_sheet_cache:
            path = self._asset_source_path(asset_id, "sprite_sheet")
            if path is None:
                return None
            self._skeleton_sheet_cache[asset_id] = load_sprite_sheet(path)
        return self._skeleton_sheet_cache[asset_id]

    def _draw_skeleton_entities(self):
        if self.tile_view is not None:
            return
        scale = float(self.manifest["field"].get("world_to_screen_scale", 3.0))
        runtime = self

        class Camera:
            zoom = scale * runtime.field_camera.zoom

            @staticmethod
            def world_to_screen(x, y):
                return runtime._field_screen_xy(x, y)

        for entity in self.game.scene.entities():
            try:
                draws = self._skeleton_scene_runtime.draw_entity(
                    entity, Camera(), self._skeleton_sheet
                )
                for draw in draws:
                    path = self._asset_source_path(draw.texture_asset_id, "texture")
                    if path is None:
                        continue
                    image = self.load_image(path)
                    image = image.subsurface(self.pg.Rect(draw.source)).copy()
                    size = (max(1, round(draw.width)), max(1, round(draw.height)))
                    image = self.pg.transform.scale(image, size)
                    if draw.flip_x:
                        image = self.pg.transform.flip(image, True, False)
                    if draw.rotation_deg:
                        image = self.pg.transform.rotate(image, -draw.rotation_deg)
                    if draw.opacity < 1:
                        image.set_alpha(round(255 * draw.opacity))
                    center = (
                        round(draw.screen_x + draw.width / 2),
                        round(draw.screen_y + draw.height / 2),
                    )
                    self.screen.blit(image, image.get_rect(center=center))
            except (OSError, TypeError, ValueError, KeyError):
                continue

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

        self._draw_skeleton_entities()
        pt = self.game.player.get(Transform)
        px, py = self._field_screen_xy(pt.x, pt.y)
        pf = self._player_frame(self.game.facing, moving)
        render_w, render_h = field_player_render_size(
            pf.get_size(), self.manifest["field"].get("player_render_width", 64) * zoom
        )
        if self.manifest["field"].get("player_scaling") == "smooth":
            # a painted or rendered walker: blended pixels, as a smooth battle sheet gets
            pf = self.pg.transform.smoothscale(pf.convert_alpha(), (render_w, render_h))
        else:
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

    def _multiplayer_connected(self):
        return self.multiplayer_bridge is not None and self.multiplayer_bridge.connected

    def _enable_authoritative_project_controls(self):
        self._authoritative_project_mode = True
        if getattr(self, "_network_legacy_attack_injected", False):
            from asteria.runtime.action_play import ARPG_ACTIONS
            from asteria.runtime.input_map import InputBinding

            self.input.input_map.set_bindings(
                "attack", [InputBinding(device, code) for device, code in ARPG_ACTIONS["attack"]]
            )
            self._network_legacy_attack_injected = False

    def _network_gameplay_frozen(self):
        return (
            getattr(self, "_authoritative_project_mode", False)
            and not self._multiplayer_connected()
        )

    def _server_save_command(self, command):
        self.multiplayer_bridge.send_command(command, {})
        self.message = (
            self.game.tr("coop.requested", "Server {command} requested", command=command)
            if self._multiplayer_connected()
            else self.game.tr("coop.required", "Server connection required · F3 to retry")
        )
        self.message_until = self.pg.time.get_ticks() + 2500

    def _send_multiplayer_input(self, move_x, move_y, actions=None):
        bridge = self.multiplayer_bridge
        if bridge is None or not bridge.connected:
            return False
        actions = actions or {}
        attack_value = actions.get("attack", actions.get("primary_attack", 0.0))
        input_state = {
            **dict(actions),
            "actions": dict(actions),
            "move_x": max(-1.0, min(1.0, float(move_x))),
            "move_y": max(-1.0, min(1.0, float(move_y))),
            "attack": bool(attack_value),
        }
        previous = getattr(self, "_last_network_input", {})
        changed = previous != input_state
        self._last_network_input = input_state
        sent = bridge.send_input(input_state, force=changed)
        predictor = getattr(self, "_network_predictor", None)
        sequence = getattr(bridge, "last_input_sequence", 0)
        if sent and predictor is not None and sequence:
            mappings = getattr(self, "_network_input_prediction_sequences", {})
            mappings[sequence] = getattr(self, "_network_prediction_sequence", 0)
            self._network_input_prediction_sequences = mappings
        if sent and not self.message:
            self.message = (
                self.game.tr(
                    "coop.connected_project",
                    "Co-op connected · WASD / arrows · J attack · F pickup",
                )
                if self._authoritative_project_mode
                else self.game.tr(
                    "coop.connected",
                    "Co-op connected · move with WASD / arrows · attack with F",
                )
            )
            self.message_until = self.pg.time.get_ticks() + 6000
        return sent

    def _predict_multiplayer_player(self, move_x, move_y, dt):
        """Predict the demo adapter's local player in its authoritative network coordinates."""
        bridge = self.multiplayer_bridge
        if bridge is None or not bridge.connected or self._authoritative_project_mode:
            return False
        state = bridge.state
        players = state.get("players", ())
        local = next(
            (
                player
                for player in players
                if isinstance(player, dict) and player.get("player_id") == bridge.player_id
            ),
            None,
        )
        if local is None:
            return False
        from asteria.multiplayer.smoothing import InputPredictor

        if self._network_predictor is None:
            speed = self.multiplayer_profile.get("preview_movement_speed", 4.0)
            try:
                speed = float(speed)
            except (TypeError, ValueError):
                speed = 4.0
            if not math.isfinite(speed) or speed <= 0:
                speed = 4.0
            self._network_predictor = InputPredictor(
                (float(local.get("x", 0)), float(local.get("y", 0))), speed=speed
            )
        self._network_prediction_sequence += 1
        position = self._network_predictor.apply_local(
            self._network_prediction_sequence,
            max(-1.0, min(1.0, float(move_x))),
            max(-1.0, min(1.0, float(move_y))),
            max(0.0, min(0.1, float(dt))),
        )
        from asteria.runtime.multiplayer_preview import map_network_position

        if self._network_origin is None:
            transform = self.game.player.get(Transform)
            self._network_origin = (float(transform.x), float(transform.y))
        world_x, world_y = map_network_position(
            {"x": position[0], "y": position[1]},
            state.get("boss"),
            origin=self._network_origin,
            scale=self._network_scale,
        )
        transform = self.game.player.get(Transform)
        transform.x, transform.y = world_x, world_y
        self.game.save.player_position = (world_x, world_y)
        return True

    def _sync_multiplayer_player(self):
        bridge = self.multiplayer_bridge
        if bridge is None or not bridge.connected:
            return
        from asteria.core import Transform
        from asteria.runtime.multiplayer_preview import map_network_position

        state, network_events, network_revision = bridge.snapshot()
        if state.get("schema") == "asteria.multiplayer.project_state":
            self._network_predictor = None
            self._network_input_prediction_sequences.clear()
            self._enable_authoritative_project_controls()
            from asteria.runtime.multiplayer_preview import (
                apply_project_snapshot,
                install_authoritative_commands,
            )

            install_authoritative_commands(self)
            if network_revision != self._network_revision:
                try:
                    if apply_project_snapshot(self, state, bridge.player_id):
                        self._network_revision = network_revision
                        from asteria.runtime.combat import CombatEvent

                        self.game.combat.events = tuple(
                            CombatEvent(
                                **{
                                    key: value
                                    for key, value in event.items()
                                    if key in CombatEvent.__dataclass_fields__
                                }
                            )
                            for event in network_events
                            if event.get("kind")
                            in {"damage", "staggered", "knocked_down", "state_applied"}
                        )
                except (KeyError, TypeError, ValueError) as exc:
                    self._multiplayer_error = f"Invalid server snapshot: {exc}"
            return
        boss = state.get("boss")
        players = state.get("players", ())
        player_id = bridge.player_id
        local = next(
            (
                player
                for player in players
                if isinstance(player, dict) and player.get("player_id") == player_id
            ),
            None,
        )
        if local is None:
            return
        if self._network_origin is None:
            transform = self.game.player.get(Transform)
            self._network_origin = (float(transform.x), float(transform.y))
        x, y = map_network_position(
            local, boss, origin=self._network_origin, scale=self._network_scale
        )
        transform = self.game.player.get(Transform)
        predictor = self._network_predictor
        if predictor is not None:
            acknowledged = bridge.acked_input_sequence
            acknowledged_prediction = max(
                (
                    prediction
                    for sequence, prediction in self._network_input_prediction_sequences.items()
                    if sequence <= acknowledged
                ),
                default=0,
            )
            if (
                acknowledged_prediction
                and network_revision > bridge.acked_input_revision
                and network_revision > self._network_prediction_reconciled_revision
            ):
                predictor.reconcile(
                    (float(local["x"]), float(local["y"])), acknowledged_prediction
                )
                self._network_prediction_reconciled_revision = network_revision
                self._network_input_prediction_sequences = {
                    sequence: prediction
                    for sequence, prediction in self._network_input_prediction_sequences.items()
                    if sequence > acknowledged
                }
            x, y = map_network_position(
                {"x": predictor.position[0], "y": predictor.position[1]},
                boss,
                origin=self._network_origin,
                scale=self._network_scale,
            )
        transform.x, transform.y = x, y
        self.game.save.player_position = (x, y)
        if network_revision > self._network_revision:
            self._network_revision = network_revision
            for event in network_events:
                if event.get("player_id") != player_id:
                    continue
                if event.get("type") == "experience_awarded":
                    amount = int(event.get("amount", 0))
                    self.message = self.game.tr(
                        "coop.boss_defeated", "Boss defeated · +{amount} XP", amount=amount
                    )
                    self.message_until = self.pg.time.get_ticks() + 6000
                elif event.get("type") == "loot_awarded":
                    self.message = self.game.tr(
                        "coop.boss_loot", "Boss loot: {item}", item=event.get("item_id", "item")
                    )
                    self.message_until = self.pg.time.get_ticks() + 6000

    def _draw_multiplayer_world(self):
        bridge = self.multiplayer_bridge
        if bridge is None:
            if self.multiplayer_profile_error:
                self.panel((12, 12, self.width - 24, 48))
                self.text(
                    self.game.tr(
                        "coop.profile_error",
                        "Co-op profile error: {error}",
                        error=self.multiplayer_profile_error,
                    ),
                    24,
                    25,
                    size=18,
                    color=(255, 154, 132),
                )
            return
        if not bridge.connected:
            status = self._multiplayer_error or self.game.tr(
                "coop.start_server", "Start the local server in Multiplayer first"
            )
            self.panel((12, 12, self.width - 24, 48))
            self.text(
                self.game.tr(
                    "coop.retry", "Co-op offline · {status} · F3 to retry", status=status
                ),
                24,
                25,
                size=18,
                color=(255, 190, 132),
            )
            return

        from asteria.runtime.multiplayer_preview import map_network_position

        state = bridge.state
        if state.get("schema") == "asteria.multiplayer.project_state":
            self.text(
                self.game.tr(
                    "coop.players", "Co-op · {count} players", count=len(state.get("players", ()))
                ),
                16,
                12,
                size=18,
                color=(170, 230, 190),
            )
            return
        boss = state.get("boss")
        players = state.get("players", ())
        if not isinstance(boss, dict) or not isinstance(players, list):
            return
        if self._network_origin is None:
            player_transform = self.game.player.get(Transform)
            self._network_origin = (float(player_transform.x), float(player_transform.y))
        origin = self._network_origin
        boss_world = map_network_position(boss, boss, origin=origin, scale=self._network_scale)
        zoom = self.field_camera.zoom
        boss_x, boss_y = self._field_screen_xy(*boss_world)
        radius = max(12, round(12 * zoom))
        boss_color = (220, 89, 84) if boss.get("alive", True) else (128, 128, 138)
        self.pg.draw.rect(
            self.screen,
            (35, 24, 31),
            (round(boss_x - radius), round(boss_y - radius), radius * 2, radius * 2),
        )
        self.pg.draw.rect(
            self.screen,
            boss_color,
            (round(boss_x - radius), round(boss_y - radius), radius * 2, radius * 2),
            max(2, round(2 * zoom)),
        )
        hp, max_hp = int(boss.get("hp", 0)), max(1, int(boss.get("max_hp", 1)))
        bar_width = max(64, round(84 * zoom))
        bar_y = round(boss_y - radius - 18 * zoom)
        self.pg.draw.rect(
            self.screen, (28, 28, 34), (round(boss_x - bar_width / 2), bar_y, bar_width, 7)
        )
        self.pg.draw.rect(
            self.screen,
            boss_color,
            (
                round(boss_x - bar_width / 2),
                bar_y,
                round(bar_width * max(0, min(max_hp, hp)) / max_hp),
                7,
            ),
        )
        self.text(
            self.game.tr("coop.boss", "Co-op Boss · {hp}/{max_hp}", hp=hp, max_hp=max_hp),
            boss_x,
            bar_y - 22,
            size=20,
            color=(255, 224, 214),
            center=True,
        )

        for drop in state.get("world_drops", []):
            if drop.get("claimed_by") or bridge.player_id in drop.get("claimed_by_players", []):
                continue
            world = map_network_position(drop, boss, origin=origin, scale=self._network_scale)
            sx, sy = self._field_screen_xy(*world)
            self.pg.draw.circle(self.screen, (249, 214, 106), (round(sx), round(sy)), 7)
            claim = self.game.tr("coop.claim", "G: claim treasure")
            self.text(claim, sx, sy + 12, size=16, color=(249, 214, 106), center=True)

        local_id = bridge.player_id
        local = next(
            (
                player
                for player in players
                if isinstance(player, dict) and player.get("player_id") == local_id
            ),
            None,
        )
        local_xp = int(local.get("experience", 0)) if local is not None else 0
        self.panel((12, 66, min(330, self.width - 24), 48))
        self.text(
            self.game.tr(
                "coop.status",
                "Co-op · {count} players · XP {xp} · B: bag / G: loot",
                count=len(players),
                xp=local_xp,
            ),
            24,
            80,
            size=20,
            color=(132, 229, 220),
        )
        frame = self._player_frame("down", False)
        source_w, source_h = frame.get_size()
        render_width = max(18, round(self.manifest["field"].get("player_render_width", 64) * zoom))
        render_height = max(1, round(source_h * render_width / max(1, source_w)))
        if self.manifest["field"].get("player_scaling") == "smooth":
            frame = self.pg.transform.smoothscale(
                frame.convert_alpha(), (render_width, render_height)
            )
        else:
            frame = self.pg.transform.scale(frame, (render_width, render_height))
        remote_positions = bridge.remote_positions()
        for index, player in enumerate(players):
            if not isinstance(player, dict) or player.get("player_id") == local_id:
                continue
            network_position = remote_positions.get(player.get("player_id"))
            positioned_player = (
                {**player, "x": network_position[0], "y": network_position[1]}
                if network_position is not None
                else player
            )
            world = map_network_position(
                positioned_player, boss, origin=origin, scale=self._network_scale
            )
            screen_x, screen_y = self._field_screen_xy(*world)
            ground = (round(screen_x), round(screen_y + 5 * zoom))
            self.pg.draw.ellipse(
                self.screen,
                (28, 34, 42),
                (ground[0] - render_width // 3, ground[1] - 4, 2 * render_width // 3, 9),
            )
            position = (
                round(screen_x - render_width / 2),
                round(screen_y - render_height + 10 * zoom),
            )
            self.screen.blit(frame, position)
            color = ((84, 196, 211), (160, 132, 234), (226, 174, 78), (106, 194, 133))[index % 4]
            self.pg.draw.circle(self.screen, color, ground, max(4, round(5 * zoom)), 2)
            label = str(player.get("display_name", self.game.tr("coop.player", "Player")))
            self.text(
                self.game.tr(
                    "coop.player_hp", "{name} · {hp} HP", name=label, hp=player.get("hp", 0)
                ),
                screen_x,
                position[1] - 20,
                size=18,
                color=color,
                center=True,
            )

    def _draw_field_overlays(self):
        """Everything drawn over the field's world: HUD, effects, popups, dialogue, help."""
        self._draw_multiplayer_world()
        if self.game.action_scene:
            self.action_hud.draw_world(self)
        elif self._field_abilities():  # field strikes in a turn-based game: its thrown shots
            self.action_hud.draw_projectiles(self)
        self._draw_field_effects()
        self._draw_popups()
        self._draw_pictures()
        self._draw_event_timers()
        self._draw_field_windows()
        self._draw_entity_icons()
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

        tr = self.game.tr
        self.panel((18, self.height - 92, self.width - 36, 72))
        self.text(
            tr("field.title", "Field Test"), 34, self.height - 82, size=24, color=(255, 220, 124)
        )
        self.text(
            tr(
                "field.controls",
                "Move: WASD / Arrows   C: Build   Q: Quests   E: Interact   F5: Save   Esc: Pause",
            ),
            34,
            self.height - 52,
            size=19,
        )
        candidate = self._interaction_candidate()
        if candidate is not None and not self.game.event_busy:
            self.text(
                tr("field.interact", "E  Interact — {name}", name=candidate.entity.name),
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
        self._draw_equip_offer()

    def _equip_offer_text(self, offer):
        """("Wear the Demon Ring?", "Aldric - weapon (a free hand)") for an offer."""
        db = self.project.rpg_database
        bag = self.game.save.rpg_state.equipment_bag
        item = next((g for g in bag if g.instance_id == offer.instance_id), None)
        name = item.equipment.display_name if item is not None else offer.instance_id
        actor = db.actors.get(offer.actor_id)
        who = getattr(actor, "display_name", "") or offer.actor_id
        if offer.replaces:
            loadout = self.game.save.rpg_state.loadouts[offer.actor_id]
            worn = next(
                (g for g in loadout.equipped(offer.slot_id) if g.instance_id == offer.replaces),
                None,
            )
            old = worn.equipment.display_name if worn is not None else offer.replaces
            return (
                self.game.tr("equip_offer.new", "New: {name}", name=name),
                self.game.tr(
                    "equip_offer.instead",
                    "{who}: wear it instead of {old}?",
                    who=who,
                    old=old,
                ),
            )
        return (
            self.game.tr("equip_offer.new", "New: {name}", name=name),
            self.game.tr(
                "equip_offer.free",
                "{who} has a free {slot} place. Wear it now?",
                who=who,
                slot=offer.slot_id,
            ),
        )

    def _draw_equip_offer(self):
        """New gear asks whether to wear it (InventoryRules.equip_offer)."""
        offers = self.game.equip_offers
        if not offers or self.game.pending_dialogue is not None:
            return
        title, question = self._equip_offer_text(offers[0])
        box = (self.width / 2 - 300, self.height - 250, 600, 150)
        self.panel(box, fill=(10, 14, 24, 240), border=(240, 201, 93))
        self.text(title, self.width / 2, box[1] + 26, size=26, color=(255, 220, 124), center=True)
        self.text(question, self.width / 2, box[1] + 64, size=21, center=True)
        self.text(
            self.game.tr("equip_offer.keys", "1 / Enter: wear it     2 / Esc: keep it in the bag"),
            self.width / 2,
            box[1] + 108,
            size=18,
            color=(170, 210, 240),
            center=True,
        )

    def _equip_offer_input(self, events):
        """Keys for a waiting equip offer. Returns True when one is open."""
        if not self.game.equip_offers or self.game.event_busy:
            return False
        wear = self.input.just_pressed("confirm") or any(
            e.type == self.pg.KEYDOWN and e.key == self.pg.K_1 for e in events
        )
        keep = self.input.just_pressed("cancel") or any(
            e.type == self.pg.KEYDOWN and e.key == self.pg.K_2 for e in events
        )
        if wear or keep:
            self.game.answer_equip_offer(bool(wear))
        return True

    def _picture_image(self, picture):
        """The sub-image of a picture's asset for its sprite-sheet cell, or ``None``."""
        from .menu_icons import icon_source

        source = icon_source(self.project, picture.asset_id)
        if source is None:
            return None
        try:
            image = self.load_image(source[0])
        except (OSError, ValueError, self.pg.error):
            return None
        x, y, w, h = picture.cell(*image.get_size())
        return image.subsurface(self.pg.Rect(x, y, w, h).clip(image.get_rect()))

    def _picture_size(self, picture):
        image = self._picture_image(picture)
        if image is None:
            return None
        return self.load_image(self._picture_path(picture)).get_size()

    def _picture_path(self, picture):
        from .menu_icons import icon_source

        return icon_source(self.project, picture.asset_id)[0]

    def _draw_pictures(self):
        """Pictures events put on screen (SHOW_PICTURE), bottom layer first."""
        for picture in self.game.pictures.pictures():
            image = self._picture_image(picture)
            if image is None or picture.opacity <= 0:
                continue
            w, h = image.get_size()
            target = (max(1, round(w * picture.scale)), max(1, round(h * picture.scale)))
            if target != (w, h):
                image = self.pg.transform.scale(image, target)
            if picture.opacity < 1.0:
                image = image.copy()
                image.set_alpha(round(255 * picture.opacity))
            self.screen.blit(image, (round(picture.x), round(picture.y)))

    def _click_picture(self, x, y):
        return self.game.click_picture(x, y, self._picture_size)

    def _draw_event_timers(self):
        """Visible event timers (TIMER_START) stacked at the top right: ``MM:SS``."""
        for row, (timer_id, clock) in enumerate(self.game.timers.display()):
            low = (self.game.timers.remaining(timer_id) or 99) <= 10
            color = (255, 150, 140) if low else (245, 245, 250)
            self.panel((self.width - 118, 14 + row * 40, 104, 34))
            self.text(clock, self.width - 66, 31 + row * 40, size=30, color=color, center=True)

    def battle_option(self, name):
        """A battle option: the project's ``BattleOptions`` record (first by id) when it has one,
        else the manifest's ``battle.<name>``; ``False`` / ``0`` when neither says."""
        values = self.project.rpg_database.battle_options
        if values:
            return getattr(values[sorted(values)[0]], name)
        return self.manifest.get("battle", {}).get(name, 0)

    def _draw_entity_icons(self):
        """Icons events keep over entities (``SET_ENTITY_ICON``), above their heads."""
        from asteria.core import Transform

        icons = self.game.entity_icons()
        for entity_id, icon_id in icons.items():
            entity = self.game.scene.get_entity(entity_id)
            if entity is None or not entity.has(Transform):
                continue
            transform = entity.get(Transform)
            x, y = self._field_screen_xy(transform.x, transform.y)
            self._draw_icon(icon_id, round(x) - 11, round(y) - 64, 22)

    def _draw_field_windows(self):
        """Optional map windows (manifest ``field.hud``): ``gold`` shows the wallet and
        ``quest_tracker`` the active quests' objectives, stacked at the top left. Off unless the
        project asks, so existing games look as they did."""
        hud = self.manifest.get("field", {}).get("hud", {})
        if not isinstance(hud, dict) or not (hud.get("gold") or hud.get("quest_tracker")):
            return
        lines = []
        state = self.game.save.rpg_state
        if hud.get("gold"):
            wallet = "   ".join(f"{state.currencies[k]:g} {k}" for k in sorted(state.currencies))
            if wallet:
                lines.append((wallet, (255, 222, 150)))
        if hud.get("quest_tracker"):
            quests = self.project.rpg_database.quests
            for quest_id, progress in sorted(state.quests.items()):
                if progress.status != "active" or quest_id not in quests:
                    continue
                quest = quests[quest_id]
                lines.append((quest.display_name, (245, 245, 250)))
                for objective in quest.objectives:
                    have = progress.counts.get(objective.objective_id, 0)
                    done = have >= objective.required
                    label = objective.description or objective.objective_id
                    lines.append(
                        (
                            f"  {label}  {min(have, objective.required)}/{objective.required}",
                            (170, 240, 170) if done else (200, 205, 220),
                        )
                    )
        if not lines:
            return
        from asteria.presentation.text_cells import cells

        row_h = 22  # a full-width (Chinese) character takes the room of two
        width = min(420, max(160, 14 + 9 * max(cells(text) for text, _ in lines)))
        self.panel((14, 14, width, 12 + row_h * len(lines)))
        for row, (text, color) in enumerate(lines):
            self.text(text, 24, 20 + row * row_h, size=18, color=color)

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
        from asteria.platform.pygame_battle_ui import cjk_size, font_for_text

        latin = self.pg.font.Font(None, 30)
        for packet in packets:
            color = self.POPUP_COLORS.get(packet.metadata.get("kind"), self.POPUP_COLORS["info"])
            # Chinese, Japanese or Korean words come from a system face that has them
            font = font_for_text(self.pg, latin, packet.text, self._cjk_fonts, cjk_size(latin))
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

    def dialogue_portrait(self, portrait_id, width, height):
        """The picture ``portrait_id`` names (an image asset, a sheet cell or a project path)
        fitted inside ``width`` x ``height`` with its proportions kept, or ``None``. A picture
        made larger keeps sharp pixels (pixel-art faces); one made smaller is smoothed."""
        from .menu_icons import icon_source

        key = (str(portrait_id or ""), int(width), int(height))
        cache = self._portrait_cache
        if key in cache:
            return cache[key]
        picture = None
        source = icon_source(self.project, portrait_id) if portrait_id else None
        if source is not None:
            uri, region = source
            try:
                image = self.load_image(uri)
                if region is not None:
                    image = image.subsurface(self.pg.Rect(region).clip(image.get_rect()))
                w, h = image.get_size()
                scale = min(width / max(1, w), height / max(1, h))
                size = (max(1, round(w * scale)), max(1, round(h * scale)))
                fit = self.pg.transform.scale if scale >= 1 else self.pg.transform.smoothscale
                picture = fit(image, size)
            except (OSError, ValueError, self.pg.error):
                picture = None  # a missing portrait: the line shows without one
        if len(cache) > 32:
            cache.clear()
        cache[key] = picture
        return picture

    PORTRAIT_BUST_SHARE = 0.55  # a bust's height on screen when Portrait Size is 0
    DIALOGUE_BOX_HEIGHT = 130

    def _dialogue_layout(self, line):
        """The message window ``(x, y, w, h)`` for ``line`` and its portrait as ``(picture,
        (x, y), style, room)`` or ``None``; ``room`` is the rect the portrait keeps. A face sits
        centred in a square at the window's left or right end (the window grows to hold a big
        one); a bust stands on the window's bottom edge."""
        settings = self.game.message_settings
        style = settings.portrait_style if settings is not None else "face"
        size = settings.portrait_size if settings is not None else 0
        height = self.DIALOGUE_BOX_HEIGHT
        box = (60, self.height - 100 - height, self.width - 120, height)
        portrait_id = getattr(line, "portrait_asset_id", "") if line is not None else ""
        if not portrait_id:
            return box, None
        left = line.portrait_side == "left"
        if style == "bust":
            x, y, w, h = box
            tall = size or round(self.height * self.PORTRAIT_BUST_SHARE)
            picture = self.dialogue_portrait(portrait_id, w // 2, tall)
            if picture is None:
                return box, None
            at = (
                x + 24 if left else x + w - 24 - picture.get_width(),
                y + h - picture.get_height(),
            )
            return box, (picture, at, style, (*at, *picture.get_size()))
        side = size or height - 24
        picture = self.dialogue_portrait(portrait_id, side, side)
        if picture is None:
            return box, None
        height = max(height, side + 24)  # a big face: the window grows upwards to hold it
        box = x, y, w, h = (60, self.height - 100 - height, self.width - 120, height)
        room = (x + 12 if left else x + w - 12 - side, y + (h - side) // 2, side, side)
        at = (
            room[0] + (side - picture.get_width()) // 2,
            room[1] + (side - picture.get_height()) // 2,
        )
        return box, (picture, at, style, room)

    def _draw_dialogue(self):
        request = (
            getattr(self, "_network_dialogue", None)
            if self._multiplayer_connected()
            else self.game.pending_dialogue
        )
        if request is None:
            return
        line = getattr(request, "line", None)
        box, portrait = self._dialogue_layout(line)
        if portrait is not None and portrait[2] == "bust":  # stands behind the window
            self.screen.blit(portrait[0], portrait[1])
        self.panel(box, fill=(10, 14, 24, 235), border=(240, 201, 93))
        x, y, w, h = box
        if line is not None:
            text_x = x + 24
            hint_x, hint_anchor = self.width - 250, None
            if portrait is not None and portrait[2] == "face":
                picture, at, _, room = portrait
                self.screen.blit(picture, at)
                if line.portrait_side == "left":
                    text_x = room[0] + room[2] + 18  # the text starts after the face's square
                else:  # the hint ends before the face
                    hint_x, hint_anchor = room[0] - 14, "topright"
            if line.speaker:
                speaker = self.game.expand_message(line.speaker, plain=True)
                self.text(speaker, text_x, y + 12, size=24, color=(255, 220, 124))
            self._draw_message(self.game.expand_message(line.text), text_x, y + 46)
            self.text(
                self.game.tr("dialogue.continue", "Enter / E: continue"),
                hint_x,
                y + h - 28,
                size=18,
                color=(170, 210, 240),
                anchor=hint_anchor,
            )
            return
        self.text(
            request.prompt or self.game.tr("dialogue.choose", "Choose"),
            84,
            self.height - 218,
            size=22,
            color=(255, 220, 124),
        )
        for i, choice in enumerate(request.choices[:9], 1):
            self.text(
                f"{i}. {choice.text}",
                84 + ((i - 1) % 3) * 270,
                self.height - 184 + ((i - 1) // 3) * 26,
                size=20,
            )

    def _draw_message(self, text, x, y, *, size=22):
        """Draw a message whose data codes are expanded: colour and size spans, icons as boxes,
        ``\\n`` starts a new line."""
        from asteria.presentation.message_codes import parse_message

        left, top = x, y
        for span in parse_message(text):
            if span.icon is not None:
                icon_id = self.game.message_icon(span.icon)
                if not (icon_id and self._draw_icon(icon_id, left, top, size)):
                    box = self.pg.Rect(left, top + 2, size - 4, size - 4)  # no icon: a box
                    self.pg.draw.rect(self.screen, span.color, box, 2, 3)
                left += size
                continue
            for number, part in enumerate(span.text.split("\n")):
                if number:
                    left, top = x, top + size + 6
                if part:
                    rect = self.text(
                        part, left, top, size=size + 6 * span.size_steps, color=span.color
                    )
                    left = rect.right

    def _dialogue_input(self, events):
        """Route keys to a waiting dialogue/choice. Returns True when one is open."""
        request = (
            getattr(self, "_network_dialogue", None)
            if self._multiplayer_connected()
            else self.game.pending_dialogue
        )
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
        for event in events:  # clicking a picture that has an event
            if event.type == self.pg.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
                if self._click_picture(*event.pos) is not None:
                    return False
                if self.game.click_entity(*self._field_world_xy(*event.pos)) is not None:
                    return False
        if self.game.cutscene_active:
            if self.game.cutscene_skippable and self.input.just_pressed("cancel"):
                self.game.skip_cutscene()
                return False
            self._dialogue_input(events)
            return False
        if self._equip_offer_input(events):
            return False
        if self._dialogue_input(events) or (
            getattr(self, "_network_event_busy", False)
            if self._multiplayer_connected()
            else self.game.event_busy
        ):
            if self._multiplayer_connected():
                self._send_multiplayer_input(0, 0, {})
            else:
                self.game.set_field_input(None)
            return False
        if (
            self.multiplayer_bridge is not None
            and not self.multiplayer_bridge.connected
            and any(
                event.type == self.pg.KEYDOWN and event.key == self.pg.K_F3 for event in events
            )
        ):
            if self.multiplayer_bridge.connect():
                self._network_predictor = None
                self._network_input_prediction_sequences.clear()
                self._network_prediction_reconciled_revision = -1
                self.multiplayer_bridge.send_input(
                    {"move_x": 0.0, "move_y": 0.0, "attack": False}, force=True
                )
                self._multiplayer_error = ""
                self._network_revision = -1
            else:
                self._multiplayer_error = self.multiplayer_bridge.error
        if self.game.action_scene:
            return self._action_input(events, dt)
        # Project input map: keyboard and gamepad (stick / d-pad) both drive movement.
        dx, dy = self.input.current.movement_vector()
        moving = bool(dx or dy)
        connected = self._multiplayer_connected()
        if connected:
            self._predict_multiplayer_player(dx, dy, dt)
            self._send_multiplayer_input(dx, dy, dict(self.input.current.actions))
            self._sync_multiplayer_player()
        elif moving:
            mag = max(1.0, (dx * dx + dy * dy) ** 0.5)
            speed = 36.0
            pt = self.game.player.get(Transform)
            blocked = CollisionWorld.from_scene(self.game.scene).blocking_query(
                exclude={self.game.player.id}
            )
            x_range, y_range = (-120.0, 120.0), (-52.0, 52.0)
            if self.tile_view is not None:
                # a tile map: its walls block and its edge bounds the walk, the pace is a walk
                # across a screen in a few seconds
                from asteria.runtime.collision import CombinedQuery

                walls = self.game._tile_blocking.get(self.game.scene.id)
                blocked = CombinedQuery(blocked, walls)
                x0, y0, x1, y1 = self.tile_view.bounds
                x_range, y_range, speed = (x0 + 6, x1 - 6), (y0 + 6, y1 - 2), 64.0
            nx = max(x_range[0], min(x_range[1], pt.x + dx / mag * speed * dt))
            if not blocked.collides_world_point(nx, pt.y):
                pt.x = nx
            ny = max(y_range[0], min(y_range[1], pt.y + dy / mag * speed * dt))
            if not blocked.collides_world_point(pt.x, ny):
                pt.y = ny
            self.game.save.player_position = (pt.x, pt.y)
            if abs(dx) > abs(dy):
                self.game.set_player_facing("right" if dx > 0 else "left")
            else:
                self.game.set_player_facing("down" if dy > 0 else "up")
            self._field_step += 1
        if not connected:  # a player with ActionCombat bindings strikes and shoots here too
            self.game.set_field_input(
                dict(self.input.current.actions) if self._field_abilities() else None
            )

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
        if moving and not connected and self.game.mode == "field":
            self.game.field_step({})  # doors and other triggers walked into
        # GameSessionRuntime interaction is edge-triggered. Emit release after press.
        if self.input.just_pressed("interact") and not connected:
            self.game.field_step({"interact": 1.0})
            if self.game.mode == "field":
                self.game.field_step({"interact": 0.0})
        return moving

    def _field_abilities(self):
        """The player carries ActionCombat bindings (a field attack in a turn-based game)."""
        from asteria.runtime.action_combat import ActionCombatComponent

        combat = self.game.player.try_get(ActionCombatComponent)
        return combat is not None and combat.enabled and bool(combat.bindings.strip())

    # -- action scenes (ASTERIA_SPEC §20; D22 A8) -------------------------------------------------
    @property
    def action_hud(self):
        hud = getattr(self, "_action_hud", None)
        if hud is None:
            from asteria.runtime.action_play import ActionHud

            hud = self._action_hud = ActionHud()
        return hud

    def _action_input(self, events, dt=0.0):
        """Real-time control: the input actions drive the player's controller and abilities through
        the session."""
        if not self._multiplayer_connected():
            self.game.prepare_action_player()
        actions = dict(self.input.current.actions)
        if self._multiplayer_connected():
            dx, dy = self.input.current.movement_vector()
            self._predict_multiplayer_player(dx, dy, dt)
            self._send_multiplayer_input(dx, dy, actions)
            self._sync_multiplayer_player()
        else:
            self.game.set_field_input(actions)
        if self._multiplayer_connected() and (
            self.input.just_pressed("pickup")
            or any(event.type == self.pg.KEYDOWN and event.key == self.pg.K_g for event in events)
        ):
            import uuid

            self.multiplayer_bridge.send_command("pickup", {"operation_id": uuid.uuid4().hex})
        if self.input.just_pressed("pickup") and not self._multiplayer_connected():
            self.game.loot.pick_up_nearest(self.game.scene, self.game.player)
        if self.input.just_pressed("bag"):
            from asteria.runtime.bag_screen import BagScreen

            if (
                self._multiplayer_connected()
                and self.multiplayer_bridge.state.get("schema")
                != "asteria.multiplayer.project_state"
            ):
                from asteria.runtime.network_bag_screen import NetworkBagScreen

                self._bag_screen = NetworkBagScreen(self)
            else:
                self._bag_screen = BagScreen(self)
            self._ui_mode = "bag"
        if self.input.just_pressed("menu"):  # the skill tree (D22 A10)
            from asteria.runtime.skill_tree_screen import SkillTreeScreen

            if self._multiplayer_connected():
                from asteria.runtime.network_bag_screen import NetworkSkillTreeScreen

                self._skill_tree = NetworkSkillTreeScreen(self)
            else:
                self._skill_tree = SkillTreeScreen(self)
            self._ui_mode = "skills"
        if self.input.just_pressed("cancel"):
            self._pause_menu.index = 0
            self._ui_mode = "pause"
        if (
            not self._multiplayer_connected()
            and self.input.just_pressed("interact")
            and not self.input.just_pressed("jump")
        ):
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
        tr = self.game.tr
        name = tr("title.name", "ASTERIA")
        self.text(name, self.width / 2, 120, size=64, color=(255, 220, 120), center=True)
        # the game's own name (manifest "subtitle"); the reference project keeps its old text
        subtitle = self.manifest.get("subtitle") or tr("title.subtitle", "Complex Reference RPG")
        self.text(subtitle, self.width / 2, 180, size=36, center=True)
        self.panel((280, 250, 400, 150))
        if self._multiplayer_connected() or self._network_gameplay_frozen():
            self.text(tr("title.server_session", "N   Enter Server Session"), 310, 282, size=25)
            self.text(tr("title.server_save", "L   Reload Server Save"), 310, 330, size=25)
            self.text(
                tr("title.guest", "Guest: {player}", player=self.multiplayer_bridge.player_id),
                310,
                372,
                size=16,
                color=(170, 210, 240),
            )
            return
        self.text(tr("title.new_game", "N   New Game"), 330, 282, size=28)
        self.text(tr("title.load_game", "L   Load Game"), 330, 330, size=28)
        from asteria.runtime.save_slots import SaveSlots

        used = sum(
            1
            for s in SaveSlots(self.resource_root / "saves", self.project).slots()
            if self._slot_exists(s)
        )
        self.text(
            tr("title.saves", "{count} save(s) found", count=used)
            if used
            else tr("title.no_saves", "No saves yet"),
            330,
            372,
            size=18,
            color=(170, 210, 240),
        )

    def _load_player_save(self):
        if self._multiplayer_connected() or self._network_gameplay_frozen():
            self._server_save_command("load")
            self._ui_mode = "field"
            return True
        path = self.resource_root / "saves" / "playtest_autosave.asteria-save.json"
        if not path.exists():
            self.message = self.game.tr("title.no_player_save", "No player save exists yet")
            self.message_until = self.pg.time.get_ticks() + 1800
            return False
        loaded = GameRuntimeSave.load_json(path, self.project)
        self.save = loaded
        self.game = GameSessionRuntime(self.project, loaded)
        self._victory = False
        self._defeat = False
        self._ui_mode = "field"
        self.message = self.game.tr("title.loaded", "Loaded player save")
        self.message_until = self.pg.time.get_ticks() + 1800
        return True

    def _adopt_new_game_plus(self):
        """An event asked for New Game Plus: play on in the carried-over save from the start."""
        fresh = getattr(self.game, "pending_new_game", None)
        if fresh is None:
            return False
        self.game.pending_new_game = None
        self.save = fresh
        self.game = GameSessionRuntime(self.project, fresh)
        self._victory = self._defeat = False
        self._ui_mode = "field"
        self.message = self.game.tr("title.new_game_plus", "New Game+")
        self.message_until = self.pg.time.get_ticks() + 2400
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
        tr = self.game.tr
        title = tr("build.title", "Character / Build Acceptance Menu")
        self.text(title, 44, 38, size=30, color=(255, 220, 120))
        keys = tr("build.keys", "Q/E Actor   C Close     Current: {actor}", actor=actor_id)
        self.text(keys, 44, 76, size=19)
        self.text(
            tr(
                "build.points",
                "Level {level}   EXP {exp}   AP {ap}   Ability Pts {ability_points}",
                level=state.level,
                exp=int(state.experience),
                ap=int(allocation.balance("ap")),
                ability_points=int(state.points.get("ability_points", 0)),
            ),
            44,
            106,
            size=20,
            color=(170, 220, 255),
        )
        classes = " + ".join(state.active_class_ids) or "—"
        self.text(tr("build.class", "1 Secondary Class: {value}", value=classes), 44, 148, size=20)
        passives = ", ".join(ability.active_passives[:4]) or "—"
        self.text(tr("build.passives", "3 Passives: {value}", value=passives), 44, 178, size=20)
        held = weapon.equipment.display_name if weapon else "—"
        self.text(tr("build.weapon", "4 Weapon: {value}", value=held), 44, 208, size=20)
        growth = (
            "—"
            if weapon is None or weapon.growth is None
            else ", ".join(f"{k}:{v}" for k, v in sorted(weapon.growth.ranks.items()))
            or tr("build.base", "base")
        )
        self.text(tr("build.upgrade", "5 Weapon Upgrade: {value}", value=growth), 44, 238, size=20)
        accessories = self.save.rpg_state.loadouts[actor_id].equipped("accessory")
        worn = ", ".join(x.equipment.display_name for x in accessories) or "—"
        self.text(tr("build.accessories", "6 Accessories: {value}", value=worn), 44, 268, size=20)
        active = ", ".join(self.save.rpg_state.party_active_actor_ids)
        self.text(
            tr("build.party", "7 Party / Formation: {value}", value=active), 44, 298, size=20
        )
        tree = tr("build.tree", "2 Skill Tree: allocate next available node")
        self.text(tree, 44, 328, size=20)
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
            tr(
                "build.note",
                "All changes are Runtime State and are verified again after Save/Load.",
            ),
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
                self.game.allocate_progression(actor_id, graph_id, node.node_id, 1)
                self.message = self.game.tr(
                    "build.learned", "Learned {name}", name=node.display_name
                )
                self.message_until = self.pg.time.get_ticks() + 1400
                return
        self.message = self.game.tr("build.no_node", "No affordable/unlocked node")
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
                if self._multiplayer_connected():
                    self.multiplayer_bridge.send_command(
                        "upgrade", {"slot_id": "weapon", "node_id": node.node_id}
                    )
                    return
                growth.unlock(node.node_id)
                self.message = self.game.tr(
                    "build.upgraded", "Weapon upgraded: {name}", name=node.display_name
                )
                self.message_until = self.pg.time.get_ticks() + 1400
                return
        self.message = self.game.tr("build.no_upgrade", "Weapon growth maxed or blocked")
        self.message_until = self.pg.time.get_ticks() + 1400

    def _cycle_accessory(self, actor_id):
        ids = sorted(
            k for k, v in self.project.rpg_database.equipment.items() if v.slot == "accessory"
        )
        loadout = self.save.rpg_state.loadouts[actor_id]
        if loadout.equipped("accessory"):
            if self._multiplayer_connected():
                self.game.unequip_to_bag(actor_id, "accessory")
            else:
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
            elif actor is not None and event.key == self.pg.K_8:
                self._ui_mode = "workshop"

    # --- workshop: refine, sockets and attribute points on one screen --------------------

    def _workshop_input(self, events):
        """R refine the weapon, S socket the next fitting bag item, X take a gem out, A spend
        an attribute point (cycling the attribute nodes), C / Escape back to the build menu."""
        actor = self._menu_actor()
        if actor is None:
            return
        weapon = self._current_weapon(actor)
        game = self.game
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            try:
                if event.key in (self.pg.K_c, self.pg.K_ESCAPE):
                    self._ui_mode = "build"
                elif weapon is not None and event.key == self.pg.K_r:
                    result = game.refine_equipment(actor, weapon.instance_id)
                    self._workshop_message = game.tr(
                        "workshop.refined", "Refine: {outcome}", outcome=result.outcome
                    )
                elif weapon is not None and event.key == self.pg.K_s:
                    self._workshop_message = self._socket_next(actor, weapon)
                elif weapon is not None and event.key == self.pg.K_x:
                    for socket_id, attached in weapon.attachments.items():
                        game.unsocket_item(actor, weapon.instance_id, socket_id)
                        self._workshop_message = game.tr(
                            "workshop.took_out",
                            "Took {name} out of {socket}",
                            name=attached.display_name,
                            socket=socket_id,
                        )
                        break
                elif event.key == self.pg.K_a:
                    self._workshop_message = self._spend_attribute_point(actor)
            except Exception as exc:  # noqa: BLE001 - shown on the screen, the game goes on
                self._workshop_message = translated(exc, game.tr)

    def _socket_next(self, actor, weapon):
        game, db = self.game, self.project.rpg_database
        bag = self.save.rpg_state.inventory
        for socket in weapon.equipment.sockets:
            if socket.socket_id in weapon.attachments or socket.locked:
                continue
            for item in db.items.values():
                if not item.attachment_id or bag.count(item.item_id) < 1:
                    continue
                try:
                    game.socket_item(actor, weapon.instance_id, socket.socket_id, item.item_id)
                except Exception:  # noqa: BLE001 - a gem that does not fit this socket
                    continue
                return game.tr(
                    "workshop.socketed",
                    "Socketed {name} into {socket}",
                    name=item.display_name,
                    socket=socket.socket_id,
                )
        return game.tr(
            "workshop.nothing_to_socket",
            "Nothing to socket (no free socket or no fitting item in the bag)",
        )

    def _spend_attribute_point(self, actor):
        allocation = self.save.rpg_state.progression_allocations[actor]
        graph = allocation.definitions.get("attributes")
        if graph is None:
            return self.game.tr("workshop.no_attributes", "This project has no attribute graph")
        for node in graph.nodes:
            try:
                allocation.allocate("attributes", node.node_id)
            except ValueError:
                continue
            self.game.refresh_actor_combatants(actor)
            return self.game.tr("workshop.point_spent", "+1 {name}", name=node.display_name)
        return self.game.tr("workshop.no_points", "No attribute points left")

    def _draw_workshop(self):
        self._draw_field(False)
        overlay = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
        overlay.fill((6, 9, 18, 220))
        self.screen.blit(overlay, (0, 0))
        actor = self._menu_actor()
        if actor is None:
            return
        game = self.game
        weapon = self._current_weapon(actor)
        allocation = self.save.rpg_state.progression_allocations[actor]
        rules = game.refine_rules
        self.panel((24, 22, 912, 496), fill=(11, 15, 25, 242))
        tr = game.tr
        self.text(tr("workshop.title", "Workshop"), 44, 38, size=30, color=(255, 220, 120))
        self.text(
            tr(
                "workshop.keys",
                "R Refine   S Socket   X Take out   A Attribute point   C Back  [{actor}]",
                actor=actor,
            ),
            44,
            76,
            size=18,
        )
        gold = self.save.rpg_state.currencies.get("gold", 0)
        gold = tr("workshop.gold", "Gold {amount}", amount=int(gold))
        self.text(gold, 760, 40, size=20, color=(255, 214, 120))
        y = 120
        if weapon is None:
            self.text(tr("workshop.no_weapon", "No weapon equipped"), 44, y, size=22)
        else:
            self.text(f"{weapon.equipment.display_name}  +{weapon.refine_level}", 44, y, size=26)
            if rules is not None and weapon.refine_level < rules.max_level:
                chance = round(rules.chance(weapon.refine_level) * 100)
                self.text(
                    tr(
                        "workshop.next",
                        "Next +{level}: {chance}% for {cost} {currency}",
                        level=weapon.refine_level + 1,
                        chance=chance,
                        cost=int(rules.cost(weapon.refine_level)),
                        currency=rules.currency,
                    ),
                    44,
                    y + 34,
                    size=18,
                    color=(170, 220, 255),
                )
            y += 80
            for socket in weapon.equipment.sockets:
                attached = weapon.attachments.get(socket.socket_id)
                if attached is not None:
                    label = attached.display_name
                elif socket.locked:
                    label = tr("workshop.locked", "locked")
                else:
                    label = tr("workshop.empty", "empty")
                self.text(
                    tr(
                        "workshop.socket",
                        "Socket {socket}: {value}",
                        socket=socket.socket_id,
                        value=label,
                    ),
                    64,
                    y,
                    size=20,
                )
                y += 30
        graph = allocation.definitions.get("attributes")
        if graph is not None:
            self.text(
                tr(
                    "workshop.points",
                    "Attribute points: {count}",
                    count=int(allocation.balance("stat_points")),
                ),
                520,
                120,
                size=22,
                color=(255, 220, 120),
            )
            ranks = allocation.allocations.get("attributes", {})
            for i, node in enumerate(graph.nodes):
                self.text(
                    f"{node.display_name}: {ranks.get(node.node_id, 0)}",
                    540,
                    160 + i * 30,
                    size=20,
                )
        self.text(getattr(self, "_workshop_message", ""), 44, 470, size=20, color=(170, 210, 240))

    def _battle_actor(self):
        return None if self.game.battle is None else self._turn_actor

    def _finish_battle_victory(self):
        """Every foe is down: rewards, levels, the victory screen and jingle."""
        try:
            before = self.game.capture_hero_state()
            applied = self.game.finish_victory()
            self._victory_summary = []
            rewards = self.manifest.get("progression_rewards", {})
            gained = {}
            for hero_id in self.save.rpg_state.party_active_actor_ids:
                gained[hero_id] = rewards.get("experience", 1600)
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
            self._victory_screen = None
            if self.manifest.get("battle", {}).get("victory_aftermath"):
                self._victory_screen = self._make_victory_screen(applied, before, gained)
            self._victory = True
            # The jingle waits for the presentation to finish showing the final blows.
            self._victory_audio_pending = True  # played by _present_battle once the screen is idle
            self._last_action_name = "Victory — rewards + progression applied"
        except Exception as exc:
            self._last_action_name = f"Victory finalize failed: {exc}"

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
        elif not self.game.active_enemy_ids() and not self._victory:
            self._finish_battle_victory()  # the last foe fell on its own turn (poison, burn...)

    @property
    def battle_commands(self):
        """The player's battle command menu for the current game (skills, items, concoct, boost,
        targets)."""
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
            screen = getattr(self, "_victory_screen", None)
            if screen is not None and self._victory and not self._presentation_busy():
                screen.update(dt)
                screen.draw(self)
        self._flush_victory_audio()

    def _draw_battle_extras(self):
        """Shield and weaknesses under each enemy, boost points under each hero (unless the
        party panel has them), the chosen boost level (runtime/battle_extras.py)."""
        game, adapter = self.game, self._battle_presentation
        box = getattr(adapter, "member_screen_box", None)
        if game.battle is None or box is None or self._victory or self._defeat:
            return
        pg, battle = self.pg, game.battle
        scale = getattr(getattr(adapter, "textures", None), "scale", 3.0)
        composer = getattr(getattr(adapter, "screen", None), "composer", None)
        ui_layout = getattr(composer, "layout", None)
        below = ui_layout is not None and getattr(ui_layout, "overhead_below", False)
        drop = 17.0 * scale if below and getattr(ui_layout, "overhead_zones", ()) else 0.0
        shown = [  # zones whose combatants float a name and bar over the head
            z
            for z in getattr(ui_layout, "overhead_zones", ())
            if z not in getattr(ui_layout, "hidden_zones", ())
        ]
        head_gap = 24.0 * scale if shown and not below else None  # past that name and bar
        labels = getattr(composer, "overhead_labels", None) or {}
        caption_at = {  # state names fill the line each overhead label kept over the name
            member_id: ((x + w / 2) * scale, (y + 8.0) * scale)
            for member_id, (x, y, w, _h) in labels.items()
        }
        zones = getattr(getattr(adapter, "screen", None), "placement_by_member", None) or {}
        follows = {m for m, zone in zones.items() if zone in shown}  # names over heads
        blocks = extras_layout(
            game, box, scale, self.width, drop, head_gap, caption_at, caption_follows=follows
        )
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
                from asteria.presentation.text_cells import cut

                label = cut(" ".join(names), 28)  # a Chinese name takes the room of two letters
                self.text(label, x, y + 20, size=15, color=(220, 180, 255), center=True)
        actor = self._battle_actor()
        commands = getattr(self, "_battle_commands", None)
        if actor is not None and commands is not None and commands.game is game:
            where = box(actor)
            if where is not None and commands.boost:
                self.text(
                    game.tr("battle.boost_level", "BOOST x{level}", level=commands.boost + 1),
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
        if self.game.battle is None:  # the party ran away: no reward, back on the field
            self._turn_actor = None
            self._last_action_name = "Got away safely"
            return
        self.game.end_turn()
        if not self.game.active_enemy_ids():
            self._finish_battle_victory()
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
            **({pg.K_t: "auto"} if self.battle_option("auto_key") else {}),
        }

    def _make_victory_screen(self, applied, before, gained):
        from .victory_screen import VictoryScreen

        db = self.game.project.rpg_database
        aftermath = self.game.build_aftermath(applied, before, gained)
        return VictoryScreen(
            aftermath,
            item_names={k: v.display_name for k, v in {**db.items, **db.equipment}.items()},
            tr=self.game.tr,
        )

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
                    screen = getattr(self, "_victory_screen", None)
                    if screen is not None and not screen.confirm():
                        continue  # the next results page
                    self._victory_screen = None
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
        if self._multiplayer_connected() or self._network_gameplay_frozen():
            self._send_multiplayer_input(0, 0, {})
            self._ui_mode = "title"
            return
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
                except Exception as exc:  # noqa: BLE001 - shown to the player, play goes on
                    menu.message = translated(exc, self.game.tr)

    def _draw_status_menu(self):
        from asteria.runtime.status_menu import TAB_WORDS, TABS

        self._draw_field(False)
        shade = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
        shade.fill((6, 9, 18, 215))
        self.screen.blit(shade, (0, 0))
        menu = self.status_menu
        tr = self.game.tr
        self.panel((24, 22, self.width - 48, self.height - 44), fill=(11, 15, 25, 242))
        x = 44
        for tab in TABS:
            label = tr(TAB_WORDS[tab], tab.title())
            active = tab == menu.tab
            self.text(label, x, 36, size=24, color=(255, 220, 120) if active else (150, 160, 180))
            x += 150
        actor = menu.actor_id or "—"
        name = getattr(self.project.rpg_database.actors.get(actor), "display_name", actor)
        member = tr("status.member", "Q / E  {name}", name=name)
        self.text(member, self.width - 330, 40, size=20, color=(170, 220, 255))
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
            empty = tr("status.empty", "Nothing here yet.")
            self.text(empty, 56, 92, size=20, color=(150, 160, 180))
        hint = tr(
            "status.hint",
            "Tab: next tab   Up/Down: choose   Enter: use / equip / unequip   Esc: back",
        )
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
        elif choice in ("backlog", "music", "credits", "skill_slots"):
            from asteria.runtime import extras_screens

            screen = {
                "backlog": extras_screens.BacklogScreen,
                "music": extras_screens.MusicRoomScreen,
                "credits": extras_screens.CreditsScreen,
                "skill_slots": extras_screens.AbilitySlotsScreen,
            }[choice]
            self._extra_screen = screen(self)
            self._ui_mode = "extra"
        elif choice.startswith("entry:"):
            self._run_menu_entry(choice[len("entry:") :])
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

    def _run_menu_entry(self, entry_id):
        """A project-defined pause entry: close the menu and queue its event program."""
        entry = self.project.rpg_database.menu_entries.get(entry_id)
        if entry is None:
            return
        context = self.game.save.event_context
        if entry.visible_switch and not context.get_switch(entry.visible_switch):
            return
        if entry.enabled_switch and not context.get_switch(entry.enabled_switch):
            return
        self._ui_mode = "field"
        self.game.pending_followups.append(entry.event_program_id)

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
        if self._multiplayer_connected():
            from asteria.runtime.network_bag_screen import NetworkCraftingScreen

            self._crafting_screen = NetworkCraftingScreen(self, station)
        else:
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
                    self.project.input_map, self.settings.input_overrides, tr=self.game.tr
                )
                self._ui_mode = "controls"
            return
        delta = (1 if self.input.just_pressed("move_right") else 0) - (
            1 if self.input.just_pressed("move_left") else 0
        )
        if self.input.just_pressed("confirm") and key in ("show_battle_log", "language"):
            delta = 1
        if delta and key == "language":
            locales = self.game.localizer.locales()
            current = self.game.localizer.locale
            index = locales.index(current) if current in locales else 0
            self.game.set_locale(locales[(index + delta) % len(locales)])
            return
        if delta:
            self.settings.adjust(key, delta)
            self.settings.apply(self.audio)

    # -- save slots (ENG-21) ----------------------------------------------------------------------
    def _slot_exists(self, slot):
        from asteria.runtime.save_slots import SaveSlots

        return SaveSlots(self.resource_root / "saves", self.project).path(slot).exists()

    def open_slots(self, mode, back="pause"):
        if self._multiplayer_connected() or self._network_gameplay_frozen():
            self._server_save_command(mode)
            self._ui_mode = "field" if mode == "load" else back
            return
        from asteria.runtime.save_slots import SaveSlots, SlotMenu

        self.slot_menu = SlotMenu(
            SaveSlots(self.resource_root / "saves", self.project), mode, tr=self.game.tr
        )
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
                    self.message = self.game.tr(
                        "slots.loaded", "Loaded slot {slot}", slot=menu.slot
                    )
                    self.message_until = self.pg.time.get_ticks() + 1800
                elif outcome == "saved":
                    self.message = menu.message
                    self.message_until = self.pg.time.get_ticks() + 1800

    def _draw_slots(self):
        self._draw_backdrop()
        menu = self.slot_menu
        self.panel((100, 60, self.width - 200, self.height - 120))
        tr = self.game.tr  # the slot screens' titles are the pause menu's own words
        title = (
            tr("pause.save", "Save Game") if menu.mode == "save" else tr("pause.load", "Load Game")
        )
        self.text(title, self.width / 2, 76, size=32, color=(255, 220, 124), center=True)
        for i, info in enumerate(menu.rows()):
            y = 140 + i * 64
            selected = i == menu.row
            if selected:
                self.pg.draw.rect(
                    self.screen, (40, 52, 78), (120, y - 8, self.width - 240, 54), border_radius=6
                )
            if info.slot == "autosave":
                name = tr("slots.autosave", "Autosave (F5)")
            else:
                name = tr("slots.slot", "Slot {slot}", slot=info.slot)
            self.text(
                name, 140, y, size=24, color=(255, 226, 129) if selected else (235, 238, 245)
            )
            self.text(info.summary_text(tr), 140, y + 24, size=18, color=(170, 210, 240))
        hint = menu.message or tr("slots.hint", "Enter: choose   Delete: erase   Esc: back")
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
        tr = self.game.tr
        title = tr("controls.title", "Controls")
        self.text(title, self.width / 2, 44, size=32, color=(255, 220, 124), center=True)
        for i, (action, bindings) in enumerate(menu.rows()):
            y = 92 + i * 30
            selected = i == menu.row
            color = (255, 226, 129) if selected else (235, 238, 245)
            self.menu_row(menu.action_name(action), 90, y, selected=selected, size=21, color=color)
            self.text(bindings, self.width / 2, y, size=21, color=(170, 210, 240))
        hint = menu.message or tr(
            "controls.hint", "Enter: rebind   Backspace: reset action   Esc: save and back"
        )
        self.text(
            hint, self.width / 2, self.height - 58, size=19, color=(255, 226, 129), center=True
        )

    def _draw_crafting(self):
        screen = self._crafting_screen
        self._draw_backdrop()
        if screen is None:
            return
        self.panel((60, 40, self.width - 120, self.height - 80))
        tr = self.game.tr
        title = tr("pause.crafting", "Crafting") + (
            f" — {screen.station.replace('_', ' ').title()}" if screen.station else ""
        )
        self.text(title, 90, 54, size=30, color=(255, 220, 124))
        rows = screen.rows()
        if not rows:
            empty = tr("crafting.none", "No known recipes here.")
            self.text(empty, 90, 110, size=22, color=(170, 210, 240))
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
            self.menu_row(
                f"{row.name}  ->  {row.outputs}", 90, y, selected=selected, size=22, color=color
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
                tr("crafting.hidden", "??? {count} recipe(s) not yet discovered", count=hidden),
                90,
                self.height - 128,
                size=18,
                color=(150, 155, 175),
            )
        if screen.message:
            self.text(screen.message, 90, self.height - 100, size=20, color=(255, 220, 124))
        self.text(
            tr("crafting.hint", "Up/Down: select   Enter: craft   Esc: back"),
            90,
            self.height - 72,
            size=18,
            color=(170, 210, 240),
        )

    def _draw_list_screen(self, kind):
        self._draw_backdrop()
        self.panel((60, 40, self.width - 120, self.height - 80))
        tr = self.game.tr
        line_icons = []  # an icon per line (achievements may carry one)
        if kind == "achievements":
            rows = achievement_rows(self.game)
            by_name = {
                a.display_name: a.icon_id for a in self.project.rpg_database.achievements.values()
            }
            line_icons = [by_name.get(name, "") for name, _description, _unlocked in rows]
            done = sum(1 for r in rows if r[2])
            self.text(
                tr(
                    "achievements.title",
                    "Achievements  {done}/{count}",
                    done=done,
                    count=len(rows),
                ),
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
                tr("bestiary.title", "Bestiary  {seen}/{count} seen", seen=seen, count=len(rows)),
                self.width / 2,
                56,
                size=30,
                color=(255, 220, 124),
                center=True,
            )
            lines = [
                (name, self._bestiary_detail(row), (235, 238, 245) if row[1] else (150, 155, 175))
                for row in rows
                for name in (row[0],)
            ]
        if not lines:
            self.text(
                tr("status.empty", "Nothing here yet."), 90, 110, size=22, color=(170, 210, 240)
            )
        self._list_scroll = min(self._list_scroll, max(0, len(lines) - 1))
        y = 104
        shift = 30 if any(line_icons) else 0
        for number, (title, detail, color) in enumerate(lines[self._list_scroll :]):
            if y > self.height - 110:
                break
            index = self._list_scroll + number
            if index < len(line_icons) and line_icons[index]:
                self._draw_icon(line_icons[index], 90, y - 2, 24)
            self.text(title, 90 + shift, y, size=22, color=color)
            y += 24
            for part in detail.split("\n") if detail else ():
                self.text(part, 120, y, size=17, color=(170, 210, 240))
                y += 22
            y += 6
        self.text(
            tr("list.hint", "Up/Down: scroll   Enter / Esc: back"),
            self.width - 360,
            self.height - 72,
            size=18,
            color=(170, 210, 240),
        )

    def _resource_labels(self):
        """Resource id -> the short label the battle HUD gives it (``vitality`` -> ``HP``)."""
        labels = {}
        library = getattr(self.project, "battle_presentation_library", None)
        for key in library.ids("hud") if library is not None else ():
            for style in getattr(library.require("hud", key), "resources", ()):
                labels.setdefault(style.resource_id, style.label or style.resource_id)
        return labels

    def _bestiary_detail(self, row):
        """The lines under a bestiary entry: counts; weaknesses and resources once one fell;
        the drops that really fell."""
        _name, seen, defeated, captured, tags, resources, drops = row
        if not seen:
            return ""
        tr = self.game.tr
        lines = [
            tr(
                "bestiary.counts",
                "seen {seen}   defeated {defeated}   captured {captured}",
                seen=seen,
                defeated=defeated,
                captured=captured,
            )
        ]
        if defeated:
            labels = self._resource_labels()
            known = [f"{labels.get(r, r)} {v:,.0f}" for r, v in resources]
            groups = {}
            for tag in tags:
                kind, _, what = tag.partition(".")
                groups.setdefault(kind, []).append(what.replace("_", " "))
            for kind, names in sorted(groups.items()):  # weak / resist...: the kind is drawn
                word = tr(f"bestiary.tag.{kind}", kind) if kind in BESTIARY_TAG_KINDS else kind
                known.append(f"{word}: {', '.join(names)}")
            lines.append("   ".join(known) or tr("bestiary.nothing_special", "nothing special"))
        else:
            lines.append(tr("bestiary.unknown", "Defeat one to learn its weaknesses and health."))
        if drops:
            found = ", ".join(f"{n} x{t}" for n, t in drops)
            lines.append(tr("bestiary.drops", "Drops: {items}", items=found))
        else:
            lines.append(tr("bestiary.no_drops", "Drops: none seen yet"))
        return "\n".join(lines)

    def _language_name(self):
        """The chosen locale as its own table calls it (``language.name``), else its code."""
        localizer = self.game.localizer
        return localizer.tr("language.name", localizer.locale)

    def _draw_settings(self):
        self._draw_backdrop()
        cursor = self._settings_menu
        tall = max(260, 120 + len(cursor.options) * 38)  # every row inside the panel
        x, y = self.width / 2 - 220, self.height / 2 - tall / 2
        self.panel((x, y, 440, tall))
        tr = self.game.tr
        title = tr("pause.settings", "Settings")
        self.text(title, self.width / 2, y + 18, size=34, color=(255, 220, 124), center=True)
        for i, (key, label) in enumerate(cursor.labels(tr)):
            selected = i == cursor.index
            color = (255, 226, 129) if selected else (235, 238, 245)
            self.menu_row(label, x + 40, y + 76 + i * 38, selected=selected, size=24, color=color)
            if key == "language":
                value = self._language_name()
            else:
                value = self.settings.value_text(key, tr)
            if value:
                self.text(
                    f"< {value} >" if selected else value,
                    x + 300,
                    y + 76 + i * 38,
                    size=24,
                    color=color,
                )
        self.text(
            tr("settings.hint", "Left/Right: change   Esc: save and back"),
            self.width / 2,
            y + tall - 24,
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
        shift = 30 if cursor.icons else 0  # room for the rows' icons: the panel grows with it
        x, y = self.width / 2 - 170 - shift / 2, self.height / 2 - height / 2
        self.panel((x, y, 340 + shift, height))
        self.text(title, self.width / 2, y + 18, size=34, color=(255, 220, 124), center=True)
        for i, (option_id, label) in enumerate(cursor.labels(self.game.tr)):
            selected = i == cursor.index
            if option_id in cursor.icons:
                self._draw_icon(cursor.icons[option_id], round(x + 36), round(y + 68 + i * 34), 26)
            self.menu_row(
                label,
                x + 40 + shift,
                y + 70 + i * 34,
                selected=selected,
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
        tr = self.game.tr
        title = tr("pause.quests", "Quest Log")
        self.text(title, self.width / 2, 56, size=32, color=(255, 220, 124), center=True)
        rows = quest_rows(self.game)
        if not rows:
            self.text(tr("quests.none", "No quests yet."), 90, 110, size=22, color=(170, 210, 240))
        y = 104
        colors = {
            "active": (235, 238, 245),
            "completed": (130, 220, 150),
            "failed": (230, 120, 120),
        }
        for row in rows:
            if y > self.height - 110:
                break
            icon = self.project.rpg_database.quests[row.quest_id].icon_id
            if icon:
                self._draw_icon(icon, 90, y - 2, 24)
            status = tr(f"quests.status.{row.status}", row.status)  # the status is an id
            self.text(
                f"{row.name}  [{status}]",
                90 + (30 if icon else 0),
                y,
                size=24,
                color=colors[row.status],
            )
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
            tr("quests.hint", "Enter / Esc: back"),
            self.width - 260,
            self.height - 72,
            size=18,
            color=(170, 210, 240),
        )

    def _draw_shop(self):
        screen = self._shop_screen
        self._draw_backdrop()
        if screen is None or screen.shop is None:
            return
        self.panel((60, 40, self.width - 120, self.height - 80))
        shop_icon = screen.shop.icon_id
        if shop_icon:
            self._draw_icon(shop_icon, 90, 50, 32)
        self.text(
            screen.shop.display_name,
            90 + (40 if shop_icon else 0),
            54,
            size=30,
            color=(255, 220, 124),
        )
        tr = self.game.tr
        for i, tab in enumerate(("buy", "sell")):
            self.text(
                tr(f"shop.{tab}", tab.title()),
                self.width - 300 + i * 100,
                60,
                size=24,
                color=(255, 226, 129) if screen.tab == tab else (130, 140, 160),
            )
        self.text(tr("shop.item", "Item"), 90, 104, size=19, color=(170, 210, 240))
        self.text(tr("shop.price", "Price"), 420, 104, size=19, color=(170, 210, 240))
        self.text(tr("shop.stock", "Stock"), 640, 104, size=19, color=(170, 210, 240))
        self.text(tr("shop.owned", "Owned"), 740, 104, size=19, color=(170, 210, 240))
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
            if i == screen.index:
                self.menu_mark(72, y, size=22, color=color)
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
            tr(
                "shop.hint",
                "Up/Down: select   Left/Right: buy/sell   Enter: confirm   Esc: leave",
            ),
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
        tr = self.game.tr
        try:
            captured = self.game.attempt_capture(actor, target_id)
        except Exception as exc:
            reason = translated(exc, tr)
            self._last_action_name = tr(
                "capture.failed", "Capture failed: {reason}", reason=reason
            )
            return False
        if captured:
            self._last_action_name = tr("capture.caught", "Captured {name}!", name=name)
        else:
            self._last_action_name = tr("capture.broke_free", "{name} broke free", name=name)
        self._sound(self.manifest.get("dialogue_confirm_sfx") if captured else None)
        self._after_hero_action()
        return captured

    def _draw_capture_menu(self):
        targets = self.game.capture_targets()
        height = 70 + 30 * max(1, len(targets))
        self.panel((300, 190, 360, height), fill=(12, 18, 28, 240), border=(130, 200, 255))
        tr = self.game.tr
        title = tr("capture.title", "Capture")
        self.text(title, 480, 200, size=28, color=(175, 235, 255), center=True)
        inventory = self.save.rpg_state.inventory
        for i, (member_id, chance, item_id) in enumerate(targets, 1):
            name = member_id.split(":", 1)[0].replace("_", " ").title()
            need = ""
            if item_id:
                need = "  " + tr(
                    "capture.uses",
                    "(uses {item}: {count})",
                    item=item_id,
                    count=inventory.count(item_id),
                )
            self.text(f"{i}. {name}  {chance * 100:.0f}%{need}", 320, 236 + (i - 1) * 30, size=20)
        self.text(
            tr("capture.cancel", "Esc: cancel"),
            480,
            190 + height - 24,
            size=16,
            color=(170, 210, 240),
            center=True,
        )

    def save_playtest(self):
        if self._multiplayer_connected() or self._network_gameplay_frozen():
            self._server_save_command("save")
            return None
        self.game.sync_world_state()
        out = self.resource_root / "saves" / "playtest_autosave.asteria-save.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        self.save.save_json(out)
        self.message = self.game.tr("field.saved", "Saved: {file}", file=out.name)
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
        self._adopt_new_game_plus()
        self._update_resource_scope()
        self._update_popups(float(dt))
        if self.debug_server is not None:
            self.debug_server.poll()
        with self.profiler.section("input"):
            self.input_source.handle_events(events)
            self.input.update(self.input_source.raw_state())
        if self._network_gameplay_frozen():
            for event in events:
                if event.type == self.pg.QUIT:
                    self.running = False
                elif event.type == self.pg.KEYDOWN and event.key == self.pg.K_F3:
                    if self.multiplayer_bridge.connect():
                        self._network_revision = -1
                        self._multiplayer_error = ""
                        self._sync_multiplayer_player()
            if self._network_gameplay_frozen():
                if self._ui_mode == "title":
                    self._draw_title()
                else:
                    self._draw_field(False)
                self.panel((100, self.height / 2 - 32, self.width - 200, 64))
                self.text(
                    self.game.tr("coop.paused", "Server connection paused · F3 to retry"),
                    self.width / 2,
                    self.height / 2 - 10,
                    size=22,
                    center=True,
                    color=(255, 190, 132),
                )
                return
        if self._multiplayer_connected():
            self._sync_multiplayer_player()
            for result in self.multiplayer_bridge.command_results(self._network_revision):
                self.message = (
                    self.game.tr(
                        "coop.confirmed",
                        "Server {command} confirmed",
                        command=result.get("command", "command"),
                    )
                    if result["accepted"]
                    else result.get(
                        "reason", self.game.tr("coop.rejected", "Server rejected command")
                    )
                )
                self.message_until = self.pg.time.get_ticks() + 2500
            if self._ui_mode != "field":
                self._send_multiplayer_input(0, 0, {})
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
                if request.name == "PLAY_BGM":
                    self.game.note_music_heard(request.args.get("asset_id", ""))
                    self._bgm_override = request.args.get("asset_id", "")
                elif request.name == "STOP_BGM":
                    self._bgm_override = ""
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
        elif self._ui_mode == "workshop":
            self._workshop_input(events)
            self._draw_workshop()
        elif self._ui_mode == "pause":
            self._pause_input()
            self._draw_overlay_menu(self.game.tr("pause.heading", "Paused"), self._pause_menu)
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
        elif self._ui_mode == "extra":
            self._extra_screen.handle(dt, events)
            if self._extra_screen.closed:
                self._ui_mode = "pause"
            else:
                self._extra_screen.draw()
        elif self._ui_mode == "pets":
            self._pets_screen.handle(dt, events)
            if self._pets_screen.closed:
                self._ui_mode = "pause"
            else:
                self._pets_screen.draw()
        elif self._ui_mode == "skills":
            self._skill_tree.handle(dt, events)
            if self._skill_tree.closed:
                self._ui_mode = "field"
            else:
                self._skill_tree.draw()
        elif self._ui_mode == "game_over":
            self._game_over_input()
            title = self.game.tr("game_over.heading", "Game Over")
            self._draw_overlay_menu(title, self._game_over_menu, base="battle")
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
            if not self._multiplayer_connected():
                with self.profiler.section("events"):
                    self.game.update_events(dt)
            if (
                self._ui_mode == "field"
                and self.game.open_shop_id
                and not (
                    getattr(self, "_network_event_busy", False)
                    if self._multiplayer_connected()
                    else self.game.event_busy
                )
            ):
                self._shop_screen = ShopScreen(self.game)
                self._ui_mode = "shop"
            if (
                self._ui_mode == "field"
                and self.game.open_crafting_station is not None
                and not (
                    getattr(self, "_network_event_busy", False)
                    if self._multiplayer_connected()
                    else self.game.event_busy
                )
            ):
                self._open_crafting(self.game.open_crafting_station, back="field")
            if self.game.mode == "field" and self._ui_mode == "field":
                if not self._multiplayer_connected():
                    with self.profiler.section("update"):
                        self.game.field_update(dt)
                self._sync_multiplayer_player()
                if self.game.action_scene:
                    self.action_hud.observe(self.game, dt)
                    if self._multiplayer_connected():
                        self.game.combat.events = ()
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
            self._skeleton_scene_runtime.update(self.game.scene, dt)
            if self.game.mode == "battle":
                self._turn_actor = None
                self._battle_presentation.begin()
                self._music(self.manifest["battle"].get("bgm"))
                self._advance_to_hero_turn()
                self._present_battle(dt)
            else:
                override = getattr(self, "_bgm_override", None)  # a story event chose the track
                self._music(self.manifest["field"].get("bgm") if override is None else override)
                self._preload_battle_images()
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
