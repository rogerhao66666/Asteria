from __future__ import annotations

import os
import sys

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

CJK_FONT_FAMILIES = (
    "microsoftjhenghei",
    "microsoftyahei",
    "hiraginosans",
    "hiraginosansgb",
    "applesdgothicneo",
    "arialunicode",
    "notosanscjktc",
    "notosanscjk",
    "wenquanyi zen hei",
)
CJK_RANGES = (
    (0x1100, 0x11FF),
    (0x2E80, 0x2FFF),
    (0x3000, 0x303F),
    (0x3040, 0x30FF),
    (0x3100, 0x312F),
    (0x3130, 0x318F),
    (0x31A0, 0x31EF),
    (0x3200, 0x33FF),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xAC00, 0xD7AF),
    (0xF900, 0xFAFF),
    (0xFE30, 0xFE4F),
    (0xFF00, 0xFFEF),
    (0x20000, 0x3134F),
)


def _cjk_font_paths(platform_name):
    if platform_name == "darwin":
        return (
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        )
    if platform_name.startswith("win"):
        font_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        return tuple(os.path.join(font_dir, name) for name in ("msjh.ttc", "msyh.ttc"))
    return (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    )


def cjk_font_path(pg):
    """Find an installed system font that can draw common CJK scripts."""
    for path in _cjk_font_paths(sys.platform):
        if os.path.isfile(path):
            return path
    for family in CJK_FONT_FAMILIES:
        path = pg.font.match_font(family)
        if path:
            return path
    return None


def contains_cjk(value):
    """Whether ``value`` contains Han, kana, Hangul, or CJK punctuation."""
    return any(any(start <= ord(char) <= end for start, end in CJK_RANGES) for char in str(value))


def font_for_text(pg, font, value, cache, size):
    """Use a cached CJK system font for CJK text and retain the normal font otherwise."""
    if not contains_cjk(value):
        return font
    key = (id(font), int(size))
    if key not in cache:
        path = cjk_font_path(pg)
        cache[key] = pg.font.Font(path, int(size)) if path else font
    return cache[key]


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

    return "".join(
        char if has_glyph(char) else GLYPH_FALLBACKS.get(char, "?") for char in str(value)
    )


