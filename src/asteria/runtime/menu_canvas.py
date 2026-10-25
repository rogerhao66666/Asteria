"""Drawing a menu screen through its layout (U2, ``presentation/menu_layout.py``).

A screen draws through a ``MenuCanvas``: ``canvas.panel("frame", rect, ...)``,
``canvas.text("title", words, x, y, ...)``, ``canvas.rect("rows", rect)``... Each call names
the element and gives the engine's own place and style; the screen's layout (when the project
has one) moves, resizes, recolours, reskins or hides it. Without a layout every call draws
exactly what the screen drew before.

``begin()`` draws the layout's background and the author's elements under the screen (layer
below 0), ``finish()`` those over it. ``boxes`` keeps where each element was drawn, so the
editor can outline and drag them.

A screen drawn at its own resolution (the creature screens' 240x160, then scaled up) passes
``size`` (what anchors measure from) and ``target`` (the small surface its pictures go on).
A picture that is a strip of frames (``frames``, ``frame_axis``, ``fps``) shows one frame at a
time: by the clock, or the frame the screen asks for (a cooldown's fill).
"""

from __future__ import annotations

import re

from asteria.presentation.menu_layout import resolve_rect, screen_spec

_FIELD = re.compile(r"\{([A-Za-z0-9_.]+)\}")


class Place:
    """Where a list or grid goes: ``x(v)`` / ``y(v)`` move the engine's coordinates by the
    layout's offset, ``bottom`` is where rows stop, ``row`` the row height."""

    __slots__ = ("bottom", "dx", "dy", "rect", "right", "row")

    def __init__(self, rect, default, row):
        self.rect = rect
        self.dx, self.dy = rect[0] - default[0], rect[1] - default[1]
        self.bottom, self.right = rect[1] + rect[3], rect[0] + rect[2]
        self.row = row

    def x(self, value):
        return value + self.dx

    def y(self, value):
        return value + self.dy


