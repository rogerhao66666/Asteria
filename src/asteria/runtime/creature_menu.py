"""The field's own menus in a creature game's art: the start menu and the screens it opens.

Opened from the field with the pause key when the playable manifest has
``field.creature_menu``; drawn like the creature battle screen at the game's own resolution
(240 x 160, scaled by whole pixels) with the same fonts and pictures
(``battle.creature_screen``: ``font``, ``font_small``, ``front``, ``icon``, ``item_icon``,
``party``, ``bag``). Every screen is optional; what is not given is drawn with shapes.

``field.creature_menu``:

* ``entries``: the start menu's rows in order - ``{"id", "label", "screen", "switch"}``.
  ``label`` may use message codes (``\\V[player.name]``); ``switch`` hides the row until that
  switch is on; ``screen`` is one of ``dex``, ``party``, ``bag``, ``card``, ``save``,
  ``options``, ``close``. ``start_at`` is the menu window's inside top left, ``start_width``
  its inside width; the window uses ``frame`` (a 3 x 3 grid of border pieces, default the
  manifest's ``dialogue.choice_frame``) filled with ``fill``.
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
"""

from __future__ import annotations

import json
from pathlib import Path

from asteria.presentation.creature_screens import creature_settings
from asteria.runtime.creature_battle import CreatureBattleScreen, H, W
from asteria.runtime.pointer import hand_over

OVERLAY_PHASES = ("start", "save")  # drawn over the field
PLAY_SECONDS = "play.seconds"  # the world counter of the time played (the card, the save)
SUMMARY_PLACES = {  # the summary pages' words: (x, y) in the screen's own pixels
    "title": (8, 1),
    "number": (4, 19),
    "name": (40, 19),
    "level": (4, 112),
    "picture": (40, 72),
    "info.ot": (96, 34),
    "info.id": (184, 34),
    "info.type": (96, 50),
    "info.item": (96, 66),
    "info.memo": (96, 114),
    "skills.labels": (88, 58),
    "skills.values": (184, 58),
    "skills.exp": (88, 114),
    "moves.list": (128, 34),
}
CARD_PLACES = {  # the trainer card's words (pokeemerald's Hoenn card)
    "name": (24, 41),
    "id": (176, 17),
    "money": (24, 65),
    "money_value": (136, 65),
    "dex": (24, 81),
    "dex_value": (136, 81),
    "time": (24, 97),
    "time_value": (136, 97),
}


def taught_ability(item):
    from asteria.runtime.session.pets import taught_ability as taught

    return taught(item)


def _me(asset_id):
    from asteria.events.world_commands import WorldCommand

    return WorldCommand("PLAY_ME", {"asset_id": str(asset_id)})


