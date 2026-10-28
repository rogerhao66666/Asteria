"""The pause menu's pages (D87): Status, Items, Equipment and Skills as entries of their own.

``_pause_options`` lists the entries a game can use in the order Game Systems ▸ Pause Menu
sets, without the ones it hides (``rpg.menu_pages.pause_menu``; D97). Equipment opens the
paper doll, Skills the skill tree when the member has one (else the list of skills). The
Status page is a stat table in the manner of a MapleStory stat window: the member's profile
and resources, the stats a stat graph raises with a + each and the points left, and a table of
the other stats. The Items page has tabs and a filter (F), and shows the chosen thing's
picture, description and facts beside the list or behind a Details button (D88, Menu Pages'
``item_details``).
"""

from __future__ import annotations

from asteria.rpg.data_text import record_key
from asteria.rpg.menu_pages import (
    MENU_ENTRY,
    PAGE_ENTRY,
    menu_pages,
    page_entries,
    pause_menu,
    usable_pause_entries,
)


def _number(value):
    """A stat as the status page writes it: whole numbers plain, else one decimal."""
    value = round(float(value), 1)
    return f"{value:g}"


def _signed(value):
    """``+12`` / ``-3`` / ``0``."""
    text = _number(value)
    return text if text.startswith("-") or text == "0" else f"+{text}"


PAGES = ("status", "items", "equipment", "skills")


COLUMN_GAP, BLOCK_GAP = 20, 12
FULL_HEIGHT = 160  # a full-width block without a height, above the columns


def _stack(blocks, x, y, w, h):
    """``(block, (x, y, w, h))`` for ``blocks`` one under another in a column ``h`` high."""
    fixed = sum(b.height for b in blocks if b.height)
    free = [b for b in blocks if not b.height]
    room = h - fixed - BLOCK_GAP * (len(blocks) - 1)
    share = room // len(free) if free else 0
    out = []
    for block in blocks:
        height = block.height or share
        out.append((block, (x, y, w, max(0, height))))
        y += height + BLOCK_GAP
    return out


def menu_page_boxes(blocks, rect):
    """Where each of a page's ``blocks`` is drawn in ``rect`` (D96): full-width blocks first
    (all of ``rect`` when the page has no columns), then the left and right columns."""
    x, y, w, h = rect
    full = [b for b in blocks if b.place == "full"]
    left = [b for b in blocks if b.place == "left"]
    right = [b for b in blocks if b.place == "right"]
    if not left and not right:
        return _stack(full, x, y, w, h)
    out = []
    for block in full:
        height = block.height or FULL_HEIGHT
        out.append((block, (x, y, w, height)))
        y, h = y + height + BLOCK_GAP, h - height - BLOCK_GAP
    if left and right:
        left_w = min(560, int((w - 24) * 0.45))
        right_x = x + left_w + COLUMN_GAP
        out += _stack(left, x, y, left_w, h)
        out += _stack(right, right_x, y, x + w - right_x, h)
    else:
        out += _stack(left or right, x, y, w, h)
    return out


