"""Pause, quests, shop, status, crafting, list screens and settings: their input."""

from __future__ import annotations

from asteria.rpg.built_in_text import translated
from asteria.runtime.game_menus import (
    CraftingScreen,
)
from asteria.runtime.game_session import GameSessionRuntime

from .support import (  # noqa: F401 - the names the moved methods use
    BESTIARY_TAG_KINDS,
    FIELD_BODY_HEIGHT,
    WALK_PATTERN_SEQUENCE,
    WALK_ROW_BY_FACING,
    _load_manifest,
    field_player_render_size,
    walking_pattern_index,
    walking_row_index,
)


class MenusInputMixin:
    # --- pause, quests, shop and game over (UI-02) --------------------------

    def _menu_step(self, cursor):
        if self.input.just_pressed("move_up"):
            cursor.move(-1)
        if self.input.just_pressed("move_down"):
            cursor.move(1)
        return self.input.just_pressed("confirm")

    def _restart_to_title(self):
        if self._multiplayer_connected() or self._network_gameplay_frozen():
            self._send_multiplayer_input(0, 0, {})
            self._ui_mode = "title"
            return
        if self.project.game_start is not None:
            self.save = self.project.game_start.instantiate(self.project)
            self.game = GameSessionRuntime(self.project, self.save)
        self._victory = False
        self._defeat = False
        self._shop_screen = None
        self.audio.stop_music(fade_out=0.3)
        self._title_running = ""  # a title made as an event program starts again
        self._ui_mode = "title"

    # -- status menu (UI-01) ----------------------------------------------------------------------
    def open_status_menu(self, back="field", page=None):
        """The status menu: its four tabs, or ``page`` alone (a pause entry of its own, D87)."""
        from asteria.runtime.status_menu import StatusMenu

        self.status_menu = StatusMenu(self.game, page)
        self._status_back = back
        self._ui_mode = "status"

    def _status_input(self, events):
        menu = self.status_menu
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            if event.key in (self.pg.K_ESCAPE, self.pg.K_i) and menu.details_open:
                menu.details_open = False  # Esc closes the details first
            elif event.key in (self.pg.K_ESCAPE, self.pg.K_i):
                self._ui_mode = self._status_back
            elif event.key == self.pg.K_d and menu.tab == "items":
                if menu.details_mode == "button":
                    menu.details_open = not menu.details_open
            elif event.key == self.pg.K_TAB and menu.single and menu.tab == "items":
                pointed = getattr(menu, "point_category", None)
                if getattr(event, "pointer", False) and pointed is not None:
                    menu.category, menu.row = pointed, 0  # the tab the mouse clicked
                else:
                    menu.next_category(-1 if getattr(event, "mod", 0) & self.pg.KMOD_SHIFT else 1)
            elif event.key == self.pg.K_TAB:
                menu.next_tab(-1 if getattr(event, "mod", 0) & self.pg.KMOD_SHIFT else 1)
            elif event.key in (self.pg.K_LEFT, self.pg.K_RIGHT) and menu.tab == "items":
                menu.next_category(-1 if event.key == self.pg.K_LEFT else 1)
            elif event.key == self.pg.K_f and menu.tab == "items":
                menu.next_filter()
            elif event.key == self.pg.K_RIGHT and menu.tab == "status":
                rows = menu.stat_rows()
                if rows:
                    menu.allocate_stat(rows[menu.row % len(rows)].node_id)
            elif event.key in (self.pg.K_q, self.pg.K_PAGEUP):
                menu.next_actor(-1)
            elif event.key in (self.pg.K_e, self.pg.K_PAGEDOWN):
                menu.next_actor(1)
            elif event.key in (self.pg.K_UP, self.pg.K_w):
                menu.move(-1)
            elif event.key in (self.pg.K_DOWN, self.pg.K_s):
                menu.move(1)
            elif event.key in (self.pg.K_RETURN, self.pg.K_SPACE):
                try:
                    menu.activate()
                except Exception as exc:  # noqa: BLE001 - shown to the player, play goes on
                    menu.message = translated(exc, self.game.tr)

    def _draw_status_menu(self):
        from asteria.runtime.status_menu import TAB_WORDS, TABS

        menu = self.status_menu
        actor = menu.actor_id or "—"
        record = self.project.rpg_database.actors.get(actor)
        name = self.game.name_of(record, actor)
        c = self.menu_canvas("status", self._member_fields(actor))
        layout = c.layout
        if layout is None or (layout.background_color is None and not layout.background_image):
            self._draw_field(False)
            dim = 215 if layout is None or layout.dim < 0 else layout.dim
            shade = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
            shade.fill((6, 9, 18, dim))
            self.screen.blit(shade, (0, 0))
        c.begin()
        tr = self.game.tr
        c.panel("frame", (24, 22, self.width - 48, self.height - 44), fill=(11, 15, 25, 242))
        tabs = c.place("tabs", (44, 36, 150 * len(TABS), 30), 150)
        if menu.single and menu.page_id:  # a project's own page (D96): its name
            title = self.game.name_of(menu.page)
            c.text("title", title, 44, 34, size=30, color=c.tone("title", (255, 220, 124)))
        elif menu.single:  # a page of its own: its name where the tabs were
            title = tr(TAB_WORDS[menu.tab], menu.tab.title())
            c.text("title", title, 44, 34, size=30, color=c.tone("title", (255, 220, 124)))
        elif c.shown("tabs"):
            x = tabs.x(44)
            for tab in TABS:
                label = tr(TAB_WORDS[tab], tab.title())
                active = tab == menu.tab
                color = c.tone("selected", (255, 220, 120)) if active else (150, 160, 180)
                rect = self.text(label, x, tabs.y(36), size=c.size("tabs", 24), color=color)
                self.hotspot(  # a click opens the tab
                    rect.inflate(12, 8),
                    lambda tab=tab: (
                        tab != menu.tab and menu.next_tab(TABS.index(tab) - TABS.index(menu.tab))
                    ),
                    key="",
                )
                x += tabs.row
        member = tr("status.member", "Q / E  {name}", name=name)
        c.text("member", member, self.width - 330, 40, size=20, color=(170, 220, 255))
        self.hotspot((self.width - 336, 34, 300, 32), key="e")  # a click: the next member
        if menu.page is not None:  # D96: the page's blocks, each in its place
            self._draw_menu_page(c, menu, (44, 84, self.width - 88, self.height - 184))
        else:  # Equipment and Skills: the list
            self._draw_item_list(c, menu, (44, 84, self.width - 88, self.height - 184))
        details = menu.details_mode if menu.tab == "items" else "off"
        if menu.tab == "status":
            hint = tr(
                "status.hint.status",
                "Up/Down: choose   Enter / Right: +1   Q / E: member   Esc: back",
            )
            if not menu.single:
                hint = tr("status.hint.tabs", "Tab: next tab") + "   " + hint
        elif menu.single and menu.tab == "items":
            hint = tr(
                "status.hint.items",
                "Left/Right: tab   F: filter   Up/Down: choose   Enter: use   Esc: back",
            )
            if details == "button":
                hint += "   " + tr("status.hint.details", "D: details")
        elif menu.single:
            hint = tr("status.hint.page", "Up/Down: choose   Enter: use / equip   Esc: back")
        else:
            hint = tr(
                "status.hint",
                "Tab: next tab   Up/Down: choose   Enter: use / equip / unequip   Esc: back",
            )
        self._status_footer(c, menu, hint)

    def _draw_item_list(self, c, menu, rect):
        """The bag (an ``item_list`` block, D96) - or the Equipment / Skills tab's list - in
        ``rect``: the Items page's tabs above, the chosen thing's details beside or behind a
        button."""
        tr = self.game.tr
        # the list reaches 4 px past the page's edge, as it always has
        x, y, w = rect[0] - 4, rect[1] - 4, rect[2] + 8
        bottom = rect[1] + rect[3] - 10
        top = y + 8
        details = menu.details_mode if menu.tab == "items" else "off"
        if menu.tab == "items":
            self._draw_item_tabs(c, menu, y)
            top = y + 48
        rows = menu.rows()
        list_w = w
        if details == "panel":  # the list on the left, the chosen thing's details on the right
            list_w = int(w * 0.58)
            panel = (x + list_w + 12, top - 6, w - 12 - list_w, bottom - top + 6)
            self._draw_item_detail(c, menu, panel)
        icons = menu.row_icons() if menu.tab in ("items", "equipment") else [""] * len(rows)
        at = c.place("rows", (x, top, list_w, (bottom - top) // 28 * 28), 28)
        icon_size = c.icon_size("rows", 22)
        label_x = at.x(x + 16) + (icon_size + 8 if any(icons) else 0)
        fit = max(1, at.rect[3] // at.row)
        start = max(0, menu.row - (fit - 1))
        size = c.size("rows", 20)
        normal = c.color("rows", c.tone("text", (210, 215, 225)))
        for i, (_kind, _key, label, detail) in enumerate(rows[start : start + fit]):
            row_y = at.y(top + 4) + i * at.row
            selected = start + i == menu.row
            row_box = (at.x(x), row_y - 4, at.rect[2], at.row - 2)
            self.hotspot(row_box, lambda row=start + i: setattr(menu, "row", row))
            if selected:
                band = (at.x(x), row_y - 4, at.rect[2], at.row - 2)
                c.selection(
                    "rows",
                    band,
                    lambda band=band: self.pg.draw.rect(
                        self.screen, (40, 52, 78), band, border_radius=4
                    ),
                )
            self._draw_icon(icons[start + i], at.x(x + 16), row_y - 3, icon_size)
            picked = c.tone("selected", (255, 255, 255))
            self.text(label, label_x, row_y, size=size, color=picked if selected else normal)
            self.text(
                detail,
                at.x(x) + at.rect[2] - 12,
                row_y,
                size=size,
                color=c.tone("muted", (170, 210, 240)),
                anchor="topright",
            )
        if not rows:
            empty = tr("status.empty", "Nothing here yet.")
            c.text("empty", empty, x + 16, top + 4, size=20, color=(150, 160, 180))
        if details == "button":
            self._draw_details_button(c, menu, rows)

    def _draw_details_button(self, c, menu, rows):
        """The Items page's Details button (item_details "button"); open, the details over the
        list - a click on the button, D, or Esc closes them."""
        tr = self.game.tr
        words = tr("status.details_button", "D  Details")
        x, y = self.width - 48, self.height - 92
        rect = self.text(words, x - 14, y + 6, size=19, color=(255, 236, 190), anchor="topright")
        box = rect.inflate(28, 12)
        self.pg.draw.rect(self.screen, (255, 220, 120), box, 2, border_radius=6)
        self.hotspot(box, key="d")
        if menu.details_open and rows:
            w, h = min(520, self.width - 120), min(380, self.height - 160)
            self._draw_item_detail(c, menu, ((self.width - w) // 2, 96, w, h))

    def _status_footer(self, c, menu, hint):
        """The status menu's key hint and last message."""
        c.text("hint", hint, 44, self.height - 60, size=18, color=c.tone("muted", (170, 210, 240)))
        if menu.message:
            c.text("message", menu.message, 44, self.height - 88, size=19, color=(255, 226, 129))
        c.finish()

    def _member_fields(self, actor_id):
        """Fields a screen about one party member offers the author's own texts (U2)."""
        game = self.game
        db = self.project.rpg_database

        def level():
            state = game.save.rpg_state.actor_progression.get(actor_id)
            return getattr(state, "level", "")

        def job():
            state = game.save.rpg_state.actor_progression.get(actor_id)
            ids = getattr(state, "active_class_ids", ()) or ()
            return ", ".join(game.name_of(db.classes.get(c), c) for c in ids)

        return {
            "member.name": lambda: game.name_of(db.actors.get(actor_id), actor_id),
            "member.level": level,
            "member.class": job,
            "wallet.gold": game.save.rpg_state.currencies.get("gold", 0),
        }

    def _pause_input(self):
        if self.input.just_pressed("cancel"):
            self._ui_mode = "field"
            return
        if not self._menu_step(self._pause_menu):
            return
        choice = self._pause_menu.selected
        if choice == "resume":
            self._ui_mode = "field"
        elif choice in ("status", "items", "equipment", "skills") or choice.startswith("page:"):
            self._open_pause_page(choice)  # page:<id>: a project's own menu page (D96)
        elif choice == "enhance":
            self.open_enhance_screen(back="pause")
        elif choice in ("backlog", "music", "credits", "skill_slots"):
            from asteria.runtime import extras_screens

            screen = {
                "backlog": extras_screens.BacklogScreen,
                "music": extras_screens.MusicRoomScreen,
                "credits": extras_screens.CreditsScreen,
                "skill_slots": extras_screens.AbilitySlotsScreen,
            }[choice]
            self._extra_screen = screen(self)
            self._ui_mode = "extra"
        elif choice.startswith("entry:"):
            self._run_menu_entry(choice[len("entry:") :])
        elif choice == "pets":
            from asteria.runtime.pets_screen import PetsScreen

            self._pets_screen = PetsScreen(self)
            self._ui_mode = "pets"
        elif choice == "quests":
            self._quest_return = "pause"
            self._ui_mode = "quests"
        elif choice == "crafting":
            self._open_crafting("", back="pause")
        elif choice in ("achievements", "bestiary"):
            self._list_scroll = 0
            self._ui_mode = choice
        elif choice == "settings":
            self._settings_menu.index = 0
            self._ui_mode = "settings"
        elif choice == "save":
            self.open_slots("save", back="pause")
        elif choice == "load":
            self.open_slots("load", back="pause")
        elif choice == "title":
            self._restart_to_title()
        elif choice == "quit":
            self.running = False

    def _run_menu_entry(self, entry_id):
        """A project-defined pause entry: close the menu and queue its event program."""
        entry = self.project.rpg_database.menu_entries.get(entry_id)
        if entry is None:
            return
        context = self.game.save.event_context
        if entry.visible_switch and not context.get_switch(entry.visible_switch):
            return
        if entry.enabled_switch and not context.get_switch(entry.enabled_switch):
            return
        self._ui_mode = "field"
        self.game.pending_followups.append(entry.event_program_id)

    def _game_over_input(self):
        if not self._menu_step(self._game_over_menu):
            return
        if self._game_over_menu.selected == "load":
            self._load_player_save()
        else:
            self._restart_to_title()

    def _quests_input(self):
        if self.input.just_pressed("cancel") or self.input.just_pressed("confirm"):
            self._ui_mode = self._quest_return

    def _shop_input(self):
        screen = self._shop_screen
        if screen is None or screen.shop is None or self.input.just_pressed("cancel"):
            if screen is not None:
                screen.close()
            self._shop_screen = None
            self._ui_mode = "field"
            return
        if self.input.just_pressed("move_up"):
            screen.move(-1)
        if self.input.just_pressed("move_down"):
            screen.move(1)
        if self.input.just_pressed("move_left") or self.input.just_pressed("move_right"):
            screen.switch_tab()
        if self.input.just_pressed("confirm"):
            theme = self.menu_theme()
            if screen.confirm() is not None:  # the theme's "buy", else the dialogue's sound
                bought = theme.sound("buy") if theme is not None else ""
                self._sound(bought or self.manifest.get("dialogue_confirm_sfx"))
            elif theme is not None:
                self._sound(theme.sound("fail"))

    def _open_crafting(self, station, back="field"):
        if self._multiplayer_connected():
            from asteria.runtime.network_bag_screen import NetworkCraftingScreen

            self._crafting_screen = NetworkCraftingScreen(self, station)
        else:
            self._crafting_screen = CraftingScreen(self.game, station)
        self._crafting_back = back
        self._ui_mode = "crafting"

    def _crafting_input(self, events=()):
        screen = self._crafting_screen
        if screen is None or self.input.just_pressed("cancel"):
            if screen is not None:
                screen.close()
            self._crafting_screen = None
            self._ui_mode = getattr(self, "_crafting_back", "field")
            return
        pg = self.pg
        keys = {e.key for e in events if e.type == pg.KEYDOWN}
        if keys & {pg.K_TAB, pg.K_e, pg.K_PAGEDOWN}:
            screen.switch_tab(1)
        elif keys & {pg.K_q, pg.K_PAGEUP}:
            screen.switch_tab(-1)
        if self.input.just_pressed("move_up"):
            screen.move(-1)
        if self.input.just_pressed("move_down"):
            screen.move(1)
        if self.input.just_pressed("move_left"):
            screen.change_quantity(-1)
        if self.input.just_pressed("move_right"):
            screen.change_quantity(1)
        if self.input.just_pressed("confirm"):
            theme = self.menu_theme()
            station = screen.workstation()
            result = screen.confirm()
            if result is not None and getattr(result, "success", True):
                # the station's sound, else the theme's "buy", else the dialogue's
                bought = theme.sound("buy") if theme is not None else ""
                sound = station.craft_sound or bought
                self._sound(sound or self.manifest.get("dialogue_confirm_sfx"))
            else:
                self._sound(station.fail_sound or (theme.sound("fail") if theme else ""))

    def _list_screen_input(self):
        if self.input.just_pressed("cancel") or self.input.just_pressed("confirm"):
            self._ui_mode = "pause"
            return
        if self.input.just_pressed("move_down"):
            self._list_scroll += 1
        if self.input.just_pressed("move_up"):
            self._list_scroll = max(0, self._list_scroll - 1)

    def _settings_input(self):
        cursor = self._settings_menu
        if self.input.just_pressed("cancel"):
            self.settings.save(self._settings_path())
            self._ui_mode = "pause"
            return
        if self.input.just_pressed("move_up"):
            cursor.move(-1)
        if self.input.just_pressed("move_down"):
            cursor.move(1)
        key = cursor.selected
        if key == "back":
            if self.input.just_pressed("confirm"):
                self.settings.save(self._settings_path())
                self._ui_mode = "pause"
            return
        if key == "controls":
            if self.input.just_pressed("confirm"):
                from asteria.runtime.input_rebinding import ControlsMenu

                self.controls_menu = ControlsMenu(
                    self.project.input_map, self.settings.input_overrides, tr=self.game.tr
                )
                self._ui_mode = "controls"
            return
        delta = (1 if self.input.just_pressed("move_right") else 0) - (
            1 if self.input.just_pressed("move_left") else 0
        )
        if self.input.just_pressed("confirm") and key in (
            "show_battle_log",
            "developer_menu",
            "language",
        ):
            delta = 1
        if delta and key == "language":
            locales = self.game.localizer.locales()
            current = self.game.localizer.locale
            index = locales.index(current) if current in locales else 0
            self.game.set_locale(locales[(index + delta) % len(locales)])
            return
        if delta:
            self.settings.adjust(key, delta)
            self.settings.apply(self.audio)
