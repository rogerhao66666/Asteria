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
    """The font file for Chinese, Japanese and Korean text: ``ASTERIA_CJK_FONT`` (a font that
    travels with the game, e.g. a web export's Noto Sans TC) when it names a file, else an
    installed system font that covers those scripts, else None (the built-in face draws boxes)."""
    bundled = os.environ.get("ASTERIA_CJK_FONT", "")
    if bundled and os.path.isfile(bundled):
        return bundled
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


def cjk_size(font, pg=None, path=None):
    """The size to draw Chinese, Japanese or Korean text at beside ``font`` (a face that has
    no CJK characters): a quarter taller than the face's line. Asked for the same size, a system
    CJK face came out 45 % larger than pygame's built-in face (which draws smaller than asked)
    and towered over the Latin text beside it.

    With ``pg`` the size is fitted to the CJK face that will draw (``path``, else the system
    one), so its line - not its point size - is a quarter taller: faces differ in how tall a
    line they set per point (WenQuanYi Zen Hei sets about 1.3x)."""
    line = max(1, round(font.get_height() * 1.25))
    if pg is None:
        return line
    path = path or cjk_font_path(pg)
    if not path:
        return line
    key = (path, line)
    size = _CJK_SIZES.get(key)
    if size is None:
        size = max(1, round(line * line / max(1, pg.font.Font(path, line).get_height())))
        while size > 1 and pg.font.Font(path, size).get_height() > line:
            size -= 1
        _CJK_SIZES[key] = size
    return size


_CJK_SIZES = {}  # (CJK face file, line height) -> the point size that sets that line


def _centre(font, char, cache):
    """How far below the top of ``font``'s line the middle of ``char`` stands, in pixels."""
    key = (id(font), "centre", char)
    value = cache.get(key)
    if value is None:
        metrics = font.metrics(char)
        if metrics and metrics[0] is not None:
            _, _, low, high, _ = metrics[0]
            value = font.get_ascent() - (high + low) / 2
        else:  # a face without the character: the middle of its line
            value = font.get_height() / 2
        cache[key] = value
    return value


def glyph_shift(pg, font, cjk_font, cache):
    """Pixels to move a line drawn in ``cjk_font`` down (negative: up) so its characters stand
    level with the capitals of ``font`` drawn from the same top: a cursor centred on the
    capitals then sits level with a Chinese label too. ``cache`` keeps what was measured."""
    if cjk_font is font:
        return 0
    return round(_centre(font, "H", cache) - _centre(cjk_font, "中", cache))


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


def render_with_fallback(pg, font, value, color, cache, fallback):
    """``value`` drawn in ``font``; the characters it lacks (a pixel font often has no brackets or
    percent sign) come from ``fallback(height)``, the built-in face, run by run."""
    text = str(value)
    if all(char.isspace() or char_in_font(pg, font, char, cache) for char in text):
        return font.render(text, True, color)
    runs = []
    for char in text:
        ok = char.isspace() or char_in_font(pg, font, char, cache)
        if runs and runs[-1][0] == ok:
            runs[-1][1] += char
        else:
            runs.append([ok, char])
    height = font.get_height()
    parts = []
    for ok, chars in runs:
        face = font if ok else fallback(height)
        parts.append(
            face.render(chars if ok else renderable_text(pg, face, chars, cache), True, color)
        )
    image = pg.Surface(
        (sum(p.get_width() for p in parts), max(p.get_height() for p in parts)), pg.SRCALPHA
    )
    x = 0
    for part in parts:
        image.blit(part, (x, image.get_height() - part.get_height()))
        x += part.get_width()
    return image


