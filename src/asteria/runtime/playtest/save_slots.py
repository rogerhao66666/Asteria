"""Save slots (ENG-21)."""

from __future__ import annotations

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


class SaveSlotsMixin:
    # -- save slots (ENG-21) ----------------------------------------------------------------------
    def _slot_exists(self, slot):
        from asteria.runtime.save_slots import SaveSlots

        return SaveSlots(self.resource_root / "saves", self.project).path(slot).exists()

    def open_slots(self, mode, back="pause"):
        if self._multiplayer_connected() or self._network_gameplay_frozen():
            self._server_save_command(mode)
            self._ui_mode = "field" if mode == "load" else back
            return
        from asteria.runtime.save_slots import SaveSlots, SlotMenu

        self.slot_menu = SlotMenu(
            SaveSlots(self.resource_root / "saves", self.project, lookup=self.game.data_lookup),
            mode,
            tr=self.game.tr,
        )
        self._slots_back = back
        self._ui_mode = "slots"

    def _slots_input(self, events):
        menu = self.slot_menu
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            if event.key == self.pg.K_ESCAPE:
                self._ui_mode = self._slots_back
            elif event.key in (self.pg.K_UP, self.pg.K_w):
                menu.move(-1)
            elif event.key in (self.pg.K_DOWN, self.pg.K_s):
                menu.move(1)
            elif event.key in (self.pg.K_DELETE, self.pg.K_BACKSPACE):
                menu.delete()
            elif event.key in (self.pg.K_RETURN, self.pg.K_SPACE):
                outcome, value = menu.activate(self.game)
                if outcome == "loaded":
                    self.save = value
                    self.game = GameSessionRuntime(self.project, value)
                    self._victory = self._defeat = False
                    self._ui_mode = "field"
                    self._title_running = ""  # (a title made as an event program has ended)
                    self.message = self.game.tr(
                        "slots.loaded", "Loaded slot {slot}", slot=menu.slot
                    )
                    self.message_until = self.pg.time.get_ticks() + 1800
                elif outcome == "saved":
                    self.message = menu.message
                    self.message_until = self.pg.time.get_ticks() + 1800

    def _draw_slots(self):
        c = self.menu_canvas("save_slots")
        self._draw_backdrop(canvas=c)
        menu = self.slot_menu
        c.panel("frame", (100, 60, self.width - 200, self.height - 120))
        tr = self.game.tr  # the slot screens' titles are the pause menu's own words
        title = (
            tr("pause.save", "Save Game") if menu.mode == "save" else tr("pause.load", "Load Game")
        )
        title_color = c.tone("title", (255, 220, 124))
        c.text("title", title, self.width / 2, 76, size=32, color=title_color, center=True)
        rows = menu.rows()
        at = c.place("slots", (120, 132, self.width - 240, 64 * len(rows)), 64)
        size = c.size("slots", 24)
        for i, info in enumerate(rows):
            y = at.y(140) + i * at.row
            selected = i == menu.row
            if selected:
                band = (at.x(120), y - 8, at.rect[2], at.row - 10)
                c.selection(
                    "slots",
                    band,
                    lambda band=band: self.pg.draw.rect(
                        self.screen, (40, 52, 78), band, border_radius=6
                    ),
                )
            if info.slot == "autosave":
                name = tr("slots.autosave", "Autosave (F5)")
            else:
                name = tr("slots.slot", "Slot {slot}", slot=info.slot)
            normal = c.color("slots", c.tone("text", (235, 238, 245)))
            picked = c.tone("selected", (255, 226, 129))
            self.text(name, at.x(140), y, size=size, color=picked if selected else normal)
            summary = info.summary_text(tr)
            self.text(summary, at.x(140), y + 24, size=18, color=c.tone("muted", (170, 210, 240)))
        hint = menu.message or tr("slots.hint", "Enter: choose   Delete: erase   Esc: back")
        c.text(
            "hint",
            hint,
            self.width / 2,
            self.height - 96,
            size=19,
            color=(255, 226, 129),
            center=True,
        )
        c.finish()