class MenuCanvas:
    def __init__(self, runtime, screen_id, fields=None, *, size=None, target=None):
        self.rt = runtime
        self.screen_id = screen_id
        self.layout = runtime.menu_layout(screen_id)
        self.theme = runtime.menu_theme()
        self.fields = dict(fields or {})
        self.boxes = {}
        if size is None:
            spec = screen_spec(screen_id)
            size = spec.size if spec is not None and spec.size else None
        self.own_size = tuple(size) if size else None  # None: the window's, read when drawn
        self.target = target
        recorder = getattr(runtime, "_menu_boxes", None)
        if recorder is not None:  # the editor's preview reads them back
            recorder[screen_id] = self.boxes

    @property
    def area(self):
        """``(width, height)`` the layout's rectangles are measured in."""
        return self.own_size or (self.rt.width, self.rt.height)

    @property
    def screen(self):
        return self.target if self.target is not None else self.rt.screen

    # --- the screen's own elements ------------------------------------------------------
    def element(self, element_id):
        return None if self.layout is None else self.layout.element(element_id)

    def shown(self, element_id):
        element = self.element(element_id)
        return element is None or element.visible

    def rect(self, element_id, default):
        """The element's rectangle: the layout's (from its anchor) or ``default``."""
        element = self.element(element_id)
        if element is not None and element.rect is not None:
            rect = resolve_rect(element.rect, element.anchor, self.area)
        else:
            rect = tuple(int(v) for v in default)
        self._box(element_id, rect)
        return rect

    def _box(self, element_id, rect):
        if element_id not in self.boxes:
            self.boxes[element_id] = tuple(int(v) for v in rect)

    def place(self, element_id, default, row=0):
        """A list's or grid's ``Place``: ``default`` is the engine's rectangle (its bottom is
        where rows stop), ``row`` the engine's row height."""
        rect = self.rect(element_id, default)
        return Place(rect, tuple(int(v) for v in default), self.row_height(element_id, row))

    def tone(self, role, default):
        """A text colour of the menu theme (``title``, ``text``, ``muted``, ``selected``),
        else ``default``."""
        if self.theme is None:
            return default
        value = getattr(self.theme, f"{role}_color", None)
        return value or default

    def color(self, element_id, default):
        element = self.element(element_id)
        if element is not None and element.color is not None:
            return element.color
        return default

    def size(self, element_id, default):
        element = self.element(element_id)
        return element.size if element is not None and element.size else default

    def row_height(self, element_id, default):
        element = self.element(element_id)
        return element.row_height if element is not None and element.row_height else default

    def icon_size(self, element_id, default):
        element = self.element(element_id)
        return element.icon_size if element is not None and element.icon_size else default

    def number(self, element_id, name, default):
        """``columns``, ``cell`` or ``gap`` of a list or grid, else ``default``."""
        element = self.element(element_id)
        if element is None:
            return default
        value = getattr(element, name)
        empty = -1 if name == "gap" else 0
        return default if value == empty else value

    def panel(self, element_id, rect, fill=(13, 17, 28, 220), border=(124, 145, 190)):
        """A frame: the element's skin, picture or colours, else the screen's panel."""
        if not self.shown(element_id):
            self._box(element_id, self.rect(element_id, rect))
            return self.boxes[element_id]
        rect = self.rect(element_id, rect)
        element = self.element(element_id)
        if element is not None and (element.skin or element.image):
            self._draw_look(element, rect)
            return rect
        if element is not None and (element.fill or element.border):
            fill = element.fill or fill
            border = element.border or border
            self._plain_panel(rect, fill, border)
            return rect
        self.rt.panel(rect, fill=fill, border=border)
        return rect

    def text(self, element_id, value, x, y, *, size=20, color=(245, 245, 250), **place):
        """Words at the engine's place, or inside the element's rectangle by its ``align``."""
        element = self.element(element_id)
        if element is not None and not element.visible:
            return None
        if element is None:
            rect = self.rt.text(value, x, y, size=size, color=color, **place)
            self._box(element_id, rect)
            return rect
        size = element.size or size
        color = element.color or color
        font = self.font_of(element)
        if element.text:
            value = self.words(element.text)
        if element.rect is not None:
            rx, ry, rw, rh = resolve_rect(element.rect, element.anchor, self.area)
            align = element.align or "left"
            if align == "center":
                place = {"anchor": "midtop"}
                x, y = rx + rw / 2, ry
            elif align == "right":
                place = {"anchor": "topright"}
                x, y = rx + rw, ry
            else:
                place = {}
                x, y = rx, ry
        rect = self.rt.text(value, x, y, size=size, color=color, font=font, **place)
        self._box(element_id, rect)
        return rect

    def selection(self, element_id, rect, default):
        """The selected row's highlight: the element's selection skin or colour, else the
        theme's, else ``default()`` (the screen's own); the theme's cursor picture, when it has
        one, stands left of the row."""
        self._highlight(element_id, rect, default)
        cursor = self.theme.cursor_image if self.theme is not None else ""
        image = self.rt.skin_image(cursor) if cursor else None
        if image is not None:
            x, y, _w, h = (int(v) for v in rect)
            iw, ih = image.get_size()
            scale = max(1, min(4, int(h * 0.8 // max(1, ih))))
            size = (iw * scale, ih * scale)
            picture = self.rt.scaled_image(image, size)
            self.screen.blit(picture, (x - size[0] - 4, y + (h - size[1]) // 2))

    def _highlight(self, element_id, rect, default):
        element = self.element(element_id)
        skin = (element.selection_skin if element else None) or (
            self.theme.selection_skin if self.theme else None
        )
        fill = (element.selection_fill if element else None) or (
            self.theme.selection_fill if self.theme else None
        )
        if skin is not None:
            image = self.rt.skin_image(skin.asset_id)
            if image is not None:
                from asteria.presentation.ui_skin import draw_nine_patch

                draw_nine_patch(self.rt.pg, self.screen, image, tuple(map(int, rect)), skin)
                return
        if fill is not None:
            self.rt.pg.draw.rect(self.screen, fill, rect, border_radius=4)
            return
        default()

    # --- fields, background and the author's own elements --------------------------------
    def field(self, name):
        value = self.fields.get(name)
        return value() if callable(value) else value

    def words(self, text):
        """An element's text: ``key:<translation key>|<English>`` or plain words; ``{field}``
        is filled from the screen's fields."""
        text = str(text)
        if text.startswith("key:"):
            key, _bar, english = text[4:].partition("|")
            text = self.rt.game.tr(key.strip(), english or key.strip())

        def fill(match):
            value = self.field(match.group(1))
            if value is None:
                return match.group(0)
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            return str(value)

        return _FIELD.sub(fill, text)

    def begin(self, dim_default=None):
        """The layout's background and the author's elements under the screen. Returns how
        dark to draw the map behind (``dim_default`` unless the layout says)."""
        layout = self.layout
        if layout is None:
            return dim_default
        size = self.area
        if layout.music:  # played while the screen is open; the field's comes back after
            self.rt._music(layout.music)
        if layout.background_color is not None:
            self.screen.fill(layout.background_color)
        if layout.background_image:
            self._image(layout.background_image, (0, 0, *size), layout.background_mode)
        self._extras(lambda layer: layer < 0)
        return dim_default if layout.dim < 0 else layout.dim

    def finish(self):
        if self.layout is not None:
            self._extras(lambda layer: layer >= 0)

    def _extras(self, wanted):
        elements = [e for e in self.layout.elements if e.extra and e.visible and wanted(e.layer)]
        for element in sorted(elements, key=lambda e: e.layer):
            if element.rect is None:
                continue
            rect = resolve_rect(element.rect, element.anchor, self.area)
            self._box(element.element_id, rect)
            self._draw_extra(element, rect)

    def _draw_extra(self, element, rect):
        rt = self.rt
        if element.kind in ("panel", "image"):
            self._draw_look(element, rect)
        elif element.kind == "portrait":
            asset = self.field(element.binding) if element.binding else element.image
            if asset:
                self._image(str(asset), rect, element.image_mode or "fit")
        elif element.kind == "gauge":
            value = self.field(element.binding) if element.binding else None
            current, maximum = (value if isinstance(value, tuple) else (value or 0, 1))[:2]
            if element.skin or element.image:
                self._draw_look(element, rect)
            fill = element.color or (90, 203, 130)
            rt.bar(*rect, current, maximum, fill=fill, bg=element.fill or (48, 53, 66))
        else:  # text, hint and any other kind: words in the rectangle
            if element.skin or element.image or element.fill:
                self._draw_look(element, rect)
            if element.text:
                words = self.words(element.text)
            else:
                value = self.field(element.binding) if element.binding else None
                words = "" if value is None else str(value)
            if not words:
                return
            size = element.size or 20
            color = element.color or self._theme_color("text_color", (245, 245, 250))
            align = element.align or "left"
            font = self.font_of(element)
            if align == "center":
                rt.text(words, rect[0] + rect[2] / 2, rect[1], size=size, color=color,
                        font=font, anchor="midtop")  # fmt: skip
            elif align == "right":
                rt.text(words, rect[0] + rect[2], rect[1], size=size, color=color,
                        font=font, anchor="topright")  # fmt: skip
            else:
                rt.text(words, rect[0], rect[1], size=size, color=color, font=font)

    @staticmethod
    def font_of(element):
        """The ``font`` argument of ``rt.text`` for an element: its bitmap font, its font
        file, or None (the menu theme's)."""
        if element is None:
            return None
        if element.bitmap_font:
            return "bitmap:" + element.bitmap_font
        return element.font or None

    def _theme_color(self, name, default):
        value = getattr(self.theme, name, None) if self.theme is not None else None
        return value or default

    def _draw_look(self, element, rect, frame=None, mode=None):
        if element.skin is not None:
            image = self.rt.skin_image(element.skin.asset_id)
            if image is not None:
                from asteria.presentation.ui_skin import draw_nine_patch

                draw_nine_patch(self.rt.pg, self.screen, image, tuple(rect), element.skin)
                return
        if element.image:
            if self._image(element.image, rect, mode or element.image_mode, element, frame):
                return
        if element.fill or element.border:
            self._plain_panel(rect, element.fill or (0, 0, 0, 0), element.border)

    def _plain_panel(self, rect, fill, border):
        pg = self.rt.pg
        x, y, w, h = (int(v) for v in rect)
        if fill and (len(fill) == 3 or fill[3] > 0):
            surface = pg.Surface((max(1, w), max(1, h)), pg.SRCALPHA)
            surface.fill(fill)
            self.screen.blit(surface, (x, y))
        if border:
            pg.draw.rect(self.screen, border, (x, y, w, h), 2, border_radius=6)

    def strip_frame(self, image, element, frame=None):
        """One frame of a strip picture: ``frame`` when the screen picks it (a fraction
        0-1 of the strip, e.g. a cooldown, or a whole frame number), else by the clock at the
        element's ``fps``. A still picture comes back as it is."""
        count = element.frames if element is not None else 0
        if count <= 1:
            return image
        iw, ih = image.get_size()
        if frame is None:
            ticks = self.rt.pg.time.get_ticks() / 1000.0
            index = int(ticks * element.fps) if element.fps > 0 else 0
        elif isinstance(frame, float):
            index = min(count - 1, int(max(0.0, frame) * count))
        else:
            index = int(frame)
        index %= count
        if element.frame_axis == "y":
            step = ih // count
            area = (0, index * step, iw, step)
        else:
            step = iw // count
            area = (index * step, 0, step, ih)
        if step <= 0:
            return image
        return image.subsurface(self.rt.pg.Rect(area))

    def picture(
        self, element_id, rect, frame=None, mode=None, *, repeated=False, pictures_only=False
    ):
        """Draw the element's own picture or frame (skin, picture or colours) at ``rect``
        (moved by the layout); False when the layout gives it no look, so the screen draws
        its own. Screens offer their pieces (a node's frame, an orb, a keycap) this way. A
        ``repeated`` piece (every node, every slot) stays where the screen puts it;
        ``pictures_only``: the element's colours mean something else there (an orb's liquid),
        so only a nine-patch or a picture counts as its look."""
        element = self.element(element_id)
        if repeated:
            self._box(element_id, rect)
        else:
            rect = self.rect(element_id, rect)
        if element is None:
            return False
        if not element.visible:
            return True  # hidden: nothing drawn, and not the screen's own either
        colours = not pictures_only and (element.fill or element.border)
        if not (element.skin or element.image or colours):
            return False
        if pictures_only and not element.skin:
            return self._image(element.image, rect, mode or element.image_mode, element, frame)
        self._draw_look(element, rect, frame, mode)
        return True

    def _image(self, asset_id, rect, mode="stretch", element=None, frame=None):
        image = self.rt.skin_image(asset_id)
        if image is None:
            return False
        image = self.strip_frame(image, element, frame)
        pg, screen = self.rt.pg, self.screen
        x, y, w, h = (int(v) for v in rect)
        iw, ih = image.get_size()
        if w <= 0 or h <= 0 or iw <= 0 or ih <= 0:
            return False
        if mode == "tile":
            clip = screen.get_clip()
            screen.set_clip(pg.Rect(x, y, w, h).clip(clip) if clip else pg.Rect(x, y, w, h))
            for ty in range(y, y + h, ih):
                for tx in range(x, x + w, iw):
                    screen.blit(image, (tx, ty))
            screen.set_clip(clip)
        elif mode == "center":
            screen.blit(image, (x + (w - iw) // 2, y + (h - ih) // 2))
        elif mode == "fit":
            scale = min(w / iw, h / ih)
            size = (max(1, round(iw * scale)), max(1, round(ih * scale)))
            scaled = self.rt.scaled_image(image, size)
            screen.blit(scaled, (x + (w - size[0]) // 2, y + (h - size[1]) // 2))
        else:
            screen.blit(self.rt.scaled_image(image, (w, h)), (x, y))
        return True
