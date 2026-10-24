"""What the quest board, the recruiting office and the gacha do to a save (U5).

The screens call these; they work on a ``GameSessionRuntime`` (``game``) and keep their own
state in ``game.world.systems`` (saved with the world): ``quest_board.<id>`` holds when each
quest was taken and handed in, ``gacha.<id>`` the pulls, pity and history. Play time is the
world counter ``play.seconds``.
"""

from __future__ import annotations

import random

from asteria.rpg.gacha import GachaRuntime, GachaState


class BoardError(ValueError):
    pass


def play_seconds(game):
    return float(game.world.counters.get("play.seconds", 0.0))


def _switch(game, name):
    return not name or bool(game.save.event_context.get_switch(name))


def _pay(game, currency, cost):
    wallet = game.save.rpg_state.currencies
    if wallet.get(currency, 0.0) < cost:
        raise BoardError(f"not enough {currency}")
    wallet[currency] = wallet.get(currency, 0.0) - cost


# -- the quest board -------------------------------------------------------------------------
CARD_STATES = ("available", "locked", "active", "ready", "done", "waiting", "failed", "full")


class QuestBoard:
    def __init__(self, game, board_id):
        self.game = game
        self.board = game.project.rpg_database.quest_boards[str(board_id)]

    @property
    def record(self):
        return self.game.world.systems.setdefault(
            f"quest_board.{self.board.board_id}", {"taken": {}, "handed": {}}
        )

    def quests(self):
        quests = self.game.project.rpg_database.quests
        return [quests[q] for q in self.board.quest_ids if q in quests]

    def active_count(self):
        log = self.game.quest_log
        return sum(1 for q in self.board.quest_ids if log.status(q) == "active")

    def expire(self):
        """Fail the board's taken quests whose time is up; returns their ids."""
        now, log, failed = play_seconds(self.game), self.game.quest_log, []
        for quest in self.quests():
            taken = self.record["taken"].get(quest.quest_id)
            if (
                quest.time_limit
                and taken is not None
                and log.status(quest.quest_id) == "active"
                and now - taken > quest.time_limit * 60
            ):
                self.game.fail_quest(quest.quest_id)
                failed.append(quest.quest_id)
        return failed

    def time_left(self, quest):
        """Seconds left to finish a taken quest with a time limit, else None."""
        taken = self.record["taken"].get(quest.quest_id)
        if not quest.time_limit or taken is None:
            return None
        return max(0.0, quest.time_limit * 60 - (play_seconds(self.game) - taken))

    def state(self, quest):
        log = self.game.quest_log
        status = log.status(quest.quest_id)
        if status == "active":
            return "ready" if log.is_ready(quest.quest_id) else "active"
        if status == "failed":
            return "failed" if not quest.repeatable else self._again(quest)
        if status == "completed":
            return self._again(quest) if quest.repeatable else "done"
        if not log.can_start(quest.quest_id) or not _switch(self.game, self.board.open_switch):
            return "locked"
        return self._room()

    def _room(self):
        full = self.board.max_active and self.active_count() >= self.board.max_active
        return "full" if full else "available"

    def _again(self, quest):
        if not _switch(self.game, self.board.open_switch):
            return "locked"
        handed = self.record["handed"].get(quest.quest_id)
        wait = self.board.refresh_minutes * 60
        if handed is not None and play_seconds(self.game) - handed < wait:
            return "waiting"
        return self._room()

    def cards(self):
        """``[(quest, state)]`` in the board's order (time-out quests failed first)."""
        self.expire()
        return [(q, self.state(q)) for q in self.quests()]

    def accept(self, quest_id):
        quest = self.game.project.rpg_database.quests[str(quest_id)]
        state = self.state(quest)
        if state != "available":
            raise BoardError(f"{quest_id} cannot be taken ({state})")
        if self.game.quest_log.status(quest.quest_id) != "inactive":  # taken again
            self.game.save.rpg_state.quests.pop(quest.quest_id, None)
        self.game.start_quest(quest.quest_id)
        self.record["taken"][quest.quest_id] = play_seconds(self.game)
        return quest

    def report(self, quest_id):
        quest = self.game.project.rpg_database.quests[str(quest_id)]
        if self.state(quest) != "ready":
            raise BoardError(f"{quest_id} is not finished")
        self.game.complete_quest(quest.quest_id)
        self.record["handed"][quest.quest_id] = play_seconds(self.game)
        self.record["taken"].pop(quest.quest_id, None)
        return quest


# -- the recruiting office -------------------------------------------------------------------
RECRUIT_STATES = ("available", "hired", "locked", "full", "poor")


