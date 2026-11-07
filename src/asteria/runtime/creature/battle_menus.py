"""The battle's menus: fight, bag, party and run, and the move list."""

from __future__ import annotations

from asteria.runtime.creature.battle_style import _owned_item_ids
from asteria.runtime.session.ability_use import cured_states


class BattleMenusMixin:
    """The battle's menus: fight, bag, party and run, and the move list."""

    # -- menus -----------------------------------------------------------------------------------
    def _pressed(self, name):
        return self.rt.input.just_pressed(name)

    def _menu_input(self):
        if self.phase == "command" and self.auto_choices:  # the game chooses, after a moment
            if self._auto_at is None:
                self._auto_at = self.time
            elif self.time - self._auto_at > float(self.encounter.get("auto_delay", 0.8)):
                self._auto_at = None
                self.choose(self.auto_choices.pop(0))
            return
        if self.phase == "command":
            self._grid_input(4)
            if self._pressed("confirm"):
                [self._open_fight, self._open_bag, self._open_party, self._run][self.cursor]()
        elif self.phase == "fight":
            moves = self._moves()
            self._grid_input(len(moves), attr="list_cursor")
            if self._pressed("cancel"):
                self.phase = "command"
            elif self._pressed("confirm") and self.game.out_of_uses_move(self._stage("heroes")):
                actor = self._stage("heroes")
                self.phase = "story"
                self.say(
                    self.tr(
                        "creature.no_moves_left",
                        "{name} has no moves left!",
                        name=self.name(actor),
                    )
                )
                self.choose(("out_of_uses",))
            elif self._pressed("confirm") and moves:
                move = moves[min(self.list_cursor, len(moves) - 1)]
                record = self.game.unit_record(self._stage("heroes"))
                if record is not None and self.game.pet_uses_left(record, move) == 0:
                    self.phase = "story"
                    self.say(self.tr("creature.no_pp", "There's no PP left for this move!"))
                    self.act("command")
                    return
                self.choose(("move", move))
        elif self.phase == "bag":
            items = self._bag_items()
            if self._pressed("cancel"):
                self.phase = "command"
                return
            if self._pressed("move_left") or self._pressed("move_right"):
                self.pocket, self.list_cursor = 1 - self.pocket, 0
                return
            rows = len(items) + 1  # the last row closes the bag
            if self._pressed("move_up"):
                self.list_cursor = (self.list_cursor - 1) % rows
            if self._pressed("move_down"):
                self.list_cursor = (self.list_cursor + 1) % rows
            if self._pressed("confirm") and self.list_cursor >= len(items):
                self.phase = "command"
                return
            if self._pressed("confirm") and items:
                item_id = items[min(self.list_cursor, len(items) - 1)][0]
                if self.pocket == 1:
                    if self.trainer or "no_capture" in self.tags:
                        self.phase = "story"
                        self.say(
                            self.tr(
                                "creature.no_stealing",
                                "The trainer blocked the ball! Don't be a thief!",
                            )
                        )
                        self.act("command")
                        return
                    self.choose(("ball", item_id))
                else:
                    self.choose(("item", item_id))
        elif self.phase == "yesno":
            self._yes_no_input()
        elif self.phase == "party":
            slots = self._party()
            count = len(slots) + (0 if self.forced_switch else 1)  # + cancel
            if self._pressed("move_up") or self._pressed("move_left"):
                self.list_cursor = (self.list_cursor - 1) % count
            if self._pressed("move_down") or self._pressed("move_right"):
                self.list_cursor = (self.list_cursor + 1) % count
            if self._pressed("cancel") and not self.forced_switch:
                self.phase = "story" if self.free_switch else "command"
                return
            if not self._pressed("confirm"):
                return
            if self.list_cursor >= len(slots):
                self.phase = "story" if self.free_switch else "command"
                return
            pet = slots[self.list_cursor]
            member_id = self.game.pet_member_id(pet)
            if member_id == self._stage("heroes"):
                self.party_note = self.tr(
                    "creature.already_out",
                    "{name} is already in battle!",
                    name=self.name(member_id),
                )
                return
            if member_id not in self.game.bench_ids("heroes"):
                self.party_note = self.tr("creature.no_energy", "There's no will to battle!")
                return
            if self.forced_switch:  # after a faint: in at once, no turn
                self.phase = "story"
                self._switch_in(None, member_id)
                self.act("command")
                return
            if self.free_switch:  # before a trainer's next creature: in before it, no turn
                self.phase = "story"
                waiting, self.steps = self.steps, []
                self._switch_in(self._stage("heroes"), member_id)
                self.steps += waiting
                return
            self.choose(("switch", member_id))

    def _yes_no_input(self):
        prompt = self.prompt or {}
        if self._pressed("move_up") or self._pressed("move_down"):
            prompt["cursor"] = 1 - prompt.get("cursor", 0)
        answer = None
        if self._pressed("cancel"):
            answer = False
        elif self._pressed("confirm"):
            answer = prompt.get("cursor", 0) == 0
        if answer is None:
            return
        self.prompt = None
        game = self.game
        if prompt.get("kind") == "change":
            if answer:
                self.phase, self.list_cursor = "party", 0
                self.forced_switch, self.free_switch, self.party_note = False, True, ""
            else:
                self.phase = "story"
            return
        if prompt.get("kind") == "next":
            if answer:
                self.phase, self.list_cursor = "party", 0
                self.forced_switch, self.free_switch, self.party_note = True, False, ""
                return
            self.phase = "story"
            runner = (game.bench_ids("heroes") or (None,))[0]
            reason = game.escape_unavailable()
            result = None if reason else game.attempt_escape(runner)
            game.drain_battle_log()
            if result is not None and result.succeeded:
                self.say(self.tr("creature.got_away", "Got away safely!"))
                self.act("end")
                return
            self.say(reason or self.tr("creature.cant_escape", "Can't escape!"))
            self.act("party", forced=True)

    def _grid_input(self, count, attr="cursor"):
        """A 2 x 2 grid: left / right move along a row, up / down between the rows."""
        if count <= 0:
            return
        value = getattr(self, attr)
        if self._pressed("move_right") and value % 2 == 0 and value + 1 < count:
            value += 1
        elif self._pressed("move_left") and value % 2 == 1:
            value -= 1
        elif self._pressed("move_down") and value + 2 < count:
            value += 2
        elif self._pressed("move_up") and value >= 2:
            value -= 2
        setattr(self, attr, value)

    def _open_fight(self):
        self.phase, self.list_cursor = "fight", 0

    def _open_bag(self):
        self.phase, self.list_cursor, self.pocket = "bag", 0, 0

    def _open_party(self):
        self.phase, self.list_cursor, self.forced_switch = "party", 0, False
        self.free_switch = False
        self.party_note = ""

    def _run(self):
        self.choose(("run",))

    def _moves(self):
        actor = self._stage("heroes")
        if actor is None:
            return ()
        return tuple(self.game.battle.member(actor).ability_ids)[:4]

    def _bag_items(self):
        """``[(item_id, count)]`` of the open pocket: 0 = items usable in battle, 1 = capture
        items (any capture rule's)."""

        game = self.game
        db = game.project.rpg_database
        inventory = game.save.rpg_state.inventory
        balls = set()
        for rule in db.capture_rules.values():
            balls |= set(rule.capture_items())
        result = []
        for item_id in _owned_item_ids(inventory, db.items):
            count = inventory.count(item_id)
            if count <= 0:
                continue
            item = db.items[item_id]
            if self.pocket == 1 and item_id in balls:
                result.append((item_id, count))
            elif (
                self.pocket == 0
                and item_id not in balls
                and (item.battle_ability or item.use_effects or cured_states(item))
            ):
                result.append((item_id, count))
        return result
