"""The pause menu's pages (D87): Status, Items, Equipment and Skills as entries of their own.

``_pause_options`` lists the built-in entries a game can use, in the engine's order
(``rpg.menu_rules.PAUSE_ENTRIES``) or the one Game Systems ▸ Menu Pages sets, with the
project's own entries (Pause Menu Entries) before Settings. Equipment opens the paper doll,
Skills the skill tree when the member has one (else the list of skills). The Status page is a
stat table in the manner of a MapleStory stat window: the member's profile and resources, the
stats a stat graph raises with a + each and the points left, and a table of the other stats.
The Items page has tabs and a filter (F).
"""

from __future__ import annotations

from asteria.rpg.menu_rules import PAUSE_ENTRIES, menu_rules

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
        pg, tr, game = self.pg, self.game.tr, self.game
        actor_id = menu.actor_id
        view = menu._status_view()
        width, height = self.width, self.height
        left_w = min(460, (width - 112) // 2)
        bottom = height - 100
        normal = c.tone("text", (210, 215, 225))
        muted = c.tone("muted", (150, 170, 200))
        # the profile: name, class, level, resources
        profile_h = 214
        px, py, pw, _ph = self._status_section(
            c, "profile", (44, top, left_w, profile_h), tr("status.profile", "Character")
        )
        db = self.project.rpg_database
        state = game.save.rpg_state.actor_progression.get(actor_id)
        record = db.actors.get(actor_id)
        c.text("name", game.name_of(record, actor_id or "—"), px, py, size=26)
        classes = ", ".join(
            game.name_of(db.classes.get(k), k) for k in getattr(state, "active_class_ids", ())
        )
        level = getattr(state, "level", 1)
        line = tr("status.level", "Lv {level}", level=level)
        c.text("level", f"{line}   {classes}".strip(), px, py + 34, size=19, color=muted)
        experience = getattr(state, "experience", 0.0)
        exp = tr("status.exp", "EXP {value}", value=f"{experience:g}")
        c.text("exp", exp, px + pw, py + 34, size=19, color=muted, anchor="topright")
        bar_y = py + 68
        for resource in (view.resources if view is not None else ())[:3]:
            name = menu._word("resource", resource.resource_id, resource.label)
            self.text(name, px, bar_y, size=18, color=normal)
            bar = (px + 92, bar_y + 3, pw - 92, 16)
            pg.draw.rect(self.screen, (30, 34, 48), bar, border_radius=3)
            share = resource.current / resource.maximum if resource.maximum else 0.0
            fill = (bar[0], bar[1], int(bar[2] * max(0.0, min(1.0, share))), bar[3])
            tone = (214, 72, 72) if resource.resource_id.lower() in ("hp", "vitality") else None
            pg.draw.rect(self.screen, tone or (70, 128, 222), fill, border_radius=3)
            amount = f"{resource.current:g} / {resource.maximum:g}"
            self.text(
                amount,
                bar[0] + bar[2] // 2,
                bar_y + 1,
                size=15,
                center=False,
                anchor="midtop",
                color=(250, 250, 255),
            )
            bar_y += 28
        # the stat table: points left, one row and one + per stat
        points_top = top + profile_h + 12
        ax, ay, aw, _ah = self._status_section(
            c,
            "points",
            (44, points_top, left_w, bottom - points_top),
            tr("status.ability_points", "Ability Points"),
        )
        balances = "   ".join(f"{name} {value:g}" for name, value in menu.stat_points())
        if balances:
            c.text(
                "points_left",
                balances,
                44 + left_w - 14,
                points_top + 7,
                size=19,
                color=(140, 230, 170),
                anchor="topright",
            )
        rows = menu.stat_rows()
        if not rows:
            c.text("no_points", tr("status.no_stat_graph", "—"), ax, ay, size=19, color=muted)
        row_h = 38
        for i, row in enumerate(rows):
            y = ay + i * row_h
            if y + row_h > bottom - 6:
                break
            selected = i == menu.row
            band = (ax - 6, y - 4, aw + 12, row_h - 4)
            self.hotspot(band, lambda i=i: setattr(menu, "row", i), key="")
            if selected:
                c.selection(
                    "stat_rows",
                    band,
                    lambda band=band: pg.draw.rect(
                        self.screen, (40, 52, 78), band, border_radius=4
                    ),
                )
            color = c.tone("selected", (255, 255, 255)) if selected else normal
            self.text(row.label, ax, y, size=20, color=color)
            value = "—" if row.value is None else f"{row.value:g}"
            self.text(value, ax + aw - 120, y, size=20, color=color, anchor="topright")
            rank = f"{row.rank}/{row.max_rank}"
            self.text(rank, ax + aw - 52, y + 2, size=15, color=muted, anchor="topright")
            plus = (ax + aw - 40, y - 2, 36, 28)
            fill = (64, 150, 92) if row.allowed else (52, 58, 72)
            pg.draw.rect(self.screen, fill, plus, border_radius=5)
            pg.draw.rect(
                self.screen, (150, 200, 160) if row.allowed else (90, 96, 110), plus, 1, 5
            )
            self.text(
                "+",
                plus[0] + 18,
                plus[1] + 1,
                size=22,
                anchor="midtop",
                color=(255, 255, 255) if row.allowed else (130, 136, 150),
            )
            self.hotspot(plus, lambda i=i: setattr(menu, "row", i))  # a click: raise it
        # the other stats, as a table of two columns
        right_x = 44 + left_w + 24
        dx, dy, dw, _dh = self._status_section(
            c,
            "details",
            (right_x, top, width - 44 - right_x, bottom - top),
            tr("status.details", "Details"),
        )
        details = menu.detail_rows()
        columns = 2 if dw >= 520 else 1
        cell_w = dw // columns
        per_column = max(1, -(-len(details) // columns))
        for i, (_stat_id, label, value) in enumerate(details):
            column, line = divmod(i, per_column)
            x, y = dx + column * cell_w, dy + line * 34
            if y + 30 > bottom - 6:
                continue
            if line % 2 == 0:
                pg.draw.rect(self.screen, (22, 29, 48), (x - 6, y - 4, cell_w - 12, 30))
            self.text(label, x, y, size=18, color=normal)
            self.text(
                f"{value:g}", x + cell_w - 24, y, size=18, color=(170, 220, 255), anchor="topright"
            )
        if not details:
            c.text(
                "no_details", tr("status.empty", "Nothing here yet."), dx, dy, size=19, color=muted
            )

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


__all__ = ["PAGES", "MenuPagesMixin"]
