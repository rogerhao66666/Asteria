from __future__ import annotations

import os
from pathlib import Path

from asteria.core import Transform
from asteria.graphics.scaling import ScaledImageCache
from asteria.runtime.audio_mixer import AudioMixer
from asteria.runtime.battle_presentation_adapters import create_battle_presentation_adapter
from asteria.runtime.field_camera import (
    CAMERA_COMMANDS,
    FieldCameraError,
)
from asteria.runtime.field_presentation import (
    FIELD_EFFECT_COMMANDS,
    FieldEffectError,
)
from asteria.runtime.game_menus import (
    GAME_OVER_OPTIONS,
    PAUSE_OPTIONS,
    GameSettings,
    MenuCursor,
    ShopScreen,
    text_keys,
)
from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.game_session import GameSessionRuntime
from asteria.runtime.input_map import InputActionTracker
from asteria.runtime.playtest.action_scenes import ActionSceneMixin
from asteria.runtime.playtest.battle_flow import BattleFlowMixin
from asteria.runtime.playtest.capture import CaptureMixin
from asteria.runtime.playtest.environment import EnvironmentMixin
from asteria.runtime.playtest.field_ui import FieldUiMixin
from asteria.runtime.playtest.field_view import FieldViewMixin
from asteria.runtime.playtest.menus_draw import MenusDrawMixin
from asteria.runtime.playtest.menus_input import MenusInputMixin
from asteria.runtime.playtest.multiplayer import MultiplayerMixin
from asteria.runtime.playtest.resources import ResourceMixin
from asteria.runtime.playtest.save_slots import SaveSlotsMixin
from asteria.runtime.playtest.support import (  # noqa: F401 - re-exported
    BESTIARY_TAG_KINDS,
    FIELD_BODY_HEIGHT,
    WALK_PATTERN_SEQUENCE,
    WALK_ROW_BY_FACING,
    _load_manifest,
    field_player_render_size,
    walking_pattern_index,
    walking_row_index,
)
from asteria.runtime.playtest.text_draw import TextDrawMixin
from asteria.runtime.playtest.title_build import TitleBuildMixin
from asteria.runtime.playtest.workshop import WorkshopMixin
from asteria.runtime.profiler import NullProfiler, RuntimeProfiler
from asteria.runtime.skeleton_component import SkeletonSceneRuntime


