"""Scene environment: lighting, fog, weather and post-processing (VFX-02 / VFX-03)."""

from __future__ import annotations

from stat import S_ISREG

from .support import (  # noqa: F401 - the names the moved methods use
    BESTIARY_TAG_KINDS,
    FIELD_BODY_HEIGHT,
    WALK_PATTERN_SEQUENCE,
    WALK_ROW_BY_FACING,
    _load_manifest,
    field_player_render_size,
    walking_pattern_index,
    walking_row_index,
)


class EnvironmentMixin:
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
        try:
            info = path.stat()
        except OSError:
            return None
        if not S_ISREG(info.st_mode):
            return None
        # read once per asset (asked every frame), again only when the file changes
        key = (str(path), info.st_mtime_ns, info.st_size)
        cache = self.__dict__.setdefault("_shader_sources", {})
        known = cache.get(str(asset_id))
        if known is None or known[0] != key:
            known = cache[str(asset_id)] = (key, path.read_text(encoding="utf-8"))
        return known[1]

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