class RecruitOffice:
    def __init__(self, game, office_id):
        self.game = game
        self.office = game.project.rpg_database.recruit_offices[str(office_id)]

    def party(self):
        return tuple(self.game.save.rpg_state.party_actor_ids)

    def state(self, candidate):
        if candidate.actor_id in self.party():
            return "hired"
        if not _switch(self.game, candidate.require_switch):
            return "locked"
        if self.office.party_limit and len(self.party()) >= self.office.party_limit:
            return "full"
        wallet = self.game.save.rpg_state.currencies
        if wallet.get(candidate.currency, 0.0) < candidate.cost:
            return "poor"
        return "available"

    def rows(self):
        db = self.game.project.rpg_database
        return [
            (c, db.actors[c.actor_id], self.state(c))
            for c in self.office.candidates
            if c.actor_id in db.actors
        ]

    def hire(self, actor_id, rng=None):
        """Pay, bring the character into the party and give the rolled level; returns it."""
        candidate = self.office.candidate(str(actor_id))
        if candidate is None:
            raise BoardError(f"{actor_id} is not a candidate here")
        state = self.state(candidate)
        if state != "available":
            raise BoardError(f"{actor_id} cannot be hired ({state})")
        _pay(self.game, candidate.currency, candidate.cost)
        self.game.join_party(candidate.actor_id)
        level = candidate.level_min
        if candidate.level_max > candidate.level_min:
            rng = rng or random.Random(f"{self.office.office_id}:{candidate.actor_id}")
            level = rng.randint(candidate.level_min, candidate.level_max)
        progress = self.game.ensure_actor_progression(candidate.actor_id)
        if level > progress.level:
            per = self.office.experience_per_level
            self.game.grant_actor_experience(
                candidate.actor_id, (level - progress.level) * per, level_threshold=per
            )
        return self.game.ensure_actor_progression(candidate.actor_id).level

    def dismiss(self, actor_id):
        """Send a hired candidate away (a refund of part of the price); returns the refund."""
        candidate = self.office.candidate(str(actor_id))
        if not self.office.can_dismiss or candidate is None:
            raise BoardError(f"{actor_id} cannot be dismissed here")
        if candidate.actor_id not in self.party():
            raise BoardError(f"{actor_id} is not in the party")
        if len(self.game.save.rpg_state.party_active_actor_ids) <= 1 and (
            candidate.actor_id in self.game.save.rpg_state.party_active_actor_ids
        ):
            raise BoardError("the last member cannot leave")
        self.game.leave_party(candidate.actor_id)
        refund = candidate.cost * self.office.dismiss_refund
        wallet = self.game.save.rpg_state.currencies
        wallet[candidate.currency] = wallet.get(candidate.currency, 0.0) + refund
        return refund


# -- gacha -----------------------------------------------------------------------------------
class Gacha:
    def __init__(self, game, banner_id):
        self.game = game
        self.banner = game.project.rpg_database.gacha_banners[str(banner_id)]

    @property
    def key(self):
        return f"gacha.{self.banner.banner_id}"

    def state(self):
        return GachaState.from_data(self.game.world.systems.get(self.key))

    def is_open(self):
        return _switch(self.game, self.banner.open_switch)

    def cost(self, multi):
        return self.banner.multi_cost if multi else self.banner.single_cost

    def can_pay(self, multi):
        wallet = self.game.save.rpg_state.currencies
        return wallet.get(self.banner.currency, 0.0) >= self.cost(multi)

    def pull(self, multi=False, rng=None):
        """Pay and draw once (or ``multi_count`` times); each prize is given. Returns
        ``[(pull, duplicate)]``: ``duplicate`` when a character already owned became its
        ``duplicate_item``."""
        if not self.is_open():
            raise BoardError(f"{self.banner.banner_id} is closed")
        _pay(self.game, self.banner.currency, self.cost(multi))
        state = self.state()
        rng = rng or random.Random(f"{self.banner.banner_id}:{state.total}")
        count = self.banner.multi_count if multi else 1
        pulls = GachaRuntime(self.banner).pull(rng, state, count)
        self.game.world.systems[self.key] = state.to_data()
        return [(pull, self._give(pull.prize)) for pull in pulls]

    def _give(self, prize):
        game = self.game
        rpg = game.save.rpg_state
        owned = (prize.kind == "actor" and prize.target_id in rpg.party_actor_ids) or (
            prize.kind == "pet"
            and prize.duplicate_item
            and any(p.species_id == prize.target_id for p in game.pets())
        )
        if owned and prize.duplicate_item:
            rpg.inventory.add(prize.duplicate_item, max(1, prize.duplicate_amount))
            return True
        if prize.kind == "item":
            rpg.inventory.add(prize.target_id, prize.amount)
        elif prize.kind == "equipment":
            game.gain_equipment(prize.target_id, prize.amount)
        elif prize.kind == "actor":
            if not owned:
                game.join_party(prize.target_id)
        else:
            for _ in range(prize.amount):
                game.add_pet(prize.target_id)
        return False
