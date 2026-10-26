"""The equipment screen: a paper doll of the member's slots, what fits, the change (U3).

Left, the doll: every slot the member has, one place per piece the slot holds (a slot of two
weapons has two places). The project's menu layout (``equipment`` ▸ ``doll``) may give it a
picture and put each place on it (``MenuSlotPlace``; the n-th place of a slot shows its n-th
piece); slots the layout does not place sit in a row under the doll. Without a layout the
places stand in two columns around the member's name.

Middle, the bag pieces that go in the chosen slot (one the member cannot use yet is grey and
says why). Right, the highlighted piece: rarity, refine level, durability, sockets, every stat
compared with the piece it would replace, its set and the set's bonuses; under it the member's
stats now and with that piece on.

Arrows choose, Enter goes to the list / wears the piece, X takes the chosen piece off, Q / E
change member, Esc goes back. Slots, rarities, stats and sets all come from the project.
"""

from __future__ import annotations

from asteria.rpg.built_in_text import translated

from .bag_screen import BAD, GOOD, MUTED, TITLE, _rarity, compare, format_value

TEXT = (236, 238, 245)
DOLL = (48, 112, 420, 470)
CANDIDATES = (488, 112, 362, 470)
DETAIL = (868, 112, 388, 318)
STATS = (868, 442, 388, 210)
CELL = 64


