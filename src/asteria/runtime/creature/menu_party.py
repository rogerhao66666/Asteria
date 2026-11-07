"""The start menu's party list and a creature's summary."""

from __future__ import annotations


class CreatureMenuPartyMixin:
    """The start menu's party list and a creature's summary."""

    # -- the party --------------------------------------------------------------------------
    def field_moves(self):
        """``party.field_moves``: rows the chosen creature gets for moves it knows and switches
        that are on: ``{move, label, switch, program}``, or ``screen: "fly"`` for the map."""
        pets = self._party()
        if self.list_cursor >= len(pets):
            return ()
        known = self.game.pet_moves(pets[self.list_cursor])
        rows = []
        context = self.game.save.event_context
        for row in (self.menu.get("party") or {}).get("field_moves") or ():
            needs = row.get("switch")
            if row.get("move") in known and (not needs or context.get_switch(needs)):
                rows.append(row)
        return rows

    def actions(self):
        moves = [
            (f"field:{n}", str(row.get("label", ""))) for n, row in enumerate(self.field_moves())
        ]
        return (
            ("summary", self.tr("creature.menu.summary", "SUMMARY")),
            *moves,
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
        if choice.startswith("field:"):
            row = self.field_moves()[int(choice.split(":", 1)[1])]
            if row.get("screen") == "fly":
                self.fly_mode = True
                self.open("region")
                self.region_back = "party"
            elif row.get("program"):
                self.done = True
                self.game.events.start(str(row["program"]))
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
