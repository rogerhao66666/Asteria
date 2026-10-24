"""The enhance screen: refine, sockets, cards and growth of the gear a member wears (U3).

Four pages over one list of the member's worn pieces:

* **Refine** - the next level's chance, price and materials (have / need, short in red), what a
  failure does (nothing, a level lost, broken, destroyed), the protection item and whether it
  is used (P), and the stats the next level adds. Enter tries.
* **Sockets** / **Cards** - the piece's sockets (cards: the ones that take the ``card`` tag; the
  others on Sockets), what each takes and what sits in it; Enter lists the bag's gems, orbs or
  cards that fit, with the change each makes; Enter sockets it, X takes the chosen socket's
  piece out (saying whether it comes back or is lost).
* **Growth** - the piece's growth stages: rank, what the next rank needs (counter now / needed)
  and gives; Enter unlocks a stage that waits for the player.

Q / E change member, Tab or left / right change page, Esc goes back. Everything shown comes
from the project's refine rules, sockets, attachments and growth definitions.
"""

from __future__ import annotations

from asteria.rpg.built_in_text import translated

from .bag_screen import BAD, GOOD, MUTED, TITLE, format_value

TEXT = (236, 238, 245)
TABS = ("refine", "sockets", "cards", "growth")
GEAR = (48, 124, 380, 500)
SOCKETS = (444, 124, 380, 240)
CHOICES = (444, 380, 380, 244)
DETAIL = (840, 124, 392, 500)


def _modifier_totals(modifiers):
    totals = {}
    for modifier in modifiers:
        key = (modifier.stat, modifier.operation.value)
        totals[key] = totals.get(key, 0.0) + modifier.value
    return totals


