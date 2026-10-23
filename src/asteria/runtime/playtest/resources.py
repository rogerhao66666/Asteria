"""Pictures, fonts, icons, sounds and the resource scopes of the playtest runtime."""

from __future__ import annotations

from pathlib import Path

from asteria.runtime.particle_draw import ParticleDrawer

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


class ResourceMixin:
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
        from asteria.runtime.menu_icons import icon_source

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
        from asteria.runtime.menu_icons import icon_source

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
        from asteria.runtime.menu_icons import forged_surface, icon_source

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
        from asteria.runtime.menu_icons import icon_source

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
        self._scaled.clear()
        for rel in names:
            image = self._loaded.pop(rel, None)
            self._image_scope.pop(rel, None)
            if image is not None and self._preloader is not None:
                self._preloader.keep(rel, image)  # ready for the next fight
        self.released_images += len(names)
        return len(names)

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

    def _sound(self, asset_id):
        if asset_id:
            self.audio.play_effect(asset_id)

    def _music(self, asset_id, fade=0.5):
        if asset_id:
            self.audio.play_music(asset_id, fade_in=fade)
