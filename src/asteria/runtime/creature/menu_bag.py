"""The start menu's bag: pockets, using, giving and teaching items."""

from __future__ import annotations

from asteria.runtime.creature.battle_style import _owned_item_ids
from asteria.runtime.creature.menu_style import _me, taught_ability
from asteria.runtime.session.ability_use import cured_states


class CreatureMenuBagMixin:
    """The start menu's bag: pockets, using, giving and teaching items."""

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
            for item_id in _owned_item_ids(inventory, db.items)
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
        program = dict((self.menu.get("bag") or {}).get("use_programs") or {}).get(item_id)
        if choice == "use" and program:  # the field does what it does (REPEL, a bike...)
            self.done = True
            self.game.events.start(str(program))
            return
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