class CreatureMenuScreen(CreatureBattleScreen):
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

    # -- the party --------------------------------------------------------------------------
    def actions(self):
        return (
            ("summary", self.tr("creature.menu.summary", "SUMMARY")),
            ("switch", self.tr("creature.menu.switch", "SWITCH")),
            ("cancel", self.tr("creature.cancel", "CANCEL")),
        )

    def _input_party(self):
        pets = self._party()
        count = len(pets) + 1  # + CANCEL
        if self._pressed("move_up") or self._pressed("move_left"):
            self.list_cursor = (self.list_cursor - 1) % count
        if self._pressed("move_down") or self._pressed("move_right"):
            self.list_cursor = (self.list_cursor + 1) % count
        if self._pressed("cancel"):
            if self.switch_from is not None:
                self.switch_from = None
                self.party_note = self.tr("creature.choose", "Choose a creature.")
                return
            self._back()
            return
        if not self._pressed("confirm"):
            return
        if self.list_cursor >= len(pets):
            self.switch_from = None
            self._back()
            return
        if self.switch_from is not None:  # the second creature of a switch
            self._swap(self.switch_from, self.list_cursor)
            self.switch_from = None
            self.party_note = self.tr("creature.choose", "Choose a creature.")
            return
        pet = pets[self.list_cursor]
        self.phase, self.action_cursor = "party_action", 0
        self.party_note = self.tr(
            "creature.menu.do_what", "Do what with this {name}?", name=self.game.pet_display(pet)
        )

    def _input_party_action(self):
        rows = self.actions()
        if self._pressed("move_up"):
            self.action_cursor = (self.action_cursor - 1) % len(rows)
        if self._pressed("move_down"):
            self.action_cursor = (self.action_cursor + 1) % len(rows)
        choice = None
        if self._pressed("cancel"):
            choice = "cancel"
        elif self._pressed("confirm"):
            choice = rows[self.action_cursor][0]
        if choice is None:
            return
        self.phase = "party"
        if choice == "summary":
            self.summary_pet, self.page, self.phase = self.list_cursor, 0, "summary"
        elif choice == "switch":
            self.switch_from = self.list_cursor
            self.party_note = self.tr("creature.menu.move_where", "Move to where?")
        else:
            self.party_note = self.tr("creature.choose", "Choose a creature.")

    def _swap(self, a, b):
        """Swap two places of the party (the save's order)."""
        state = self.game.save.rpg_state
        order = [p.instance_id for p in self.game.party_pets()]
        if a == b or max(a, b) >= len(order):
            return
        order[a], order[b] = order[b], order[a]
        state.party_pet_ids = tuple(order)
        self.order = list(order)

    # -- the summary -------------------------------------------------------------------------
    def _input_summary(self):
        pets = self._party()
        pages = max(1, len(self._summary_pages()) or 3)
        if self._pressed("move_left"):
            self.page = max(0, self.page - 1)
        if self._pressed("move_right"):
            self.page = min(pages - 1, self.page + 1)
        if self._pressed("move_up") and pets:
            self.summary_pet = (self.summary_pet - 1) % len(pets)
        if self._pressed("move_down") and pets:
            self.summary_pet = (self.summary_pet + 1) % len(pets)
        if self._pressed("cancel") or self._pressed("confirm"):
            self.phase = "party"
            self.party_note = self.tr("creature.choose", "Choose a creature.")

    def _summary_pages(self):
        return list((self.menu.get("summary") or {}).get("pages") or ())

    # -- the bag -----------------------------------------------------------------------------
    def pockets(self):
        pockets = (self.menu.get("bag") or {}).get("pockets")
        if pockets:
            return list(pockets)
        return [
            {"name": self.tr("creature.pocket.items", "ITEMS"), "picture": "items", "tag": ""},
            {
                "name": self.tr("creature.pocket.balls", "BALLS"),
                "picture": "balls",
                "tag": "capture",
            },  # fmt: skip
        ]

    def pocket_items(self, index=None):
        """``[(item_id, count)]`` in a pocket: the items carrying its tag; the first pocket
        has the items no pocket tags; ``capture`` holds every capture rule's items."""
        pockets = self.pockets()
        index = self.pocket if index is None else index
        db = self.game.project.rpg_database
        inventory = self.game.save.rpg_state.inventory
        balls = set()
        for rule in db.capture_rules.values():
            balls |= set(rule.capture_items())
        tags = [p.get("tag", "") for p in pockets]

        def pocket_of(item_id):
            item = db.items[item_id]
            for n, tag in enumerate(tags):
                if tag and tag != "capture" and tag in item.tags:
                    return n
            if item_id in balls and "capture" in tags:
                return tags.index("capture")
            return 0

        return [
            (item_id, inventory.count(item_id))
            for item_id in sorted(db.items)
            if inventory.count(item_id) > 0 and pocket_of(item_id) == index
        ]

    def _input_bag(self):
        pockets = self.pockets()
        items = self.pocket_items()
        count = len(items) + 1  # + CLOSE BAG
        if self._pressed("move_left"):
            self.pocket, self.list_cursor, self.bag_scroll = (self.pocket - 1) % len(pockets), 0, 0
        if self._pressed("move_right"):
            self.pocket, self.list_cursor, self.bag_scroll = (self.pocket + 1) % len(pockets), 0, 0
        if self._pressed("move_up"):
            self.list_cursor = max(0, self.list_cursor - 1)
        if self._pressed("move_down"):
            self.list_cursor = min(count - 1, self.list_cursor + 1)
        self.bag_scroll = min(self.bag_scroll, self.list_cursor)
        self.bag_scroll = max(self.bag_scroll, self.list_cursor - 5)
        if self._pressed("cancel"):
            self._back()
        elif self._pressed("confirm"):
            if self.list_cursor >= len(items):
                self._back()
                return
            self.phase, self.action_cursor, self.note = "bag_action", 0, ""

    def bag_actions(self):
        return (
            ("use", self.tr("creature.menu.use", "USE")),
            ("toss", self.tr("creature.menu.toss", "TOSS")),
            ("cancel", self.tr("creature.cancel", "CANCEL")),
        )

    def _input_bag_action(self):
        rows = self.bag_actions()
        if self.note:  # a line is shown: a key shows its next lines, then closes it
            if self._pressed("confirm") or self._pressed("cancel"):
                lines = self.wrap(self.note, 208)
                if len(lines) > 2:
                    self.note = "\n".join(lines[2:])
                else:
                    self.note, self.phase = "", "bag"
            return
        if self._pressed("move_up"):
            self.action_cursor = (self.action_cursor - 1) % len(rows)
        if self._pressed("move_down"):
            self.action_cursor = (self.action_cursor + 1) % len(rows)
        if self._pressed("cancel"):
            self.phase = "bag"
            return
        if not self._pressed("confirm"):
            return
        choice = rows[self.action_cursor][0]
        items = self.pocket_items()
        item_id = items[self.list_cursor][0] if self.list_cursor < len(items) else ""
        item = self.game.project.rpg_database.items.get(item_id) if item_id else None
        if choice == "use" and item is not None and taught_ability(item):
            # party_menu.c: "Booted up a TM." / "It contained ..." / "Teach ... ?" YES / NO
            move = self._move_name(taught_ability(item))
            self.phase, self.target_item, self.list_cursor_saved = (
                "bag_teach",
                item_id,
                (self.list_cursor),
            )
            self.teach_lines = [
                self.tr("creature.menu.tm_booted", "Booted up a TM."),
                self.tr("creature.menu.tm_contained", "It contained\n{move}.", move=move),
            ]
            self.note, self.action_cursor = self.teach_lines.pop(0), 0
        elif choice == "use" and item is not None and self._usable_on_pets(item):
            self.phase, self.target_item, self.list_cursor_saved = (
                "bag_target",
                item_id,
                (self.list_cursor),
            )
            self.list_cursor = 0
            self.party_note = self.tr("creature.menu.use_on_which", "Use on which creature?")
        elif choice == "use":
            self.note = self.game.expand_message(
                (self.menu.get("bag") or {}).get("cant_use")
                or self.tr("creature.menu.cant_use", "This can't be used now."),
                plain=True,
            )
        elif choice == "toss" and item_id:
            self.game.save.rpg_state.inventory.remove(item_id, 1)
            name = self.game.name_of(self.game.project.rpg_database.items[item_id], item_id)
            self.note = self.tr("creature.menu.tossed", "Threw away 1 {item}.", item=name)
            self.list_cursor = min(self.list_cursor, max(0, len(self.pocket_items()) - 1))
        else:
            self.phase = "bag"

    def _move_name(self, ability_id):
        ability = self.game.project.gameplay_library.abilities.get(ability_id)
        return self.game.name_of(ability, ability_id) if ability is not None else ability_id

    def _input_bag_teach(self):
        """The TM's lines, then YES / NO; YES chooses the creature to teach."""
        item = self.game.project.rpg_database.items.get(self.target_item)
        move = self._move_name(taught_ability(item)) if item is not None else ""
        if self.note:
            if self._pressed("confirm") or self._pressed("cancel"):
                if self.teach_lines:
                    self.note = self.teach_lines.pop(0)
                else:
                    self.note = ""
                    self.teach_ask = self.tr(
                        "creature.menu.teach_ask", "Teach {move}\nto a POKéMON?", move=move
                    )
            return
        if self._pressed("move_up") or self._pressed("move_down"):
            self.action_cursor = 1 - self.action_cursor
        if self._pressed("cancel") or (self._pressed("confirm") and self.action_cursor == 1):
            self.phase, self.list_cursor = "bag", self.list_cursor_saved
        elif self._pressed("confirm"):
            self.phase, self.list_cursor = "bag_target", 0
            self.party_note = self.tr(
                "creature.menu.teach_which", "Teach which POKéMON?", move=move
            )

    def slot_label(self, pet):
        """ABLE / NOT ABLE / LEARNED over a slot while a TM is chosen (party_menu.c)."""
        if self.phase != "bag_target" or not self.target_item:
            return None
        check = self.game.teaching_check(pet, self.target_item)
        if check == "able":
            return self.tr("creature.menu.able", "ABLE")
        if check == "not_able":
            return self.tr("creature.menu.not_able", "NOT ABLE")
        if check == "learned":
            return self.tr("creature.menu.learned", "LEARNED")
        return None

    @staticmethod
    def _usable_on_pets(item):
        from asteria.runtime.session.ability_use import cured_states

        return bool(item.use_effects or cured_states(item))

    def _input_bag_target(self):
        pets = self._party()
        if self.note:  # the result is shown: a key goes back to the bag
            if self._pressed("confirm") or self._pressed("cancel"):
                self.note, self.phase = "", "bag"
                self.list_cursor = min(self.list_cursor_saved, len(self.pocket_items()))
            return
        if self._pressed("move_up") or self._pressed("move_left"):
            self.list_cursor = (self.list_cursor - 1) % (len(pets) + 1)
        if self._pressed("move_down") or self._pressed("move_right"):
            self.list_cursor = (self.list_cursor + 1) % (len(pets) + 1)
        if self._pressed("cancel") or (self._pressed("confirm") and self.list_cursor >= len(pets)):
            self.phase, self.list_cursor = "bag", self.list_cursor_saved
            return
        if not self._pressed("confirm"):
            return
        pet = pets[self.list_cursor]
        if self._teach_result(pet):
            return
        hp = self.game.rules.knockout_resource_id
        before = self._pet_health(pet, None)[0]
        used = self.game.use_item_on_pet(pet, self.target_item)
        after = self._pet_health(pet, None)[0]
        if not used:
            self.note = self.tr("creature.menu.no_effect", "It won't have any effect.")
        elif after > before:
            self.note = self.tr(
                "creature.menu.hp_restored",
                "{name}'s HP was restored by {amount} point(s).",
                name=self.game.pet_display(pet),
                amount=f"{after - before:.0f}",
            )
        else:
            self.note = self.tr("creature.menu.cured", "{name} was cured.",
                                name=self.game.pet_display(pet))  # fmt: skip
        _ = hp

    def _teach_result(self, pet):
        """A TM on the chosen creature: learned, known already, not compatible, or (its
        moves full) the field's forget-a-move prompt takes over. False: not a TM."""
        item = self.game.project.rpg_database.items.get(self.target_item)
        ability = taught_ability(item) if item is not None else ""
        if not ability:
            return False
        name, move = self.game.pet_display(pet), self._move_name(ability)
        check = self.game.teaching_check(pet, self.target_item)
        if check == "learned":
            self.note = self.tr("creature.menu.already_knows", "{name} already knows\n{move}.",
                                name=name, move=move)  # fmt: skip
        elif check != "able":
            self.note = self.tr(
                "creature.menu.not_compatible",
                "{name} and {move}\nare not compatible.",
                name=name,
                move=move,
            )
        elif self.game.use_item_on_pet(pet, self.target_item):
            if any(a == ability for _p, a in self.game.pending_pet_moves()):
                self.done = True  # the field asks which move to forget
                return True
            self.note = self.tr("creature.menu.learned_move", "{name} learned\n{move}!",
                                name=name, move=move)  # fmt: skip
            sound = (self.menu.get("bag") or {}).get("learned_sound")
            if sound:
                self.game.presentation_requests.append(_me(sound))
        return True

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
        return entries[: last + 1]

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

    def _input_dex_entry(self):
        if self._pressed("cancel") or self._pressed("confirm"):
            self.phase = "dex"

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
        from asteria.runtime.save_slots import SaveSlots

        slot = int((self.menu.get("save") or {}).get("save_slot", 1))
        self.game.sync_world_state()
        SaveSlots(Path(self.rt.resource_root) / "saves", self.game.project).save(slot, self.game)
        self.save_step = ["saved", 0.0]

    # -- drawing -------------------------------------------------------------------------------
    def draw(self):
        s = self.surface
        overlay = self.phase in OVERLAY_PHASES
        s.fill((0, 0, 0, 0) if overlay else (0, 0, 0, 255))
        self._spots = []  # what the mouse can point at, marked as the phase draws (D85)
        draw = getattr(self, f"_draw_{self.phase}", None)
        if draw is not None:
            draw()
        screen = self.rt.screen
        sw, sh = screen.get_size()
        scale = max(1, min(sw // W, sh // H))
        if not overlay:
            screen.fill((0, 0, 0, 255))
        big = self.pg.transform.scale(s, (W * scale, H * scale))
        left, top = (sw - W * scale) // 2, (sh - H * scale) // 2
        screen.blit(big, (left, top))
        hand_over(self.rt, self._menu_spots() + self._spots, scale, left, top)

    def _spot(self, rect, attr=None, value=0, key="return"):
        """Mark a place the mouse can point at: pointing sets ``attr`` to ``value`` (None:
        nothing), a left click presses ``key``."""
        pick = None if attr is None else (lambda: setattr(self, attr, value))
        self._spots.append((tuple(rect), pick, key))

    def _menu_spots(self):
        """The phase's hotspots that are not marked while drawing: the party slots (the battle
        screen's), else the whole screen for a page a click reads on from."""
        phase = self.phase
        if phase in ("party", "bag_target"):
            count = len(self._party())
            spots = [(self.PARTY_SLOTS[i], self._to("list_cursor", i), "return")
                     for i in range(min(count, len(self.PARTY_SLOTS)))]  # fmt: skip
            return spots + [((*self.PARTY_CANCEL, 56, 24), self._to("list_cursor", count),
                             "return")]  # fmt: skip
        saved = phase == "save" and (self.save_step or ["ask"])[0] == "saved"
        if phase in ("summary", "card", "dex_entry") or saved:
            return [((0, 0, W, H), None, "return")]
        return []

    def _to(self, attr, value):
        return lambda: setattr(self, attr, value)

    def _menu_colours(self):
        colours = self.dialogue.get("colours") or ((98, 98, 98), (213, 213, 205))
        return tuple(colours[0]), tuple(colours[1])

    def _frame(self, inside):
        """A window in the game's border pieces around ``inside`` (x, y, w, h)."""
        pg, s = self.pg, self.surface
        x, y, w, h = inside
        path = self.menu.get("frame") or self.dialogue.get("choice_frame")
        key = ("frame", path)
        if key not in self._images:
            image = None
            if path and self._path(path).is_file():
                image = pg.image.load(str(self._path(path))).convert_alpha()
            self._images[key] = image
        frame = self._images[key]
        fill = tuple(self.menu.get("fill") or self.dialogue.get("choice_fill") or (255,) * 3)
        if frame is None:
            self._window(pg.Rect(x - 4, y - 4, w + 8, h + 8), fill, (72, 72, 96))
            return
        piece = frame.get_width() // 3
        pg.draw.rect(s, fill, (x, y, w, h))
        for col, fx in ((0, x - piece), (2, x + w)):
            for row, fy in ((0, y - piece), (2, y + h)):
                s.blit(frame, (fx, fy), (col * piece, row * piece, piece, piece))
        for fx in range(x, x + w, piece):
            s.blit(frame, (fx, y - piece), (piece, 0, piece, piece))
            s.blit(frame, (fx, y + h), (piece, 2 * piece, piece, piece))
        for fy in range(y, y + h, piece):
            s.blit(frame, (x - piece, fy), (0, piece, piece, piece))
            s.blit(frame, (x + w, fy), (2 * piece, piece, piece, piece))

    def _list_window(self, rows, cursor, right, bottom, width=None):
        """A framed list of ``rows`` (labels) with the pointer at ``cursor``; its outside
        right and bottom edges at ``right`` / ``bottom``."""
        letter, shadow = self._menu_colours()
        width = width or max(self.text_width(r) for r in rows) + 16
        width = (width + 7) // 8 * 8
        height = 16 * len(rows)
        x, y = right - 8 - width, bottom - 8 - height
        self._frame((x, y, width, height))
        for row, label in enumerate(rows):
            self._spot((x, y + row * 16, width, 16), "action_cursor", row)
            self._text(label, x + 8, y + row * 16 + 1, letter, shadow)
            if row == cursor:
                self._cursor(x, y + row * 16 + 3)

    def _message_window(self, text):
        """The field's message window at the bottom with ``text`` (two lines)."""
        path = self.dialogue.get("window")
        key = ("message_window", path)
        if key not in self._images:
            image = None
            if path and self._path(path).is_file():
                image = self.pg.image.load(str(self._path(path))).convert_alpha()
            self._images[key] = image
        window = self._images[key]
        letter, shadow = self._menu_colours()
        if window is not None:
            top = H - window.get_height()
            self.surface.blit(window, ((W - window.get_width()) // 2, top))
            x0, y0, *_rest = self.dialogue.get("text_area", (16, 8, 216, 32))
            step = int(self.dialogue.get("line_height", 16))
        else:
            top, x0, y0, step = H - 48, 12, 8, 16
            self._frame((8, top + 8, W - 16, 32))
        for row, line in enumerate(self.wrap(text, 208)[:2]):
            self._text(line, x0, top + y0 + row * step, letter, shadow)

    def _draw_start(self):
        rows = self.entries()
        letter, shadow = self._menu_colours()
        x, y = self.menu.get("start_at", (176, 8))
        width = int(self.menu.get("start_width", 56))
        self._frame((x, y, width, 16 * len(rows) + 16))
        for row, (_id, label, _screen) in enumerate(rows):
            self._spot((x, y + row * 16 + 7, width, 16), "cursor", row)
            self._text(label, x + 8, y + row * 16 + 9 - 1, letter, shadow)
            if row == self.cursor:
                self._cursor(x, y + row * 16 + 9 + 2)

    def _draw_party(self):
        super()._draw_party()

    def _draw_party_action(self):
        super()._draw_party()
        rows = [label for _id, label in self.actions()]
        self._list_window(rows, self.action_cursor, W - 2, H - 2)

    def _draw_summary(self):
        pg, s = self.pg, self.surface
        pets = self._party()
        if not pets:
            return
        pet = pets[min(self.summary_pet or 0, len(pets) - 1)]
        species = self.game.pet_species(pet)
        pages = self._summary_pages()
        settings = self.menu.get("summary") or {}
        places = {**SUMMARY_PLACES, **{k: (tuple(v) if v is not None else None) for k, v in
                                        (settings.get("places") or {}).items()}}  # fmt: skip
        background = None
        if pages:
            path = pages[min(self.page, len(pages) - 1)]
            key = ("summary", path)
            if key not in self._images:
                image = None
                if self._path(path).is_file():
                    image = pg.image.load(str(self._path(path))).convert_alpha()
                self._images[key] = image
            background = self._images[key]
        if background is not None:
            s.blit(background, (0, 0))
        else:
            s.fill((136, 184, 232))
        white, grey = (248, 248, 248), (112, 112, 112)
        ink, ink_shadow = (80, 80, 80), (208, 208, 200)
        titles = (
            self.tr("creature.summary.info", "INFO"),
            self.tr("creature.summary.skills", "SKILLS"),
            self.tr("creature.summary.moves", "MOVES"),
        )
        self._text(titles[min(self.page, 2)], *places["title"], white, grey)
        number = self._dex_number(pet.species_id)
        if number:
            self._text(f"No{number:03d}", *places["number"], white, grey)
        if self.page in settings.get("name_on_pages", (0, 1, 2)):  # a page may cover them
            self._text(self.game.pet_display(pet), *places["name"], white, grey)
            level = self.tr("creature.level", "Lv{level}", level=pet.level)
            self._text(level, *places["level"], white, grey)
        picture = self._image("front", pet.species_id, None)
        if picture is not None:
            s.blit(picture, picture.get_rect(center=places["picture"]))
        member_id = None
        current, top = self._pet_health(pet, member_id)
        if self.page == 0:
            owner = self.game.expand_message(
                str(settings.get("owner", "\\V[player.name]")), plain=True
            )
            self._text(owner, *places["info.ot"], ink, ink_shadow)
            number = self.game.expand_message(str(settings.get("id", "")), plain=True)
            self._text(number, *places["info.id"], ink, ink_shadow)
            types = [t[5:].upper() for t in (species.tags if species else ()) if t.startswith(
                "type.")]  # fmt: skip
            self._text("/".join(types), *places["info.type"], ink, ink_shadow)
            if places.get("info.item") is not None:
                item = pet.held_item_id
                name = (
                    self.game.name_of(self.game.project.rpg_database.items[item], item)
                    if item
                    else ""
                )
                self._text(name or self.tr("creature.summary.none", "NONE"),
                           *places["info.item"], ink, ink_shadow)  # fmt: skip
        elif self.page == 1:
            stats = self.game.pet_stats_at(pet)
            names = settings.get("stats") or [
                ["hp", "HP"], ["attack", "ATTACK"], ["defense", "DEFENSE"],
                ["sp_attack", "SP. ATK"], ["sp_defense", "SP. DEF"], ["speed", "SPEED"],
            ]  # fmt: skip
            lx, ly = places["skills.labels"]
            vx, vy = places["skills.values"]
            for row, entry in enumerate(names):
                stat, label = entry[0], entry[1]
                # [stat, label, label x, label y, value right, value y]: its own places
                at = entry[2:6] if len(entry) >= 6 else (lx, ly + row * 16, vx, vy + row * 16)
                if label:
                    self._text(label, at[0], at[1], white, grey)
                value = f"{current:.0f}/{top:.0f}" if stat == "hp" else f"{stats.get(stat, 0):.0f}"
                self._text(value, at[2], at[3], ink, ink_shadow, anchor="topright")
            ex, ey = places["skills.exp"]
            right = places.get("skills.exp_right", (vx, 0))[0]
            to_next = species.exp_to_next(pet.level) - pet.experience if species else 0
            if settings.get("exp_labels", True):
                self._text(self.tr("creature.summary.exp", "EXP. POINTS"), ex, ey, ink, ink_shadow)
                self._text(self.tr("creature.summary.next", "NEXT LV."), ex, ey + 16, ink,
                           ink_shadow)  # fmt: skip
            self._text(f"{pet.experience:.0f}", right, ey, ink, ink_shadow, anchor="topright")
            self._text(f"{max(0, to_next):.0f}", right, ey + 16, ink, ink_shadow,
                       anchor="topright")  # fmt: skip
            item = pet.held_item_id
            name = (
                self.game.name_of(self.game.project.rpg_database.items[item], item) if item else ""
            )
            if "skills.item" in places:
                self._text(name or self.tr("creature.summary.none", "NONE"),
                           *places["skills.item"], ink, ink_shadow)  # fmt: skip
        else:
            mx, my = places["moves.list"]
            step = int(settings.get("move_step", 16))
            pp_right = places.get("moves.pp", (W - 8, my))[0]
            for row, ability_id in enumerate(self.game.pet_moves(pet)[:4]):
                y = my + row * step
                self._text(self.move_name(ability_id), mx, y, ink, ink_shadow)
                left = self.game.pet_uses_left(pet, ability_id)
                definition = self.game.project.gameplay_library.abilities.get(ability_id)
                top_uses = int(getattr(definition, "max_uses", 0) or 0)
                if left is not None:
                    label = self.tr("creature.summary.pp", "PP")
                    self._text(f"{label}{left:>3}/{top_uses:>2}", pp_right, y, ink, ink_shadow,
                               anchor="topright")  # fmt: skip

    def _dex_number(self, species_id):
        for entry in self.dex_entries():
            if entry.get("species") == species_id:
                return int(entry.get("number", 0))
        return 0

    def _draw_bag(self):
        pg, s = self.pg, self.surface
        background = self._bag_art("background")
        if background is not None:
            s.blit(background, (0, 0))
        else:
            s.fill((232, 208, 152))
        pockets = self.pockets()
        pocket = pockets[self.pocket % len(pockets)]
        picture = self._bag_picture(pocket.get("picture", ""))
        if picture is not None:
            s.blit(picture, picture.get_rect(center=self.BAG_CENTRE))
        self._text(pocket.get("name", ""), *self.BAG_POCKET_NAME, (248, 248, 248), (232, 64, 56),
                   anchor="midtop")  # fmt: skip
        arrow = self._bag_art("arrow")
        if arrow is not None and int(self.time * 3) % 2:
            s.blit(arrow, self.BAG_ARROWS[0])
            s.blit(pg.transform.flip(arrow, True, False), self.BAG_ARROWS[1])
        (lx, ly), (rx, ry) = self.BAG_ARROWS  # a click beside the pocket: the next pocket
        if self.phase == "bag":
            self._spot((lx - 4, ly - 4, 16, 20), key="left")
            self._spot((rx - 4, ry - 4, 16, 20), key="right")
        db = self.game.project.rpg_database
        items = self.pocket_items()
        left, top, width = self.BAG_LIST
        ink, ink_shadow = (72, 72, 72), (208, 208, 200)
        rows = [(i, self.game.name_of(db.items[i], i), f"x{n}") for i, n in items]
        rows.append(("", self.tr("creature.close_bag", "CLOSE BAG"), ""))
        for row, (_item, name, count) in enumerate(rows[self.bag_scroll : self.bag_scroll + 6]):
            index = self.bag_scroll + row
            y = top + 1 + row * 16
            if self.phase == "bag":
                self._spot((left, y - 2, width, 16), "list_cursor", index)
            self._text(name, left + 8, y, ink, ink_shadow)
            if count:
                self._text(count, left + width - 4, y, ink, ink_shadow, anchor="topright")
            if index == self.list_cursor:
                self.font_cursor(left, y)
        if self.list_cursor < len(items):
            item_id = items[self.list_cursor][0]
            item = db.items[item_id]
            icon = self._image("item_icon", item_id, None)
            if icon is not None:
                s.blit(icon, self.BAG_ICON)
            words = self.game.description_of(item) or self.game.name_of(item, item_id)
            for row, line in enumerate(self.wrap(words, 104)[:3]):
                y = self.BAG_DESCRIPTION[1] + row * 14
                self._text(line, self.BAG_DESCRIPTION[0], y, (248, 248, 248), (98, 98, 98))
        else:
            words = self.tr("creature.menu.close_bag_words", "CLOSE BAG")
            self._text(words, *self.BAG_DESCRIPTION, (248, 248, 248), (98, 98, 98))

    def _draw_bag_target(self):
        super()._draw_party()
        if self.note:
            self._message_window(self.note)

    def _draw_bag_teach(self):
        self._draw_bag()
        if self.note:
            self._message_window(self.note)
            return
        self._message_window(getattr(self, "teach_ask", ""))
        rows = [self.tr("creature.yes", "YES"), self.tr("creature.no", "NO")]
        self._list_window(rows, self.action_cursor, W - 2, H - 48)

    def _draw_bag_action(self):
        self._draw_bag()
        if self.note:
            self._message_window(self.note)
            return
        rows = [label for _id, label in self.bag_actions()]
        self._list_window(rows, self.action_cursor, W - 2, H - 2)

    def _draw_card(self):
        pg, s = self.pg, self.surface
        settings = self.menu.get("card") or {}
        places = {**CARD_PLACES, **{k: tuple(v) for k, v in
                                     (settings.get("places") or {}).items()}}  # fmt: skip
        background = self._menu_picture(settings.get("background"))
        if background is not None:
            s.blit(background, (0, 0))
        else:
            s.fill((96, 168, 128))
            self._window(pg.Rect(8, 8, W - 16, H - 16), (232, 240, 232), (72, 120, 96))
        picture = self._menu_picture(settings.get("picture"))
        if picture is not None:
            s.blit(picture, settings.get("picture_at", (160, 40)))
        for badge in settings.get("badges") or ():  # {"switch", "picture", "at"}: earned ones
            if self.game.save.event_context.get_switch(badge.get("switch", "")):
                image = self._menu_picture(badge.get("picture"))
                if image is not None:
                    s.blit(image, badge.get("at", (0, 0)))
        ink, ink_shadow = (
            tuple(settings.get("ink", (96, 96, 96))),
            tuple(settings.get("ink_shadow", (208, 208, 200))),
        )
        name = self.player_name()
        self._text(self.tr("creature.card.name", "NAME: ") + name, *places["name"], ink,
                   ink_shadow)  # fmt: skip
        number = self.tr("creature.card.id", "IDNo.") + self.game.expand_message(
            str(settings.get("id", "00000")), plain=True
        )
        self._text(number, *places["id"], ink, ink_shadow, anchor="midtop")
        money = self.game.save.rpg_state.currencies.get(settings.get("currency", "gold"), 0.0)
        symbol = str(self.settings.get("currency_symbol", ""))
        self._text(self.tr("creature.card.money", "MONEY"), *places["money"], ink, ink_shadow)
        self._text(f"{symbol}{money:.0f}", *places["money_value"], ink, ink_shadow,
                   anchor="topright")  # fmt: skip
        if settings.get("dex_switch") is None or self.game.save.event_context.get_switch(
            settings.get("dex_switch")
        ):
            seen = sum(1 for e in self.dex_entries() if self.dex_status(e["species"])[0])
            self._text(self.tr("creature.card.dex", "DEX"), *places["dex"], ink, ink_shadow)
            self._text(str(seen), *places["dex_value"], ink, ink_shadow, anchor="topright")
        seconds = int(self.game.world.counters.get(PLAY_SECONDS, 0.0))
        clock = f"{min(999, seconds // 3600)}:{seconds // 60 % 60:02d}"
        self._text(self.tr("creature.card.time", "TIME"), *places["time"], ink, ink_shadow)
        self._text(clock, *places["time_value"], ink, ink_shadow, anchor="topright")

    def _menu_picture(self, path):
        if not path:
            return None
        path = self.game.expand_message(str(path), plain=True)
        key = ("menu", path)
        if key not in self._images:
            image = None
            if self._path(path).is_file():
                image = self.pg.image.load(str(self._path(path))).convert_alpha()
            self._images[key] = image
        return self._images[key]

    def _draw_options(self):
        settings = self.menu.get("options") or {}
        background = self._menu_picture(settings.get("background"))
        if background is not None:
            self.surface.blit(background, (0, 0))
        else:
            self.surface.fill(tuple(settings.get("backdrop", (128, 152, 200))))
        letter, shadow = self._menu_colours()
        title = settings.get("title") or self.tr("creature.options.title", "OPTION")
        self._frame((16, 8, W - 32, 16))
        self._text(title, 24, 9, letter, shadow)
        rows = self.options()
        self._frame((16, 40, W - 32, 16 * (len(rows) + 1)))
        chosen = tuple(settings.get("chosen", (232, 96, 72)))  # the value in force
        other = tuple(settings.get("values_colour", letter))
        value_shadow = tuple(settings.get("values_shadow", shadow))
        for row, option in enumerate(rows):
            y = 41 + row * 16
            self._spot((16, y - 1, W - 32, 16), "option_cursor", row, key="right")  # next value
            self._text(str(option.get("label", "")), 24, y, letter, shadow)
            values = list(option.get("values") or ())
            value = self.option_value(option["id"])
            if values:
                x = 120
                for n, word in enumerate(values[:3] if len(values) <= 3 else (values[value],)):
                    index = n if len(values) <= 3 else value
                    colour = chosen if index == value else other
                    rect = self._text(str(word), x, y, colour, value_shadow)
                    x = rect.right + 8
            if row == self.option_cursor:
                self._cursor(16, y + 2)
        y = 41 + len(rows) * 16
        self._spot((16, y - 1, W - 32, 16), "option_cursor", len(rows))
        self._text(self.tr("creature.cancel", "CANCEL"), 24, y, letter, shadow)
        if self.option_cursor == len(rows):
            self._cursor(16, y + 2)

    def _draw_dex(self):
        settings = self.menu.get("dex") or {}
        s = self.surface
        background = self._menu_picture(settings.get("background"))
        if background is not None:
            s.blit(background, (0, 0))
        else:
            s.fill((200, 72, 64))
            self._window(self.pg.Rect(112, 8, 120, 144), (248, 248, 240), (96, 96, 96))
        rows = self.dex_rows()
        ink, ink_shadow = (72, 72, 72), (208, 208, 200)
        x, y = settings.get("list_at", (128, 12))
        ball = self._menu_picture(settings.get("ball"))
        fixed = settings.get("cursor_row")
        if fixed is not None:
            self.dex_scroll = self.list_cursor - int(fixed)
        for row in range(8):
            index = self.dex_scroll + row
            if not 0 <= index < len(rows):
                continue
            entry = rows[index]
            seen, owned = self.dex_status(entry["species"])
            ty = y + row * 16
            self._spot((x - 8, ty - 2, 112, 16), "list_cursor", index)
            self._text(f"No{int(entry['number']):03d}", x, ty, ink, ink_shadow)
            if owned and ball is not None:
                s.blit(ball, (x + 36, ty + 3))
            self._text(entry["name"] if seen else "-----", x + 46, ty, ink, ink_shadow)
            if index == self.list_cursor:
                self._cursor(x - 8, ty + 2)
        counts = [self.dex_status(e["species"]) for e in self.dex_entries()]
        white, grey = (248, 248, 248), (112, 112, 112)
        sx, sy = settings.get("counts_at", (8, 120))
        self._text(self.tr("creature.dex.seen", "SEEN"), sx, sy, white, grey)
        self._text(str(sum(1 for c in counts if c[0])), sx + 80, sy, white, grey,
                   anchor="topright")  # fmt: skip
        self._text(self.tr("creature.dex.owned", "OWN"), sx, sy + 16, white, grey)
        self._text(str(sum(1 for c in counts if c[1])), sx + 80, sy + 16, white, grey,
                   anchor="topright")  # fmt: skip
        if rows:
            picture = self._image("front", rows[self.list_cursor]["species"], None)
            if picture is not None and self.dex_status(rows[self.list_cursor]["species"])[0]:
                s.blit(picture, picture.get_rect(center=settings.get("picture_at", (56, 64))))

    def _draw_dex_entry(self):
        settings = self.menu.get("dex") or {}
        s = self.surface
        background = self._menu_picture(settings.get("entry_background"))
        if background is not None:
            s.blit(background, (0, 0))
        else:
            s.fill((232, 232, 216))
        rows = self.dex_rows()
        entry = rows[self.list_cursor]
        owned = self.dex_status(entry["species"])[1]
        ink, ink_shadow = (72, 72, 72), (208, 208, 200)
        picture = self._image("front", entry["species"], None)
        if picture is not None:
            s.blit(picture, picture.get_rect(center=settings.get("entry_picture_at", (48, 72))))
        x, y = settings.get("entry_text_at", (120, 24))
        self._text(f"No{int(entry['number']):03d}  {entry['name']}", x, y, ink, ink_shadow)
        if owned:
            self._text(str(entry.get("category", "")), x, y + 16, ink, ink_shadow)
            self._text(self.tr("creature.dex.height", "HT") + "  " + str(entry.get("height", "")),
                       x, y + 40, ink, ink_shadow)  # fmt: skip
            self._text(self.tr("creature.dex.weight", "WT") + "  " + str(entry.get("weight", "")),
                       x, y + 56, ink, ink_shadow)  # fmt: skip
            tx, ty = settings.get("entry_words_at", (16, 104))
            step = int(settings.get("entry_line_height", 14))
            for row, line in enumerate(str(entry.get("text", "")).split("\n")[:4]):
                self._text(line, tx, ty + row * step, ink, ink_shadow)

    def _draw_save(self):
        letter, shadow = self._menu_colours()
        x, y = (self.menu.get("save") or {}).get("info_at", (8, 8))
        place = str(getattr(self.game, "area_title_shown", "") or "")
        rows = [(place, "")] if place else []
        rows += [
            (self.tr("creature.save.player", "PLAYER"), self.player_name()),
            (self.tr("creature.save.badges", "BADGES"), str(self._badges())),
            (self.tr("creature.card.dex", "DEX"),
             str(sum(1 for e in self.dex_entries() if self.dex_status(e["species"])[1]))),
            (self.tr("creature.card.time", "TIME"), self._clock()),
        ]  # fmt: skip
        self._frame((x, y, 136, 16 * len(rows)))
        for row, (label, value) in enumerate(rows):
            if not value:  # where the player is: centred, in the place colour
                colour = tuple((self.menu.get("save") or {}).get("place_colour", (0, 160, 0)))
                self._text(label, x + 68, y + row * 16, colour, shadow, anchor="midtop")
                continue
            self._text(label, x, y + row * 16, letter, shadow)
            self._text(value, x + 136, y + row * 16, letter, shadow, anchor="topright")
        step = (self.save_step or ["ask"])[0]
        if step == "ask":
            self._message_window(
                self.tr("creature.save.confirm", "Would you like to save the game?")
            )
            words = [self.tr("creature.yes", "YES"), self.tr("creature.no", "NO")]
            self._list_window(words, self.action_cursor, 216, 112)
        elif step == "saving":
            self._message_window(
                self.tr("creature.save.saving", "SAVING… DON'T TURN OFF THE POWER.")
            )
        else:
            self._message_window(
                self.tr(
                    "creature.save.saved", "{player} saved the game.", player=self.player_name()
                )
            )

    def _badges(self):
        names = (self.menu.get("save") or {}).get("badge_switches") or ()
        return sum(1 for name in names if self.game.save.event_context.get_switch(name))

    def _clock(self):
        seconds = int(self.game.world.counters.get(PLAY_SECONDS, 0.0))
        return f"{min(999, seconds // 3600)}:{seconds // 60 % 60:02d}"


__all__ = ["CreatureMenuScreen", "PLAY_SECONDS"]