class EnhanceScreen:
    """Made when opened; each frame ``handle(dt, events)`` then ``draw()``; ``closed`` ends it."""

    def __init__(self, runtime, back="pause"):
        self.rt = runtime
        self.back = back
        self.closed = False
        self.tab = 0
        self.member = 0
        self.focus = "gear"  # gear -> sockets -> choices (sockets / cards), gear -> nodes
        self.rows = {"gear": 0, "sockets": 0, "choices": 0, "nodes": 0, "levels": 0}
        self.protect = False
        self._started = False
        self.message, self.message_left = "", 0.0

    # -- data ------------------------------------------------------------------------------------
    @property
    def game(self):
        return self.rt.game

    @property
    def page(self):
        return TABS[self.tab]

    def party(self):
        state = self.game.save.rpg_state
        return [a for a in state.party_active_actor_ids if a in state.loadouts]

    @property
    def actor_id(self):
        party = self.party()
        return party[self.member % len(party)] if party else None

    def gear(self):
        """``[(slot_id, piece)]`` the member wears, in slot order."""
        loadout = self.game.save.rpg_state.loadouts.get(self.actor_id)
        if loadout is None:
            return []
        return [(s, piece) for s in loadout.slot_ids() for piece in loadout.equipped(s)]

    def _pick(self, name, rows):
        if not rows:
            return None
        self.rows[name] = min(self.rows[name], len(rows) - 1)
        return rows[self.rows[name]]

    def fits_page(self, piece):
        """Whether this page has something to do with ``piece`` (refine rules that take it,
        sockets of the page's kind, growth stages)."""
        if self.page == "refine":
            return self.game.refine_rules_for(piece) is not None
        if self.page == "growth":
            return piece.growth is not None
        cards = self.page == "cards"
        return any(("card" in s.accepted_tags) == cards for s in piece.equipment.sockets)

    def _first_fitting(self):
        """On a new page or member: the chosen piece moves to the first one the page fits
        (unless the chosen one fits)."""
        gear = self.gear()
        chosen = self.rows["gear"]
        if gear and chosen < len(gear) and self.fits_page(gear[chosen][1]):
            return
        found = next((i for i, (_s, p) in enumerate(gear) if self.fits_page(p)), None)
        if found is not None:
            self.rows["gear"] = found

    def piece(self):
        chosen = self._pick("gear", self.gear())
        return chosen[1] if chosen else None

    def sockets(self):
        """``[(socket, attachment or None, unlocked)]`` of this page's kind on the piece."""
        piece = self.piece()
        if piece is None:
            return []
        unlocked = set(piece.unlocked_socket_ids())
        cards = self.page == "cards"
        return [
            (s, piece.attachments.get(s.socket_id), s.socket_id in unlocked)
            for s in piece.equipment.sockets
            if ("card" in s.accepted_tags) == cards
        ]

    def socket(self):
        return self._pick("sockets", self.sockets())

    def choices(self):
        """``[(item, attachment, count)]``: the bag's socketables the chosen socket takes."""
        chosen = self.socket()
        if chosen is None or not chosen[2]:
            return []
        socket = chosen[0]
        db = self.game.project.rpg_database
        bag = self.game.save.rpg_state.inventory
        out = []
        for item in db.items.values():
            attachment = db.attachments.get(item.attachment_id) if item.attachment_id else None
            if attachment is None or bag.count(item.item_id) < 1:
                continue
            if socket.accepted_tags and not set(socket.accepted_tags) & set(attachment.tags):
                continue
            out.append((item, attachment, bag.count(item.item_id)))
        return out

    def nodes(self):
        piece = self.piece()
        growth = piece.growth if piece is not None else None
        return list(growth.definition.nodes) if growth is not None else []

    # -- input -----------------------------------------------------------------------------------
    def say(self, text):
        self.message, self.message_left = text, 3.0

    def handle(self, dt=0.0, events=()):
        rt, pg = self.rt, self.rt.pg
        inp = rt.input
        self.message_left = max(0.0, self.message_left - dt)
        keys = {e.key for e in events if e.type == pg.KEYDOWN}
        if keys & {pg.K_q, pg.K_PAGEUP, pg.K_e, pg.K_PAGEDOWN} and self.party():
            step = -1 if keys & {pg.K_q, pg.K_PAGEUP} else 1
            self.member = (self.member + step) % len(self.party())
            self.focus = "gear"
            self.rows = dict.fromkeys(self.rows, 0)
            self._first_fitting()
            return
        turn = (1 if pg.K_TAB in keys else 0) + (
            (1 if inp.just_pressed("move_right") else 0)
            - (1 if inp.just_pressed("move_left") else 0)
            if self.focus == "gear"
            else 0
        )
        if turn:
            self.tab = (self.tab + turn) % len(TABS)
            self.focus = "gear"
            self.rows.update(sockets=0, choices=0, nodes=0)
            self._first_fitting()
            return
        if inp.just_pressed("cancel"):
            back = {"choices": "sockets", "sockets": "gear", "nodes": "gear"}
            if self.focus in back:
                self.focus = back[self.focus]
            else:
                self.closed = True
            return
        rows = {
            "gear": self.gear,
            "sockets": self.sockets,
            "choices": self.choices,
            "nodes": self.nodes,
        }[self.focus]()
        for action, step in (("move_up", -1), ("move_down", 1)):
            if inp.just_pressed(action) and rows:
                self.rows[self.focus] = (self.rows[self.focus] + step) % len(rows)
        if pg.K_p in keys and self.page == "refine":
            self.protect = not self.protect
        if keys & {pg.K_x, pg.K_DELETE} and self.focus == "sockets":
            self._run(self.take_out)
        elif inp.just_pressed("confirm"):
            self._run(self.confirm)

    def _run(self, action):
        try:
            action()
        except Exception as exc:  # noqa: BLE001 - shown to the player, play goes on
            self.say(translated(exc, self.game.tr))

    def confirm(self):
        game = self.game
        piece = self.piece()
        if piece is None:
            return
        if self.focus == "gear":
            if self.page == "refine":
                self.refine(piece)
            elif self.page == "growth":
                if self.nodes():
                    self.focus = "nodes"
                else:
                    self.say(game.tr("enhance.no_growth", "This piece does not grow."))
            elif self.sockets():
                self.focus = "sockets"
            else:
                self.say(game.tr("enhance.no_sockets", "This piece has no such socket."))
        elif self.focus == "sockets":
            if self.choices():
                self.focus = "choices"
            else:
                self.say(game.tr("enhance.nothing_fits", "Nothing in the bag fits this socket."))
        elif self.focus == "choices":
            item, attachment, _count = self._pick("choices", self.choices())
            socket = self.socket()[0]
            game.socket_item(self.actor_id, piece.instance_id, socket.socket_id, item.item_id)
            game.refresh_actor_combatants(self.actor_id)
            self.say(
                game.tr(
                    "workshop.socketed",
                    "Socketed {name} into {socket}",
                    name=game.name_of(attachment),
                    socket=game.socket_name(piece.equipment, socket.socket_id),
                )
            )
            self.focus = "sockets"
        elif self.focus == "nodes":
            node = self._pick("nodes", self.nodes())
            piece.growth.unlock(node.node_id)
            game.refresh_actor_combatants(self.actor_id)
            self.say(game.tr("enhance.unlocked", "{name} unlocked", name=game.name_of(node)))

    def refine(self, piece):
        game = self.game
        result = game.refine_equipment(self.actor_id, piece.instance_id, protect=self.protect)
        game.refresh_actor_combatants(self.actor_id)
        words = {
            "success": game.tr("workshop.outcome.success", "success"),
            "failure": game.tr("workshop.outcome.failure", "failure"),
            "protected": game.tr("workshop.outcome.protected", "failed, level kept"),
        }
        outcome = words.get(result.outcome, result.outcome)
        if result.destroyed:
            outcome = game.tr("enhance.destroyed", "the piece was destroyed")
        self.say(game.tr("workshop.refined", "Refine: {outcome}", outcome=outcome))

    def take_out(self):
        game = self.game
        piece = self.piece()
        chosen = self.socket()
        if piece is None or chosen is None or chosen[1] is None:
            return
        socket, attachment, _open = chosen
        game.unsocket_item(self.actor_id, piece.instance_id, socket.socket_id)
        game.refresh_actor_combatants(self.actor_id)
        self.say(
            game.tr(
                "workshop.took_out",
                "Took {name} out of {socket}",
                name=game.name_of(attachment),
                socket=game.socket_name(piece.equipment, socket.socket_id),
            )
        )

    # -- drawing ---------------------------------------------------------------------------------
    def fields(self):
        actor_id = self.actor_id or ""
        fields = dict(self.rt._member_fields(actor_id)) if actor_id else {}
        fields["wallet.gold"] = self.game.save.rpg_state.currencies.get("gold", 0)
        fields["page"] = self.page
        return fields

    def draw(self):
        rt = self.rt
        game = self.game
        tr = game.tr
        if not self._started:  # the first frame: start on a piece the page fits
            self._started = True
            self._first_fitting()
        canvas = self.canvas = rt.menu_canvas("enhance", self.fields())
        layout = canvas.layout
        if layout is None or (layout.background_color is None and not layout.background_image):
            rt.screen.fill((10, 12, 20))
        canvas.begin()
        canvas.panel("frame", (24, 20, rt.width - 48, rt.height - 40), fill=(11, 15, 25, 236))
        title = canvas.tone("title", TITLE)
        muted = canvas.tone("muted", MUTED)
        canvas.text("title", tr("enhance.title", "Enhance"), 48, 32, size=32, color=title)
        member = tr(
            "enhance.member",
            "{name}  ·  Gold {gold}   (Q / E)",
            name=canvas.field("member.name") or "",
            gold=int(canvas.field("wallet.gold") or 0),
        )
        canvas.text("member", member, rt.width - 48, 40, size=20, color=TEXT, anchor="topright")
        self.draw_tabs(canvas)
        self.draw_gear(canvas)
        if self.page == "growth":
            self.draw_nodes(canvas)
        elif self.page == "refine":
            self.draw_levels(canvas)
        elif self.page in ("sockets", "cards"):
            self.draw_sockets(canvas)
            self.draw_choices(canvas)
        self.draw_detail(canvas)
        hints = {
            "refine": tr(
                "enhance.hint.refine",
                "Enter: refine   P: protection on / off   Tab: page   Q / E: member   Esc: back",
            ),
            "sockets": tr(
                "enhance.hint.sockets",
                "Enter: choose / socket   X: take out   Tab: page   Q / E: member   Esc: back",
            ),
            "growth": tr(
                "enhance.hint.growth",
                "Enter: choose / unlock   Tab: page   Q / E: member   Esc: back",
            ),
        }
        hint = hints.get(self.page, hints["sockets"])
        canvas.text("hint", hint, 48, rt.height - 52, size=18, color=muted)
        if self.message_left > 0:
            canvas.text(
                "message", self.message, rt.width / 2, rt.height - 84, size=20,
                color=(175, 235, 255), center=True,
            )  # fmt: skip
        canvas.finish()

    def tab_words(self):
        tr = self.game.tr
        return {
            "refine": tr("enhance.tab.refine", "Refine"),
            "sockets": tr("enhance.tab.sockets", "Sockets"),
            "cards": tr("enhance.tab.cards", "Cards"),
            "growth": tr("enhance.tab.growth", "Growth"),
        }

    def draw_tabs(self, canvas):
        rt = self.rt
        if not canvas.shown("tabs"):
            canvas.rect("tabs", (48, 76, 600, 36))
            return
        place = canvas.place("tabs", (48, 76, 600, 36))
        width = canvas.number("tabs", "cell", 140)
        gap = canvas.number("tabs", "gap", 10)
        words = self.tab_words()
        title = canvas.tone("title", TITLE)
        for n, page in enumerate(TABS):
            rect = (place.x(48) + n * (width + gap), place.y(76), width, 34)
            if n == self.tab:
                canvas.selection(
                    "tabs", rect,
                    lambda rect=rect: rt.pg.draw.rect(rt.screen, (60, 72, 110), rect,
                                                      border_radius=6),
                )  # fmt: skip
            else:
                rt.pg.draw.rect(rt.screen, (40, 46, 64), rect, 1, border_radius=6)
            rt.text(words[page], rect[0] + width / 2, rect[1] + 6, size=18,
                    color=title if n == self.tab else TEXT, anchor="midtop")  # fmt: skip

    def _list(self, canvas, element_id, default, head, rows, focus, empty):
        """A framed list: ``rows`` are ``(icon_id, words, colour)``."""
        rt = self.rt
        if not canvas.shown(element_id):
            canvas.rect(element_id, default)
            return
        x, y, w, h = canvas.panel(element_id, default, fill=(16, 20, 32, 236))
        rt.text(head, x + 14, y + 10, size=18, color=canvas.tone("title", TITLE))
        if not rows:
            rt.text(empty, x + 14, y + 42, size=17, color=canvas.tone("muted", MUTED))
            return
        row_h = canvas.row_height(element_id, 40)
        icon = canvas.icon_size(element_id, 28)
        top = y + 40
        visible = max(1, (h - 48) // row_h)
        chosen = self.rows[focus]
        first = max(0, min(chosen - visible + 1, len(rows) - visible)) if chosen else 0
        for n, (icon_id, words, color) in enumerate(rows[first : first + visible]):
            k = first + n
            ry = top + n * row_h
            rect = (x + 6, ry - 2, w - 12, row_h - 4)
            if k == chosen:
                active = self.focus == focus
                canvas.selection(
                    element_id, rect,
                    lambda rect=rect, active=active: rt.pg.draw.rect(
                        rt.screen, (52, 62, 92) if active else (34, 40, 58), rect,
                        border_radius=6),
                )  # fmt: skip
            if icon_id:
                rt._draw_icon(icon_id, x + 12, ry + (row_h - 4 - icon) // 2, icon)
            rt.text(words, x + 20 + (icon if icon_id else 0), ry + (row_h - 30) // 2, size=18,
                    color=color)  # fmt: skip

    def _piece_name(self, piece):
        name = self.game.name_of(piece.equipment)
        return f"{name} +{piece.refine_level}" if piece.refine_level else name

    def draw_gear(self, canvas):
        game = self.game
        muted = canvas.tone("muted", MUTED)
        rows = [  # a piece this page has nothing for is grey
            (getattr(p.equipment, "icon_id", ""), self._piece_name(p),
             TEXT if self.fits_page(p) else muted)
            for _s, p in self.gear()
        ]  # fmt: skip
        head = game.tr("enhance.gear", "Worn gear")
        empty = game.tr("equipment.empty_slot", "Nothing worn here.")
        self._list(canvas, "gear", GEAR, head, rows, "gear", empty)

    def draw_sockets(self, canvas):
        game = self.game
        tr = game.tr
        piece = self.piece()
        rows = []
        for socket, attachment, unlocked in self.sockets():
            name = game.socket_name(piece.equipment, socket.socket_id)
            if attachment is not None:
                value, color = game.name_of(attachment), GOOD
            elif not unlocked:
                value, color = tr("workshop.locked", "locked"), MUTED
            else:
                value, color = tr("workshop.empty", "empty"), TEXT
            icon = getattr(attachment, "icon_id", "") if attachment is not None else ""
            words = tr("workshop.socket_row", "{socket}: {value}", socket=name, value=value)
            rows.append((icon, words, color))
        head = (
            tr("enhance.card_sockets", "Card sockets")
            if self.page == "cards"
            else tr("enhance.sockets", "Sockets")
        )
        empty = tr("enhance.no_sockets", "This piece has no such socket.")
        self._list(canvas, "sockets", SOCKETS, head, rows, "sockets", empty)

    def draw_choices(self, canvas):
        game = self.game
        tr = game.tr
        rows = [
            (getattr(item, "icon_id", "") or attachment.icon_id,
             f"{game.name_of(item)}  x{count}", TEXT)
            for item, attachment, count in self.choices()
        ]  # fmt: skip
        head = tr("enhance.fits", "From the bag")
        empty = tr("enhance.nothing_fits", "Nothing in the bag fits this socket.")
        self._list(canvas, "choices", CHOICES, head, rows, "choices", empty)

    def draw_nodes(self, canvas):
        game = self.game
        piece = self.piece()
        rows = []
        for node in self.nodes():
            rank = piece.growth.rank(node.node_id)
            color = GOOD if rank >= node.max_rank else TEXT
            rows.append(("", f"{game.name_of(node)}  {rank}/{node.max_rank}", color))
        head = game.tr("enhance.stages", "Growth stages")
        empty = game.tr("enhance.no_growth", "This piece does not grow.")
        self._list(canvas, "sockets", (444, 124, 380, 500), head, rows, "nodes", empty)

    def level_rows(self, piece):
        """``(words, colour)`` per refine level of ``piece`` (+1 to the highest): its chance
        and price, the levels reached in green; empty when it cannot be refined."""
        game = self.game
        rules = game.refine_rules_for(piece) if piece is not None else None
        if rules is None:
            return []
        currency = game.currency_names().get(rules.currency, rules.currency)
        rows = []
        for level in range(1, rules.max_level + 1):
            chance = round(rules.chance(level - 1) * 100)
            cost = int(rules.cost(level - 1))
            words = game.tr(
                "enhance.level_row",
                "+{level}   {chance}%   {cost} {currency}",
                level=level,
                chance=chance,
                cost=cost,
                currency=currency,
            )
            reached = level <= piece.refine_level
            rows.append((words, GOOD if reached else TEXT))
        return rows

    def draw_levels(self, canvas):
        """The refine page's middle column: every level's chance and price, the next one
        marked."""
        piece = self.piece()
        rows = [("", words, color) for words, color in self.level_rows(piece)]
        self.rows["levels"] = min(piece.refine_level, len(rows) - 1) if rows else 0
        head = self.game.tr("enhance.levels", "Refine levels")
        empty = self.game.tr("enhance.cannot_refine", "This piece cannot be refined.")
        self._list(canvas, "sockets", (444, 124, 380, 500), head, rows, "levels", empty)

    # -- the detail panel ------------------------------------------------------------------------
    def draw_detail(self, canvas):
        rt = self.rt
        if not canvas.shown("detail"):
            canvas.rect("detail", DETAIL)
            return
        x, y, w, h = canvas.panel("detail", DETAIL, fill=(16, 20, 32, 240))
        lines = self.detail_lines()
        row = y + 12
        for words, color, size in lines:
            if row > y + h - 24:
                break
            if words:
                rt.text(words, x + 16, row, size=size, color=color)
            row += size + 6

    def detail_lines(self):
        """``[(words, colour, size)]`` of the panel on the right for the page and focus."""
        game = self.game
        tr = game.tr
        piece = self.piece()
        if piece is None:
            return [(tr("equipment.empty_slot", "Nothing worn here."), MUTED, 20)]
        lines = [(self._piece_name(piece), TITLE, 24)]
        if self.page == "refine":
            return lines + self.refine_lines(piece)
        if self.page == "growth":
            return lines + self.growth_lines(piece)
        return lines + self.socket_lines(piece)

    def _stat_lines(self, before, after, color=TEXT):
        out = []
        for key in sorted(set(before) | set(after)):
            old, new = before.get(key, 0.0), after.get(key, 0.0)
            if abs(new - old) < 1e-9 and not new:
                continue
            name = self.game.stat_name(key[0])
            words = f"{name}  {format_value(old, key[1])} → {format_value(new, key[1])}"
            shade = GOOD if new > old else BAD if new < old else color
            out.append((words, shade, 18))
        return out

    def refine_lines(self, piece):
        game = self.game
        tr = game.tr
        rules = game.refine_rules_for(piece)
        if rules is None:
            return [(tr("enhance.cannot_refine", "This piece cannot be refined."), MUTED, 18)]
        level = piece.refine_level
        if level >= rules.max_level:
            return [(tr("enhance.max_level", "At the highest level (+{level})",
                        level=rules.max_level), GOOD, 18)]  # fmt: skip
        lines = [
            (
                tr(
                    "enhance.next_level",
                    "+{level} → +{next}   chance {chance}%",
                    level=level,
                    next=level + 1,
                    chance=round(rules.chance(level) * 100),
                ),
                TEXT,
                20,
            )
        ]
        state = game.save.rpg_state
        cost = rules.cost(level)
        if cost:
            have = state.currencies.get(rules.currency, 0.0)
            currency = game.currency_names().get(rules.currency, rules.currency)
            words = tr(
                "enhance.price",
                "Price {cost} {currency} (have {have})",
                cost=int(cost),
                currency=currency,
                have=int(have),
            )
            lines.append((words, BAD if have < cost else TEXT, 18))
        db = game.project.rpg_database
        if rules.materials:
            lines.append((tr("enhance.materials", "Materials"), TITLE, 18))
        for item_id, need in rules.materials:
            have = state.inventory.count(item_id)
            name = game.name_of(db.items.get(item_id), item_id)
            words = tr(
                "enhance.material_row", "{name}  {have}/{need}", name=name, have=have, need=need
            )
            lines.append((words, BAD if have < need else TEXT, 18))
        fail = {
            "keep": tr("enhance.fail.keep", "A failure loses nothing but the price"),
            "drop": tr("enhance.fail.drop", "A failure drops one level"),
            "break": tr("enhance.fail.break", "A failure breaks the piece (repair it)"),
            "destroy": tr("enhance.fail.destroy", "A failure destroys the piece"),
        }
        if rules.chance(level) < 1.0:
            lines.append((fail.get(rules.on_fail, rules.on_fail), BAD, 18))
        if rules.safe_until:
            lines.append((tr("enhance.safe", "Always succeeds up to +{level}",
                             level=rules.safe_until), MUTED, 16))  # fmt: skip
        if rules.protect_item:
            have = state.inventory.count(rules.protect_item)
            name = game.name_of(db.items.get(rules.protect_item), rules.protect_item)
            state_words = tr("settings.on", "On") if self.protect else tr("settings.off", "Off")
            words = tr(
                "enhance.protect",
                "{name} x{have}: protection {state} (P)",
                name=name,
                have=have,
                state=state_words,
            )
            lines.append((words, GOOD if self.protect and have else MUTED, 17))
        lines.append(("", TEXT, 4))
        lines.append((tr("enhance.preview", "At the next level"), TITLE, 18))
        before = _modifier_totals(rules.modifiers(level, piece.instance_id))
        after = _modifier_totals(rules.modifiers(level + 1, piece.instance_id))
        return lines + self._stat_lines(before, after)

    def socket_lines(self, piece):
        game = self.game
        tr = game.tr
        chosen = self.socket()
        if chosen is None:
            return [(tr("enhance.no_sockets", "This piece has no such socket."), MUTED, 18)]
        socket, attachment, unlocked = chosen
        name = game.socket_name(piece.equipment, socket.socket_id)
        takes = ", ".join(game.tag_name(t) for t in socket.accepted_tags) or tr(
            "enhance.takes_any", "anything"
        )
        lines = [(name, TEXT, 20), (tr("enhance.takes", "Takes: {tags}", tags=takes), MUTED, 17)]
        if not unlocked:
            lines.append((tr("workshop.locked", "locked"), BAD, 18))
        current = stat_totals_of(attachment)
        if self.focus == "choices":
            item, new, _count = self._pick("choices", self.choices())
            lines.append(("", TEXT, 4))
            lines.append((game.name_of(item), TITLE, 20))
            lines += self._stat_lines(current, stat_totals_of(new))
            if attachment is not None:
                lines.append((self._removal_words(attachment), MUTED, 16))
            return lines
        if attachment is not None:
            lines.append(("", TEXT, 4))
            lines.append((game.name_of(attachment), GOOD, 20))
            for (stat, operation), value in sorted(current.items()):
                lines.append((f"{game.stat_name(stat)}  {format_value(value, operation)}",
                              TEXT, 18))  # fmt: skip
            lines.append((self._removal_words(attachment), MUTED, 16))
        return lines

    def _removal_words(self, attachment):
        tr = self.game.tr
        source = self.game._socket_item_for(attachment.attachment_id)
        if source is not None and source.destroyed_on_removal:
            return tr("enhance.removal.lost", "Taking it out destroys it")
        return tr("enhance.removal.kept", "Taking it out returns it to the bag")

    def growth_lines(self, piece):
        game = self.game
        tr = game.tr
        growth = piece.growth
        if growth is None:
            return [(tr("enhance.no_growth", "This piece does not grow."), MUTED, 18)]
        nodes = self.nodes()
        node = self._pick("nodes", nodes) if nodes else None
        if node is None:
            return []
        rank = growth.rank(node.node_id)
        lines = [(f"{game.name_of(node)}  {rank}/{node.max_rank}", TEXT, 20)]
        if rank >= node.max_rank:
            lines.append((tr("enhance.stage_done", "Complete"), GOOD, 18))
            return lines
        preview = growth.preview_unlock(node.node_id)
        lines.append((tr("enhance.needs", "Next rank needs"), TITLE, 18))
        for counter_id, needed in sorted(preview.requirements.items()):
            now = growth.counter(counter_id)
            words = tr(
                "enhance.counter_row",
                "{name}  {now}/{need}",
                name=game.stat_name(counter_id),
                now=f"{now:g}",
                need=f"{needed:g}",
            )
            lines.append((words, GOOD if now >= needed else TEXT, 18))
        reward = node.reward_for_rank(rank + 1)
        lines.append((tr("enhance.gives", "Gives"), TITLE, 18))
        for (stat, operation), value in sorted(_modifier_totals(reward.modifiers).items()):
            lines.append((f"{game.stat_name(stat)}  {format_value(value, operation)}", GOOD,
                          18))  # fmt: skip
        if reward.unlocked_sockets:
            lines.append((tr("enhance.opens_sockets", "Opens {count} socket(s)",
                             count=len(reward.unlocked_sockets)), GOOD, 18))  # fmt: skip
        if reward.evolution_equipment_id:
            target = game.project.rpg_database.equipment.get(reward.evolution_equipment_id)
            lines.append((tr("enhance.evolves", "Evolves into {name}",
                             name=game.name_of(target, reward.evolution_equipment_id)), GOOD,
                          18))  # fmt: skip
        if node.auto_unlock:
            lines.append((tr("enhance.auto", "Unlocks by itself when ready"), MUTED, 16))
        elif preview.allowed:
            lines.append((tr("enhance.ready", "Ready: Enter unlocks it"), GOOD, 16))
        return lines


def stat_totals_of(attachment):
    return _modifier_totals(attachment.modifiers) if attachment is not None else {}


__all__ = ["TABS", "EnhanceScreen"]
