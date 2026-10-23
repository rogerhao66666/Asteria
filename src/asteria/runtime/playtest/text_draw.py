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