def char_in_font(pg, font, char, cache):
    """Whether ``font`` draws ``char`` (any character, ASCII included: pixel fonts skip some)."""
    key = (id(font), "has", char)
    cached = cache.get(key)
    if cached is None:

        def pixels(value):
            return pg.image.tobytes(font.render(value, True, (255, 255, 255)), "RGBA")

        cached = pixels(char) != pixels("\ue000")
        cache[key] = cached
    return cached


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
        resolve_portrait=None,
    ):
        try:
            import pygame
        except ImportError as exc:
            raise RuntimeError("Install pygame-ce with: pip install 'asteria[pygame]'") from exc
        self.pg = pygame
        self.screen = screen
        self.resolve_icon = resolve_icon
        self.resolve_skin = resolve_skin  # asset id -> the picture at its own size, or None
        # (asset id, width, height) -> the picture fitted inside that many pixels, or None
        self.resolve_portrait = resolve_portrait
        self.font_scale = float(font_scale)
        self.font_name = font_name
        self.scale = float(scale)
        if not self.scale > 0:
            raise ValueError("scale must be positive")
        self._fonts = {}
        self._glyph_cache = {}
        self._cjk_fonts = {}
        self._text_images = {}  # (size, text, colour) -> the drawn line, reused frame to frame
        self._panel_layers = {}  # (size, colours, radius, border) -> the drawn panel, reused

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

    def _fallback_font(self, height):
        key = ("fallback", height)
        if key not in self._fonts:
            self._fonts[key] = self.pg.font.Font(None, max(1, round(height * 0.9)))
        return self._fonts[key]

    def begin_battle_ui(self, scene_id):
        if self.screen is None:
            raise RuntimeError("pygame battle UI screen is not configured")

    PANEL_LAYERS = 256  # drawn panels kept; the HUD and the menu redraw the same few

    def draw_panel(self, panel, *, fill, border, radius, border_width, skin=None):
        rect = self._rect(panel.x, panel.y, panel.width, panel.height)
        if skin is not None and self.resolve_skin is not None:
            image = self.resolve_skin(skin.asset_id)
            if image is not None:  # a picture-framed panel; a missing picture falls back below
                from asteria.presentation.ui_skin import draw_nine_patch

                draw_nine_patch(self.pg, self.screen, image, tuple(rect), skin, scale=self.scale)
                return
        alpha = lambda c: (*self._rgb(c), int(c[3]) if len(c) > 3 else 255)  # noqa: E731
        width = max(1, self._s(border_width)) if border_width else 0
        key = (rect.size, alpha(fill), alpha(border) if width else None, self._s(radius), width)
        layer = self._panel_layers.get(key)
        if layer is None:  # the same panel is drawn again on every frame
            layer = self.pg.Surface(rect.size, self.pg.SRCALPHA)
            local = layer.get_rect()
            self.pg.draw.rect(layer, key[1], local, border_radius=key[3])
            if width:
                self.pg.draw.rect(layer, key[2], local, width=width, border_radius=key[3])
            if len(self._panel_layers) >= self.PANEL_LAYERS:
                self._panel_layers.clear()  # panels that change size: start over
            self._panel_layers[key] = layer
        self.screen.blit(layer, rect.topleft)

    def _draw_pips(self, rect, count, filled, track, fill):
        """``count`` round pips spread along ``rect``, larger than a thin bar is tall: the
        first ``filled`` solid with a light rim, the rest as dark rings."""
        step = rect.width / max(1, count)
        radius = max(2, int(min(step * 0.42, max(rect.height, self._s(3)) * 0.9)))
        cy = rect.y + rect.height // 2
        rim = tuple(min(255, c + 60) for c in self._rgb(fill))
        for index in range(count):
            center = (round(rect.x + step * (index + 0.5)), cy)
            if index < filled:
                self.pg.draw.circle(self.screen, self._rgb(fill), center, radius)
                self.pg.draw.circle(self.screen, rim, center, radius, width=max(1, radius // 4))
            else:
                self.pg.draw.circle(self.screen, self._rgb(track), center, radius)
                ring = max(1, radius // 4)
                dim = tuple((a + b) // 2 for a, b in zip(self._rgb(fill), self._rgb(track)))
                self.pg.draw.circle(self.screen, dim, center, radius, width=ring)

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
            if mode == "pips":  # points: a row of round pips, filled ones solid
                self._draw_pips(rect, segments, filled_count, track, fill)
                return
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

    def draw_portrait(self, portrait):
        """A party card's portrait, fitted inside its box in screen pixels (``resolve_portrait``
        keeps the proportions: sharp pixels when enlarged, smooth when shrunk) and centred in
        it; nothing when the picture cannot be drawn."""
        if self.resolve_portrait is None:
            return
        box = self._rect(portrait.x, portrait.y, portrait.width, portrait.height)
        picture = self.resolve_portrait(portrait.asset_id, box.width, box.height)
        if picture is not None:
            self.screen.blit(picture, picture.get_rect(center=box.center))

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

    TEXT_IMAGES = 1024  # drawn lines kept; the HUD redraws the same few dozen every frame

    # a row mark drawn as a shape: no font has to have the symbol, and it sits on the label
    ARROWS = frozenset("▶►▸⯈")
    CHEVRONS = frozenset(">›»→")
    TICKS = frozenset("✓✔")

    def _draw_mark(self, text, color, size):
        """A row's cursor or tick, centred on the capital letters of the label beside it."""
        font = self._font(size)
        metrics = font.metrics("H")
        top = self._s(text.y)
        if metrics and metrics[0] is not None:
            _, _, low, high, _ = metrics[0]
            centre = top + font.get_ascent() - (high + low) / 2
            height = max(3, high - low)
        else:  # a font without capitals: the middle of its line
            centre, height = top + font.get_height() / 2, max(3, font.get_height() // 2)
        x, c = self._s(text.x), self._rgb(color)
        half = height / 2
        glyph = text.text.strip()
        line = max(1, round(height / 5))
        if glyph in self.ARROWS:
            width = max(3, round(height * 0.7))
            points = ((x, centre - half), (x + width, centre), (x, centre + half))
            self.pg.draw.polygon(self.screen, c, [(round(a), round(b)) for a, b in points])
        elif glyph in self.CHEVRONS:
            width = max(3, round(height * 0.55))
            points = ((x, centre - half), (x + width, centre), (x, centre + half))
            self.pg.draw.lines(
                self.screen, c, False, [(round(a), round(b)) for a, b in points], line + 1
            )
        elif glyph in self.TICKS:
            points = (
                (x, centre),
                (x + height * 0.35, centre + half),
                (x + height * 0.9, centre - half),
            )
            self.pg.draw.lines(
                self.screen, c, False, [(round(a), round(b)) for a, b in points], line + 1
            )
        else:  # any other mark is text: in the label's own font, on the label's line
            image = font.render(self._renderable(font, glyph), True, c)
            self.screen.blit(image, (x, top))

    def draw_text(self, text, *, color, size):
        if str(text.role).endswith(":mark"):
            self._draw_mark(text, color, size)
            return
        key = (size, text.text, self._rgb(color))
        drawn = self._text_images.get(key)
        if drawn is None:
            drawn = self._text_image(text.text, color, size)
            if len(self._text_images) >= self.TEXT_IMAGES:
                self._text_images.clear()  # changing numbers: start over, no slow bookkeeping
            self._text_images[key] = drawn
        image, shift = drawn
        x, y = self._s(text.x), self._s(text.y) + shift
        if text.align == "center":
            x -= image.get_width() // 2
        elif text.align == "right":
            x -= image.get_width()
        self.screen.blit(image, (x, y))

    def _text_image(self, value, color, size):
        """The drawn line and how far to move it down: Chinese, Japanese and Korean text is
        drawn in a system CJK face at the size the UI face really has (``point_size``: the
        built-in face is drawn smaller than asked, a skin's face by its ``font_scale``), level
        with the capitals of that face - so it takes the room the layout counted for it and a
        row's cursor sits level with it. A skin's face that has the characters itself (a Chinese
        pixel font) draws them."""
        face = self._font(size)
        em = getattr(face, "point_size", None) or self._s(size)
        own = self.font_name is not None and all(
            char_in_font(self.pg, face, c, self._glyph_cache)
            for c in set(value)
            if contains_cjk(c)
        )
        font = face if own else font_for_text(self.pg, face, value, self._cjk_fonts, em)
        shift = glyph_shift(self.pg, face, font, self._glyph_cache)
        if self.font_name is None:
            return font.render(self._renderable(font, value), True, self._rgb(color)), shift
        # a skin's own face: the built-in one fills in what it cannot draw
        image = render_with_fallback(
            self.pg, font, value, self._rgb(color), self._glyph_cache, self._fallback_font
        )
        return image, shift

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
