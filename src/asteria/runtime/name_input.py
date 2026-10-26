"""Entering a name (world command ``NAME_INPUT``): a keyboard of pages, the letters typed so
far, BACK and OK. Drawn at the game's own resolution (240 x 160) like the creature screens;
with ``field.name_input`` in the playable manifest the game's own pictures and places are
used, else plain shapes.

``field.name_input`` (every key optional):

* ``background``; ``pages``: ``[{"picture", "rows": ["ABCDEF .", ...], "columns": [x, ...],
  "label"}]`` (a row's characters in order, a space is no key; ``columns`` the keys' x);
  ``keys_at`` (the first row's top left), ``row_height``; ``cursor`` (a picture centred on the
  key) or a drawn box; ``buttons``: ``{"page", "back", "ok"}`` pictures at ``buttons_at``
  (``[x, y]`` each, their centres); ``button_cursor`` (drawn round the chosen button).
* ``page_labels`` (a picture per page: the PAGE button shows the next one at
  ``page_label_at``); ``title_at``; ``entry_x`` / ``entry_y`` (the first letter's top left,
  letters ``entry_step`` apart; without ``entry_x`` the letters are centred),
  ``underscore`` (a picture under each place); ``icon_at`` (the player's or the creature's
  icon centre); ``banner`` (words at ``banner_at``, e.g. the keys' help).
* ``colours``: ``[letter, shadow]``; ``keys_colours``: per page.

The request names what gets the name: ``target`` ``variable:<name>`` (the player's name...) or
``pet:last`` / ``pet:<instance id>`` (a creature's nickname); ``max_length``; ``title``
(message codes; ``{species}`` is the creature's kind); ``default`` (used when OK is chosen
with nothing typed).
"""

from __future__ import annotations

from asteria.presentation.creature_screens import creature_settings
from asteria.runtime.creature_battle import CreatureBattleScreen, H, W
from asteria.runtime.pointer import hand_over

DEFAULT_PAGES = (
    {"label": "UPPER", "rows": ("ABCDEF .", "GHIJKL ,", "MNOPQRS ", "TUVWXYZ ")},
    {"label": "lower", "rows": ("abcdef .", "ghijkl ,", "mnopqrs ", "tuvwxyz ")},
    {"label": "OTHERS", "rows": ("01234   ", "56789   ", "!?♂♀/-  ", "…“”‘'   ")},
)
DEFAULT_COLUMNS = (0, 12, 24, 56, 68, 80, 92, 123)
BUTTONS = ("page", "back", "ok")


