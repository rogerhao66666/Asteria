"""Text, menu rows, panels and bars: the drawing primitives every screen uses."""

from __future__ import annotations

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


class TextDrawMixin:
    def text_width(self, value, size=20):
        """The width in pixels of ``value`` drawn at ``size`` (the face ``text`` uses)."""
        return self.text_size(value, size)[0]

    def text_size(self, value, size=20):
        """``(width, height)`` in pixels of ``value`` drawn at ``size``, in the face ``text``
        draws it with (a system CJK face for Chinese, Japanese or Korean)."""
        from asteria.platform.pygame_battle_ui import cjk_size, contains_cjk, font_for_text

        f, cjk_path = self._font_face(size)
        if cjk_path and contains_cjk(value):
            return self.pg.font.Font(cjk_path, cjk_size(f)).size(str(value))
        return font_for_text(self.pg, f, value, self._cjk_fonts, cjk_size(f)).size(str(value))

    # --- menu layouts and the menu theme (U2) -----------------------------------------------
    def menu_layout(self, screen_id):
        """The project's layout for menu screen ``screen_id``, or None (the engine's look)."""
        library = self.project.battle_presentation_library
        try:
            return library.get("menu_layout", screen_id)
        except KeyError:  # a library from before menu layouts
            return None

    def menu_theme(self):
        """The project's menu theme (``default``, else the first), or None."""
        project = getattr(self, "project", None)  # a bare host (tests) has no project
        library = getattr(project, "battle_presentation_library", None)
        records = getattr(library, "_records", {})
        themes = records.get("menu_theme")  # asked for every text drawn: kept cheap
        if not themes:
            return None
        return themes.get("default") or themes[min(themes)]

    def menu_sounds(self):
        """The menu theme's sounds for this frame: ``open`` when a menu opens over the field,
        ``move`` / ``confirm`` / ``cancel`` for the keys pressed in a menu (the shop plays
        ``buy`` or ``fail`` itself). Nothing without a theme that names them."""
        mode, last = self._ui_mode, getattr(self, "_menu_last_mode", "field")
        self._menu_last_mode = mode
        theme = self.menu_theme()
        if theme is None or not theme.sounds or mode == "field":
            return
        if last == "field":
            self._sound(theme.sound("open"))
        pressed = self.input.just_pressed
        if any(pressed(a) for a in ("move_up", "move_down", "move_left", "move_right")):
            self._sound(theme.sound("move"))
        if pressed("cancel"):
            self._sound(theme.sound("cancel"))
        elif pressed("confirm") and mode != "shop":
            self._sound(theme.sound("confirm"))

    def menu_canvas(self, screen_id, fields=None):
        from asteria.runtime.menu_canvas import MenuCanvas

        return MenuCanvas(self, screen_id, fields)

    def scaled_image(self, image, size):
        """``image`` scaled to ``size`` (cached: menu pictures repeat every frame)."""
        size = (max(1, int(size[0])), max(1, int(size[1])))
        if image.get_size() == size:
            return image
        cache = self.__dict__.setdefault("_scaled_cache", {})
        key = (id(image), size)
        found = cache.get(key)
        if found is None or found[0] is not image:
            if len(cache) > 512:
                cache.clear()
            found = cache[key] = (image, self.pg.transform.scale(image, size))
        return found[1]

    def _font_face(self, size, font=None):
        """The face ``text`` draws at ``size``: the element's font asset, else the menu
        theme's Latin font, else the built-in face. Returns ``(face, cjk path or None)``."""
        theme = self.menu_theme()
        asset = font or (theme.font_latin if theme is not None else "")
        cjk = self.skin_font(theme.font_cjk) if theme is not None and theme.font_cjk else None
        if not asset:
            return self._menu_font(size), cjk
        scale = theme.font_scale if theme is not None else 1.0
        key = (str(asset), int(size), scale)
        faces = self.__dict__.setdefault("_asset_fonts", {})
        face = faces.get(key)
        if face is None:
            path = self.skin_font(asset)
            face = faces[key] = (
                self.pg.font.Font(path, max(1, round(int(size) * scale)))
                if path
                else self._menu_font(size)
            )
        return face, cjk

    def text(
        self,
        value,
        x,
        y,
        *,
        size=20,
        color=(245, 245, 250),
        center=False,
        anchor=None,
        font=None,
    ):
        """Draw text at ``(x, y)``: top-left by default, ``center=True`` centres it, ``anchor`` is
        any pygame rect attribute (``"midleft"``, ``"midright"``, ``"bottomright"``...) placed at
        the point - so a label can sit on the same horizontal line as a bar. Text drawn in the
        CJK face (Chinese...) is placed where the built-in face's line would be, centred on the
        same height as its capitals, so menu cursors and mixed rows stay level."""
        f, cjk_path = self._font_face(size, font)
        from asteria.platform.pygame_battle_ui import (
            cjk_size,
            contains_cjk,
            font_for_text,
            glyph_shift,
            render_with_fallback,
            renderable_text,
        )

        # rendered text is cached: HUD labels and damage numbers repeat every frame
        key = (str(value), int(size), tuple(color), id(f), cjk_path)
        cache = self.__dict__.setdefault("_text_cache", {})
        entry = cache.get(key)
        if entry is None:
            if len(cache) > 2048:
                cache.clear()
            if cjk_path and contains_cjk(value):  # the menu theme's own CJK font
                faces = self.__dict__.setdefault("_asset_fonts", {})
                face_key = (cjk_path, "cjk", cjk_size(f))
                if face_key not in faces:
                    faces[face_key] = self.pg.font.Font(cjk_path, cjk_size(f))
                text_font = faces[face_key]
            else:
                text_font = font_for_text(self.pg, f, value, self._cjk_fonts, cjk_size(f))
            if text_font is f and not str(value).isascii():
                # what the Latin face lacks ("→", "·" in a pixel font) comes from one that has it
                surf = render_with_fallback(
                    self.pg, f, value, color, self._glyphs, self._fallback_face
                )
            else:
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

    def _fallback_face(self, height):
        """A face for the characters an author's font lacks, ``height`` pixels tall: the
        menu theme's CJK font, else the system CJK face (both have arrows and symbols), else
        the built-in face."""
        from asteria.platform.pygame_battle_ui import cjk_font_path

        theme = self.menu_theme()
        path = self.skin_font(theme.font_cjk) if theme is not None and theme.font_cjk else None
        path = path or cjk_font_path(self.pg)
        faces = self.__dict__.setdefault("_asset_fonts", {})
        key = (path, "fallback", int(height))
        if key not in faces:
            faces[key] = self.pg.font.Font(path, int(height)) if path else self._menu_font(height)
        return faces[key]

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
        menu_theme = self.menu_theme()
        skin = menu_theme.panel_skin if menu_theme is not None else None
        if skin is None:
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
