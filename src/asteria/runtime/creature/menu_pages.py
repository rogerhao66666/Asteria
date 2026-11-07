"""The trainer card, options, the dex and its search, the navigator and the region map."""

from __future__ import annotations

import json


class CreatureMenuPagesMixin:
    """The trainer card, options, the dex and its search, the navigator and the region map."""

    # -- the trainer card, options, the dex ---------------------------------------------------
    def _input_card(self):
        if self._pressed("cancel") or self._pressed("confirm"):
            self._back()

    def options(self):
        return list((self.menu.get("options") or {}).get("options") or ())

    def option_value(self, option_id):
        return int(self.game.save.event_context.get_variable(f"option.{option_id}", 0) or 0)

    def _input_options(self):
        rows = self.options()
        count = len(rows) + 1  # + CANCEL
        if self._pressed("move_up"):
            self.option_cursor = (self.option_cursor - 1) % count
        if self._pressed("move_down"):
            self.option_cursor = (self.option_cursor + 1) % count
        if self.option_cursor < len(rows):
            row = rows[self.option_cursor]
            values = list(row.get("values") or ("",))
            step = (1 if self._pressed("move_right") else 0) - (
                1 if self._pressed("move_left") else 0
            )
            if step:
                value = (self.option_value(row["id"]) + step) % len(values)
                self.game.save.event_context.set_variable(f"option.{row['id']}", value)
        if self._pressed("cancel") or (
            self._pressed("confirm") and self.option_cursor == len(rows)
        ):
            self._back()

    def dex_entries(self):
        if self._dex is None:
            path = (self.menu.get("dex") or {}).get("entries")
            entries = []
            if path and self._path(path).is_file():
                entries = json.loads(self._path(path).read_text(encoding="utf-8"))
            self._dex = entries
        return self._dex

    def dex_status(self, species_id):
        """``(seen, owned)`` of a species."""
        owned_now = any(p.species_id == species_id for p in self.game.pets())
        record = self.game.world.bestiary.get(species_id, {})
        owned = owned_now or record.get("captured", 0) > 0
        return owned or record.get("seen", 0) > 0, owned

    def dex_rows(self):
        """The dex's rows: up to the last species seen (pokeedex.c lists to the highest)."""
        entries = self.dex_entries()
        last = max((n for n, e in enumerate(entries) if self.dex_status(e["species"])[0]),
                   default=-1)  # fmt: skip
        return self._dex_kept(entries[: last + 1])

    def _input_dex(self):
        rows = self.dex_rows()
        if self._pressed("move_up"):
            self.list_cursor = max(0, self.list_cursor - 1)
        if self._pressed("move_down"):
            self.list_cursor = min(max(0, len(rows) - 1), self.list_cursor + 1)
        fixed = (self.menu.get("dex") or {}).get("cursor_row")
        if fixed is not None:  # the list moves under a fixed selection row
            self.dex_scroll = self.list_cursor - int(fixed)
        else:
            self.dex_scroll = min(self.dex_scroll, self.list_cursor)
            self.dex_scroll = max(self.dex_scroll, self.list_cursor - 7)
        if self._pressed("cancel"):
            self._back()
        elif self._pressed("confirm") and rows:
            if self.dex_status(rows[self.list_cursor]["species"])[0]:
                self.phase = "dex_entry"
        elif self._pressed("menu") and (self.menu.get("dex") or {}).get("search"):
            self.phase, self.action_cursor = "dex_search", 0

    def _input_dex_entry(self):
        if self._pressed("cancel") or self._pressed("confirm"):
            self.phase = "dex"
        elif self._pressed("move_right") and (self.menu.get("region_map") or {}):
            self.phase = "dex_area"

    def _input_dex_area(self):
        if self._pressed("cancel") or self._pressed("move_left"):
            self.phase = "dex_entry"

    # -- the search of the POKéDEX: rows of words, what they keep ---------------------------
    def dex_search_rows(self):
        """``(id, label, [values])``: the letter a name begins with, a type, the order."""
        settings = (self.menu.get("dex") or {}).get("search") or {}
        return [
            (row["id"], str(row.get("label", row["id"])), list(row.get("values", ())))
            for row in settings.get("rows", ())
        ]

    def _input_dex_search(self):
        rows = self.dex_search_rows()
        if self._pressed("cancel"):
            self.phase = "dex"
            return
        if self._pressed("confirm"):
            self.dex_filter = dict(self.dex_choice)
            self.phase, self.list_cursor, self.dex_scroll = "dex", 0, 0
            return
        if not rows:
            return
        if self._pressed("move_up"):
            self.action_cursor = (self.action_cursor - 1) % len(rows)
        if self._pressed("move_down"):
            self.action_cursor = (self.action_cursor + 1) % len(rows)
        row_id, _label, values = rows[min(self.action_cursor, len(rows) - 1)]
        turn = int(self._pressed("move_right")) - int(self._pressed("move_left"))
        if turn and values:
            now = self.dex_choice.get(row_id, values[0])
            at = values.index(now) if now in values else 0
            self.dex_choice[row_id] = values[(at + turn) % len(values)]

    def _dex_kept(self, entries):
        """The entries the search keeps, in the order it asks for. A value equal to the row's
        first value keeps everything; ``letters`` keeps names starting with one of its letters;
        any other row keeps entries whose field of that name holds the value."""
        kept = list(entries)
        for row_id, _label, values in self.dex_search_rows():
            value = self.dex_filter.get(row_id)
            if not value or not values or value == values[0]:
                continue
            if row_id == "order":
                continue
            if row_id == "letters":
                kept = [e for e in kept if str(e.get("name", ""))[:1].upper() in value]
            else:
                kept = [e for e in kept if value in (e.get(row_id) or ())]
        order = self.dex_filter.get("order", "")
        keys = dict((self.menu.get("dex") or {}).get("search", {}).get("orders") or {})
        key = keys.get(order)
        if key:
            field, _, way = str(key).partition(":")
            kept.sort(key=lambda e: e.get(field, 0), reverse=way == "down")
        return kept

    # -- POKéNAV and the region map ---------------------------------------------------------
    def pokenav_rows(self):
        return list((self.menu.get("pokenav") or {}).get("rows") or ())

    def _input_pokenav(self):
        rows = self.pokenav_rows()
        if self._pressed("cancel"):
            self._back()
            return
        if not rows:
            return
        if self._pressed("move_up"):
            self.list_cursor = (self.list_cursor - 1) % len(rows)
        if self._pressed("move_down"):
            self.list_cursor = (self.list_cursor + 1) % len(rows)
        if self._pressed("confirm"):
            screen = rows[self.list_cursor].get("screen", "")
            if screen:
                self.open(screen)

    def _player_region_cell(self):
        """Where the player is on the region map: the area's name, else the map's middle."""
        settings = self.menu.get("region_map") or {}
        place = str(getattr(self.game, "area_title_shown", "") or "")
        names = dict(settings.get("names") or {})
        for key, name in names.items():
            if name == place:
                x, _, y = key.partition(",")
                return [int(x), int(y)]
        columns, rows = settings.get("size", (28, 15))
        return [columns // 2, rows // 2]

    def _input_region(self):
        settings = self.menu.get("region_map") or {}
        columns, rows = settings.get("size", (28, 15))
        x, y = self.region_cell
        x += int(self._pressed("move_right")) - int(self._pressed("move_left"))
        y += int(self._pressed("move_down")) - int(self._pressed("move_up"))
        self.region_cell = [max(0, min(columns - 1, x)), max(0, min(rows - 1, y))]
        if self._pressed("cancel"):
            self.phase = getattr(self, "region_back", "start")
            self.fly_mode = False
        elif self.fly_mode and self._pressed("confirm"):
            self._fly_to(self.region_cell)

    def _fly_target(self, cell):
        """``region_map.fly``: ``{"x,y": {scene, x, y, switch}}``, where a switch that is on
        lets the player go; None when this cell cannot be flown to now."""
        target = dict((self.menu.get("region_map") or {}).get("fly") or {}).get(
            f"{cell[0]},{cell[1]}"
        )
        if target is None:
            return None
        needs = target.get("switch")
        if needs and not self.game.save.event_context.get_switch(needs):
            return None
        return target

    def _fly_to(self, cell):
        target = self._fly_target(cell)
        if target is None:
            return
        self.done, self.fly_mode = True, False
        self.game.transfer_player(int(target["scene"]) if str(target["scene"]).isdigit()
                                  else target["scene"], float(target["x"]), float(target["y"]),
                                  facing="down")  # fmt: skip

    def _draw_region_base(self):
        settings = self.menu.get("region_map") or {}
        picture = self._menu_picture(settings.get("background"))
        if picture is not None:
            self.surface.blit(picture, (0, 0))
        else:
            self.surface.fill((96, 152, 200))
        return settings

    def _draw_region(self):
        settings = self._draw_region_base()
        ox, oy = settings.get("origin", (8, 16))
        cell = int(settings.get("cell", 8))
        x, y = self.region_cell
        cursor = self._menu_picture(settings.get("cursor"))
        if cursor is not None:
            self.surface.blit(cursor, (ox + x * cell - 4, oy + y * cell - 4))
        name = dict(settings.get("names") or {}).get(f"{x},{y}", "")
        letter, shadow = self._menu_colours()
        at = settings.get("name_at", (16, 2))
        self._text(name, at[0], at[1], letter, shadow)

    def _draw_dex_area(self):
        settings = self._draw_region_base()
        ox, oy = settings.get("origin", (8, 16))
        cell = int(settings.get("cell", 8))
        entry = self.dex_rows()[self.list_cursor]
        glow = 90 + int(70 * abs(((self.time * 1.2) % 2) - 1))
        mark = self.pg.Surface((cell, cell), self.pg.SRCALPHA)
        mark.fill((*settings.get("area_colour", (64, 224, 96)), glow))
        for key in entry.get("area") or ():
            x, _, y = str(key).partition(",")
            self.surface.blit(mark, (ox + int(x) * cell, oy + int(y) * cell))
        letter, shadow = self._menu_colours()
        at = settings.get("name_at", (16, 2))
        self._text(f"{entry['name']}", at[0], at[1], letter, shadow)
        if not entry.get("area"):
            self._message_window(self.tr("creature.dex.area_unknown", "AREA UNKNOWN"))

    def _draw_pokenav(self):
        settings = self.menu.get("pokenav") or {}
        picture = self._menu_picture(settings.get("background"))
        if picture is not None:
            self.surface.blit(picture, (0, 0))
        else:
            self.surface.fill((48, 96, 144))
        rows = [str(row.get("label", "")) for row in self.pokenav_rows()]
        self._list_window(rows, self.list_cursor, 176, 112)

    def _draw_dex_search(self):
        s = self.surface
        settings = (self.menu.get("dex") or {}).get("search") or {}
        picture = self._menu_picture(settings.get("background"))
        if picture is not None:
            s.blit(picture, (0, 0))
        else:
            s.fill((232, 232, 216))
        ink, ink_shadow = (72, 72, 72), (208, 208, 200)
        x, y = settings.get("rows_at", (24, 32))
        step = int(settings.get("row_height", 20))
        for n, (row_id, label, values) in enumerate(self.dex_search_rows()):
            value = self.dex_choice.get(row_id, values[0] if values else "")
            self._text(label, x, y + n * step, ink, ink_shadow)
            self._text(str(value), x + 72, y + n * step, ink, ink_shadow)
            if n == self.action_cursor:
                self.font_cursor(x - 12, y + n * step)
