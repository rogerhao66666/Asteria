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
        self._ui_mode = "title"

    # -- status menu (UI-01) ----------------------------------------------------------------------
    def open_status_menu(self, back="field"):
        from asteria.runtime.status_menu import StatusMenu

        self.status_menu = StatusMenu(self.game)
        self._status_back = back
        self._ui_mode = "status"

    def _status_input(self, events):
        menu = self.status_menu
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            if event.key in (self.pg.K_ESCAPE, self.pg.K_i):
                self._ui_mode = self._status_back
            elif event.key == self.pg.K_TAB:
                menu.next_tab(-1 if getattr(event, "mod", 0) & self.pg.KMOD_SHIFT else 1)
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

        self._draw_field(False)
        shade = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
        shade.fill((6, 9, 18, 215))
        self.screen.blit(shade, (0, 0))
        menu = self.status_menu
        tr = self.game.tr
        self.panel((24, 22, self.width - 48, self.height - 44), fill=(11, 15, 25, 242))
        x = 44
        for tab in TABS:
            label = tr(TAB_WORDS[tab], tab.title())
            active = tab == menu.tab
            self.text(label, x, 36, size=24, color=(255, 220, 120) if active else (150, 160, 180))
            x += 150
        actor = menu.actor_id or "—"
        name = self.game.name_of(self.project.rpg_database.actors.get(actor), actor)
        member = tr("status.member", "Q / E  {name}", name=name)
        self.text(member, self.width - 330, 40, size=20, color=(170, 220, 255))
        rows = menu.rows()
        icons = menu.row_icons() if menu.tab in ("items", "equipment") else [""] * len(rows)
        label_x = 56 + (30 if any(icons) else 0)
        start = max(0, menu.row - 13)
        for i, (_kind, _key, label, detail) in enumerate(rows[start : start + 14]):
            y = 92 + i * 28
            selected = start + i == menu.row
            if selected:
                self.pg.draw.rect(
                    self.screen, (40, 52, 78), (40, y - 4, self.width - 80, 26), border_radius=4
                )
            self._draw_icon(icons[start + i], 56, y - 3)
            self.text(
                label, label_x, y, size=20, color=(255, 255, 255) if selected else (210, 215, 225)
            )
            self.text(detail, self.width - 420, y, size=20, color=(170, 210, 240))
        if not rows:
            empty = tr("status.empty", "Nothing here yet.")
            self.text(empty, 56, 92, size=20, color=(150, 160, 180))
        hint = tr(
            "status.hint",
            "Tab: next tab   Up/Down: choose   Enter: use / equip / unequip   Esc: back",
        )
        self.text(hint, 44, self.height - 60, size=18, color=(170, 210, 240))
        if menu.message:
            self.text(menu.message, 44, self.height - 88, size=19, color=(255, 226, 129))

    def _pause_input(self):
        if self.input.just_pressed("cancel"):
            self._ui_mode = "field"
            return
        if not self._menu_step(self._pause_menu):
            return
        choice = self._pause_menu.selected
        if choice == "resume":
            self._ui_mode = "field"
        elif choice == "status":
            self.open_status_menu(back="pause")
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
        if self.input.just_pressed("confirm") and screen.confirm() is not None:
            self._sound(self.manifest.get("dialogue_confirm_sfx"))

    def _open_crafting(self, station, back="field"):
        if self._multiplayer_connected():
            from asteria.runtime.network_bag_screen import NetworkCraftingScreen

            self._crafting_screen = NetworkCraftingScreen(self, station)
        else:
            self._crafting_screen = CraftingScreen(self.game, station)
        self._crafting_back = back
        self._ui_mode = "crafting"

    def _crafting_input(self):
        screen = self._crafting_screen
        if screen is None or self.input.just_pressed("cancel"):
            if screen is not None:
                screen.close()
            self._crafting_screen = None
            self._ui_mode = getattr(self, "_crafting_back", "field")
            return
        if self.input.just_pressed("move_up"):
            screen.move(-1)
        if self.input.just_pressed("move_down"):
            screen.move(1)
        if self.input.just_pressed("confirm") and screen.confirm() is not None:
            self._sound(self.manifest.get("dialogue_confirm_sfx"))

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
        if self.input.just_pressed("confirm") and key in ("show_battle_log", "language"):
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
