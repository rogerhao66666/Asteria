r"""The field's own menus in a creature game's art: the start menu and the screens it opens.

Opened from the field with the pause key when the playable manifest has
``field.creature_menu``; drawn like the creature battle screen at the game's own resolution
(240 x 160, scaled by whole pixels) with the same fonts and pictures
(``battle.creature_screen``: ``font``, ``font_small``, ``front``, ``icon``, ``item_icon``,
``party``, ``bag``). Every screen is optional; what is not given is drawn with shapes.

``field.creature_menu``:

* ``entries``: the start menu's rows in order - ``{"id", "label", "screen", "switch"}``.
  ``label`` may use message codes (``\V[player.name]``); ``switch`` hides the row until that
  switch is on; ``screen`` is one of ``dex``, ``party``, ``bag``, ``card``, ``navigator``,
  ``region``, ``save``, ``options``, ``close``. ``start_at`` is the menu window's inside top
  left, ``start_width`` its inside width; the window uses ``frame`` (a 3 x 3 grid of border
  pieces, default the manifest's ``dialogue.choice_frame``) filled with ``fill``.
* ``party``: the party screen of the battle (``battle.creature_screen.party``) with a
  SUMMARY / SWITCH / CANCEL window for the chosen creature.
* ``summary``: ``pages`` (a background per page: info, skills, moves), the creature's picture
  at ``picture_at`` and its words at the places in ``places`` (see ``SUMMARY_PLACES``).
* ``bag``: ``pockets`` - ``{"name", "picture", "tag"}`` (an item is in the pocket whose tag
  it carries; the first pocket takes the rest, the capture items go to a pocket tagged
  ``capture``); USE (``cant_use`` is said: the field has no item uses yet), TOSS, CANCEL.
* ``card``: ``background``, ``picture`` (a message-coded path, e.g. one per gender) at
  ``picture_at``; name, number, money, seen count and play time at ``places``; ``badges``
  (``{"switch", "picture", "at"}``) drawn once their switch is on.
* ``save``: the save question in the message window, an info window at ``save_info_at``;
  the game is written to save slot ``save_slot`` (default 1).
* ``options``: ``options`` - ``{"id", "label", "values"}``; each kept in the event variable
  ``option.<id>`` (an index; ``text_speed`` sets the field's letters a second through
  ``dialogue.speeds``).
* ``dex``: ``entries`` (a JSON list of ``{"number", "species", "name", "category", "height",
  "weight", "text"}``), ``background`` / ``entry_background``, ``ball`` (the caught mark).
  Seen: a battle met it (``world.bestiary``) or one is owned; owned: one is or was caught.
* ``navigator``: a list of rows over ``background``, each ``{"label", "screen"}`` (``screen``
  opens as a start menu row does, such as ``region``). The key was ``pokenav`` before; a
  project that still says so is read the same."""

from __future__ import annotations

from pathlib import Path

from asteria.presentation.screens.creature import creature_settings
from asteria.runtime.creature.battle import CreatureBattleScreen
from asteria.runtime.creature.menu_bag import CreatureMenuBagMixin
from asteria.runtime.creature.menu_draw import CreatureMenuDrawMixin
from asteria.runtime.creature.menu_pages import CreatureMenuPagesMixin
from asteria.runtime.creature.menu_party import CreatureMenuPartyMixin
from asteria.runtime.save_slots import SaveSlots