class MenuPagesMixin:
    def _pause_options(self):
        """``(options, icons, keys)`` of the pause menu's ``MenuCursor``."""
        from asteria.runtime.game_menus import PAUSE_WORDS, text_keys

        db = self.project.rpg_database
        settings = self.game.message_settings
        usable = usable_pause_entries(
            db,
            loadouts=getattr(self.save.rpg_state, "loadouts", None),
            backlog=settings.backlog_limit if settings is not None else 0,
            abilities=self.project.gameplay_library.abilities.ids(),
        )
        pages = menu_pages(db)
        own_pages = page_entries(db)  # D96: a project's own menu page is an entry of its own
        listed = {e: pages[e[len(PAGE_ENTRY) :]] for e in own_pages}
        # ``keys`` below word a page's name in the player's language
        names = {e: page.display_name for e, page in listed.items()}  # no session: as written
        names.update({f"{MENU_ENTRY}{k}": e.label for k, e in db.menu_entries.items()})
        # D97: Game Systems ▸ Pause Menu - the author's order, without the hidden entries
        options = [(e, names.get(e) or PAUSE_WORDS[e]) for e in pause_menu(db, usable)]
        icons = {
            f"entry:{e.entry_id}": e.icon_id for e in db.menu_entries.values() if e.icon_id
        }  # project-defined entries may carry an icon
        for entry in own_pages:
            page = pages[entry[len(PAGE_ENTRY) :]]
            if page.icon_id:
                icons[entry] = page.icon_id
        built_in = [o for o in options if not o[0].startswith(("entry:", PAGE_ENTRY))]
        keys = text_keys("pause", built_in)
        # a page's name in the player's language: the locale table's data.menu_page.<id>.name
        keys.update({e: record_key(pages[e[len(PAGE_ENTRY) :]]) for e in own_pages})
        # the project's own entries keep their label unless a table words it (pause.entry.<id>)
        keys.update({f"entry:{e}": f"pause.entry.{e}" for e in db.menu_entries})
        return options, icons, keys

    def _open_pause_page(self, page):
        """Open Status, Items, Equipment, Skills or a project's own page (``page:<id>``) from
        the pause menu."""
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

    # -- a page of blocks (D96) -----------------------------------------------------------------
    def _draw_menu_page(self, c, menu, rect):
        """``menu.page``'s blocks in ``rect``: ``full`` blocks across the top, then the ``left``
        and ``right`` columns (the left one 45% of the width, at most 560 px); a block's
        ``height`` is kept, the ones without share what is left of their column."""
        draw = {
            "profile": self._draw_status_profile,
            "stat_points": self._draw_stat_table,
            "stat_details": self._draw_stat_details,
            "item_list": self._draw_item_list,
        }
        for block, box in menu_page_boxes(menu.page.blocks, rect):
            draw[block.kind](c, menu, box)

    def _draw_status_profile(self, c, menu, rect):
        """The member: name, level and jobs, experience, and a bar per resource."""
        pg, tr, game = self.pg, self.game.tr, self.game
        actor_id = menu.actor_id
        view = menu._status_view()
        normal = c.tone("text", (210, 215, 225))
        muted = c.tone("muted", (150, 170, 200))
        px, py, pw, ph = self._status_section(
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
        # what each of its jobs is (Database ▸ Classes / Jobs ▸ Description), as room allows
        from asteria.runtime.crafting_screen import wrap

        line_y = bar_y + 2
        for class_id in getattr(state, "active_class_ids", ()):
            job = db.classes.get(class_id)
            about = game.description_of(job, "")
            if not about:
                continue
            words = tr("status.job_meaning", "{job}: {meaning}", job=game.name_of(job, class_id),
                       meaning=about)  # fmt: skip
            for part in wrap(self, words, 15, pw):
                if line_y + 18 > py + ph:
                    break
                self.text(part, px, line_y, size=15, color=muted)
                line_y += 18

    # where the stat table's columns end, back from its right edge: the last column the first
    STAT_EDGES = (54, 108, 164, 220, 278, 340)  # 12 px clear of the row colour's end

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
        # the picked row's stat, in the author's words (Stats ▸ What It Means), under the
        # table: room for two lines is kept whenever any row has words, so rows never jump
        abouts = [self._stat_about(row.stat_id) for row in rows]
        about_h = 44 if any(abouts) else 0
        row_h = min(36, max(28, (ah - 26 - about_h) // max(1, len(rows))))
        if about_h and 0 <= menu.row < len(rows) and abouts[menu.row]:
            from asteria.runtime.crafting_screen import wrap

            about_y = ay + ah - about_h + 6
            for line in wrap(self, abouts[menu.row], 16, aw)[:2]:
                self.text(line, ax, about_y, size=16, color=muted)
                about_y += 20
        for i, row in enumerate(rows):
            line_y = ay + 26 + i * row_h
            if line_y + row_h > ay + ah - about_h + 8:
                break
            selected = i == menu.row
            band = (ax - 6, line_y - 4, aw + 12, row_h - 4)
            self.hotspot(band, lambda i=i: setattr(menu, "row", i), key="")
            # the row's colour stops short of the + button: a button on a dark row and one on a
            # light row looked different sizes; every button now sits on the panel's own colour
            shade = (ax - 6, line_y - 4, aw - 36, row_h - 4)
            if selected:
                c.selection(
                    "stat_rows",
                    shade,
                    lambda shade=shade: pg.draw.rect(
                        self.screen, (40, 52, 78), shade, border_radius=4
                    ),
                )
            elif i % 2:
                pg.draw.rect(self.screen, (20, 26, 42), shade, border_radius=4)
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
            mid = line_y + 10  # the row's middle: the + button's too
            for key, edge in columns:
                text, tone, size = values[key]
                sign = text.startswith("+")
                drawn = self.text(
                    text[1:] if sign else text,
                    right(edge),
                    mid,
                    size=size,
                    color=tone,
                    anchor="midright",
                )
                if sign and drawn is not None:
                    # the sign drawn as bars, not the font's "+": the font's is small and sits
                    # low beside the digits (D98), as the + button's cross (D93)
                    arm = max(3, size // 4)
                    cx, cy = drawn.left - arm - 2, drawn.centery - 2  # the digits, not descents
                    pg.draw.rect(self.screen, tone, (cx - arm, cy - 1, arm * 2 + 1, 2))
                    pg.draw.rect(self.screen, tone, (cx - 1, cy - arm, 2, arm * 2 + 1))
            plus = (ax + aw - 36, line_y - 3, 36, 26)
            fill = (64, 150, 92) if row.allowed else (52, 58, 72)
            pg.draw.rect(self.screen, fill, plus, border_radius=5)
            pg.draw.rect(
                self.screen, (150, 200, 160) if row.allowed else (90, 96, 110), plus, 1, 5
            )
            # two bars, not a "+" letter: a scaled-down window thinned each row's letter
            # differently (D93); bars keep every button's cross the same size and centred
            ink = (255, 255, 255) if row.allowed else (130, 136, 150)
            mid_x, mid_y = plus[0] + plus[2] // 2, plus[1] + plus[3] // 2
            pg.draw.rect(self.screen, ink, (mid_x - 7, mid_y - 2, 14, 4))
            pg.draw.rect(self.screen, ink, (mid_x - 2, mid_y - 7, 4, 14))
            self.hotspot(plus, lambda i=i: setattr(menu, "row", i))  # a click: raise it

    def _stat_about(self, stat_id):
        """A stat's What It Means in the player's language (``data.stat.<id>.description``)."""
        definition = getattr(self.project.rpg_database, "stat_definitions", {}).get(stat_id)
        return self.game.description_of(definition, "") if definition is not None else ""

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
        if detail.meanings:  # what its tags mean (Game Systems ▸ Tags), under its own words
            line_y += 6
        for meaning in detail.meanings:
            for line in wrap(self, meaning, 16, w):
                if line_y + 21 > bottom - facts_h - 8:
                    break
                self.text(line, x, line_y, size=16, color=muted)
                line_y += 21
        line_y = max(line_y + 8, bottom - facts_h)
        for label, value in detail.facts:
            if line_y + 22 > bottom:
                break
            self.pg.draw.line(self.screen, (40, 50, 76), (x, line_y - 3), (x + w, line_y - 3))
            self.text(label, x, line_y, size=18, color=muted)
            self.text(value, x + w, line_y, size=18, color=(240, 240, 248), anchor="topright")
            line_y += 26


__all__ = ["PAGES", "MenuPagesMixin"]
