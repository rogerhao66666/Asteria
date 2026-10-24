"""The quest board, recruiting office and gacha screens (U5; ``runtime/boards_play.py``).

``OPEN_QUEST_BOARD`` / ``OPEN_RECRUIT`` / ``OPEN_GACHA`` name the record; the runtime opens its
screen once the event is done. Each screen draws through its menu layout (the record's
``layout``, else ``<screen>.<id>`` when the project has one, else the shared one), so an author
can move, reskin or hide every part.

* **Quest board** - the board's quests as cards (a grid, or one row): picture, rank, category,
  name, reward and a stamp of where the quest stands (taken, ready, done, waiting, locked,
  failed). Enter takes a quest or hands a finished one in; Space / F turns the card over to
  its objectives (with progress), reward and time limit.
* **Recruiting office** - the candidates with portrait, class, price and level range; the
  panel shows the character's stats and note. Enter hires (asked once more), X sends a hired
  candidate away when the office allows it.
* **Gacha** - the banner, the price of one and of a multi-pull, the rates of every rarity (on
  the banner page itself, and the full table on R), the pity count and the last pulls (H).
  A pull shows the chest of the best rarity drawn: it appears, shakes and opens in that
  rarity's colour, then the prizes show in a grid (new / turned into their duplicate item).
"""

from __future__ import annotations

import math

from asteria.rpg.data_text import key
from asteria.rpg.data_text import words as id_words

from .bag_screen import BAD, GOOD, MUTED, TITLE
from .boards_play import Gacha, QuestBoard, RecruitOffice, play_seconds
from .crafting_screen import wrap

TEXT = (236, 238, 245)
GREY = (130, 134, 150)
GOLD = (255, 214, 120)


def actor_portrait(game, actor_id, own=""):
    """A character's picture: ``own``, else its battle look's portrait, else ``""``."""
    if own:
        return own
    library = game.project.battle_presentation_library
    try:
        visuals = library.get("combatant_visuals", actor_id)
    except (KeyError, ValueError):
        return ""
    assets = getattr(visuals, "assets", None)
    return (assets.portrait_asset_id or assets.small_portrait_asset_id or "") if assets else ""