class EquipmentScreen:
    """Made when opened; each frame ``handle(dt, events)`` then ``draw()``; ``closed`` ends it."""

    def __init__(self, runtime, back="pause"):
        self.rt = runtime
        self.back = back
        self.closed = False
        self.member = 0
        self.place = 0  # the chosen place on the doll
        self.focus = "doll"  # or "list"
        self.row = 0
        self.message, self.message_left = "", 0.0

    # -- data ------------------------------------------------------------------------------------
    @property
    def game(self):
        return self.rt.game

    def party(self):
        state = self.game.save.rpg_state
        return [a for a in state.party_active_actor_ids if a in state.loadouts]

    @property
    def actor_id(self):
        party = self.party()
        return party[self.member % len(party)] if party else None

    def loadout(self):
        return self.game.save.rpg_state.loadouts.get(self.actor_id)

    def places(self):
        """``[(slot_id, index, piece or None)]``: one per piece each slot can hold."""
        loadout = self.loadout()
        if loadout is None:
            return []
        out = []
        for slot_id in loadout.slot_ids():
            held = loadout.equipped(slot_id)
            capacity = loadout._slots[slot_id].capacity
            count = max(len(held), capacity if capacity is not None else len(held) + 1, 1)
            for index in range(count):
                out.append((slot_id, index, held[index] if index < len(held) else None))
        return out

    def chosen(self):
        places = self.places()
        if not places:
            return None, 0, None
        return places[min(self.place, len(places) - 1)]

    def candidates(self):
        """``[(piece, allowed, reason)]``: the bag pieces the chosen slot takes."""
        slot_id, _index, _worn = self.chosen()
        loadout = self.loadout()
        if slot_id is None or loadout is None:
            return []
        slot = loadout._slots[slot_id]
        capabilities = self.game.resolve_actor_build(self.actor_id).capabilities
        out = []
        for piece in self.game.save.rpg_state.equipment_bag:
            # its own slot, or a slot that names tags the piece has (a slot without tags
            # takes pieces made for it only)
            if piece.equipment.slot != slot_id and not (
                slot.accepted_tags and slot.accepts(piece.equipment)
            ):
                continue
            check = piece.equipment.eligibility(capabilities)
            reason = "; ".join(check.reasons) if not check.allowed else ""
            out.append((piece, check.allowed, reason))
        return out

    def highlighted(self):
        """``(piece, the piece it would replace or None, is_worn)``."""
        _slot, _index, worn = self.chosen()
        if self.focus == "list":
            rows = self.candidates()
            if rows:
                return rows[min(self.row, len(rows) - 1)][0], worn, False
            return None, worn, False
        return worn, None, True

    def name(self, piece):
        from asteria.rpg.loot import item_display_name

        affixes = self.game.project.rpg_database.affixes
        text = item_display_name(piece, affixes, brief=True, name_of=self.game.name_of)
        return f"{text} +{piece.refine_level}" if piece.refine_level else text

    def set_info(self, piece):
        """``(set, pieces the member wears, [(pieces, words)])`` (the bag screen's words)."""
        from .bag_screen import BagScreen

        return BagScreen.set_info(_Member(self.rt, self.actor_id), piece)

    def stat_rows(self):
        """``[(stat_id, name, now, with the highlighted piece or None)]`` in the project's
        character-screen order."""
        from asteria.runtime.status_menu import StatusMenu

        game, actor_id = self.game, self.actor_id
        if actor_id is None:
            return []
        menu = StatusMenu(game)
        state = game.save.rpg_state
        view = menu.screens["status"].project(
            game.resolve_actor_build(actor_id),
            loadout=state.loadouts.get(actor_id),
            actor_definition=game.project.rpg_database.actors.get(actor_id),
        )
        piece, replaced, worn = self.highlighted()
        change = {}
        if piece is not None and not worn:
            for stat, _value, delta, operation in compare(piece, replaced):
                if operation == "add" and delta:
                    change[stat] = change.get(stat, 0.0) + delta
                elif operation == "add" and replaced is None:
                    change[stat] = change.get(stat, 0.0) + _value
        rows = []
        for stat in view.stats:
            after = stat.value + change[stat.stat_id] if stat.stat_id in change else None
            rows.append((stat.stat_id, game.stat_name(stat.stat_id), stat.value, after))
        return rows

    # -- input -----------------------------------------------------------------------------------
    def say(self, text):
        self.message, self.message_left = text, 2.5

    def handle(self, dt=0.0, events=()):
        rt, pg = self.rt, self.rt.pg
        inp = rt.input
        self.message_left = max(0.0, self.message_left - dt)
        keys = {e.key for e in events if e.type == pg.KEYDOWN}
        if keys & {pg.K_q, pg.K_PAGEUP, pg.K_e, pg.K_PAGEDOWN} and self.party():
            step = -1 if keys & {pg.K_q, pg.K_PAGEUP} else 1
            self.member = (self.member + step) % len(self.party())
            self.place, self.row, self.focus = 0, 0, "doll"
            return
        if inp.just_pressed("cancel"):
            if self.focus == "list":
                self.focus = "doll"
            else:
                self.closed = True
            return
        if self.focus == "doll":
            count = len(self.places())
            for action, step in (("move_up", -1), ("move_left", -1), ("move_down", 1),
                                 ("move_right", 1)):  # fmt: skip
                if inp.just_pressed(action) and count:
                    self.place = (self.place + step) % count
            if keys & {pg.K_x, pg.K_DELETE}:
                self.take_off()
            elif inp.just_pressed("confirm"):
                if self.candidates():
                    self.focus, self.row = "list", 0
                else:
                    self.say(self.game.tr("equipment.nothing_fits", "Nothing in the bag fits."))
        else:
            count = len(self.candidates())
            for action, step in (("move_up", -1), ("move_down", 1)):
                if inp.just_pressed(action) and count:
                    self.row = (self.row + step) % count
            if inp.just_pressed("confirm"):
                self.wear()

    def _pointer(self, focus, index):
        """Pointing at a place on the doll or a piece in the list (D85): the cursor goes there,
        a click is Enter (opens what fits / puts it on)."""

        def pick():
            self.focus = focus
            if focus == "doll":
                self.place = index
            else:
                self.row = index

        return pick

    def wear(self):
        game = self.game
        slot_id, index, worn = self.chosen()
        rows = self.candidates()
        if not rows:
            return
        piece, allowed, reason = rows[min(self.row, len(rows) - 1)]
        if not allowed:
            self.say(game.tr("bag.cannot_equip", "Cannot equip: {reason}", reason=reason))
            return
        try:
            game.wear_from_bag(self.actor_id, piece.instance_id, slot_id, index)
        except Exception as exc:  # noqa: BLE001 - shown to the player, play goes on
            reason = translated(exc, game.tr)
            self.say(game.tr("bag.cannot_equip", "Cannot equip: {reason}", reason=reason))
            return
        self.say(game.tr("bag.equipped", "Equipped {name}", name=self.name(piece)))
        self.focus = "doll"

    def take_off(self):
        game = self.game
        slot_id, index, worn = self.chosen()
        if worn is None:
            return
        game.unequip_to_bag(self.actor_id, slot_id, index)
        self.say(game.tr("bag.unequipped", "Unequipped {name}", name=self.name(worn)))

    # -- drawing ---------------------------------------------------------------------------------
    def fields(self):
        game = self.game
        actor_id = self.actor_id or ""
        fields = dict(self.rt._member_fields(actor_id)) if actor_id else {}
        fields["wallet.gold"] = game.save.rpg_state.currencies.get("gold", 0)
        return fields

    def draw(self):
        rt = self.rt
        game = self.game
        tr = game.tr
        canvas = self.canvas = rt.menu_canvas("equipment", self.fields())
        layout = canvas.layout
        if layout is None or (layout.background_color is None and not layout.background_image):
            rt.screen.fill((10, 12, 20))
        canvas.begin()
        canvas.panel("frame", (24, 20, rt.width - 48, rt.height - 40), fill=(11, 15, 25, 236))
        title = canvas.tone("title", TITLE)
        muted = canvas.tone("muted", MUTED)
        text = canvas.tone("text", TEXT)
        canvas.text("title", tr("equipment.title", "Equipment"), 48, 32, size=32, color=title)
        actor_id = self.actor_id
        if actor_id is None:
            canvas.text("member", tr("status.empty", "Nothing here yet."), 48, 74, color=muted)
            canvas.finish()
            return
        line = tr(
            "equipment.member",
            "{name}  ·  Lv {level}  ·  {job}   (Q / E)",
            name=canvas.field("member.name"),
            level=canvas.field("member.level"),
            job=canvas.field("member.class"),
        )
        canvas.text("member", line, 48, 74, size=20, color=text)
        self.draw_doll(canvas)
        self.draw_candidates(canvas)
        self.draw_detail(canvas)
        self.draw_stats(canvas)
        hint = tr(
            "equipment.hint",
            "Arrows: choose   Enter: change   X: take off   Q / E: member   Esc: back",
        )
        canvas.text("hint", hint, 48, rt.height - 52, size=18, color=muted)
        if self.message_left > 0:
            canvas.text(
                "message", self.message, rt.width / 2, rt.height - 84, size=20,
                color=(175, 235, 255), center=True,
            )  # fmt: skip
        canvas.finish()

    def _slot_cell(self, rect, piece, label, *, chosen, placeholder="", bare=False):
        """One place: its frame (none on a doll picture), the piece's icon or the empty
        place's picture / name, the highlight when chosen."""
        rt = self.rt
        pg, screen = rt.pg, rt.screen
        rect = pg.Rect(rect)
        rarities = self.game.project.rpg_database.loot_rarities()
        color = (70, 78, 98)
        if piece is not None:
            rarity = rarities.get(_rarity(piece))
            if rarity is not None:
                theme = rt.menu_theme()
                own = theme.rarity_color(rarity.rarity_id) if theme is not None else None
                color = tuple(own[:3]) if own else rarity.rgb()
        if not bare:
            pg.draw.rect(screen, (22, 26, 40), rect, border_radius=6)
            pg.draw.rect(screen, color, rect, 2, border_radius=6)
        elif piece is not None:
            pg.draw.rect(screen, color, rect, 2, border_radius=4)
        inset = max(2, rect.w // 9)
        size = min(rect.w, rect.h) - 2 * inset
        x, y = rect.x + (rect.w - size) // 2, rect.y + (rect.h - size) // 2
        if piece is not None:
            icon_id = getattr(piece.equipment, "icon_id", "")
            if not (icon_id and rt._draw_icon(icon_id, x, y, size)):
                words = self.game.name_of(piece.equipment).split()
                initials = "".join(w[0] for w in words[:2]).upper()
                rt.text(initials, rect.centerx, rect.centery, size=22, color=color, center=True)
            if piece.broken:
                pg.draw.line(screen, BAD, rect.topleft, rect.bottomright, 3)
        elif placeholder and rt.skin_image(placeholder) is not None:
            screen.blit(rt.scaled_image(rt.skin_image(placeholder), (size, size)), (x, y))
        elif not bare:
            rt.text(label[:8], rect.centerx, rect.centery, size=14, color=MUTED, center=True)
        if chosen:
            canvas = self.canvas
            canvas.selection(
                "doll",
                rect.inflate(6, 6),
                lambda: pg.draw.rect(screen, TITLE, rect.inflate(6, 6), 3, border_radius=8),
            )

    def draw_doll(self, canvas):
        rt = self.rt
        game = self.game
        places = self.places()
        if not canvas.shown("doll"):
            canvas.rect("doll", DOLL)
            return
        element = canvas.element("doll")
        x, y, w, h = canvas.rect("doll", DOLL)
        own = element is not None and (element.skin or element.image or element.fill)
        if own:
            canvas._draw_look(element, (x, y, w, h))
        else:
            canvas.panel("doll", DOLL, fill=(16, 20, 32, 236))
        placed = {}
        for place in element.slots if element is not None else ():
            placed.setdefault(place.slot_id, []).append(place)
        chosen = min(self.place, len(places) - 1) if places else -1
        loose = []
        for k, (slot_id, index, piece) in enumerate(places):
            spots = placed.get(slot_id, [])
            label = game.slot_name(slot_id)
            if index < len(spots):
                px, py, pw, ph = spots[index].rect
                rt.hotspot((x + px, y + py, pw, ph), self._pointer("doll", k))
                self._slot_cell(
                    (x + px, y + py, pw, ph), piece, label, chosen=k == chosen and
                    self.focus == "doll", placeholder=spots[index].placeholder, bare=bool(own),
                )  # fmt: skip
            else:
                loose.append((k, slot_id, piece, label))
        if not loose:
            return
        if not placed:  # the engine's doll: two columns of places around the member's name
            cell = CELL
            left, right = x + 24, x + w - 24 - cell
            name = canvas.field("member.name") or ""
            rt.text(str(name), x + w / 2, y + h / 2 - 12, size=22, color=TITLE, center=True)
            for n, (k, _slot, piece, label) in enumerate(loose):
                column, row = n % 2, n // 2
                cx = left if column == 0 else right
                cy = y + 24 + row * (cell + 30)
                rt.hotspot((cx, cy, cell, cell), self._pointer("doll", k))
                self._slot_cell((cx, cy, cell, cell), piece, label,
                                chosen=k == chosen and self.focus == "doll")  # fmt: skip
                anchor = "topleft" if column == 0 else "topright"
                lx = cx + cell + 10 if column == 0 else cx - 10
                rt.text(label, lx, cy + cell / 2 - 10, size=16, color=MUTED, anchor=anchor)
            return
        cell = 48  # slots the layout left out: a row under the doll
        for n, (k, _slot, piece, label) in enumerate(loose):
            rt.hotspot((x + n * (cell + 8), y + h + 10, cell, cell), self._pointer("doll", k))
            self._slot_cell((x + n * (cell + 8), y + h + 10, cell, cell), piece, label,
                            chosen=k == chosen and self.focus == "doll")  # fmt: skip

    def draw_candidates(self, canvas):
        rt = self.rt
        game = self.game
        tr = game.tr
        if not canvas.shown("candidates"):
            canvas.rect("candidates", CANDIDATES)
            return
        x, y, w, h = canvas.panel("candidates", CANDIDATES, fill=(16, 20, 32, 236))
        slot_id, _index, _worn = self.chosen()
        title = canvas.tone("title", TITLE)
        muted = canvas.tone("muted", MUTED)
        head = tr("equipment.fits", "For {slot}", slot=game.slot_name(slot_id or ""))
        rt.text(head, x + 16, y + 12, size=20, color=title)
        rows = self.candidates()
        if not rows:
            rt.text(tr("equipment.nothing_fits", "Nothing in the bag fits."), x + 16, y + 48,
                    size=18, color=muted)  # fmt: skip
            return
        row_h = canvas.row_height("candidates", 44)
        icon = canvas.icon_size("candidates", 32)
        top = y + 46
        visible = max(1, (h - 56) // row_h)
        first = max(0, min(self.row - visible + 1, len(rows) - visible)) if self.row else 0
        rarities = game.project.rpg_database.loot_rarities()
        for n, (piece, allowed, _reason) in enumerate(rows[first : first + visible]):
            k = first + n
            ry = top + n * row_h
            rect = (x + 8, ry - 2, w - 16, row_h - 4)
            rt.hotspot(rect, self._pointer("list", k))
            if self.focus == "list" and k == self.row:
                canvas.selection(
                    "candidates", rect,
                    lambda rect=rect: rt.pg.draw.rect(rt.screen, (52, 62, 92), rect,
                                                      border_radius=6),
                )  # fmt: skip
            icon_id = getattr(piece.equipment, "icon_id", "")
            if icon_id:
                rt._draw_icon(icon_id, x + 14, ry + (row_h - 4 - icon) // 2, icon)
            rarity = rarities.get(_rarity(piece))
            color = rarity.rgb() if rarity is not None and allowed else TEXT
            rt.text(self.name(piece), x + 22 + icon, ry + (row_h - 30) // 2, size=20,
                    color=color if allowed else muted)  # fmt: skip

    def draw_detail(self, canvas):
        rt = self.rt
        game = self.game
        tr = game.tr
        if not canvas.shown("detail"):
            canvas.rect("detail", DETAIL)
            return
        x, y, w, h = canvas.panel("detail", DETAIL, fill=(16, 20, 32, 240))
        piece, replaced, worn = self.highlighted()
        muted = canvas.tone("muted", MUTED)
        title = canvas.tone("title", TITLE)
        if piece is None:
            rt.text(tr("equipment.empty_slot", "Nothing worn here."), x + 16, y + 16, size=20,
                    color=muted)  # fmt: skip
            return
        rarities = game.project.rpg_database.loot_rarities()
        rarity = rarities.get(_rarity(piece))
        color = rarity.rgb() if rarity is not None else TEXT
        rt.text(self.name(piece), x + 16, y + 12, size=24, color=color)
        kind = game.name_of(rarity) if rarity is not None else ""
        kind = kind or tr("bag.common", "Common")
        bits = [kind, game.slot_name(piece.equipment.slot)]
        if piece.durability is not None:
            bits.append(
                tr(
                    "equipment.durability",
                    "durability {now}/{most}",
                    now=int(piece.durability),
                    most=int(piece.max_durability),
                )
            )
        rt.text("  ·  ".join(bits), x + 16, y + 42, size=16, color=muted)
        row = y + 70
        header = (
            tr("bag.compared", "Compared with the worn piece")
            if replaced is not None
            else tr("bag.stats", "Stats")
        )
        rt.text(header, x + 16, row, size=17, color=title)
        row += 24
        for stat, value, delta, operation in compare(piece, replaced):
            if row > y + h - 60:
                break
            rt.text(f"{game.stat_name(stat)}  {format_value(value, operation)}", x + 16, row,
                    size=18)  # fmt: skip
            if delta is not None and abs(delta) > 1e-9:
                rt.text(f"({delta:+g})", x + w - 90, row, size=17,
                        color=GOOD if delta > 0 else BAD)  # fmt: skip
            row += 22
        sockets = piece.equipment.sockets
        if sockets and row < y + h - 40:
            filled = sum(1 for s in sockets if s.socket_id in piece.attachments)
            rt.text(
                tr("equipment.sockets", "Sockets {filled}/{total}", filled=filled,
                   total=len(sockets)),
                x + 16, row + 4, size=16, color=muted,
            )  # fmt: skip
            row += 24
        definition, have, bonuses = self.set_info(piece)
        if definition is not None and row < y + h - 30:
            total = len(definition.equipment_ids)
            rt.text(f"{game.name_of(definition)}  ({have}/{total})", x + 16, row + 4, size=18,
                    color=GOOD)  # fmt: skip
            row += 28
            for pieces, words in bonuses:
                if row > y + h - 24:
                    break
                rt.text(f"({pieces}) {words}", x + 24, row, size=16,
                        color=GOOD if have >= pieces else muted)  # fmt: skip
                row += 20

    def draw_stats(self, canvas):
        rt = self.rt
        tr = self.game.tr
        if not canvas.shown("stats"):
            canvas.rect("stats", STATS)
            return
        x, y, w, h = canvas.panel("stats", STATS, fill=(16, 20, 32, 240))
        title = canvas.tone("title", TITLE)
        rt.text(tr("equipment.stats", "Stats"), x + 16, y + 10, size=18, color=title)
        rows = self.stat_rows()
        row_h = canvas.row_height("stats", 22)
        per_column = max(1, (h - 44) // row_h)
        column_w = (w - 32) // 2
        for n, (_stat, name, now, after) in enumerate(rows[: per_column * 2]):
            cx = x + 16 + (n // per_column) * column_w
            cy = y + 38 + (n % per_column) * row_h
            rt.text(f"{name}  {now:g}", cx, cy, size=16)
            if after is not None and abs(after - now) > 1e-9:  # the new value, at the right
                rt.text(f"→ {after:g}", cx + column_w - 12, cy, size=16,
                        color=GOOD if after > now else BAD, anchor="topright")  # fmt: skip


class _Member:
    """``BagScreen.set_info`` for another member than the player."""

    def __init__(self, runtime, actor_id):
        self.rt, self.actor_id = runtime, actor_id

    @property
    def game(self):
        return self.rt.game


__all__ = ["EquipmentScreen"]
