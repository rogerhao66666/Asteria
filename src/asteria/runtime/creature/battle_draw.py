"""Drawing the creature battle: the field, the creatures, their boxes and the effects."""

from __future__ import annotations

import math
from pathlib import Path

from asteria.graphics.bitmap_font import BitmapFont
from asteria.platform.pygame_battle_ui import font_for_text, renderable_text
from asteria.runtime.creature.battle_style import (
    BALL_SECONDS,
    BALL_SPIN,
    BAR_FRAME,
    BAR_TRACK,
    BOX_DARK,
    BOX_EDGE,
    BOX_FILL,
    BOX_SLIDE,
    BOX_TOP,
    CMD_EDGE,
    CMD_LINE,
    CMD_X,
    EXP_BLUE,
    EXP_TRACK,
    FOE_BOX,
    FOE_CENTRE,
    GRASS,
    GRASS_BAND,
    GROW_SECONDS,
    HP_GREEN,
    HP_LABEL,
    HP_RED,
    HP_YELLOW,
    INFO_X,
    INK,
    INK_SHADOW,
    MINE_BOX,
    MINE_CENTRE,
    MOVE_X,
    MSG_EDGE,
    MSG_FILL,
    MSG_INNER,
    MSG_X,
    PAD,
    PAD_EDGE,
    ROW_1,
    ROW_2,
    WHITE,
    H,
    W,
    _move_type,
)
from asteria.runtime.pointer import hand_over