def _clock(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


class ServiceScreen:
    """Made when opened; each frame ``handle(dt, events)`` then ``draw()``; ``closed`` ends it."""

    SCREEN = ""
    ID = ""

    def __init__(self, runtime, record, back="field"):
        self.rt = runtime
        self.record = record
        self.back = back
        self.closed = False
        self.index = 0
        self.message, self.message_left = "", 0.0

    @property
    def game(self):
        return self.rt.game

    @property
    def record_id(self):
        return getattr(self.record, self.ID)

    def say(self, text, seconds=2.5):
        self.message, self.message_left = str(text), seconds

    def layout_id(self):
        if self.record.layout:
            return self.record.layout
        own = f"{self.SCREEN}.{self.record_id}"
        return own if self.rt.menu_layout(own) is not None else self.SCREEN

    def money(self, currency, amount=None):
        """``"1,200 Gold"``: ``amount`` (the wallet's when None) and the currency's name."""
        if amount is None:
            amount = self.game.save.rpg_state.currencies.get(currency, 0.0)
        return f"{amount:,.0f} {self.currency_word(currency)}"

    def currency_word(self, currency):
        """A currency's translated name, else its id in words (``star_stones``: Star Stones)."""
        return self.game.currency_names().get(currency) or id_words(currency)

    def item_name(self, item_id):
        db = self.game.project.rpg_database
        record = db.items.get(item_id) or db.equipment.get(item_id)
        return self.game.name_of(record, item_id) if record is not None else item_id

    def reward_words(self, reward):
        tr = self.game.tr
        parts = [f"{v:,.0f} {self.currency_word(k)}" for k, v in reward.currencies.items() if v]
        if reward.experience:
            exp = sum(reward.experience.values())
            parts.append(tr("board.experience", "{amount} EXP", amount=f"{exp:,.0f}"))
        for entry in reward.loot:
            count = f" x{entry.maximum}" if entry.maximum > 1 else ""
            parts.append(f"{self.item_name(entry.item_id)}{count}")
        return ", ".join(parts) or tr("board.no_reward", "no reward")

    def frame(self, fields, title):
        rt = self.rt
        canvas = self.canvas = rt.menu_canvas(self.layout_id(), fields)
        rt._draw_backdrop(canvas=canvas)
        if self.record.music:
            rt._music(self.record.music)
        canvas.panel("frame", (24, 20, rt.width - 48, rt.height - 40), fill=(11, 15, 25, 236))
        canvas.text("title", title, 48, 32, size=32, color=canvas.tone("title", TITLE))
        return canvas

    def footer(self, canvas, hint):
        rt = self.rt
        canvas.text("hint", hint, 48, rt.height - 52, size=18, color=canvas.tone("muted", MUTED))
        if self.message_left > 0:
            canvas.text(
                "message", self.message, rt.width / 2, rt.height - 84, size=20,
                color=(175, 235, 255), anchor="midtop",
            )  # fmt: skip
        canvas.finish()

    def tick(self, dt):
        self.message_left = max(0.0, self.message_left - dt)

    def lines(self, x, y, w, bottom, lines):
        """Draw ``[(words, colour, size)]`` wrapped inside ``w``; returns where it stopped."""
        rt = self.rt
        for words, color, size in lines:
            for line in wrap(rt, words, size, w) if words else [""]:
                if y > bottom - size:
                    return y
                if line:
                    rt.text(line, x, y, size=size, color=color)
                y += size + 6 if line else size
        return y

    def sound(self, kind):
        theme = self.rt.menu_theme()
        name = theme.sound(kind) if theme is not None else ""
        if kind == "buy":
            name = name or self.rt.manifest.get("dialogue_confirm_sfx")
        self.rt._sound(name)


# -- the quest board -------------------------------------------------------------------------
CARDS = (48, 124, 760, 500)
CARD_DETAIL = (824, 124, 408, 500)
STAMP_COLORS = {
    "available": (120, 200, 255),
    "active": (240, 200, 110),
    "ready": (130, 230, 150),
    "done": (150, 160, 180),
    "waiting": (170, 170, 200),
    "locked": (120, 124, 140),
    "failed": (235, 120, 120),
    "full": (200, 160, 120),
}


class QuestBoardScreen(ServiceScreen):
    SCREEN, ID = "quest_board", "board_id"

    def __init__(self, runtime, board_id, back="field"):
        self.board = QuestBoard(runtime.game, board_id)
        super().__init__(runtime, self.board.board, back)
        self.flipped = False
        self._cards = self.board.cards()

    def cards(self):
        return self._cards

    def selected(self):
        cards = self.cards()
        return cards[min(self.index, len(cards) - 1)] if cards else None

    def columns(self):
        if self.record.card_style == "row":
            return max(1, len(self.cards()))
        return max(1, int(self.canvas_number("cards", "columns", 3)))

    def canvas_number(self, element_id, name, default):
        canvas = getattr(self, "canvas", None)
        return canvas.number(element_id, name, default) if canvas is not None else default

    def refresh(self):
        self._cards = self.board.cards()

    def handle(self, dt=0.0, events=()):
        rt, pg = self.rt, self.rt.pg
        inp = rt.input
        self.tick(dt)
        if int(play_seconds(self.game)) != getattr(self, "_second", None):
            self._second = int(play_seconds(self.game))
            self.refresh()  # deadlines and refresh times move on
        keys = {e.key for e in events if e.type == pg.KEYDOWN}
        if inp.just_pressed("cancel"):
            if self.flipped:
                self.flipped = False
            else:
                self.closed = True
            return
        cards = self.cards()
        if not cards:
            return
        columns = self.columns()
        step = 0
        for action, move in (("move_left", -1), ("move_right", 1)):
            if inp.just_pressed(action):
                step += move
        for action, move in (("move_up", -columns), ("move_down", columns)):
            if inp.just_pressed(action) and columns < len(cards):
                step += move
        if step:
            self.index = max(0, min(len(cards) - 1, self.index + step))
        if keys & {pg.K_SPACE, pg.K_f}:
            self.flipped = not self.flipped
        elif inp.just_pressed("confirm"):
            self.confirm()

    def confirm(self):
        tr = self.game.tr
        chosen = self.selected()
        if chosen is None:
            return None
        quest, state = chosen
        name = self.game.name_of(quest)
        if state == "available":
            self.board.accept(quest.quest_id)
            self.say(tr("board.accepted", "Accepted: {name}", name=name))
            self.sound("buy")
        elif state == "ready":
            self.board.report(quest.quest_id)
            self.say(tr("board.reported", "Handed in: {name}", name=name))
            self.sound("buy")
        else:
            self.say(self.state_reason(quest, state))
            self.sound("fail")
        self.refresh()
        return state

    def category(self, quest):
        """A card's category in the player's language (``data.quest_category.<c>.name``)."""
        return self.game.tr(key("quest_category", quest.category), quest.category)

    def state_reason(self, quest, state):
        tr = self.game.tr
        if state == "active":
            return tr("board.not_ready", "Finish the objectives first.")
        if state == "waiting":
            return tr("board.waiting_long", "Back on the board soon.")
        if state == "full":
            limit = self.record.max_active
            return tr("board.full", "You can take {count} of these at once.", count=limit)
        if state == "done":
            return tr("board.done_long", "Already done.")
        if state == "failed":
            return tr("board.failed_long", "This quest failed.")
        return tr("board.locked_long", "Not open to you yet.")

    def stamp(self, quest, state):
        tr = self.game.tr
        if state == "waiting":
            handed = self.board.record["handed"].get(quest.quest_id, 0.0)
            left = self.record.refresh_minutes * 60 - (play_seconds(self.game) - handed)
            return tr("board.state.waiting", "Back in {time}", time=_clock(left))
        words = {
            "available": tr("board.state.available", "Open"),
            "active": tr("board.state.active", "Taken"),
            "ready": tr("board.state.ready", "Report!"),
            "done": tr("board.state.done", "Done"),
            "locked": tr("board.state.locked", "Locked"),
            "failed": tr("board.state.failed", "Failed"),
            "full": tr("board.state.full", "Full"),
        }
        return words.get(state, state)

    def draw(self):
        rt, game = self.rt, self.game
        tr = game.tr
        active = self.board.active_count()
        fields = {
            "board.name": game.name_of(self.record),
            "board.active": active,
            "board.limit": self.record.max_active,
            "wallet.gold": game.save.rpg_state.currencies.get("gold", 0),
        }
        canvas = self.frame(fields, fields["board.name"])
        limit = self.record.max_active
        count = (
            tr("board.count_limit", "Taken {count} / {limit}", count=active, limit=limit)
            if limit
            else tr("board.count", "Taken {count}", count=active)
        )
        canvas.text("count", count, rt.width - 48, 40, size=20, color=TEXT, anchor="topright")
        about = game.description_of(self.record)
        if about:
            canvas.text("description", about, 48, 80, size=18, color=canvas.tone("muted", MUTED))
        self.draw_cards(canvas)
        self.draw_detail(canvas)
        hint = tr(
            "board.hint",
            "Arrows: card   Enter: take / hand in   Space / F: turn over   Esc: back",
        )
        self.footer(canvas, hint)

    def draw_cards(self, canvas):
        tr = self.game.tr
        default = CARDS
        if not canvas.shown("cards"):
            canvas.rect("cards", default)
            return
        x, y, w, h = canvas.rect("cards", default)
        cards = self.cards()
        if not cards:
            words = tr("board.empty", "No quests on this board.")
            canvas.text("empty", words, x + 8, y + 8, size=20, color=canvas.tone("muted", MUTED))
            return
        gap = canvas.number("cards", "gap", 16)
        if self.record.card_style == "row":
            cw = canvas.number("cards", "cell", 220)
            ch = h
            visible = max(1, (w + gap) // (cw + gap))
            first = max(0, min(self.index - visible + 1, len(cards) - visible))
            places = [
                (first + n, (x + n * (cw + gap), y, cw, ch))
                for n in range(min(visible, len(cards) - first))
            ]
        else:
            columns = self.columns()
            cw = canvas.number("cards", "cell", 0) or (w - gap * (columns - 1)) // columns
            ch = canvas.row_height("cards", 236)
            rows = max(1, (h + gap) // (ch + gap))
            row = self.index // columns
            first_row = max(0, row - rows + 1)
            places = []
            for k in range(first_row * columns, min(len(cards), (first_row + rows) * columns)):
                r, c = divmod(k, columns)
                places.append((k, (x + c * (cw + gap), y + (r - first_row) * (ch + gap), cw, ch)))
        for k, rect in places:
            self.draw_card(canvas, cards[k], rect, k == self.index)

    def draw_card(self, canvas, card, rect, chosen):
        rt, game = self.rt, self.game
        quest, state = card
        x, y, w, h = rect
        pg = rt.pg
        dim = state in ("done", "locked", "failed", "waiting")
        fill = (44, 38, 30) if not dim else (30, 30, 34)
        surface = pg.Surface((w, h), pg.SRCALPHA)
        surface.fill((*fill, 240))
        rt.screen.blit(surface, (x, y))
        edge = STAMP_COLORS.get(state, TEXT)
        if chosen:
            canvas.selection(
                "cards", (x - 3, y - 3, w + 6, h + 6),
                lambda: pg.draw.rect(rt.screen, GOLD, (x - 3, y - 3, w + 6, h + 6), 3,
                                     border_radius=10),
            )  # fmt: skip
        pg.draw.rect(rt.screen, edge, rect, 2, border_radius=8)
        picture = quest.card_image or quest.icon_id
        top = y + 12
        if picture:
            size = min(w - 24, canvas.icon_size("cards", 72))
            rt._draw_icon(picture, x + (w - size) // 2, top, size)
            top += size + 8
        if quest.rank:
            badge = (x + w - 46, y + 8, 38, 26)
            pg.draw.rect(rt.screen, (90, 60, 30), badge, border_radius=5)
            rt.text(quest.rank, badge[0] + 19, badge[1] + 3, size=17, color=GOLD, anchor="midtop")
        if quest.category:
            rt.text(self.category(quest), x + 10, y + 10,
                    size=14, color=MUTED)  # fmt: skip
        name_color = GREY if dim else TEXT
        for line in wrap(rt, game.name_of(quest), 19, w - 20)[:2]:
            rt.text(line, x + w / 2, top, size=19, color=name_color, anchor="midtop")
            top += 24
        if self.flipped and chosen:  # the back: objectives, progress, reward, description
            self.draw_card_back(quest, state, (x, top, w, y + h - top))
            return
        reward = self.reward_words(quest.reward)
        for line in wrap(rt, reward, 14, w - 20)[:2]:
            rt.text(line, x + w / 2, top + 2, size=14, color=GOLD if not dim else GREY,
                    anchor="midtop")  # fmt: skip
            top += 18
        words = self.stamp(quest, state)
        rt.text(words, x + w / 2, y + h - 30, size=18, color=edge, anchor="midtop")
        left = self.board.time_left(quest) if state in ("active", "ready") else None
        if left is not None:
            rt.text(f"⏱ {_clock(left)}", x + w - 10, y + h - 54, size=14,
                    color=BAD if left < 60 else MUTED, anchor="topright")  # fmt: skip

    def draw_card_back(self, quest, state, rect):
        rt, game = self.rt, self.game
        x, top, w, h = rect
        lines = []
        for words, value, required in self.objective_rows(quest, state):
            done = value is not None and value >= required
            count = f"{value}/{required}" if value is not None else f"x{required}"
            lines.append((f"{words}  {count}", GOOD if done else TEXT))
        left = self.board.time_left(quest)
        if left is not None:
            lines.append((game.tr("board.time_left", "Time left {time}", time=_clock(left)), BAD))
        lines.append((self.reward_words(quest.reward), GOLD))
        about = game.description_of(quest)
        if about:
            lines.append((about, MUTED))
        for words, color in lines:
            for line in wrap(rt, words, 14, w - 20)[: 4 if color == MUTED else 2]:
                if top > rect[1] + h - 18:
                    return
                rt.text(line, x + w / 2, top, size=14, color=color, anchor="midtop")
                top += 18

    def objective_rows(self, quest, state):
        """``[(words, done so far or None when not taken, required)]``."""
        from .game_menus import objective_words

        game = self.game
        log = game.quest_log
        taken = state in ("active", "ready")
        rows = []
        for objective in quest.objectives:
            words = game.description_of(objective) or objective_words(game, objective)
            required = 1 if objective.kind == "switch" else objective.required
            value = None
            if taken:
                value = min(required, log.objective_value(quest.quest_id, objective))
            rows.append((words, value, required))
        return rows

    def detail_lines(self):
        game = self.game
        tr = game.tr
        chosen = self.selected()
        if chosen is None:
            return []
        quest, state = chosen
        lines = [(game.name_of(quest), TITLE, 24)]
        tags = " · ".join(
            x
            for x in (
                quest.rank,
                self.category(quest) if quest.category else "",
                tr("board.repeatable", "repeatable") if quest.repeatable else "",
            )
            if x
        )
        if tags:
            lines.append((tags, MUTED, 16))
        about = game.description_of(quest)
        if about:
            lines.append((about, TEXT, 17))
        lines.append(("", TEXT, 6))
        lines.append((tr("board.objectives", "Objectives"), TITLE, 18))
        for words, value, required in self.objective_rows(quest, state):
            if value is not None:
                color = GOOD if value >= required else TEXT
                lines.append((f"{words}  {value}/{required}", color, 17))
            else:
                lines.append((f"{words}  x{required}" if required > 1 else words, TEXT, 17))
        lines.append(("", TEXT, 6))
        lines.append((tr("board.reward", "Reward"), TITLE, 18))
        lines.append((self.reward_words(quest.reward), GOLD, 17))
        if quest.time_limit:
            lines.append(("", TEXT, 6))
            left = self.board.time_left(quest)
            if left is not None:
                words = tr("board.time_left", "Time left {time}", time=_clock(left))
            else:
                words = tr("board.time_limit", "Time limit {minutes} min",
                           minutes=f"{quest.time_limit:g}")  # fmt: skip
            lines.append((words, BAD if left is not None and left < 60 else TEXT, 17))
        if quest.prerequisites and state == "locked":
            db = game.project.rpg_database
            needs = ", ".join(game.name_of(db.quests[q]) for q in quest.prerequisites)
            lines.append((tr("board.needs", "After: {quests}", quests=needs), BAD, 16))
        lines.append(("", TEXT, 6))
        lines.append((self.stamp(quest, state), STAMP_COLORS.get(state, TEXT), 20))
        return lines

    def draw_detail(self, canvas):
        if not canvas.shown("detail"):
            canvas.rect("detail", CARD_DETAIL)
            return
        x, y, w, h = canvas.panel("detail", CARD_DETAIL, fill=(16, 20, 32, 240))
        chosen = self.selected()
        top = y + 14
        if chosen is not None and (chosen[0].card_image or chosen[0].icon_id):
            size = canvas.icon_size("detail", 64)
            self.rt._draw_icon(chosen[0].card_image or chosen[0].icon_id, x + w - size - 16,
                               y + 14, size)  # fmt: skip
        self.lines(x + 16, top, w - 32 - 72, y + h - 8, self.detail_lines()[:2])
        self.lines(x + 16, top + 84, w - 32, y + h - 8, self.detail_lines()[2:])


# -- the recruiting office -------------------------------------------------------------------
CANDIDATES = (48, 124, 560, 500)
PROFILE = (624, 124, 608, 500)


class RecruitScreen(ServiceScreen):
    SCREEN, ID = "recruit", "office_id"

    def __init__(self, runtime, office_id, back="field"):
        self.office = RecruitOffice(runtime.game, office_id)
        super().__init__(runtime, self.office.office, back)
        self.asking = False  # Enter once more hires

    def rows(self):
        return self.office.rows()

    def selected(self):
        rows = self.rows()
        return rows[min(self.index, len(rows) - 1)] if rows else None

    def handle(self, dt=0.0, events=()):
        rt, pg = self.rt, self.rt.pg
        inp = rt.input
        self.tick(dt)
        keys = {e.key for e in events if e.type == pg.KEYDOWN}
        if inp.just_pressed("cancel"):
            if self.asking:
                self.asking = False
            else:
                self.closed = True
            return
        rows = self.rows()
        if not rows:
            return
        for action, step in (("move_up", -1), ("move_down", 1)):
            if inp.just_pressed(action):
                self.index = (self.index + step) % len(rows)
                self.asking = False
        if keys & {pg.K_x, pg.K_DELETE}:
            self.dismiss()
        elif inp.just_pressed("confirm"):
            self.confirm()

    def confirm(self, rng=None):
        game = self.game
        tr = game.tr
        chosen = self.selected()
        if chosen is None:
            return None
        candidate, actor, state = chosen
        name = game.name_of(actor)
        if state != "available":
            reasons = {
                "hired": tr("recruit.hired_long", "{name} is already in the party.", name=name),
                "locked": tr("recruit.locked_long", "{name} will not join yet.", name=name),
                "full": tr("recruit.full_long", "The party is full."),
                "poor": tr("recruit.poor_long", "You cannot afford it."),
            }
            self.say(reasons.get(state, state))
            self.sound("fail")
            return None
        if not self.asking:
            self.asking = True
            return None
        self.asking = False
        level = self.office.hire(candidate.actor_id, rng)
        game.refresh_actor_combatants(candidate.actor_id)
        self.say(tr("recruit.joined", "{name} joined the party (Lv {level})", name=name,
                    level=level))  # fmt: skip
        self.sound("buy")
        return level

    def dismiss(self):
        game = self.game
        tr = game.tr
        chosen = self.selected()
        if chosen is None:
            return None
        candidate, actor, state = chosen
        name = game.name_of(actor)
        if state != "hired" or not self.record.can_dismiss:
            self.say(tr("recruit.cannot_dismiss", "{name} cannot be sent away here.", name=name))
            self.sound("fail")
            return None
        roster = game.save.rpg_state.party_active_actor_ids
        if len(roster) <= 1 and candidate.actor_id in roster:
            self.say(tr("recruit.last", "The last member cannot leave."))
            self.sound("fail")
            return None
        refund = self.office.dismiss(candidate.actor_id)
        words = tr("recruit.dismissed", "{name} left the party", name=name)
        if refund:
            words += "  +" + self.money(candidate.currency, refund)
        self.say(words)
        return refund

    def portrait(self, candidate):
        return actor_portrait(self.game, candidate.actor_id, candidate.portrait)

    def class_name(self, actor):
        db = self.game.project.rpg_database
        ids = [a.class_id for a in actor.class_assignments if a.role == "primary"] or [
            a.class_id for a in actor.class_assignments
        ]
        return ", ".join(self.game.name_of(db.classes.get(c), c) for c in ids[:1])

    def level_words(self, candidate):
        tr = self.game.tr
        low, high = candidate.level_min, candidate.level_max
        if not low:
            return tr("recruit.level_own", "Lv 1")
        if high > low:
            return tr("recruit.level_range", "Lv {low}-{high}", low=low, high=high)
        return tr("recruit.level", "Lv {level}", level=low)

    def draw(self):
        rt, game = self.rt, self.game
        tr = game.tr
        party = len(game.save.rpg_state.party_actor_ids)
        limit = self.record.party_limit
        fields = {
            "office.name": game.name_of(self.record),
            "party.count": party,
            "party.limit": limit,
            "wallet.gold": game.save.rpg_state.currencies.get("gold", 0),
        }
        canvas = self.frame(fields, fields["office.name"])
        currencies = sorted({c.currency for c in self.record.candidates}) or ["gold"]
        wallet = "   ".join(self.money(c) for c in currencies)
        canvas.text("wallet", wallet, rt.width - 48, 40, size=20, color=TEXT, anchor="topright")
        count = (
            tr("recruit.party_limit", "Party {count} / {limit}", count=party, limit=limit)
            if limit
            else tr("recruit.party", "Party {count}", count=party)
        )
        canvas.text("party", count, 48, 82, size=18, color=canvas.tone("muted", MUTED))
        self.draw_rows(canvas)
        self.draw_profile(canvas)
        if self.asking and self.selected() is not None:
            candidate, actor, _state = self.selected()
            ask = tr(
                "recruit.ask",
                "Hire {name} for {price}?  Enter: yes   Esc: no",
                name=game.name_of(actor),
                price=self.money(candidate.currency, candidate.cost),
            )
            self.message_left = 0.0  # the question takes the message's line
            width = rt.text_width(ask, 22) + 40
            strip = canvas.rect("ask", (rt.width / 2 - width / 2, rt.height - 94, width, 36))
            if canvas.shown("ask"):
                rt.panel(strip, fill=(40, 30, 14, 240), border=GOLD)
                rt.text(ask, strip[0] + strip[2] / 2, strip[1] + 6, size=22, color=GOLD,
                        anchor="midtop")  # fmt: skip
        hint = tr("recruit.hint", "Up/Down: candidate   Enter: hire   X: send away   Esc: back")
        if not self.record.can_dismiss:
            hint = tr("recruit.hint_no_dismiss", "Up/Down: candidate   Enter: hire   Esc: back")
        self.footer(canvas, hint)

    def draw_rows(self, canvas):
        rt, game = self.rt, self.game
        tr = game.tr
        if not canvas.shown("rows"):
            canvas.rect("rows", CANDIDATES)
            return
        x, y, w, h = canvas.panel("rows", CANDIDATES, fill=(16, 20, 32, 236))
        rows = self.rows()
        if not rows:
            words = tr("recruit.empty", "Nobody is looking for work here.")
            canvas.text("empty", words, x + 14, y + 14, size=18, color=canvas.tone("muted", MUTED))
            return
        row_h = canvas.row_height("rows", 76)
        icon = canvas.icon_size("rows", 60)
        visible = max(1, (h - 16) // row_h)
        first = max(0, min(self.index - visible + 1, len(rows) - visible))
        colors = {"available": TEXT, "hired": GOOD, "locked": GREY, "full": GREY, "poor": BAD}
        states = {
            "available": "",
            "hired": tr("recruit.state.hired", "In the party"),
            "locked": tr("recruit.state.locked", "Not yet"),
            "full": tr("recruit.state.full", "Party full"),
            "poor": tr("recruit.state.poor", "Too dear"),
        }
        for n, (candidate, actor, state) in enumerate(rows[first : first + visible]):
            ry = y + 8 + n * row_h
            rect = (x + 6, ry, w - 12, row_h - 6)
            if first + n == self.index:
                canvas.selection(
                    "rows", rect,
                    lambda rect=rect: rt.pg.draw.rect(rt.screen, (52, 62, 92), rect,
                                                      border_radius=6),
                )  # fmt: skip
            picture = rt.dialogue_portrait(self.portrait(candidate), icon, icon)
            if picture is not None:
                pw, ph = picture.get_size()
                rt.screen.blit(picture, (x + 14 + (icon - pw) // 2, ry + (row_h - 6 - ph) // 2))
            tx = x + 26 + icon
            rt.text(game.name_of(actor), tx, ry + 6, size=20, color=colors.get(state, TEXT))
            sub = f"{self.class_name(actor)}  ·  {self.level_words(candidate)}"
            rt.text(sub, tx, ry + 32, size=15, color=MUTED)
            price = self.money(candidate.currency, candidate.cost) if candidate.cost else ""
            price = price or tr("recruit.free", "Free")
            rt.text(price, x + w - 16, ry + 8, size=17, color=GOLD, anchor="topright")
            if states.get(state):
                rt.text(states[state], x + w - 16, ry + 34, size=15,
                        color=colors.get(state, TEXT), anchor="topright")  # fmt: skip

    def stat_lines(self, actor):
        game = self.game
        stats = [(k, v) for k, v in actor.base_stats.items() if v]  # a 0 says nothing
        return [f"{game.stat_name(k)} {v:g}" for k, v in stats[:8]]

    def draw_profile(self, canvas):
        rt, game = self.rt, self.game
        tr = game.tr
        if not canvas.shown("detail"):
            canvas.rect("detail", PROFILE)
            return
        x, y, w, h = canvas.panel("detail", PROFILE, fill=(16, 20, 32, 240))
        chosen = self.selected()
        if chosen is None:
            return
        candidate, actor, state = chosen
        size = canvas.icon_size("detail", 200)
        picture = rt.dialogue_portrait(self.portrait(candidate), size, size)
        if picture is not None:
            pw, ph = picture.get_size()
            rt.screen.blit(picture, (x + 16 + (size - pw) // 2, y + 16 + (size - ph) // 2))
        tx = x + 32 + size
        lines = [
            (game.name_of(actor), TITLE, 28),
            (self.class_name(actor), TEXT, 18),
            (self.level_words(candidate), TEXT, 18),
            ("", TEXT, 6),
            (tr("recruit.price", "Price {price}",
                price=self.money(candidate.currency, candidate.cost)), GOLD, 18),
        ]  # fmt: skip
        if self.record.can_dismiss and self.record.dismiss_refund:
            refund = self.money(candidate.currency, candidate.cost * self.record.dismiss_refund)
            lines.append((tr("recruit.refund", "Sent away: {refund} back", refund=refund),
                          MUTED, 15))  # fmt: skip
        self.lines(tx, y + 18, w - (tx - x) - 16, y + size + 24, lines)
        top = y + size + 36
        rt.text(tr("recruit.stats", "Stats"), x + 16, top, size=18, color=TITLE)
        stats = self.stat_lines(actor)
        for n, words in enumerate(stats):
            column, row = divmod(n, (len(stats) + 1) // 2)
            rt.text(words, x + 16 + column * (w // 2), top + 28 + row * 24, size=17, color=TEXT)
        note = game.tr(key("recruit", f"{self.record_id}.{actor.actor_id}", "description"),
                       candidate.note)  # fmt: skip
        if note:
            rows = (len(stats) + 1) // 2
            self.lines(x + 16, top + 40 + rows * 24, w - 32, y + h - 8, [(note, MUTED, 16)])


# -- gacha -----------------------------------------------------------------------------------
BANNER = (48, 80, 760, 380)
RATES = (824, 80, 408, 380)
BUTTONS = (48, 476, 1184, 72)
RESULTS = (88, 100, 1104, 460)


class GachaScreen(ServiceScreen):
    SCREEN, ID = "gacha", "banner_id"
    ACTIONS = ("single", "multi", "rates", "history")

    def __init__(self, runtime, banner_id, back="field"):
        self.gacha = Gacha(runtime.game, banner_id)
        super().__init__(runtime, self.gacha.banner, back)
        self.page = "banner"  # banner / rates / history / show / results
        self.action = 0
        self.results = []  # [(pull, duplicate)]
        self.show_time = 0.0
        self.played = set()

    @property
    def banner(self):
        return self.record

    def handle(self, dt=0.0, events=()):
        rt, pg = self.rt, self.rt.pg
        inp = rt.input
        self.tick(dt)
        keys = {e.key for e in events if e.type == pg.KEYDOWN}
        if self.page == "show":
            self.show_time += dt
            self.show_sounds()
            if inp.just_pressed("confirm") or inp.just_pressed("cancel"):
                self.page = "results"  # skip the show
            elif self.show_time >= self.show_length() + 0.4:
                self.page = "results"
            return
        if self.page in ("rates", "history", "results"):
            if inp.just_pressed("cancel") or inp.just_pressed("confirm"):
                self.page = "banner"
            return
        if inp.just_pressed("cancel"):
            self.closed = True
            return
        for action, step in (("move_left", -1), ("move_right", 1)):
            if inp.just_pressed(action):
                self.action = (self.action + step) % len(self.ACTIONS)
        if pg.K_r in keys:
            self.page = "rates"
        elif pg.K_h in keys:
            self.page = "history"
        elif inp.just_pressed("confirm"):
            self.confirm()

    def confirm(self, rng=None):
        tr = self.game.tr
        action = self.ACTIONS[self.action]
        if action in ("rates", "history"):
            self.page = action
            return None
        multi = action == "multi"
        if not self.gacha.is_open():
            self.say(tr("gacha.closed", "This banner is closed."))
            self.sound("fail")
            return None
        if not self.gacha.can_pay(multi):
            self.say(tr("gacha.poor", "Not enough {currency}.",
                        currency=self.currency_name()))  # fmt: skip
            self.sound("fail")
            return None
        self.results = self.gacha.pull(multi, rng)
        for pull, _duplicate in self.results:
            if pull.prize.kind == "actor":
                self.game.refresh_actor_combatants(pull.prize.target_id)
        self.page, self.show_time, self.played = "show", 0.0, set()
        return self.results

    def currency_name(self):
        return self.currency_word(self.banner.currency)

    # -- the show --------------------------------------------------------------------------
    def best(self):
        """The best rarity of the last pull (whose chest is shown)."""
        if not self.results:
            return None
        rarity_id = max((p.rarity for p, _d in self.results), key=self.banner.rank)
        return self.banner.rarity(rarity_id)

    def show_length(self):
        b = self.banner
        return b.appear_seconds + b.shake_seconds + b.open_seconds

    def show_phase(self):
        """``(phase, 0..1)``: appear, shake, open, then done."""
        b, t = self.banner, self.show_time
        for phase, length in (
            ("appear", b.appear_seconds),
            ("shake", b.shake_seconds),
            ("open", b.open_seconds),
        ):
            if t < length:
                return phase, t / length if length else 1.0
            t -= length
        return "done", 1.0

    def show_sounds(self):
        phase, _ = self.show_phase()
        best = self.best()
        sounds = {
            "appear": self.banner.appear_sound,
            "shake": self.banner.shake_sound,
            "open": best.open_sound if best is not None else "",
        }
        if phase in sounds and phase not in self.played:
            self.played.add(phase)
            if sounds[phase]:
                self.rt._sound(sounds[phase])

    def draw(self):
        game = self.game
        fields = {
            "banner.name": game.name_of(self.banner),
            "pity.count": self.gacha.state().since_top,
            "pity.limit": self.banner.hard_pity,
            "wallet": game.save.rpg_state.currencies.get(self.banner.currency, 0),
            "page": self.page,
        }
        canvas = self.frame(fields, fields["banner.name"])
        rt = self.rt
        canvas.text("wallet", self.money(self.banner.currency), rt.width - 48, 40, size=20,
                    color=TEXT, anchor="topright")  # fmt: skip
        tr = game.tr
        if self.page == "show":
            self.draw_show(canvas)
            hint = tr("gacha.hint.show", "Enter: skip")
        elif self.page == "results":
            self.draw_results(canvas)
            hint = tr("gacha.hint.results", "Enter / Esc: back to the banner")
        elif self.page == "rates":
            self.draw_rate_table(canvas)
            hint = tr("gacha.hint.back", "Enter / Esc: back")
        elif self.page == "history":
            self.draw_history(canvas)
            hint = tr("gacha.hint.back", "Enter / Esc: back")
        else:
            self.draw_banner(canvas)
            self.draw_rates(canvas)
            self.draw_buttons(canvas)
            hint = tr(
                "gacha.hint",
                "Left/Right: choose   Enter: pull   R: rates   H: history   Esc: back",
            )
        self.footer(canvas, hint)

    def draw_banner(self, canvas):
        rt, game = self.rt, self.game
        tr = game.tr
        if not canvas.shown("banner"):
            canvas.rect("banner", BANNER)
            return
        x, y, w, h = canvas.panel("banner", BANNER, fill=(22, 18, 40, 240))
        if self.banner.banner_image:
            canvas._image(self.banner.banner_image, (x + 4, y + 4, w - 8, h - 8), "fit")
        about = game.description_of(self.banner)
        top = y + 16
        if about:
            top = self.lines(x + 20, top, w - 40, y + h - 120, [(about, TEXT, 18)])
        featured = [p for p in self.banner.prizes if p.featured]
        if featured:
            words = tr("gacha.featured", "Rate up: {prizes}",
                       prizes=", ".join(self.prize_name(p) for p in featured))  # fmt: skip
            self.lines(x + 20, top + 6, w - 40, y + h - 60, [(words, GOLD, 18)])
            icon = canvas.icon_size("banner", 72)
            for n, prize in enumerate(featured[:6]):
                ix = x + 20 + n * (icon + 14)
                self.prize_icon(prize, ix, y + h - icon - 54, icon)
        state = self.gacha.state()
        if self.banner.hard_pity:
            top_name = self.rarity_name(self.banner.top_rarity())
            left = self.banner.hard_pity - state.since_top
            words = tr("gacha.pity", "{rarity} guaranteed within {count} pulls",
                       rarity=top_name, count=left)  # fmt: skip
            canvas.text("pity", words, x + 20, y + h - 34, size=18, color=TEXT)
        total = tr("gacha.total", "Pulls so far: {count}", count=state.total)
        rt.text(total, x + w - 20, y + h - 34, size=16, color=MUTED, anchor="topright")

    def rarity_name(self, rarity_id):
        rarity = self.banner.rarity(rarity_id)
        return self.game.name_of(rarity, rarity_id) if rarity is not None else rarity_id

    def prize_record(self, prize):
        db = self.game.project.rpg_database
        store = {"item": db.items, "equipment": db.equipment, "actor": db.actors}.get(prize.kind)
        if prize.kind == "pet":
            store = db.pet_species
        return (store or {}).get(prize.target_id)

    def prize_name(self, prize):
        record = self.prize_record(prize)
        name = (
            self.game.name_of(record, prize.target_id) if record is not None else prize.target_id
        )
        return f"{name} x{prize.amount}" if prize.amount > 1 else name

    def prize_icon(self, prize, x, y, size):
        rt = self.rt
        record = self.prize_record(prize)
        icon = getattr(record, "icon_id", "") if record is not None else ""
        if prize.kind == "actor":
            office = self.game.project.rpg_database.recruit_offices.values()
            own = next(
                (
                    c.portrait
                    for o in office
                    for c in o.candidates
                    if c.actor_id == prize.target_id
                ),
                "",
            )
            icon = actor_portrait(self.game, prize.target_id, own) or icon
            picture = rt.dialogue_portrait(icon, size, size) if icon else None
            if picture is not None:
                pw, ph = picture.get_size()
                rt.screen.blit(picture, (x + (size - pw) // 2, y + (size - ph) // 2))
                return True
        return rt._draw_icon(icon, x, y, size) if icon else False

    def draw_rates(self, canvas):
        """The rates of every rarity, always on the banner page."""
        rt, game = self.rt, self.game
        tr = game.tr
        if not canvas.shown("rates"):
            canvas.rect("rates", RATES)
            return
        x, y, w, h = canvas.panel("rates", RATES, fill=(16, 20, 32, 240))
        rt.text(tr("gacha.rates", "Rates"), x + 16, y + 12, size=20, color=TITLE)
        top = y + 48
        for rarity, chance, prizes in reversed(self.banner.rates()):
            if top > y + h - 30:
                break
            rt.text(self.rarity_name(rarity.rarity_id), x + 16, top, size=19, color=rarity.color)
            rt.text(f"{chance * 100:.2f}%", x + w - 16, top, size=19, color=rarity.color,
                    anchor="topright")  # fmt: skip
            top += 28
            for prize, share in prizes[:3]:
                if top > y + h - 30:
                    break
                star = "★ " if prize.featured else ""
                rt.text(f"{star}{self.prize_name(prize)}", x + 32, top, size=15, color=MUTED)
                rt.text(f"{share * 100:.2f}%", x + w - 16, top, size=15, color=MUTED,
                        anchor="topright")  # fmt: skip
                top += 20
            if len(prizes) > 3:
                more = tr("gacha.more", "+{count} more (R)", count=len(prizes) - 3)
                rt.text(more, x + 32, top, size=14, color=GREY)
                top += 20
            top += 6

    def draw_buttons(self, canvas):
        rt, game = self.rt, self.game
        tr = game.tr
        if not canvas.shown("buttons"):
            canvas.rect("buttons", BUTTONS)
            return
        x, y, w, h = canvas.rect("buttons", BUTTONS)
        b = self.banner
        labels = {
            "single": (tr("gacha.single", "Pull x1"), self.money(b.currency, b.single_cost)),
            "multi": (
                tr("gacha.multi", "Pull x{count}", count=b.multi_count),
                self.money(b.currency, b.multi_cost),
            ),
            "rates": (tr("gacha.rates_button", "All rates"), "R"),
            "history": (tr("gacha.history_button", "History"), "H"),
        }
        gap = 16
        bw = (w - gap * (len(self.ACTIONS) - 1)) // len(self.ACTIONS)
        for n, action in enumerate(self.ACTIONS):
            rect = (x + n * (bw + gap), y, bw, h)
            enabled = action not in ("single", "multi") or self.gacha.can_pay(action == "multi")
            if n == self.action:
                canvas.selection(
                    "buttons", rect,
                    lambda rect=rect: rt.pg.draw.rect(rt.screen, (88, 64, 140), rect,
                                                      border_radius=8),
                )  # fmt: skip
            else:
                rt.pg.draw.rect(rt.screen, (40, 36, 64), rect, border_radius=8)
            rt.pg.draw.rect(rt.screen, GOLD if n == self.action else (90, 84, 130), rect, 2,
                            border_radius=8)  # fmt: skip
            title, cost = labels[action]
            color = TEXT if enabled else GREY
            rt.text(title, rect[0] + bw / 2, y + 10, size=22, color=color, anchor="midtop")
            rt.text(cost, rect[0] + bw / 2, y + 40, size=16,
                    color=GOLD if enabled else BAD, anchor="midtop")  # fmt: skip

    def draw_rate_table(self, canvas):
        rt, game = self.rt, self.game
        tr = game.tr
        x, y, w, h = canvas.panel("table", (88, 80, rt.width - 176, rt.height - 180),
                                  fill=(16, 20, 32, 244))  # fmt: skip
        rt.text(tr("gacha.rates", "Rates"), x + 20, y + 14, size=24, color=TITLE)
        b = self.banner
        notes = []
        if b.hard_pity:
            top_name = self.rarity_name(b.top_rarity())
            notes.append(tr("gacha.rule.pity", "{rarity} at the latest on pull {count}",
                            rarity=top_name, count=b.hard_pity))  # fmt: skip
        if b.soft_pity_start and b.soft_pity_step:
            notes.append(tr("gacha.rule.soft", "From pull {start} each pull adds {step}%",
                            start=b.soft_pity_start + 1,
                            step=f"{b.soft_pity_step * 100:g}"))  # fmt: skip
        if b.multi_guarantee:
            notes.append(tr("gacha.rule.multi", "Every x{count}: at least one {rarity}",
                            count=b.multi_count,
                            rarity=self.rarity_name(b.multi_guarantee)))  # fmt: skip
        if b.featured_multiplier != 1:
            notes.append(tr("gacha.rule.featured", "★ rate up x{times}",
                            times=f"{b.featured_multiplier:g}"))  # fmt: skip
        top = y + 52
        for note in notes:
            rt.text(note, x + 20, top, size=16, color=MUTED)
            top += 22
        top += 8
        columns = 2
        cw = (w - 60) // columns
        column, start = 0, top
        for rarity, chance, prizes in reversed(b.rates()):
            block = 30 + 22 * len(prizes)
            if top + block > y + h - 10 and column + 1 < columns:
                column, top = column + 1, start
            cx = x + 20 + column * (cw + 20)
            rt.text(self.rarity_name(rarity.rarity_id), cx, top, size=20, color=rarity.color)
            rt.text(f"{chance * 100:.3f}%", cx + cw, top, size=20, color=rarity.color,
                    anchor="topright")  # fmt: skip
            top += 28
            for prize, share in prizes:
                if top > y + h - 24:
                    break
                star = "★ " if prize.featured else ""
                rt.text(f"{star}{self.prize_name(prize)}", cx + 16, top, size=16, color=TEXT)
                rt.text(f"{share * 100:.3f}%", cx + cw, top, size=16, color=MUTED,
                        anchor="topright")  # fmt: skip
                top += 22
            top += 8

    def draw_history(self, canvas):
        rt, game = self.rt, self.game
        tr = game.tr
        x, y, w, h = canvas.panel("table", (88, 80, rt.width - 176, rt.height - 180),
                                  fill=(16, 20, 32, 244))  # fmt: skip
        rt.text(tr("gacha.history", "Last pulls"), x + 20, y + 14, size=24, color=TITLE)
        state = self.gacha.state()
        prizes = {p.prize_id: p for p in self.banner.prizes}
        rows = list(reversed(state.history))
        if not rows:
            rt.text(tr("gacha.no_history", "No pulls yet."), x + 20, y + 56, size=18, color=MUTED)
            return
        per = max(1, (h - 70) // 24)
        for n, (prize_id, rarity_id) in enumerate(rows[: per * 3]):
            column, row = divmod(n, per)
            cx, cy = x + 20 + column * ((w - 40) // 3), y + 56 + row * 24
            rarity = self.banner.rarity(rarity_id)
            color = rarity.color if rarity is not None else TEXT
            prize = prizes.get(prize_id)
            name = self.prize_name(prize) if prize is not None else prize_id
            rt.text(f"{state.total - n}. {name}", cx, cy, size=16, color=color)

    def draw_show(self, canvas):
        rt = self.rt
        best = self.best()
        if best is None:
            return
        phase, t = self.show_phase()
        pg = rt.pg
        cx, cy = rt.width / 2, rt.height / 2 - 10
        if phase in ("open", "done"):  # the rarity's light
            glow = pg.Surface((rt.width, rt.height), pg.SRCALPHA)
            strength = int(140 * (t if phase == "open" else 1.0))
            for radius, alpha in ((300, strength // 3), (200, strength // 2), (120, strength)):
                pg.draw.circle(glow, (*best.color, alpha), (int(cx), int(cy)), radius)
            rt.screen.blit(glow, (0, 0))
        image_id = best.open_image if phase in ("open", "done") and best.open_image else ""
        image_id = image_id or best.chest_image
        size = 256
        if phase == "appear":
            size = int(256 * (0.3 + 0.7 * t))
        dx = math.sin(self.show_time * 60) * 10 * t if phase == "shake" else 0
        rect = canvas.rect("chest", (cx - 128, cy - 128, 256, 256))
        if image_id:
            canvas._image(image_id, (rect[0] + (256 - size) / 2 + dx, rect[1] + (256 - size) / 2,
                                     size, size), "fit")  # fmt: skip
        else:
            pg.draw.rect(rt.screen, best.color, (cx - size / 2 + dx, cy - size / 3, size,
                                                 size * 2 / 3), border_radius=12)  # fmt: skip
        if phase in ("open", "done"):
            name = self.rarity_name(best.rarity_id)
            rt.text(name, cx, rect[1] + 270, size=34, color=best.color, anchor="midtop")

    def draw_results(self, canvas):
        rt, game = self.rt, self.game
        tr = game.tr
        if not canvas.shown("results"):
            canvas.rect("results", RESULTS)
            return
        x, y, w, h = canvas.rect("results", RESULTS)
        count = len(self.results)
        columns = min(5, max(1, count))
        gap = 16
        cw = min(200, (w - gap * (columns - 1)) // columns)
        rows = (count + columns - 1) // columns
        ch = min(210, (h - gap * (rows - 1)) // max(1, rows))
        left = x + (w - (columns * cw + gap * (columns - 1))) / 2
        icon = min(canvas.icon_size("results", 96), ch - 80)
        for n, (pull, duplicate) in enumerate(self.results):
            r, c = divmod(n, columns)
            cell = (left + c * (cw + gap), y + r * (ch + gap), cw, ch)
            rarity = self.banner.rarity(pull.rarity)
            color = rarity.color if rarity is not None else TEXT
            rt.pg.draw.rect(rt.screen, (20, 18, 34), cell, border_radius=8)
            rt.pg.draw.rect(rt.screen, color, cell, 3, border_radius=8)
            self.prize_icon(pull.prize, cell[0] + (cw - icon) / 2, cell[1] + 10, icon)
            words = self.prize_name(pull.prize)
            ty = cell[1] + 16 + icon
            for line in wrap(rt, words, 16, cw - 12)[:2]:
                rt.text(line, cell[0] + cw / 2, ty, size=16, color=TEXT, anchor="midtop")
                ty += 20
            note = self.rarity_name(pull.rarity)
            if duplicate and pull.prize.duplicate_item:
                note = tr("gacha.duplicate", "→ {item}",
                          item=self.item_name(pull.prize.duplicate_item))  # fmt: skip
            elif pull.pity or pull.guaranteed:
                note = f"{note} ✦"
            rt.text(note, cell[0] + cw / 2, cell[1] + ch - 24, size=15, color=color,
                    anchor="midtop")  # fmt: skip


SCREENS = {"quest_board": QuestBoardScreen, "recruit": RecruitScreen, "gacha": GachaScreen}


def open_service(rt, kind, record_id, back="field"):
    """Open the quest board, recruiting office or gacha banner ``record_id``."""
    rt._service_screen = SCREENS[kind](rt, record_id, back)
    rt._ui_mode = "service"
    return rt._service_screen