class PlayableTestRuntime(
    ResourceMixin,
    EnvironmentMixin,
    TextDrawMixin,
    FieldViewMixin,
    MultiplayerMixin,
    FieldUiMixin,
    ActionSceneMixin,
    TitleBuildMixin,
    WorkshopMixin,
    BattleFlowMixin,
    MenusInputMixin,
    SaveSlotsMixin,
    MenusDrawMixin,
    CaptureMixin,
):
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
        self.multiplayer_profile_error = ""
        self.multiplayer_profile = self.multiplayer_bridge = None
        try:
            from asteria.runtime.multiplayer_preview import (
                MultiplayerPreviewBridge,
                load_runtime_multiplayer_profile,
            )
        except ImportError as exc:  # a build without the multiplayer package (the web export)
            if (self.resource_root / ".asteria" / "multiplayer.json").is_file():
                self.multiplayer_profile_error = f"multiplayer is not part of this build ({exc})"
        else:
            try:
                self.multiplayer_profile = load_runtime_multiplayer_profile(self.resource_root)
            except ValueError as exc:
                self.multiplayer_profile_error = str(exc)
            if self.multiplayer_profile is not None:
                self.multiplayer_bridge = MultiplayerPreviewBridge(self.multiplayer_profile)
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
        self._scaled = ScaledImageCache()  # resized field sprites, dropped with the pictures
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
        db = self.project.rpg_database
        loadouts = getattr(self.save.rpg_state, "loadouts", None)
        gear = []
        if loadouts:  # U3: the paper doll, and the enhance screen when gear can change
            gear.append(("equipment", "Equipment"))
            if db.refine_rules or any(e.sockets or e.growth_id for e in db.equipment.values()):
                gear.append(("enhance", "Enhance"))
        options[2:2] = gear
        if getattr(self.project.rpg_database, "pet_species", None):  # a game with pets
            options.insert(2 + len(gear), ("pets", "Pets"))
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
        self._creature_menu = None  # field.creature_menu: the start menu and its screens
        self._creature_shop = None  # field.creature_shop: a shop in the game's own art
        self._name_input = None  # NAME_INPUT: the name screen
        self._picture_choice = None  # PICTURE_CHOICE: a choice of pictured options
        self._game_over_menu = MenuCursor(
            GAME_OVER_OPTIONS, keys=text_keys("game_over", GAME_OVER_OPTIONS)
        )
        self._shop_screen = None
        self._quest_return = "field"
        self._capture_menu = False
        self._creature_battle = None  # the one-on-one creature battle screen while it runs
        self._capture_item_menu = None  # the target whose capture item is being chosen
        self._switch_menu = False  # a creature fell: choosing who comes in from the bench
        self._crafting_screen = None
        self._service_screen = None
        self._list_scroll = 0
        self.settings = GameSettings.load(self._settings_path())
        settings_options = list(GameSettings.OPTIONS)
        if len(self.game.localizer.locales()) > 1:  # a translated game: the player picks one
            settings_options.insert(-2, ("language", "Language"))
        self._settings_menu = MenuCursor(
            settings_options, keys=text_keys("settings", settings_options)
        )

    def enable_debugger(self, *, port=0, token=None):
        """Start the editor debug channel (EDT-10); returns the DebugServer."""
        from asteria.runtime.debug_server import DebugServer
        from asteria.runtime.debugger import RuntimeDebugger

        self.debug_server = DebugServer(RuntimeDebugger(self.game, self), port=port, token=token)
        return self.debug_server

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
        # the editor's "Open in game" (Menu Screens ▸ Layout): start on that menu screen
        start_menu = os.environ.pop("ASTERIA_OPEN_MENU", "")
        if start_menu:
            from asteria.runtime.menu_preview import open_menu_screen

            open_menu_screen(self, start_menu)
        if profile_path is not None:
            self.enable_profiling(target_fps=target_fps)
        frames = 0
        try:
            while self.running:
                self.step(self.tick(target_fps))
                frames += 1
                if max_frames is not None and frames >= max_frames:
                    break
        finally:
            if profile_path is not None:
                self.profiler.write(profile_path)
                self.profiler.close()
            self.close()
        return 0

    def _creature_shop_frame(self, dt, events):
        """``field.creature_shop``: the screen over the field; on its buy screen the field's
        camera puts the cell the player faces at ``map_front_at`` (the map beside the goods)."""
        from asteria.runtime.creature_shop import MAP_PHASES

        shop = self._creature_shop
        shop.update(dt, events)
        view = getattr(self, "tile_view", None)
        if shop.done:
            self._creature_shop = None
            self._ui_mode = "field"
            if view is not None:
                view.player_at = None
            self._draw_field(False)
            return
        if view is not None:
            front = shop.shop_settings.get("map_front_at")
            if front and shop.phase in MAP_PHASES:
                dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}.get(
                    self.game.facing, (0, -1)
                )
                tile = view.tilemap.tile_width
                view.player_at = (front[0] - dx * tile, front[1] - dy * tile)
            else:
                view.player_at = None
            view.follow(0.0)  # the field does not update under a screen: place it now
        if shop.phase in ("menu", *MAP_PHASES):
            self._draw_field(False)
        shop.draw()

    def _audio_status(self):
        """Fanfares end and give the music back; the ``audio`` condition source (``me``,
        ``se``) tells the event programs waiting for them."""
        self.audio.update()
        self.game.plays_audio = True
        status = self.game.audio_status
        status["me"], status["se"] = self.audio.me_playing(), self.audio.se_playing()

    def step(self, dt, events=None):
        """One whole frame: pygame's events (or ``events``), the game, drawing and the flip,
        with the profiler's frame around it. ``run`` calls it after waiting for the frame's
        time; a browser build calls it from its own async loop (``asteria.export_web``)."""
        self.profiler.begin_frame()
        self._frame(self.pg.event.get() if events is None else events, dt)
        with self.profiler.section("present"):
            self.present()
        self._sample_counters()
        self.profiler.end_frame()

    def _frame(self, events, dt):
        """Process one frame of input, event programs and drawing (no flip)."""
        self._frame_dt = float(dt)
        self._clock_seconds += float(dt)
        if (  # the time played (saved with the world: card, save); a network game's is not
            self._ui_mode != "title"
            and not self._multiplayer_connected()
            and not self._network_gameplay_frozen()
        ):
            self.game.world.add_counter("play.seconds", float(dt))
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
                    # a temporary track (a trainer's encounter music) lasts until a battle
                    self._bgm_temporary = bool(request.args.get("temporary"))
                elif request.name == "STOP_BGM":
                    self._bgm_override = ""
                elif request.name == "RESTORE_BGM":  # back to the area's own music
                    self._bgm_override, self._bgm_temporary = None, False
        self._audio_status()
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

        self.menu_sounds()  # the menu theme's open / move / confirm / cancel sounds (U2)
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
        elif self._ui_mode in ("equipment", "enhance"):
            screen = self._gear_screen
            screen.handle(dt, events)
            if screen.closed:
                self._ui_mode = screen.back
            else:
                screen.draw()
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
            self._crafting_input(events)
            self._draw_crafting()
        elif self._ui_mode == "service":  # a quest board, recruiting office or gacha (U5)
            screen = self._service_screen
            screen.handle(dt, events)
            if screen.closed:
                self._service_screen = None
                self._ui_mode = screen.back
            else:
                screen.draw()
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
        elif self._ui_mode == "creature_menu":  # the start menu in the game's own art
            menu = self._creature_menu
            menu.update(dt, events)
            if menu.done:
                self._creature_menu = None
                self._ui_mode = "field"
                self._draw_field(False)
            else:
                from asteria.runtime.creature_menu import OVERLAY_PHASES

                if menu.phase in OVERLAY_PHASES:
                    self._draw_field(False)
                menu.draw()
        elif self._ui_mode == "name_input":  # NAME_INPUT: entering a name
            self._name_input.update(dt, events)
            if self._name_input.done:
                self._name_input = None
                self._ui_mode = "field"
                self._draw_field(False)
            else:
                self._name_input.draw()
        elif self._ui_mode == "picture_choice":  # PICTURE_CHOICE: pictured options
            self._picture_choice.update(dt, events)
            if self._picture_choice.done:
                self._picture_choice = None
                self._ui_mode = "field"
                self._draw_field(False)
            else:
                self._picture_choice.draw()
        elif self._ui_mode == "creature_shop":  # a shop in the game's own art
            self._creature_shop_frame(dt, events)
        elif self._ui_mode == "pets":
            self._pets_screen.handle(dt, events)
            if self._pets_screen.closed:
                self._ui_mode = getattr(self._pets_screen, "back", "pause")
            else:
                self._pets_screen.draw()
        elif self._ui_mode == "learn":  # a creature learned a move past its limit
            self._learn_input(events)
            self._draw_field(False)
            self._draw_learn_prompt()
        elif self._ui_mode == "skills":
            self._skill_tree.handle(dt, events)
            if self._skill_tree.closed:
                self._ui_mode = "field"
            else:
                self._skill_tree.draw()
        elif self._ui_mode == "game_over":
            self._game_over_input()
            title = self.game.tr("game_over.heading", "Game Over")
            self._draw_overlay_menu(
                title, self._game_over_menu, base="battle", screen_id="game_over"
            )
        elif self._creature_battle is not None:  # the creature battle screen (one on one)
            screen = self._creature_battle
            if not self._dialogue_input(events):
                screen.update(dt, events)
            screen.draw()
            self._draw_dialogue()
            if screen.done:
                self._creature_battle = None
                if screen.defeated and "defeat_continues" in screen.tags:
                    self.game.mode = "field"  # a battle the story goes on after, lost or won
                    self.game.battle = None
                elif screen.defeated and self.game.rules.defeat == "respawn":
                    self.game.respawn_after_defeat()  # healed at the last respawn point
                elif screen.defeated:
                    self.game.mode = "field"
                    self.game.battle = None
                    self._game_over_menu.index = 0
                    self._ui_mode = "game_over"
                    self.audio.stop_music(fade_out=0.5)
                else:
                    self.game.mode = "field"
        elif (
            self.game.mode == "battle" and self._creature_style() and not self._victory
        ):  # a creature battle started outside the field (an event, a test): its own screen
            from asteria.runtime.creature_battle import CreatureBattleScreen

            self._creature_battle = CreatureBattleScreen(self)
            self._end_temporary_music()
            self._music(self._creature_battle.music("start") or self.manifest["battle"].get("bgm"))
            self._creature_battle.draw()
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
            if (  # NAME_INPUT: the name screen (the event waits for the name)
                self._ui_mode == "field"
                and self.game.name_input_request
                and self.game.pending_dialogue is None
            ):
                from asteria.runtime.name_input import NameInputScreen

                self._name_input = NameInputScreen(self, self.game.name_input_request)
                self._ui_mode = "name_input"
            if (  # PICTURE_CHOICE: the pictured options (the event waits for the choice)
                self._ui_mode == "field"
                and self.game.picture_choice_request
                and self.game.pending_dialogue is None
            ):
                from asteria.runtime.picture_choice import PictureChoiceScreen

                self._picture_choice = PictureChoiceScreen(self, self.game.picture_choice_request)
                self._ui_mode = "picture_choice"
            if (  # a shop in the game's own art opens at once: the event waits for it
                self._ui_mode == "field"
                and self.game.open_shop_id
                and self.manifest.get("field", {}).get("creature_shop")
                and self.game.pending_dialogue is None
            ):
                from asteria.runtime.creature_shop import CreatureShopScreen

                self._creature_shop = CreatureShopScreen(self)
                self._ui_mode = "creature_shop"
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
            busy = (
                getattr(self, "_network_event_busy", False)
                if self._multiplayer_connected()
                else self.game.event_busy
            )
            if self._ui_mode == "field" and self.game.pet_storage_requested and not busy:
                from asteria.runtime.pets_screen import PetsScreen

                self.game.pet_storage_requested = False
                self._pets_screen = PetsScreen(self, back="field", storage=True)
                self._ui_mode = "pets"
            if self._ui_mode == "field" and self.game.pending_pet_moves() and not busy:
                self._ui_mode = "learn"
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
            service = getattr(self.game, "open_service", None)
            if self._ui_mode == "field" and service and not busy:
                from asteria.runtime.service_screens import open_service

                self.game.open_service = None
                open_service(self, *service, back="field")
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
            if self.game.mode == "battle" and self._creature_style():
                from asteria.runtime.creature_battle import CreatureBattleScreen

                self._creature_battle = CreatureBattleScreen(self)
                self._end_temporary_music()
                self._music(
                    self._creature_battle.music("start") or self.manifest["battle"].get("bgm")
                )
                self._creature_battle.draw()
            elif self.game.mode == "battle":
                self._turn_actor = None
                self._battle_presentation.begin()
                self._music(self.manifest["battle"].get("bgm"))
                self._advance_to_hero_turn()
                self._present_battle(dt)
            else:
                override = getattr(self, "_bgm_override", None)  # a story event chose the track
                if override is None:  # else the map area's own music, else the field's
                    override = self.game.area_music or self.manifest["field"].get("bgm")
                self._music(override)
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
