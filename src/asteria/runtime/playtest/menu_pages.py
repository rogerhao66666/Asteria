"""The pause menu's pages (D87): Status, Items, Equipment and Skills as entries of their own.

``_pause_options`` lists the built-in entries a game can use, in the engine's order
(``rpg.menu_rules.PAUSE_ENTRIES``) or the one Game Systems ▸ Menu Pages sets, with the
project's own entries (Pause Menu Entries) before Settings. Equipment opens the paper doll,
Skills the skill tree when the member has one (else the list of skills). The Status page is a
stat table in the manner of a MapleStory stat window: the member's profile and resources, the
stats a stat graph raises with a + each and the points left, and a table of the other stats.
The Items page has tabs and a filter (F), and shows the chosen thing's picture, description
and facts beside the list or behind a Details button (D88, Menu Pages' ``item_details``).
"""

from __future__ import annotations

from asteria.rpg.menu_rules import PAUSE_ENTRIES, menu_rules


def _number(value):
    """A stat as the status page writes it: whole numbers plain, else one decimal."""
    value = round(float(value), 1)
    return f"{value:g}"


def _signed(value):
    """``+12`` / ``-3`` / ``0``."""
    text = _number(value)
    return text if text.startswith("-") or text == "0" else f"+{text}"


PAGES = ("status", "items", "equipment", "skills")


