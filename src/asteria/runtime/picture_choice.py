"""Choosing one of a few pictured things (world command ``PICTURE_CHOICE``): a starter from a
bag, a class from a row of statues... Drawn at the game's own resolution (240 x 160) from the
layout ``field.picture_choices.<layout>`` of the playable manifest; the event waits until the
choice is made (condition ``rpg`` ``picture_choice`` is "" again) and the chosen option's
``value`` is in the request's ``variable``.

A layout (every key but ``options`` optional):

* ``background``: pictures drawn in order; ``prompt``: the words in the message window;
  ``start``: the option chosen first.
* ``options``: ``[{"value", "at", "label", "label_at", "preview"}]`` - ``at`` the option's
  picture centre; ``label`` lines shown in a darkened box (``label_size``, ``label_dim``
  0..1) at ``label_at`` while it is chosen; ``preview`` a picture shown on confirming.
* ``item``: the options' picture - ``sheet`` with ``frame`` ``[w, h]`` frames under each
  other, ``still`` (frame), ``moving`` (``[[frame, GBA frames], ...]`` looped for the chosen).
* ``cursor``: ``sheet`` frame ``frame_index`` at ``cursor_at`` (one per option) bobbing
  ``bob`` pixels up and down.
* ``confirm``: ``prompt``, ``circle`` (a picture growing behind the preview) moving to
  ``centre``, ``yes_no_at`` (the YES / NO window's inside).
"""

from __future__ import annotations

import math

from asteria.presentation.creature_screens import creature_settings
from asteria.runtime.creature_battle import H, W
from asteria.runtime.creature_menu import CreatureMenuScreen

FRAME = 1 / 59.7275


