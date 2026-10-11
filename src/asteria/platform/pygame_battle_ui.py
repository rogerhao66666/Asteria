from __future__ import annotations

GLYPH_FALLBACKS = {
    "▶": ">",
    "▸": ">",
    "►": ">",
    "◀": "<",
    "◂": "<",
    "…": "...",
    "•": "*",
    "→": "->",
    "←": "<-",
    "↑": "^",
    "↓": "v",
    "−": "-",
    "–": "-",
    "—": "-",
    "·": "-",
}


def renderable_text(pg, font, value, cache):
    """``value`` with characters ``font`` cannot draw (empty boxes) replaced by ASCII fallbacks.

    ``cache`` maps ``(id(font), char)`` to whether the font has the glyph.
    """

    def has_glyph(char):
        key = (id(font), char)
        cached = cache.get(key)
        if cached is None:

            def pixels(text):
                return pg.image.tobytes(font.render(text, True, (255, 255, 255)), "RGBA")

            cached = char.isspace() or char.isascii() or pixels(char) != pixels("\ue000")
            cache[key] = cached
        return cached

    return "".join(char if has_glyph(char) else GLYPH_FALLBACKS.get(char, "?") for char in str(value))


class PygameBattleUiBackend:
    """Concrete pygame-ce adapter for Asteria BattleUiFrame commands.

    `resolve_icon(asset_id)` may return either a pygame Surface or an object
    whose `backend_handle` is a Surface. Missing icons fall back to a styled
    placeholder so project data errors do not crash presentation.

    UI frames are composed in the layout's virtual resolution; `scale`
    multiplies every coordinate, size and font size so the same frame can be
    drawn crisply at a larger window size.
    """

    def __init__(self, screen, *, resolve_icon=None, font_name=None, scale=1.0):
        try:
            import pygame
        except ImportError as exc:
            raise RuntimeError("Install pygame-ce with: pip install 'asteria[pygame]'") from exc
        self.pg = pygame
        self.screen = screen
        self.resolve_icon = resolve_icon
        self.font_name = font_name
        self.scale = float(scale)
        if not self.scale > 0:
            raise ValueError("scale must be positive")
        self._fonts = {}
        self._glyph_cache = {}

    def _s(self, value):
        return round(float(value) * self.scale)

    def _rect(self, x, y, width, height):
        return self.pg.Rect(self._s(x), self._s(y), max(1, self._s(width)), max(1, self._s(height)))

    @staticmethod
    def _rgb(color):
        return tuple(color[:3])

    def _font(self, size):
        size = max(1, round(float(size) * self.scale))
        if size not in self._fonts:
            if not self.pg.font.get_init():
                self.pg.font.init()
            self._fonts[size] = self.pg.font.Font(self.font_name, size)
        return self._fonts[size]

    def begin_battle_ui(self, scene_id):
        if self.screen is None:
            raise RuntimeError("pygame battle UI screen is not configured")

    def draw_panel(self, panel, *, fill, border, radius, border_width):
        rect = self._rect(panel.x, panel.y, panel.width, panel.height)
        self.pg.draw.rect(self.screen, self._rgb(fill), rect, border_radius=self._s(radius))
        if border_width:
            self.pg.draw.rect(
                self.screen, self._rgb(border), rect, width=max(1, self._s(border_width)), border_radius=self._s(radius)
            )

    def draw_gauge(self, gauge, *, track, fill):
        mode = str(getattr(gauge, "presentation", "bar"))
        normalized = max(0.0, min(1.0, float(gauge.normalized)))
        rect = self._rect(gauge.x, gauge.y, gauge.width, gauge.height)

        if mode in {"pips", "segmented_bar", "icon_stack"}:
            segments = int(getattr(gauge, "segments", 0))
            if segments <= 0:
                segments = max(1, int(round(float(gauge.maximum)))) if float(gauge.maximum) <= 24 else 5
            gap = max(1, self._s(1))
            cell_w = max(1, (rect.width - gap * (segments - 1)) // segments)
            filled_count = int(round(normalized * segments))
            icon = None
            if mode == "icon_stack" and self.resolve_icon is not None and getattr(gauge, "icon_asset_id", None):
                value = self.resolve_icon(gauge.icon_asset_id)
                icon = getattr(value, "backend_handle", value)
            for index in range(segments):
                cell = self.pg.Rect(rect.x + index * (cell_w + gap), rect.y, cell_w, rect.height)
                active = index < filled_count
                if icon is not None and active:
                    image = icon if icon.get_size() == cell.size else self.pg.transform.scale(icon, cell.size)
                    self.screen.blit(image, cell.topleft)
                else:
                    self.pg.draw.rect(
                        self.screen, self._rgb(fill if active else track), cell, border_radius=max(1, cell.height // 3)
                    )
            return

        if mode == "ring":
            radius = max(3, round(max(rect.width, rect.height) / 2))
            center = (rect.x + rect.width // 2, rect.y + rect.height // 2)
            self.pg.draw.circle(self.screen, self._rgb(track), center, radius, width=max(1, radius // 4))
            if normalized > 0:
                import math

                ring_rect = self.pg.Rect(center[0] - radius, center[1] - radius, radius * 2, radius * 2)
                start = -math.pi / 2
                self.pg.draw.arc(
                    self.screen,
                    self._rgb(fill),
                    ring_rect,
                    start,
                    start + 2 * math.pi * normalized,
                    width=max(1, radius // 4),
                )
            return

        # bar/action_gauge/timeline/custom roles have a readable bar fallback.
        self.pg.draw.rect(self.screen, self._rgb(track), rect, border_radius=max(1, rect.height // 2))
        width = max(0, min(rect.width, round(rect.width * normalized)))
        if width:
            filled = self.pg.Rect(rect.x, rect.y, width, rect.height)
            self.pg.draw.rect(self.screen, self._rgb(fill), filled, border_radius=max(1, rect.height // 2))

    def draw_icon(self, icon):
        surface = None
        if self.resolve_icon is not None:
            value = self.resolve_icon(icon.asset_id)
            surface = getattr(value, "backend_handle", value)
        target = self._rect(icon.x, icon.y, 8, 8)
        if surface is not None:
            image = surface if surface.get_size() == target.size else self.pg.transform.scale(surface, target.size)
            self.screen.blit(image, target.topleft)
        else:
            self.pg.draw.rect(self.screen, (116, 130, 154), target, border_radius=2)
            self.pg.draw.rect(self.screen, (202, 211, 226), target, width=1, border_radius=2)

    def draw_marker(self, marker, *, color):
        cx, cy = self._s(marker.x), self._s(marker.y)
        c = self._rgb(color)
        radius = self._s(7 if marker.primary else 5)
        self.pg.draw.polygon(
            self.screen,
            c,
            ((cx, cy - radius), (cx - radius, cy), (cx, cy + radius), (cx + radius, cy)),
            width=max(1, self._s(2)),
        )

    def _renderable(self, font, value):
        """Replace characters the font cannot draw (shown as empty boxes otherwise)."""
        return renderable_text(self.pg, font, value, self._glyph_cache)

    def draw_text(self, text, *, color, size):
        font = self._font(size)
        image = font.render(self._renderable(font, text.text), True, self._rgb(color))
        x, y = self._s(text.x), self._s(text.y)
        if text.align == "center":
            x -= image.get_width() // 2
        elif text.align == "right":
            x -= image.get_width()
        self.screen.blit(image, (x, y))

    # Set by the battle presentation adapter: draws one VFX cue (sprite sheet playback).
    vfx_drawer = None

    def draw_vfx(self, effect):
        if self.vfx_drawer is not None:
            self.vfx_drawer(effect)

    def draw_screen_fx(self, effect):
        payload = dict(getattr(effect, "payload", {}) or {})
        effect_name = str(getattr(effect, "effect", ""))
        if effect_name not in {"flash", "hit_flash"}:
            return
        alpha = max(0, min(255, int(payload.get("alpha", 72))))
        overlay = self.pg.Surface(self.screen.get_size(), self.pg.SRCALPHA)
        overlay.fill((255, 255, 255, alpha))
        self.screen.blit(overlay, (0, 0))

    def end_battle_ui(self):
        pass