class MenuPagesMixin:
    def _pause_options(self):
        """``(options, icons, keys)`` of the pause menu's ``MenuCursor``."""
        from asteria.runtime.game_menus import PAUSE_WORDS, text_keys

        db = self.project.rpg_database
        usable = set(PAUSE_ENTRIES) - {
            "equipment",
            "enhance",
            "skills",
            "pets",
            "backlog",
            "skill_slots",
            "music",
            "credits",
        }
        if getattr(self.save.rpg_state, "loadouts", None):  # U3: gear the party can change
            usable.add("equipment")
            if db.refine_rules or any(e.sockets or e.growth_id for e in db.equipment.values()):
                usable.add("enhance")
        if db.progression_graphs or self.project.gameplay_library.abilities.ids():
            usable.add("skills")
        if getattr(db, "pet_species", None):
            usable.add("pets")
        settings = self.game.message_settings
        if settings is not None and settings.backlog_limit:
            usable.add("backlog")
        for entry, store in (
            ("skill_slots", db.ability_loadout_rules),
            ("music", db.music_tracks),
            ("credits", db.credits_pages),
        ):
            if store:
                usable.add(entry)
        rules = menu_rules(db)
        order = rules.pause_entries if rules is not None and rules.pause_entries else PAUSE_ENTRIES
        options = [(e, PAUSE_WORDS[e]) for e in order if e in usable]
        own = [
            (f"entry:{entry.entry_id}", entry.label)
            for entry in sorted(db.menu_entries.values(), key=lambda e: (e.order, e.entry_id))
        ]
        at = next((i for i, o in enumerate(options) if o[0] == "settings"), len(options))
        options[at:at] = own  # in order, before Settings
        icons = {
            f"entry:{e.entry_id}": e.icon_id for e in db.menu_entries.values() if e.icon_id
        }  # project-defined entries may carry an icon
        keys = text_keys("pause", [o for o in options if not o[0].startswith("entry:")])
        # the project's own entries keep their label unless a table words it (pause.entry.<id>)
        keys.update({f"entry:{e}": f"pause.entry.{e}" for e in db.menu_entries})
        return options, icons, keys

    def _open_pause_page(self, page):
        """Open Status, Items, Equipment or Skills from the pause menu."""
        if page == "equipment" and getattr(self.save.rpg_state, "loadouts", None):
            self.open_equipment_screen(back="pause")
            return
        if page == "skills":
            from asteria.runtime.skill_tree_screen import SkillTreeScreen

            if self._multiplayer_connected():
                from asteria.runtime.network_bag_screen import NetworkSkillTreeScreen

                tree = NetworkSkillTreeScreen(self)
            else:
                tree = SkillTreeScreen(self)
            if tree.graphs():
                tree.back = "pause"
                self._skill_tree, self._ui_mode = tree, "skills"
                return
        self.open_status_menu(back="pause", page=page)

    # -- the Status page -------------------------------------------------------------------------
    def _status_section(self, c, element_id, rect, title):
        """A panel with a heading strip; the rect inside it below the heading."""
        x, y, w, h = c.panel(element_id, rect, fill=(16, 21, 36, 236))
        strip = (x + 2, y + 2, w - 4, 32)
        self.pg.draw.rect(self.screen, (34, 46, 78), strip, border_radius=4)
        c.text(
            f"{element_id}_title",
            title,
            x + 14,
            y + 7,
            size=c.size(f"{element_id}_title", 19),
            color=c.tone("title", (255, 220, 124)),
        )
        return (x + 14, y + 44, w - 28, h - 52)

    def _draw_status_page(self, c, menu, top):
        """The Status page: profile, stat table with +, details (see the module)."""
        width, height = self.width, self.height
        left_w = min(560, int((width - 112) * 0.45))
        bottom = height - 100
        profile_h = 190
        self._draw_status_profile(c, menu, (44, top, left_w, profile_h))
        points_top = top + profile_h + 12
        self._draw_stat_table(c, menu, (44, points_top, left_w, bottom - points_top))
        right_x = 44 + left_w + 20
        self._draw_stat_details(c, menu, (right_x, top, width - 44 - right_x, bottom - top))

    def _draw_status_profile(self, c, menu, rect):
        """The member: name, level and jobs, experience, and a bar per resource."""
        pg, tr, game = self.pg, self.game.tr, self.game
        actor_id = menu.actor_id
        view = menu._status_view()
        normal = c.tone("text", (210, 215, 225))
        muted = c.tone("muted", (150, 170, 200))
        px, py, pw, _ph = self._status_section(
            c, "profile", rect, tr("status.profile", "Character")
        )
        db = self.project.rpg_database
        state = game.save.rpg_state.actor_progression.get(actor_id)
        record = db.actors.get(actor_id)
        c.text("name", game.name_of(record, actor_id or "—"), px, py - 2, size=26)
        classes = ", ".join(
            game.name_of(db.classes.get(k), k) for k in getattr(state, "active_class_ids", ())
        )
        level = getattr(state, "level", 1)
        line = tr("status.level", "Lv {level}", level=level)
        c.text("level", f"{line}   {classes}".strip(), px, py + 30, size=18, color=muted)
        experience = getattr(state, "experience", 0.0)
        exp = tr("status.exp", "EXP {value}", value=f"{experience:g}")
        c.text("exp", exp, px + pw, py + 2, size=18, color=muted, anchor="topright")
        bar_y = py + 62
        for resource in (view.resources if view is not None else ())[:3]:
            name = menu._word("resource", resource.resource_id, resource.label)
            self.text(name, px, bar_y, size=18, color=normal)
            bar = (px + 92, bar_y + 2, pw - 92, 18)
            pg.draw.rect(self.screen, (30, 34, 48), bar, border_radius=4)
            share = resource.current / resource.maximum if resource.maximum else 0.0
            fill = (bar[0], bar[1], int(bar[2] * max(0.0, min(1.0, share))), bar[3])
            tone = (214, 72, 72) if resource.resource_id.lower() in ("hp", "vitality") else None
            pg.draw.rect(self.screen, tone or (70, 128, 222), fill, border_radius=4)
            amount = f"{resource.current:g} / {resource.maximum:g}"
            self.text(amount, bar[0] + bar[2] // 2, bar_y + 2, size=16, anchor="midtop")
            bar_y += 28

    # where the stat table's columns end, back from its right edge: the last column the first
    STAT_EDGES = (44, 98, 154, 210, 268, 330)

    @classmethod
    def _stat_columns(cls, menu):
        """``[(column, right edge)]`` of the stat table: Menu Pages' ``stat_columns`` (D89),
        packed from the right so a hidden column leaves no gap."""
        from asteria.rpg.menu_rules import STAT_COLUMNS

        columns = menu.rules.columns() if menu.rules is not None else STAT_COLUMNS
        return list(zip(columns, reversed(cls.STAT_EDGES[: len(columns)]), strict=True))

    @staticmethod
    def _stat_headers(tr):
        return {
            "rank": tr("status.col.rank", "Rank"),
            "total": tr("status.col.total", "Total"),
            "base": tr("status.col.base", "Base"),
            "points": tr("status.col.points", "Points"),
            "gear": tr("status.col.gear", "Gear"),
            "gain": tr("status.col.gain", "Each +"),
        }

    def _draw_stat_table(self, c, menu, rect):
        """Points left, then a row per stat of the stat graph: its rank, total and where the
        total comes from (base, points, gear), what one more point adds, and its + (D89)."""
        pg, tr = self.pg, self.game.tr
        normal = c.tone("text", (210, 215, 225))
        muted = c.tone("muted", (150, 170, 200))
        ax, ay, aw, ah = self._status_section(
            c, "points", rect, tr("status.ability_points", "Ability Points")
        )
        x, y, w, _h = rect
        balances = "   ".join(f"{name} {value:g}" for name, value in menu.stat_points())
        if balances:
            c.text(
                "points_left",
                balances,
                x + w - 14,
                y + 7,
                size=19,
                color=(140, 230, 170),
                anchor="topright",
            )
        rows = menu.stat_rows()
        if not rows:
            c.text("no_points", tr("status.no_stat_graph", "—"), ax, ay, size=19, color=muted)
            return

        def right(edge):
            return ax + aw - edge

        headers = self._stat_headers(tr)
        columns = self._stat_columns(menu)
        for key, edge in columns:
            self.text(headers[key], right(edge), ay - 2, size=14, color=muted, anchor="topright")
        pg.draw.line(self.screen, (52, 64, 96), (ax - 4, ay + 18), (ax + aw + 4, ay + 18))
        row_h = min(36, max(28, (ah - 26) // max(1, len(rows))))
        for i, row in enumerate(rows):
            line_y = ay + 26 + i * row_h
            if line_y + row_h > ay + ah + 8:
                break
            selected = i == menu.row
            band = (ax - 6, line_y - 4, aw + 12, row_h - 4)
            self.hotspot(band, lambda i=i: setattr(menu, "row", i), key="")
            if selected:
                c.selection(
                    "stat_rows",
                    band,
                    lambda band=band: pg.draw.rect(
                        self.screen, (40, 52, 78), band, border_radius=4
                    ),
                )
            elif i % 2:
                pg.draw.rect(self.screen, (20, 26, 42), band, border_radius=4)
            color = c.tone("selected", (255, 255, 255)) if selected else normal
            self.text(row.label, ax, line_y, size=19, color=color)
            values = {
                "rank": (f"{row.rank}/{row.max_rank}", muted, 15),
                "total": ("—" if row.value is None else _number(row.value), color, 20),
                "base": (_number(row.base), normal, 17),
                "points": (_signed(row.points), (140, 230, 170) if row.points else muted, 17),
                "gear": (_signed(row.gear), (130, 190, 255) if row.gear else muted, 17),
                "gain": (_signed(row.gain) if row.gain else "", (255, 220, 124), 17),
            }
            for key, edge in columns:
                text, tone, size = values[key]
                self.text(
                    text,
                    right(edge),
                    line_y + (20 - size) // 2,
                    size=size,
                    color=tone,
                    anchor="topright",
                )
            plus = (ax + aw - 36, line_y - 3, 36, 26)
            fill = (64, 150, 92) if row.allowed else (52, 58, 72)
            pg.draw.rect(self.screen, fill, plus, border_radius=5)
            pg.draw.rect(
                self.screen, (150, 200, 160) if row.allowed else (90, 96, 110), plus, 1, 5
            )
            self.text(
                "+",
                plus[0] + 18,
                plus[1],
                size=22,
                anchor="midtop",
                color=(255, 255, 255) if row.allowed else (130, 136, 150),
            )
            self.hotspot(plus, lambda i=i: setattr(menu, "row", i))  # a click: raise it

    def _draw_stat_details(self, c, menu, rect):
        """The detail table: its groups top to bottom, in as many columns as fit, a line per
        stat - its name, where it comes from (base and points + gear) and its value written as
        a number, a percent, a range or a battle chance (D89)."""
        pg, tr = self.pg, self.game.tr
        normal = c.tone("text", (210, 215, 225))
        muted = c.tone("muted", (150, 170, 200))
        dx, dy, dw, dh = self._status_section(c, "details", rect, tr("status.details", "Details"))
        groups = menu.detail_groups()
        if not groups:
            c.text(
                "no_details", tr("status.empty", "Nothing here yet."), dx, dy, size=19, color=muted
            )
            return
        columns = 2 if dw >= 560 else 1
        gap = 18
        col_w = (dw - gap * (columns - 1)) // columns
        line_h, head_h = 22, 27
        column, y = 0, dy
        for heading, lines in groups:
            first = True
            whole = head_h + line_h * len(lines)
            if y > dy and y + whole > dy + dh + 6 and whole <= dh + 6:
                column, y = column + 1, dy  # the group whole in the next column
                if column >= columns:
                    return
            for i, line in enumerate(lines):
                needed = (head_h if first else 0) + line_h
                if y + needed > dy + dh + 6:
                    column += 1
                    y, first = dy, True
                    if column >= columns:
                        return
                x = dx + column * (col_w + gap)
                if first:
                    head = (x - 4, y, col_w + 8, head_h - 6)
                    pg.draw.rect(self.screen, (34, 46, 78), head, border_radius=4)
                    self.text(
                        heading, x + 4, y + 2, size=16, color=c.tone("title", (255, 220, 124))
                    )
                    y += head_h
                    first = False
                if i % 2 == 0:
                    pg.draw.rect(self.screen, (20, 26, 42), (x - 4, y - 3, col_w + 8, line_h - 1))
                self.text(line.label, x + 4, y, size=16, color=normal)
                self.text(
                    line.text, x + col_w - 2, y, size=16, color=(245, 245, 252), anchor="topright"
                )
                if line.gear:
                    origin = f"({_number(line.base + line.points)}{_signed(line.gear)})"
                    self.text(
                        origin,
                        x + col_w - 104,
                        y + 2,
                        size=14,
                        color=(130, 190, 255),
                        anchor="topright",
                    )
                y += line_h

    # -- the Items page --------------------------------------------------------------------------
    def _draw_item_tabs(self, c, menu, y):
        """The Items page's tabs and filter on one line at ``y``."""
        tr = self.game.tr
        categories = menu.categories()
        x = 44
        for i, category in enumerate(categories):
            label = menu.category_name(category)
            active = i == menu.category % max(1, len(categories))
            color = c.tone("selected", (255, 220, 120)) if active else (150, 160, 180)
            rect = self.text(label, x + 12, y + 4, size=c.size("item_tabs", 21), color=color)
            box = (x, y, rect.width + 24, 34)
            if active:
                self.pg.draw.rect(self.screen, (255, 220, 120), box, 2, border_radius=6)
            self.hotspot(box, lambda i=i: setattr(menu, "point_category", i), key="tab")
            x += box[2] + 8
        filters = menu.filters()
        current = (
            menu.filter_name(filters[menu.filter])
            if 0 <= menu.filter < len(filters)
            else tr("status.filter.none", "All")
        )
        words = tr("status.filter", "F  Filter: {name}", name=current)
        rect = c.text(
            "filter",
            words,
            self.width - 48,
            y + 6,
            size=19,
            color=(170, 220, 255),
            anchor="topright",
        )
        if rect is not None:
            self.hotspot(rect.inflate(16, 10), key="f")  # a click: the next filter

    def _draw_item_detail(self, c, menu, rect):
        """The chosen row's :class:`~asteria.runtime.status_menu.ItemDetail` in ``rect``: its
        icon big, its name in its rarity's colour, what it is, its description and facts."""
        from asteria.runtime.crafting_screen import wrap

        detail = menu.detail()
        tr = self.game.tr
        x, y, w, h = self._status_section(c, "item_detail", rect, tr("status.item_info", "About"))
        muted = c.tone("muted", (170, 210, 240))
        if detail is None:
            c.text(
                "no_detail", tr("status.empty", "Nothing here yet."), x, y, size=19, color=muted
            )
            return
        side = min(96, w // 3)
        self.pg.draw.rect(self.screen, (26, 32, 52), (x, y, side, side), border_radius=6)
        self.pg.draw.rect(self.screen, (70, 84, 120), (x, y, side, side), 2, border_radius=6)
        icon = self.fitted_icon(detail.icon_id, (side - 12, side - 12), trim=True)
        if icon is not None:
            iw, ih = icon.get_size()
            self.screen.blit(icon, (x + (side - iw) // 2, y + (side - ih) // 2))
        text_x, text_w = x + side + 14, w - side - 14
        name_color = detail.rarity_rgb or c.tone("title", (255, 236, 190))
        line_y = y + 2
        for line in wrap(self, detail.name, 23, text_w)[:2]:
            self.text(line, text_x, line_y, size=23, color=name_color)
            line_y += 28
        for line in wrap(self, detail.kind, 17, text_w)[:2]:
            self.text(line, text_x, line_y, size=17, color=muted)
            line_y += 22
        line_y = max(line_y, y + side) + 12
        bottom = y + h
        facts_h = 26 * len(detail.facts)
        for line in wrap(self, detail.description, 18, w) if detail.description else ():
            if line_y + 24 > bottom - facts_h - 8:
                break
            self.text(line, x, line_y, size=18, color=c.tone("text", (210, 215, 225)))
            line_y += 24
        line_y = max(line_y + 8, bottom - facts_h)
        for label, value in detail.facts:
            if line_y + 22 > bottom:
                break
            self.pg.draw.line(self.screen, (40, 50, 76), (x, line_y - 3), (x + w, line_y - 3))
            self.text(label, x, line_y, size=18, color=muted)
            self.text(value, x + w, line_y, size=18, color=(240, 240, 248), anchor="topright")
            line_y += 26


__all__ = ["PAGES", "MenuPagesMixin"]