class PygameBattleUiBackend:
    """Concrete pygame-ce adapter for Asteria BattleUiFrame commands.

    `resolve_icon(asset_id)` may return either a pygame Surface or an object
    whose `backend_handle` is a Surface. Missing icons fall back to a styled
    placeholder so project data errors do not crash presentation.

    UI frames are composed in the layout's virtual resolution; `scale`
    multiplies every coordinate, size and font size so the same frame can be
    drawn crisply at a larger window size.
    """

    def __init__(
        self,
        screen,
        *,
        resolve_icon=None,
        font_name=None,
        scale=1.0,
        resolve_skin=None,
        font_scale=1.0,
    ):
        try:
            import pygame
        except ImportError as exc:
            raise RuntimeError("Install pygame-ce with: pip install 'asteria[pygame]'") from exc
        self.pg = pygame
        self.screen = screen
        self.resolve_icon = resolve_icon
        self.resolve_skin = resolve_skin  # asset id -> the picture at its own size, or None
        self.font_scale = float(font_scale)
        self.font_name = font_name
        self.scale = float(scale)
        if not self.scale > 0:
            raise ValueError("scale must be positive")
        self._fonts = {}
        self._glyph_cache = {}
        self._cjk_fonts = {}

    def _s(self, value):
        return round(float(value) * self.scale)

    def _rect(self, x, y, width, height):
        return self.pg.Rect(
            self._s(x), self._s(y), max(1, self._s(width)), max(1, self._s(height))
        )

    @staticmethod
    def _rgb(color):
        return tuple(color[:3])

    def _font(self, size):
        size = max(1, round(float(size) * self.scale * self.font_scale))
        if size not in self._fonts:
            if not self.pg.font.get_init():
                self.pg.font.init()
            self._fonts[size] = self.pg.font.Font(self.font_name, size)
        return self._fonts[size]

    def begin_battle_ui(self, scene_id):
        if self.screen is None:
            raise RuntimeError("pygame battle UI screen is not configured")

    def draw_panel(self, panel, *, fill, border, radius, border_width, skin=None):
        rect = self._rect(panel.x, panel.y, panel.width, panel.height)
        if skin is not None and self.resolve_skin is not None:
            image = self.resolve_skin(skin.asset_id)
            if image is not None:  # a picture-framed panel; a missing picture falls back below
                from asteria.presentation.ui_skin import draw_nine_patch

                draw_nine_patch(self.pg, self.screen, image, tuple(rect), skin, scale=self.scale)
                return
        layer = self.pg.Surface(rect.size, self.pg.SRCALPHA)
        local = layer.get_rect()
        alpha = lambda c: (*self._rgb(c), int(c[3]) if len(c) > 3 else 255)  # noqa: E731
        self.pg.draw.rect(layer, alpha(fill), local, border_radius=self._s(radius))
        if border_width:
            self.pg.draw.rect(
                layer,
                alpha(border),
                local,
                width=max(1, self._s(border_width)),
                border_radius=self._s(radius),
            )
        self.screen.blit(layer, rect.topleft)

    def draw_gauge(self, gauge, *, track, fill):
        mode = str(getattr(gauge, "presentation", "bar"))
        normalized = max(0.0, min(1.0, float(gauge.normalized)))
        rect = self._rect(gauge.x, gauge.y, gauge.width, gauge.height)

        if mode in {"pips", "segmented_bar", "icon_stack"}:
            segments = int(getattr(gauge, "segments", 0))
            if segments <= 0:
                segments = (
                    max(1, int(round(float(gauge.maximum)))) if float(gauge.maximum) <= 24 else 5
                )
            gap = max(1, self._s(1))
            cell_w = max(1, (rect.width - gap * (segments - 1)) // segments)
            filled_count = int(round(normalized * segments))
            icon = None
            if (
                mode == "icon_stack"
                and self.resolve_icon is not None
                and getattr(gauge, "icon_asset_id", None)
            ):
                value = self.resolve_icon(gauge.icon_asset_id)
                icon = getattr(value, "backend_handle", value)
            for index in range(segments):
                cell = self.pg.Rect(rect.x + index * (cell_w + gap), rect.y, cell_w, rect.height)
                active = index < filled_count
                if icon is not None and active:
                    image = (
                        icon
                        if icon.get_size() == cell.size
                        else self.pg.transform.scale(icon, cell.size)
                    )
                    self.screen.blit(image, cell.topleft)
                else:
                    self.pg.draw.rect(
                        self.screen,
                        self._rgb(fill if active else track),
                        cell,
                        border_radius=max(1, cell.height // 3),
                    )
            return

        if mode == "ring":
            radius = max(3, round(max(rect.width, rect.height) / 2))
            center = (rect.x + rect.width // 2, rect.y + rect.height // 2)
            self.pg.draw.circle(
                self.screen, self._rgb(track), center, radius, width=max(1, radius // 4)
            )
            if normalized > 0:
                import math

                ring_rect = self.pg.Rect(
                    center[0] - radius, center[1] - radius, radius * 2, radius * 2
                )
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
        self.pg.draw.rect(
            self.screen, self._rgb(track), rect, border_radius=max(1, rect.height // 2)
        )
        width = max(0, min(rect.width, round(rect.width * normalized)))
        if width:
            filled = self.pg.Rect(rect.x, rect.y, width, rect.height)
            self.pg.draw.rect(
                self.screen, self._rgb(fill), filled, border_radius=max(1, rect.height // 2)
            )

    def draw_icon(self, icon):
        surface = None
        if self.resolve_icon is not None:
            value = self.resolve_icon(icon.asset_id)
            surface = getattr(value, "backend_handle", value)
        target = self._rect(icon.x, icon.y, 8, 8)
        if surface is not None:
            image = (
                surface
                if surface.get_size() == target.size
                else self.pg.transform.scale(surface, target.size)
            )
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
        font = font_for_text(self.pg, font, text.text, self._cjk_fonts, self._s(size))
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