class CreatureMenuScreen(
    CreatureMenuPartyMixin,
    CreatureMenuBagMixin,
    CreatureMenuPagesMixin,
    CreatureMenuDrawMixin,
    CreatureBattleScreen,
):
    """Made when the start menu opens; each frame ``update(dt, events)`` then ``draw()``;
    ``done`` turns true when the player is back on the field."""

    def __init__(self, runtime, screen="start"):
        super().__init__(runtime)
        self.menu = creature_settings(runtime, "field.creature_menu")  # project, else manifest
        settings = getattr(runtime, "dialogue_settings", None)  # the picture window (V2)
        self.dialogue = dict(
            settings() if settings is not None else runtime.manifest.get("dialogue", {})
        )
        self.phase = screen
        self.alone = False  # opened at one screen by itself (open_alone), not from the START menu
        self.cursor = self.list_cursor = self.pocket = 0
        self.action_cursor = 0
        self.switch_from = None
        self.page = 0
        self.summary_pet = None
        self.note = ""  # a line in the message window of the menu screens
        self.save_step = None  # (step, seconds) of the save: ask / saving / saved
        self.dex_scroll = 0
        self.dex_filter, self.dex_choice = {}, {}  # the search's values, kept and being chosen
        self.region_cell, self.region_back = [0, 0], "start"
        self.fly_mode = False  # the region map is choosing where to fly
        self.bag_scroll = 0
        self.option_cursor = 0
        self._dex = None
        self.target_item, self.list_cursor_saved = "", 0
        self.teach_lines, self.teach_ask = [], ""  # a TM's lines, then its question

    def _remember_hp(self):  # no battle: nothing to remember
        return None

    def _intro(self):
        return None

    # -- the start menu -----------------------------------------------------------------------
    def entries(self):
        """The start menu rows shown now: ``(id, label, screen)``."""
        rows = []
        for entry in self.menu.get("entries") or ():
            switch = entry.get("switch")
            if switch and not self.game.save.event_context.get_switch(switch):
                continue
            label = self.game.expand_message(str(entry.get("label", "")), plain=True)
            rows.append((entry.get("id", ""), label, entry.get("screen", "close")))
        if not rows:
            rows = [("exit", self.tr("menu.exit", "EXIT"), "close")]
        return rows

    def open_alone(self, screen):
        """Open at ``screen`` by itself (from a title screen): leaving it closes the menu."""
        self.open(screen)
        self.alone = True

    def open(self, screen):
        if screen == "close":
            self.done = True
        elif screen == "party":
            self.phase, self.list_cursor, self.note = "party", 0, ""
            self.party_note = self.tr("creature.choose", "Choose a creature.")
        elif screen == "bag":
            self.phase, self.list_cursor, self.pocket, self.bag_scroll = "bag", 0, 0, 0
        elif screen == "save":
            self.phase, self.save_step, self.action_cursor = "save", ["ask", 0.0], 0
        elif screen == "options":
            self.phase, self.option_cursor = "options", 0
        elif screen == "dex":
            self.phase, self.list_cursor, self.dex_scroll = "dex", 0, 0
        elif screen == "card":
            self.phase = "card"
        elif screen in ("navigator", "pokenav"):  # "pokenav": the name used before D105
            self.phase, self.list_cursor = "navigator", 0
        elif screen == "region":
            self.region_back, self.phase = self.phase, "region"
            self.region_cell = self._player_region_cell()

    def update(self, dt, events=()):
        self.time += dt
        if self.save_step is not None and self.save_step[0] in ("saving", "saved"):
            self.save_step[1] += dt
            if self.save_step[0] == "saving" and self.save_step[1] > 0.8:
                self._write_save()
            elif self.save_step[0] == "saved" and self.save_step[1] > 0.4:
                if self._pressed("confirm") or self._pressed("cancel"):
                    self.done = True
            return
        handler = getattr(self, f"_input_{self.phase}", None)
        if handler is not None:
            handler()

    def _input_start(self):
        rows = self.entries()
        if self._pressed("move_up"):
            self.cursor = (self.cursor - 1) % len(rows)
        if self._pressed("move_down"):
            self.cursor = (self.cursor + 1) % len(rows)
        if self._pressed("cancel"):
            self.done = True
        elif self._pressed("confirm"):
            self.open(rows[min(self.cursor, len(rows) - 1)][2])

    def _back(self):
        if self.alone:  # opened at this screen (a title's OPTION): leaving it closes the menu
            self.done = True
        self.phase = "start"

    # -- saving --------------------------------------------------------------------------------
    def _input_save(self):
        if self.save_step is None or self.save_step[0] != "ask":
            return
        if self._pressed("move_up") or self._pressed("move_down"):
            self.action_cursor = 1 - self.action_cursor
        if self._pressed("cancel") or (self._pressed("confirm") and self.action_cursor == 1):
            self._back()
            self.save_step = None
        elif self._pressed("confirm"):
            self.save_step = ["saving", 0.0]

    def _write_save(self):
        slot = int((self.menu.get("save") or {}).get("save_slot", 1))
        self.game.sync_world_state()
        SaveSlots(Path(self.rt.resource_root) / "saves", self.game.project).save(slot, self.game)
        self.save_step = ["saved", 0.0]


__all__ = ["CreatureMenuScreen"]