class BattleDrawMixin:
    """Drawing the creature battle: the field, the creatures, their boxes and the effects."""

    # -- drawing ---------------------------------------------------------------------------------
    def _font(self, size=16):
        font = self._fonts.get(size)
        if font is None:
            font = self._fonts[size] = self.pg.font.Font(None, size)
        return font

    def _text(self, value, x, y, colour=INK, shadow=INK_SHADOW, size=16, anchor="topleft"):
        value = str(value)
        if self.font is not None and self.font.covers(value):
            rect = self.pg.Rect(0, 0, self.font.width(value), self.font.line)
            setattr(rect, anchor, (int(x), int(y)))
            self.font.render(self.surface, value, rect.x, rect.y, colour, shadow)
            return rect

        base = self._font(size)
        font = font_for_text(self.pg, base, value, self._cjk, max(9, size - 4))
        text = renderable_text(self.pg, font, str(value), self._glyphs)
        image = font.render(text, False, colour)
        rect = image.get_rect(**{anchor: (int(x), int(y))})
        if shadow is not None:
            back = font.render(text, False, shadow)
            self.surface.blit(back, rect.move(1, 0))
            self.surface.blit(back, rect.move(0, 1))
            self.surface.blit(back, rect.move(1, 1))
        self.surface.blit(image, rect)
        return rect

    def _image(self, kind, key, size):
        """Project art for ``kind`` (front / back / trainer / background) named by ``key``, at
        ``size``; ``None`` when the project has none."""
        cache_key = (kind, key, size)
        if cache_key in self._images:
            return self._images[cache_key]
        image = None
        pattern = self.settings.get(kind)
        if pattern:
            path = Path(self.rt.resource_root) / str(pattern).format(
                species=key, trainer=key, item=key
            )
            if path.is_file():
                try:
                    image = self.pg.image.load(str(path)).convert_alpha()
                except Exception:  # noqa: BLE001 - a broken file is drawn as a shape
                    image = None
                if image is not None and size and image.get_size() != size:
                    from asteria.graphics.scaling import resized

                    image = resized(self.pg, image, size)
        self._images[cache_key] = image
        return image

    def _load_font(self, name):
        if not self.settings.get(name):
            return None

        try:
            return BitmapFont(self.pg, self._path(self.settings[name]))
        except (OSError, ValueError, KeyError):
            return None

    def _path(self, value):
        return Path(self.rt.resource_root) / str(value)

    def _art(self, name):
        """The project's picture for a part of the screen (``battle.creature_screen[name]``)."""
        key = ("art", name)
        if key not in self._images:
            image = None
            value = self.settings.get(name)
            if isinstance(value, str) and "\\" in value:  # \\V[..]: a picture per variable value
                value = self.game.expand_message(value, plain=True)
            if isinstance(value, str) and self._path(value).is_file():
                try:
                    image = self.pg.image.load(str(self._path(value))).convert_alpha()
                except Exception:  # noqa: BLE001 - a broken file is drawn as before
                    image = None
            self._images[key] = image
        return self._images[key]

    def _bar_tiles(self, colour):
        key = ("bar", colour)
        if key not in self._images:
            image = None
            value = (
                self.settings.get("hp_bar") if colour != "exp" else self.settings.get("exp_bar")
            )
            if isinstance(value, dict):
                value = value.get(colour)
            if isinstance(value, str) and self._path(value).is_file():
                image = self.pg.image.load(str(self._path(value))).convert_alpha()
            self._images[key] = image
        return self._images[key]

    def _tile_bar(self, tiles, x, y, share, cells):
        """A bar of ``cells`` 8-pixel tiles, each the tile of its fill (0-8 pixels)."""
        pixels = round(cells * 8 * max(0.0, min(1.0, share)))
        if share > 0 and pixels == 0:
            pixels = 1
        offset = 9 if tiles.get_width() >= 80 else 0  # strips with a leading cap tile
        for cell in range(cells):
            filled = max(0, min(8, pixels - cell * 8))
            self.surface.blit(
                tiles, (x + cell * 8, y), ((offset + filled) * 8 % tiles.get_width(), 0, 8, 8)
            )

    def _offset(self, member_id, side):
        """How far a creature's picture sits below its battle spot (``sprite_offsets``)."""
        table = self._images.get(("offsets",))
        if table is None:
            value = self.settings.get("sprite_offsets") or {}
            if isinstance(value, str):
                import json

                path = self._path(value)
                value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            table = self._images[("offsets",)] = dict(value)
        entry = table.get(self._species_key(member_id), {})
        if side == "heroes":
            return int(entry.get("back", 0))
        return int(entry.get("front", 0)) - int(entry.get("lift", 0))

    def _species_key(self, member_id):
        record = self.game.unit_record(member_id) if member_id else None
        return record.species_id if record is not None else str(member_id).split(":", 1)[0]

    def draw(self):
        s = self.surface
        s.fill((0, 0, 0, 255))
        self._draw_background()
        if self.phase == "party":
            self._draw_party()
        elif self.phase == "bag":
            self._draw_bag()
        else:
            self._draw_creatures()
            self._draw_info_boxes()
            self._draw_message()
            if self.phase == "command":
                self._draw_commands()
            elif self.phase == "fight":
                self._draw_fight()
            elif self.phase == "yesno":
                self._draw_yes_no()
        screen = self.rt.screen
        sw, sh = screen.get_size()
        scale = max(1, min(sw // W, sh // H))
        screen.fill((0, 0, 0, 255))
        big = self.pg.transform.scale(s, (W * scale, H * scale))
        left, top = (sw - W * scale) // 2, (sh - H * scale) // 2
        screen.blit(big, (left, top))
        hand_over(self.rt, self._pointer_spots(), scale, left, top)

    def _pointer_spots(self):
        """``[(rect, pick, key)]`` in the screen's own pixels: what the mouse can point at in
        this phase (D85) - a command, a move, YES / NO, a party slot, a bag row; else the
        whole screen, where a click reads on."""
        phase = self.phase

        def to(attr, value):
            return lambda: setattr(self, attr, value)

        if phase == "command" and not self.auto_choices:
            return [((CMD_X[i % 2] - 9, (ROW_1, ROW_2)[i // 2] - 3, 56, 16), to("cursor", i),
                     "return") for i in range(4)]  # fmt: skip
        if phase == "fight":
            count = len(self._moves())
            return [((MOVE_X[i % 2] - 9, (ROW_1, ROW_2)[i // 2] - 3, 72, 16),
                     to("list_cursor", i), "return") for i in range(count)]  # fmt: skip
        if phase == "yesno":
            x, y = self.layout.get("yes_no", (200, 72))
            prompt = self.prompt if isinstance(self.prompt, dict) else {}
            return [((x, y + 6 + row * 16, 40, 16), lambda row=row: prompt.update(cursor=row),
                     "return") for row in (0, 1)]  # fmt: skip
        if phase == "party":
            count = len(self._party())
            spots = [(self.PARTY_SLOTS[i], to("list_cursor", i), "return") for i in range(count)]
            if not self.forced_switch:  # CANCEL
                spots.append(((*self.PARTY_CANCEL, 56, 24), to("list_cursor", count), "return"))
            return spots
        if phase == "bag":
            items = self._bag_items()
            if self._bag_art("background") is None:  # the drawn bag: its own places
                spots = [((8, 8, 40, 18), None, "left"), ((48, 8, 40, 18), None, "right")]
                return spots + [((96, 10 + i * 15, 140, 15), to("list_cursor", i), "return")
                                for i in range(min(6, len(items)))]  # fmt: skip
            left, top, width = self.BAG_LIST
            (lx, ly), (rx, ry) = self.BAG_ARROWS
            spots = [((lx - 4, ly - 4, 16, 20), None, "left"),
                     ((rx - 4, ry - 4, 16, 20), None, "right")]  # fmt: skip
            return spots + [((left, top - 1 + i * 16, width, 16), to("list_cursor", i), "return")
                            for i in range(min(8, len(items) + 1))]  # fmt: skip
        return [((0, 0, W, H), None, "return")]

    def _draw_background(self):
        pg, s = self.pg, self.surface
        picture = self._art("background")
        if picture is not None:
            s.blit(picture, (0, 0))
        else:
            s.fill(GRASS, (0, 0, W, BOX_TOP))
            for y in range(4, BOX_TOP, 8):
                pg.draw.line(s, GRASS_BAND, (0, y), (W, y), 3)
            for rect in ((120, 52, 112, 24), (8, 94, 128, 28)):  # the two platforms
                pg.draw.ellipse(s, PAD, rect)
                pg.draw.ellipse(s, PAD_EDGE, rect, 2)
        s.fill(MSG_FILL, (0, BOX_TOP, W, H - BOX_TOP))

    def _creature_picture(self, member_id, side):
        kind = "back" if side == "heroes" else "front"
        key = self._species_key(member_id)
        image = self._image(kind, key, (64, 64))
        if image is not None:
            return image
        return self._shape(key, back=side == "heroes")

    def _shape(self, key, *, back):
        """A stand-in 64 x 64 creature: a round body in a colour of its own with ears."""
        cache_key = ("shape", key, back)
        if cache_key in self._images:
            return self._images[cache_key]
        pg = self.pg
        image = pg.Surface((64, 64), pg.SRCALPHA)
        seed = sum(ord(c) for c in key)
        colour = ((seed * 53) % 160 + 60, (seed * 97) % 160 + 60, (seed * 31) % 160 + 60)
        dark = tuple(max(0, c - 70) for c in colour)
        pg.draw.ellipse(image, colour, (10, 18, 44, 42))
        pg.draw.ellipse(image, dark, (10, 18, 44, 42), 2)
        pg.draw.polygon(image, colour, ((16, 26), (20, 6), (28, 22)))
        pg.draw.polygon(image, colour, ((48, 26), (44, 6), (36, 22)))
        if not back:
            pg.draw.circle(image, (40, 40, 40), (26, 36), 3)
            pg.draw.circle(image, (40, 40, 40), (38, 36), 3)
        self._images[cache_key] = image
        return image

    def _progress(self, name):
        """How far a slide has gone, 0..1 (None when it never started)."""
        slide = self.slides.get(name)
        if slide is None:
            return None
        start, seconds = slide
        return max(0.0, min(1.0, (self.time - start) / seconds)) if seconds else 1.0

    def _intro_offsets(self):
        """(foe side dx, player side dx) of the opening slide."""
        k = self._progress("intro")
        k = 1.0 if k is None else k
        return -round((1 - k) * W), round((1 - k) * W)

    def _draw_creatures(self):
        pg, s = self.pg, self.surface
        foe_dx, mine_dx = self._intro_offsets()
        foe = self.visible["enemies"]
        if self.trainer_shown:
            image = self._image("trainer", self.trainer.get("sprite", "trainer"), (64, 64))
            if image is None:
                image = self._shape(self.trainer.get("sprite", "trainer"), back=False)
            out = self._progress("trainer_out") or 0.0
            back_in = self._progress("trainer_in")
            if back_in is not None:  # sliding back in from the right after the win
                out = 1.0 - back_in
            centre = (FOE_CENTRE[0] + foe_dx + round(out * 120), FOE_CENTRE[1])
            s.blit(image, image.get_rect(center=centre))
        if foe is not None and not self._in_ball(foe):
            spot = (FOE_CENTRE[0] + foe_dx, FOE_CENTRE[1] + self._offset(foe, "enemies"))
            self._blit_creature(foe, "enemies", spot)
        if self.throw is not None:
            self._draw_throw()
        mine = self.visible["heroes"]
        if mine is not None:
            bob = 1 if self.phase in ("command", "fight") and int(self.time * 2.5) % 2 else 0
            spot = (MINE_CENTRE[0] + mine_dx, MINE_CENTRE[1] + self._offset(mine, "heroes") + bob)
            self._blit_creature(mine, "heroes", spot)
        if self.back_shown:
            self._draw_player_back(mine_dx)
        if self.ball is not None:
            self._draw_ball_out()
        _ = pg

    def _draw_player_back(self, dx):
        """The player seen from behind (``player_back``: frames under each other, 64 x 64):
        standing, then winding up, throwing and stepping out to the left."""
        image = self._art("player_back")
        if image is None:
            return
        size = int(self.settings.get("player_back_size", 64))
        frames = max(1, image.get_height() // size)
        k = self._progress("back_out")
        frame, out = 0, 0
        if k is not None:
            frame = min(frames - 1, int(k / 0.55 * frames)) if k < 0.55 else frames - 1
            out = round(max(0.0, (k - 0.45) / 0.55) * 110)
        centre = (MINE_CENTRE[0] + dx - out, MINE_CENTRE[1] + 4)
        piece = image.subsurface((0, frame * size, size, size))
        self.surface.blit(piece, piece.get_rect(center=centre))

    def _draw_ball_out(self):
        """A ball flying from the thrower to the spot, opening as the creature comes out."""
        ball = self.ball
        t = (self.time - ball["start"]) / BALL_SECONDS
        if t < 0:
            return
        if ball["side"] == "heroes":
            (x0, y0), (x1, y1) = (36, 92), (MINE_CENTRE[0], MINE_CENTRE[1] + 10)
        else:
            (x0, y0), (x1, y1) = (W - 20, 24), (FOE_CENTRE[0], FOE_CENTRE[1] + 10)
        k = min(1.0, t)
        x = x0 + (x1 - x0) * k
        y = y0 + (y1 - y0) * k - 34 * 4 * k * (1 - k)
        if t > 1.0 + GROW_SECONDS / BALL_SECONDS:
            return
        image = self._art("ball")
        if image is None:
            self._drawn_ball((round(x), round(y)))
            return
        size = image.get_width()
        frames = max(1, image.get_height() // size)
        frame = 0 if t < 1.0 else min(frames - 1, 1 + int((t - 1.0) * 6))
        piece = image.subsurface((0, frame * size, size, size))
        if t < 1.0:  # spinning while it flies, the way it is thrown; still once it lands
            piece = self._spun(piece, k, rightwards=x1 > x0)
        self.surface.blit(piece, piece.get_rect(center=(round(x), round(y))))

    def ball_turns(self):
        """``ball_spin``: the turns a ball makes in flight (0: it does not spin)."""
        try:
            return max(0.0, float(self.settings.get("ball_spin", BALL_SPIN)))
        except (TypeError, ValueError):
            return BALL_SPIN

    def ball_angle(self, progress, rightwards=True):
        """The ball's turn in degrees ``progress`` (0 to 1) of the way through its flight:
        clockwise when thrown to the right, the other way to the left."""
        angle = 360.0 * self.ball_turns() * max(0.0, min(1.0, progress))
        return -angle if rightwards else angle

    def _spun(self, piece, progress, rightwards=True):
        angle = self.ball_angle(progress, rightwards) % 360.0
        if angle == 0.0:
            return piece
        return self.pg.transform.rotate(piece, angle)

    def _drawn_ball(self, centre, angle=0.0):
        """A ball drawn without a picture (red over white, the band turned by ``angle``)."""

        pg, s = self.pg, self.surface
        pg.draw.circle(s, WHITE, centre, 5)
        a = math.radians(angle)
        dx, dy = math.cos(a), -math.sin(a)  # along the band; the red half lies "up" of it
        top = [
            (centre[0] + 5 * math.cos(a + step), centre[1] - 5 * math.sin(a + step))
            for step in (math.pi * i / 8 for i in range(9))
        ]
        pg.draw.polygon(s, (232, 64, 56), top)
        pg.draw.circle(s, (32, 32, 32), centre, 5, 1)
        ends = ((centre[0] - 5 * dx, centre[1] - 5 * dy), (centre[0] + 5 * dx, centre[1] + 5 * dy))
        pg.draw.line(s, (32, 32, 32), *ends)
        pg.draw.circle(s, WHITE, centre, 2)
        pg.draw.circle(s, (32, 32, 32), centre, 2, 1)

    def _blit_creature(self, member_id, side, centre):
        image = self._creature_picture(member_id, side)
        if member_id in self.flash and int(self.flash[member_id] * 16) % 2:
            return
        grow = self.grow.get(member_id)
        if grow is not None:  # coming out of its ball, or going back in
            start, seconds, appearing = grow
            k = max(0.0, min(1.0, (self.time - start) / seconds)) if seconds else 1.0
            scale = k if appearing else 1.0 - k
            if scale <= 0.02:
                return
            if scale < 1.0:
                w, h = image.get_size()
                image = self.pg.transform.scale(
                    image, (max(1, round(w * scale)), max(1, round(h * scale)))
                )
                bottom = centre[1] + 32
                self.surface.blit(image, image.get_rect(midbottom=(centre[0], bottom)))
                return
        rect = image.get_rect(center=centre)
        if member_id in self.drop:
            fall = int(min(1.0, self.drop[member_id] / 0.4) * 64)
            if fall >= 64:
                return
            area = self.pg.Rect(0, 0, 64, 64 - fall)
            self.surface.blit(image, rect.move(0, fall), area)
            return
        self.surface.blit(image, rect)

    def _in_ball(self, member_id):
        throw = self.throw
        if throw is None or throw["member"] != member_id:
            return False
        t = self.time - throw["start"]
        return t > 0.6 and (throw["caught"] or t < self._throw_length() - 0.15)

    def _draw_throw(self):
        s = self.surface
        throw = self.throw
        t = self.time - throw["start"]
        if t < 0.6:  # the arc from the player towards the foe
            k = t / 0.6
            x = 40 + (FOE_CENTRE[0] - 40) * k
            y = 90 - 70 * k + 90 * k * k * 0.5
        else:
            x, y = FOE_CENTRE[0], FOE_CENTRE[1] + 16
        if t > self._throw_length() and not throw["caught"]:
            self.throw = None
            return
        shake = 0
        if 0.9 < t < 0.9 + 0.55 * throw["shakes"]:
            phase = (t - 0.9) % 0.55
            shake = -3 if phase < 0.14 else 3 if phase < 0.28 else 0
        centre = (int(x) + shake, int(y))
        flying = min(1.0, t / 0.6)  # spinning on the way, still once it lands
        image = self._art("ball")
        if image is None:
            self._drawn_ball(centre, self.ball_angle(flying) if t < 0.6 else 0.0)
            return
        size = image.get_width()
        piece = image.subsurface((0, 0, size, size))  # closed (the project's ``ball``)
        if t < 0.6:
            piece = self._spun(piece, flying)
        s.blit(piece, piece.get_rect(center=centre))

    def _bar(self, x, y, member_id, width=48):
        """The health bar: the project's label and tiles when it has them, else drawn."""
        pg, s = self.pg, self.surface
        top = max(1.0, self._max_hp(member_id))
        share = max(0.0, min(1.0, self.shown_hp.get(member_id, 0.0) / top))
        colour_name = "green" if share > 0.5 else "yellow" if share > 0.2 else "red"
        label, tiles = self._art("hp_label"), self._bar_tiles(colour_name)
        if label is not None and tiles is not None:
            s.blit(label, (x - label.get_width(), y))
            self._tile_bar(tiles, x, y, share, width // 8)
            return
        colour = {"green": HP_GREEN, "yellow": HP_YELLOW, "red": HP_RED}[colour_name]
        pg.draw.rect(s, BAR_FRAME, (x - 17, y - 1, width + 18, 6), border_radius=2)
        pg.draw.rect(s, HP_LABEL, (x - 16, y, 14, 4))
        self._text("HP", x - 15, y - 2, colour=WHITE, shadow=None, size=9)
        pg.draw.rect(s, BAR_TRACK, (x, y, width, 4))
        filled = round(width * share)
        if share > 0 and filled == 0:
            filled = 1
        pg.draw.rect(s, colour, (x, y, filled, 3))

    def _level(self, member_id):
        record = self.game.unit_record(member_id)
        return record.level if record is not None else 1

    def _box(self, name, size):
        """An info box at its layout corner: the project's picture or a drawn frame."""
        pg, s = self.pg, self.surface
        x, y = self.layout[f"{name}_box"]
        picture = self._art(f"healthbox_{name}")
        if picture is not None:
            s.blit(picture, (x, y))
            return
        box = pg.Rect(x, y, *size)
        pg.draw.rect(s, BOX_DARK, box.inflate(2, 2), border_radius=4)
        pg.draw.rect(s, BOX_FILL, box, border_radius=4)
        pg.draw.rect(s, BOX_EDGE, box, 1, border_radius=4)

    def _at(self, name, dy=0):
        x, y = self.layout[name]
        return x, y + dy

    def _draw_info_boxes(self):
        """Both info boxes, each sliding in from its own edge when it appears."""
        saved = dict(self.layout)
        try:
            for side, sign in (("enemies", -1), ("heroes", 1)):
                start = self.boxes.get(side)
                if start is None:
                    for key in self.BOX_KEYS[side]:  # not shown: drawn far off the screen
                        self.layout[key] = (self.layout[key][0] + sign * 400, self.layout[key][1])
                    continue
                k = max(0.0, min(1.0, (self.time - start) / BOX_SLIDE))
                dx = sign * round((1 - k) * 130)
                for key in self.BOX_KEYS[side]:
                    self.layout[key] = (self.layout[key][0] + dx, self.layout[key][1])
            self._draw_info_boxes_at()
        finally:
            self.layout = saved

    def _ailment_mark(self, member_id, side):
        """The healthbox mark of the member's ailment (``status_icons``: state id -> picture,
        at ``status_at[side]`` from the box's corner)."""
        icons = dict(self.settings.get("status_icons") or {})
        battle = self.game.battle
        if not icons or battle is None or member_id not in battle.members:
            return
        states = battle.member(member_id).subject.states
        if states is None:
            return
        for active in states.active_states():
            if active.state_id in icons:
                key = ("status", active.state_id)
                if key not in self._images:
                    path = self._path(icons[active.state_id])
                    self._images[key] = (
                        self.pg.image.load(str(path)).convert_alpha() if path.is_file() else None
                    )
                picture = self._images[key]
                if picture is None:
                    return
                at = dict(self.settings.get("status_at") or {}).get(side)
                if at is None:  # in place of the bar's HP label, as the handheld games show it
                    x, y = self.layout["foe_hp" if side == "enemies" else "mine_hp"]
                    self.surface.blit(picture, (x - picture.get_width(), y))
                    return
                box = self.layout["foe_box" if side == "enemies" else "mine_box"]
                self.surface.blit(picture, (box[0] + at[0], box[1] + at[1]))
                return

    def _draw_info_boxes_at(self):
        pg, s = self.pg, self.surface
        letter, shadow = self.colours["box"]
        foe = self.visible["enemies"]
        if foe is not None and foe not in self.drop and not self._in_ball(foe):
            self._box("foe", FOE_BOX[2:])
            self._text(self.name(foe), *self._at("foe_name"), colour=letter, shadow=shadow)
            level = self.tr("creature.level", "Lv{level}", level=self._level(foe))
            self._text(
                level, *self._at("foe_level"), colour=letter, shadow=shadow, anchor="topright"
            )
            self._bar(*self._at("foe_hp"), foe)
            self._ailment_mark(foe, "enemies")
            if self._caught_before(foe):
                x, y = self.layout["foe_box"]
                pg.draw.circle(s, (232, 64, 56), (x + 6, y + 20), 3)
                pg.draw.circle(s, WHITE, (x + 6, y + 22), 2)
        mine = self.visible["heroes"]
        if mine is not None and mine not in self.drop:
            bob = 1 if self.phase in ("command", "fight") and int(self.time * 2.5 + 1) % 2 else 0
            box_x, box_y = self.layout["mine_box"]
            self.layout["mine_box"] = (box_x, box_y + bob)
            self._box("mine", MINE_BOX[2:])
            self.layout["mine_box"] = (box_x, box_y)
            self._text(self.name(mine), *self._at("mine_name", bob), colour=letter, shadow=shadow)
            level = self.tr("creature.level", "Lv{level}", level=self._level(mine))
            self._text(
                level,
                *self._at("mine_level", bob),
                colour=letter,
                shadow=shadow,
                anchor="topright",
            )
            self._bar(*self._at("mine_hp", bob), mine)
            self._ailment_mark(mine, "heroes")
            current = max(0, round(self.shown_hp.get(mine, 0)))
            self._text(
                f"{current}/{round(self._max_hp(mine))}",
                *self._at("mine_hp_text", bob),
                colour=letter,
                shadow=shadow,
                anchor="topright",
            )
            record = self.game.unit_record(mine)
            species = self.game.pet_species(record) if record is not None else None
            share = 0.0
            if species is not None and record.level < species.max_level:
                share = max(0.0, min(1.0, record.experience / species.exp_to_next(record.level)))
            x, y = self._at("exp", bob)
            tiles = self._bar_tiles("exp")
            if tiles is not None:
                self._tile_bar(tiles, x, y, share, 8)
            else:
                pg.draw.rect(s, EXP_TRACK, (x, y, 64, 3))
                pg.draw.rect(s, EXP_BLUE, (x, y, round(64 * share), 3))

    def _caught_before(self, member_id):
        record = self.game.foe_record(member_id)
        if record is None or self.trainer:
            return False
        return any(p.species_id == record.species_id for p in self.game.pets())

    def _bottom(self, name):
        """The bottom 48 rows from the project's picture of that state; True when drawn."""
        picture = self._art(name)
        if picture is None:
            return False
        self.surface.blit(picture, (0, BOX_TOP))
        return True

    def _window(self, rect, fill, edge, inner=None):
        pg, s = self.pg, self.surface
        pg.draw.rect(s, edge, rect, border_radius=4)
        pg.draw.rect(s, fill, rect.inflate(-4, -4), border_radius=3)
        if inner is not None:
            pg.draw.rect(s, inner, rect.inflate(-4, -4), 1, border_radius=3)

    def _draw_message(self):
        pg = self.pg
        state = {"command": "window_commands", "fight": "window_moves"}.get(self.phase)
        if not self._bottom(state or "window_message"):
            self._window(pg.Rect(0, BOX_TOP, W, H - BOX_TOP), MSG_FILL, MSG_EDGE, MSG_INNER)
        if self.phase == "fight":
            return
        letter, shadow = self.colours["message"]
        shown = self.message[: int(self.shown_chars)]
        for i, line in enumerate(shown.split("\n")[:2]):
            self._text(line, MSG_X, (ROW_1, ROW_2)[i], colour=letter, shadow=shadow)
        typed = int(self.shown_chars) >= len(self.message)
        if self.phase == "story" and self.step is not None and self.step.kind == "text":
            if typed and self.step.wait and int(self.time * 3) % 2:
                x, y = 226, H - 12
                pg.draw.polygon(self.surface, (248, 96, 56), ((x, y), (x + 6, y), (x + 3, y + 4)))

    def _draw_yes_no(self):
        """The yes / no box at the right above the message window."""
        pg = self.pg
        rect = pg.Rect(*self.layout.get("yes_no", (200, 72)), 40, 40)
        picture = self._art("window_yes_no")
        if picture is not None:
            self.surface.blit(picture, rect.topleft)
        else:
            self._window(rect, WHITE, CMD_EDGE, CMD_LINE)
        letter, shadow = self.colours["menu"]
        words = (self.tr("creature.yes", "YES"), self.tr("creature.no", "NO"))
        for row, word in enumerate(words):
            y = rect.y + 8 + row * 16
            self._text(word, rect.x + 14, y, colour=letter, shadow=shadow)
            if (self.prompt or {}).get("cursor", 0) == row:
                self._cursor(rect.x + 6, y + 2)

    def _cursor(self, x, y):
        letter, shadow = self.colours["menu"]
        if self.font is not None and self.font.covers("▶"):
            self.font.render(self.surface, "▶", x, y - 2, letter, shadow)
            return
        self.pg.draw.polygon(self.surface, INK, ((x, y), (x, y + 8), (x + 4, y + 4)))

    def _draw_commands(self):
        pg = self.pg
        rect = pg.Rect(120, BOX_TOP, 120, H - BOX_TOP)
        if self._art("window_commands") is None:
            self._window(rect, WHITE, CMD_EDGE, CMD_LINE)
        letter, shadow = self.colours["menu"]
        labels = (
            self.tr("creature.cmd.fight", "FIGHT"),
            self.tr("creature.cmd.bag", "BAG"),
            self.tr("creature.cmd.party", "PARTY"),
            self.tr("creature.cmd.run", "RUN"),
        )
        for i, label in enumerate(labels):
            x = CMD_X[i % 2]
            y = (ROW_1, ROW_2)[i // 2]
            self._text(label, x, y, colour=letter, shadow=shadow)
            if i == self.cursor:
                self._cursor(x - 8, y + 2)

    def _draw_fight(self):
        pg = self.pg
        left = pg.Rect(0, BOX_TOP, 160, H - BOX_TOP)
        right = pg.Rect(160, BOX_TOP, 80, H - BOX_TOP)
        if self._art("window_moves") is None:
            self._window(left, WHITE, CMD_EDGE, CMD_LINE)
            self._window(right, WHITE, CMD_EDGE, CMD_LINE)
        letter, shadow = self.colours["menu"]
        moves = self._moves()
        for i in range(4):
            x = MOVE_X[i % 2]
            y = (ROW_1, ROW_2)[i // 2]
            label = self.move_name(moves[i]) if i < len(moves) else "-"
            self._text(label, x, y, colour=letter, shadow=shadow)
            if i == self.list_cursor and i < len(moves):
                self._cursor(x - 8, y + 2)
        if not moves:
            return
        move = moves[min(self.list_cursor, len(moves) - 1)]
        record = self.game.unit_record(self._stage("heroes"))
        left_uses = self.game.pet_uses_left(record, move) if record is not None else None
        definition = self.game.project.gameplay_library.abilities.get(move)
        top = int(getattr(definition, "max_uses", 0) or 0)
        pp = "--/--" if left_uses is None else f"{left_uses}/{top}"
        colour = letter if left_uses is None or left_uses > top // 4 else HP_RED
        self._text(self.tr("creature.pp", "PP"), INFO_X, ROW_1, colour=letter, shadow=shadow)
        self._text(pp, 232, ROW_1, colour=colour, shadow=shadow, anchor="topright")
        kind = _move_type(definition)
        self._text(
            self.tr("creature.type", "TYPE/{type}", type=kind.upper() if kind else "-"),
            INFO_X,
            ROW_2,
            colour=letter,
            shadow=shadow,
        )