class NameInputScreen(CreatureBattleScreen):
    """``update(dt, events)`` / ``draw()``; ``done`` once OK (or START) gave a name."""

    def __init__(self, runtime, request):
        super().__init__(runtime)
        self.request = dict(request)
        self.skin = creature_settings(runtime, "field.name_input")
        self.pages = list(self.skin.get("pages") or DEFAULT_PAGES)
        self.page = int(self.request.get("page", 0) or 0) % len(self.pages)
        self.text = str(self.request.get("initial", "") or "")
        self.max_length = max(1, int(self.request.get("max_length", 7) or 7))
        self.cx = self.cy = 0  # the key under the cursor (cx = columns: the buttons)
        self.done = False

    def _remember_hp(self):  # not a battle: nothing to remember or announce
        pass

    def _intro(self):
        pass

    # -- the keyboard -----------------------------------------------------------------------------
    def rows(self):
        return list(self.pages[self.page].get("rows") or DEFAULT_PAGES[0]["rows"])

    def columns(self):
        page = self.pages[self.page]
        return list(page.get("columns") or DEFAULT_COLUMNS)[: max(len(r) for r in self.rows())]

    def key(self):
        """The character under the cursor ("" on a gap or a button)."""
        rows = self.rows()
        if self.cx >= len(self.columns()) or self.cy >= len(rows):
            return ""
        row = rows[self.cy]
        return row[self.cx] if self.cx < len(row) and row[self.cx] != " " else ""

    def button(self):
        """``page`` / ``back`` / ``ok`` when the cursor is on the buttons, else ""."""
        if self.cx < len(self.columns()):
            return ""
        return BUTTONS[min(len(BUTTONS) - 1, (0, 1, 1, 2)[min(self.cy, 3)])]

    # -- input -----------------------------------------------------------------------------------
    def _pressed_key(self, events, name):
        keys = {"select": (self.pg.K_TAB,)}  # SELECT on the GBA: the next page
        return any(e.type == self.pg.KEYDOWN and e.key in keys.get(name, ()) for e in events)

    def update(self, dt, events=()):
        self.time += dt
        count = len(self.columns())
        if self._pressed("move_left"):
            self.cx = (self.cx - 1) % (count + 1)
        if self._pressed("move_right"):
            self.cx = (self.cx + 1) % (count + 1)
        if self._pressed("move_up"):
            self.cy = (self.cy - 1) % len(self.rows())
        if self._pressed("move_down"):
            self.cy = (self.cy + 1) % len(self.rows())
        if self._pressed_key(events, "select"):  # the next page (SELECT on the GBA)
            self.page = (self.page + 1) % len(self.pages)
        if self._pressed("cancel"):
            self.text = self.text[:-1]
            return
        if not self._pressed("confirm"):
            return
        button = self.button()
        if button == "page":
            self.page = (self.page + 1) % len(self.pages)
        elif button == "back":
            self.text = self.text[:-1]
        elif button == "ok":
            self.finish()
        elif self.key() and len(self.text) < self.max_length:
            self.text += self.key()
            if len(self.text) >= self.max_length:  # full: the cursor goes to OK
                self.cx, self.cy = count, 3

    def finish(self):
        name = self.text.strip() or str(self.request.get("default", "") or "")
        self.game.finish_name_input(name)
        self.done = True

    # -- drawing ---------------------------------------------------------------------------------
    def _picture(self, path):
        if not path:
            return None
        key = ("name_input", path)
        if key not in self._images:
            image = None
            if self.rt.path(path).is_file():
                image = self.pg.image.load(str(self.rt.path(path))).convert_alpha()
            self._images[key] = image
        return self._images[key]

    def _colours(self, name="colours", default=((98, 98, 98), (213, 213, 205))):
        colours = self.skin.get(name) or default
        return tuple(colours[0]), tuple(colours[1])

    def title(self):
        words = str(self.request.get("title", "") or "")
        species = ""
        pet = self.game.name_input_pet()
        if pet is not None:
            record = self.game.pet_species(pet)
            species = self.game.name_of(record, pet.species_id) if record else pet.species_id
        return self.game.expand_message(words, plain=True).replace("{species}", species)

    def draw(self):
        pg, s = self.pg, self.surface
        s.fill((0, 0, 0, 255))
        background = self._picture(self.skin.get("background"))
        if background is not None:
            s.blit(background, (0, 0))
        else:
            s.fill((112, 168, 216))
            pg.draw.rect(s, (248, 248, 248), (16, 24, 208, 40))
            pg.draw.rect(s, (248, 248, 248), (16, 72, 168, 72))
        page = self.pages[self.page]
        keyboard = self._picture(page.get("picture"))
        if keyboard is not None:
            s.blit(keyboard, (0, 0))
        letter, shadow = self._colours()
        kx, ky = self.skin.get("keys_at", (24, 81))
        step = int(self.skin.get("row_height", 16))
        key_letter, key_shadow = self._page_colours()
        columns = self.columns()
        for row, keys in enumerate(self.rows()):
            for col, char in enumerate(keys[: len(columns)]):
                if char != " ":
                    x = kx + columns[col] + 14 - self.text_width(char) // 2
                    self._text(char, x, ky + row * step, key_letter, key_shadow)
        self._draw_buttons()
        self._draw_cursor(kx, ky, step)
        tx, ty = self.skin.get("title_at", (72, 33))
        self._text(self.title(), tx, ty, letter, shadow)
        ey = self.skin.get("entry_y", 49)
        ex = self.skin.get("entry_x")  # else centred (naming_screen.c inputCharBaseXPos)
        if ex is None:
            ex = (W - self.max_length * int(self.skin.get("entry_step", 8))) // 2 + 6
        gap = int(self.skin.get("entry_step", 8))
        underscore = self._picture(self.skin.get("underscore"))
        for n in range(self.max_length):
            if underscore is not None:
                s.blit(underscore, (ex + n * gap, ey + 10))
            else:
                pg.draw.line(s, shadow, (ex + n * gap, ey + 13), (ex + n * gap + 5, ey + 13))
            if n < len(self.text):
                self._text(self.text[n], ex + n * gap, ey, letter, shadow)
        icon = self._icon_picture()
        if icon is not None:
            ix, iy = self.skin.get("icon_at", (56, 37))
            s.blit(icon, (ix - icon.get_width() // 2, iy - icon.get_height() // 2))
        banner = self.skin.get("banner")
        if banner:
            bx, by = self.skin.get("banner_at", (2, 1))
            self._text(self.game.expand_message(str(banner), plain=True), bx, by,
                       (248, 248, 248), (98, 98, 98))  # fmt: skip
        screen = self.rt.screen
        sw, sh = screen.get_size()
        scale = max(1, min(sw // W, sh // H))
        screen.fill((0, 0, 0, 255))
        left, top = (sw - W * scale) // 2, (sh - H * scale) // 2
        screen.blit(self.pg.transform.scale(s, (W * scale, H * scale)), (left, top))
        hand_over(self.rt, self._key_spots(kx, ky, step), scale, left, top)

    def _key_spots(self, kx, ky, step):
        """Every letter and the three buttons as mouse hotspots (D85): pointing moves the
        cursor there, a click presses it (types the letter, PAGE / BACK / OK)."""

        def to(cx, cy):
            return lambda: (setattr(self, "cx", cx), setattr(self, "cy", cy))

        columns, spots = self.columns(), []
        for row, keys in enumerate(self.rows()):
            for col, char in enumerate(keys[: len(columns)]):
                if char != " ":
                    x, y = kx + columns[col] + 14, ky + row * step + 7
                    spots.append(((x - 8, y - step // 2, 16, step), to(col, row), "return"))
        places = self.skin.get("buttons_at") or {"page": (204, 83), "back": (204, 116),
                                                  "ok": (204, 140)}  # fmt: skip
        for name, cy in (("page", 0), ("back", 1), ("ok", 3)):
            x, y = places.get(name, (204, 83))
            spots.append(((x - 26, y - 10, 52, 20), to(len(columns), cy), "return"))
        return spots

    def _page_colours(self):
        per_page = self.skin.get("keys_colours") or []
        if self.page < len(per_page) and per_page[self.page]:
            colours = per_page[self.page]
            return tuple(colours[0]), tuple(colours[1])
        return self._colours()

    def _draw_buttons(self):
        pictures = self.skin.get("buttons") or {}
        places = self.skin.get("buttons_at") or {"page": (204, 83), "back": (204, 116),
                                                  "ok": (204, 140)}  # fmt: skip
        letter, shadow = self._colours()
        for name in BUTTONS:
            x, y = places.get(name, (204, 83))
            image = self._picture(pictures.get(name)) if pictures else None
            if image is not None:
                self.surface.blit(image, (x - image.get_width() // 2, y - image.get_height() // 2))
                labels = self.skin.get("page_labels") or []
                if name == "page" and labels:  # the page the button leads to
                    label = self._picture(labels[(self.page + 1) % len(labels)])
                    lx, ly = self.skin.get("page_label_at", (x, y))
                    if label is not None:
                        self.surface.blit(
                            label, (lx - label.get_width() // 2, ly - label.get_height() // 2)
                        )
            else:
                words = {"page": self.pages[(self.page + 1) % len(self.pages)].get("label", ""),
                         "back": "BACK", "ok": "OK"}[name]  # fmt: skip
                self.pg.draw.rect(self.surface, (248, 248, 248), (x - 24, y - 8, 48, 16))
                self._text(words, x, y - 7, letter, shadow, anchor="midtop")

    def _draw_cursor(self, kx, ky, step):
        pg, s = self.pg, self.surface
        button = self.button()
        if button:
            places = self.skin.get("buttons_at") or {"page": (204, 83), "back": (204, 116),
                                                      "ok": (204, 140)}  # fmt: skip
            x, y = places[button]
            frame = self._picture(self.skin.get("button_cursor"))
            if frame is not None:
                s.blit(frame, (x - frame.get_width() // 2, y - frame.get_height() // 2))
            else:
                pg.draw.rect(s, (248, 72, 72), (x - 26, y - 10, 52, 20), 2)
            return
        x = kx + self.columns()[self.cx] + 14
        y = ky + self.cy * step + 7
        cursor = self._picture(self.skin.get("cursor"))
        if cursor is not None:
            s.blit(cursor, (x - cursor.get_width() // 2, y - cursor.get_height() // 2))
        else:
            pg.draw.rect(s, (248, 72, 72), (x - 8, y - 8, 16, 16), 1)

    def _icon_picture(self):
        pet = self.game.name_input_pet()
        if pet is not None:
            return self._icon(pet.species_id)
        path = self.skin.get("player_icon")
        if path:
            path = self.game.expand_message(str(path), plain=True)
        return self._picture(path)


__all__ = ["NameInputScreen", "DEFAULT_PAGES"]