class PictureChoiceScreen(CreatureMenuScreen):
    def __init__(self, runtime, request):
        super().__init__(runtime, "pick")
        self.request = dict(request)
        layouts = creature_settings(runtime, "field.picture_choices")
        self.layout = dict(layouts.get(self.request.get("layout", ""), {}))
        self.options = list(self.layout.get("options") or [])
        self.index = int(self.layout.get("start", 0) or 0) % max(1, len(self.options))
        self.grow = 0.0  # the confirm circle's time
        self.yes = 0

    # -- input ------------------------------------------------------------------------------------
    def _input_pick(self):
        count = len(self.options)
        if not count:
            self._finish(None)
            return
        if self._pressed("move_left"):
            self.index = (self.index - 1) % count
            self.time = 0.0
        if self._pressed("move_right"):
            self.index = (self.index + 1) % count
            self.time = 0.0
        if self._pressed("confirm"):
            self.phase, self.grow, self.yes = "confirm", 0.0, 0

    def _input_confirm(self):
        if self._pressed("move_up") or self._pressed("move_down"):
            self.yes = 1 - self.yes
        if self._pressed("cancel") or (self._pressed("confirm") and self.yes == 1):
            self.phase = "pick"
        elif self._pressed("confirm"):
            self._finish(self.options[self.index].get("value", self.index))

    def _finish(self, value):
        self.game.finish_picture_choice(value)
        self.done = True

    def update(self, dt, events=()):
        self.grow += dt
        super().update(dt, events)

    # -- drawing ----------------------------------------------------------------------------------
    def _sheet_frame(self, spec, index):
        sheet = self._menu_picture(spec.get("sheet"))
        if sheet is None:
            return None
        w, h = spec.get("frame", (sheet.get_width(), sheet.get_width()))
        index = max(0, min(int(index), sheet.get_height() // h - 1))
        return sheet.subsurface((0, index * h, w, h))

    def _moving_frame(self, spec):
        """The chosen option's frame now (``moving``: [frame, GBA frames] looped)."""
        steps = spec.get("moving") or [[spec.get("still", 0), 30]]
        total = sum(n for _f, n in steps) * FRAME
        clock = self.time % total if total else 0.0
        for frame, frames in steps:
            clock -= frames * FRAME
            if clock < 0:
                return frame
        return steps[-1][0]

    def draw(self):
        s = self.surface
        s.fill((0, 0, 0, 255))
        for path in self.layout.get("background") or ():
            picture = self._menu_picture(path)
            if picture is not None:
                s.blit(picture, (0, 0))
        item = self.layout.get("item") or {}
        for n, option in enumerate(self.options):
            chosen = n == self.index
            frame = self._moving_frame(item) if chosen else item.get("still", 0)
            picture = self._sheet_frame(item, frame)
            if picture is not None:
                x, y = option.get("at", (0, 0))
                s.blit(picture, (x - picture.get_width() // 2, y - picture.get_height() // 2))
        if self.phase == "pick":
            self._draw_cursor()
            self._draw_label()
            self._message_window(self._words(self.layout.get("prompt", "")))
        else:
            self._draw_preview()
            confirm = self.layout.get("confirm") or {}
            self._message_window(self._words(confirm.get("prompt", "")))
            self._draw_yes_no(confirm.get("yes_no_at", (192, 72)))
        screen = self.rt.screen
        sw, sh = screen.get_size()
        scale = max(1, min(sw // W, sh // H))
        screen.fill((0, 0, 0, 255))
        screen.blit(self.pg.transform.scale(s, (W * scale, H * scale)),
                    ((sw - W * scale) // 2, (sh - H * scale) // 2))  # fmt: skip

    def _words(self, text):
        return self.game.expand_message(str(text or ""), plain=True)

    def _draw_cursor(self):
        cursor = self.layout.get("cursor") or {}
        picture = self._sheet_frame(cursor, cursor.get("frame_index", 0))
        places = cursor.get("cursor_at") or []
        if picture is None or self.index >= len(places):
            return
        x, y = places[self.index]
        steps = (self.time / FRAME) * 4  # Sin(data, 8): 256 steps a turn, 4 a frame
        y += round(math.sin(steps / 256 * 2 * math.pi) * float(cursor.get("bob", 8)))
        self.surface.blit(picture, (x - picture.get_width() // 2, y - picture.get_height() // 2))

    def _draw_label(self):
        option = self.options[self.index] if self.options else {}
        lines = [self._words(line) for line in option.get("label") or ()]
        if not lines:
            return
        x, y = option.get("label_at", (0, 0))
        w, h = self.layout.get("label_size", (104, 32))
        dim = float(self.layout.get("label_dim", 7 / 16))
        box = self.surface.subsurface((max(0, x - 4), y, min(W, w + 8), h)).copy()
        shade = self.pg.Surface(box.get_size(), self.pg.SRCALPHA)
        shade.fill((0, 0, 0, round(255 * dim)))  # BLDCNT darken inside the label's window
        box.blit(shade, (0, 0))
        self.surface.blit(box, (max(0, x - 4), y))
        for n, line in enumerate(lines):
            font = self.font_small if n == 0 and len(lines) > 1 else self.font
            main, self.font = self.font, font
            try:
                self._text(line, x + w // 2, y + 1 + n * 16, (255, 255, 255), (148, 148, 148),
                           anchor="midtop")  # fmt: skip
            finally:
                self.font = main

    def _draw_preview(self):
        option = self.options[self.index]
        confirm = self.layout.get("confirm") or {}
        sx, sy = option.get("at", (120, 64))
        cx, cy = confirm.get("centre", (120, 64))
        moved = min(1.0, self.grow / (16 * FRAME))  # 4 pixels a frame towards the centre
        x, y = sx + (cx - sx) * moved, sy + (cy - sy) * moved
        circle = self._menu_picture(confirm.get("circle"))
        if circle is not None:
            size = max(1, round(circle.get_width() * min(1.0, self.grow / (16 * FRAME))))
            grown = self.pg.transform.scale(circle, (size, size))
            self.surface.blit(grown, (round(x - size / 2), round(y - size / 2)))
        preview = self._menu_picture(self._words(option.get("preview", "")))
        if preview is not None and moved >= 1.0:
            self.surface.blit(preview, (round(x - preview.get_width() / 2),
                                        round(y - preview.get_height() / 2)))  # fmt: skip

    def _draw_yes_no(self, at):
        letter, shadow = self._menu_colours()
        x, y = at
        self._frame((x, y, 32, 32))
        rows = (self.tr("creature.yes", "YES"), self.tr("creature.no", "NO"))
        for row, label in enumerate(rows):
            self._text(label, x + 8, y + row * 16 + 1, letter, shadow)
            if row == self.yes:
                self._cursor(x, y + row * 16 + 3)


__all__ = ["PictureChoiceScreen"]
