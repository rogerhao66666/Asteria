"""Equipment bag screen for real-time play (D23): a grid of items with a tooltip.

The grid shows the equipment bag (rarity-coloured cells, an icon when the equipment has one), the
worn pieces sit in a strip of slots above it. The tooltip of the highlighted piece shows its
rarity, item level, slot, every stat (rolled affixes included) compared with what is worn in that
slot (green better, red worse), the affixes by name, and the set it belongs to with the bonuses.

Arrows move, Enter equips (or unequips a worn piece), Esc / B close. Nothing here knows a game:
slots, rarities, affixes and sets all come from the project's data.
"""

from __future__ import annotations

COLUMNS = 8
CELL = 54
GAP = 6
GOOD, BAD, MUTED, TITLE = (130, 230, 150), (240, 130, 120), (150, 160, 180), (255, 220, 124)


def _label(stat):
    return str(stat).replace("_", " ").capitalize()


def stat_totals(item):
    """``{(stat, operation): value}`` an item gives (``add`` and ``multiply`` kept apart)."""
    totals = {}
    for modifier in item.modifiers():
        key = (modifier.stat, modifier.operation.value)
        totals[key] = totals.get(key, 0.0) + modifier.value
    return totals


def compare(item, worn):
    """Lines ``(text, delta, kind)`` for an item against the piece worn in its slot (``worn`` may
    be None): ``delta`` is the change if equipped, ``kind`` ``add`` or ``multiply``."""
    mine = stat_totals(item)
    theirs = stat_totals(worn) if worn is not None else {}
    lines = []
    for key in sorted(set(mine) | set(theirs)):
        value, other = mine.get(key, 0.0), theirs.get(key, 0.0)
        lines.append((key[0], value, value - other if worn is not None else None, key[1]))
    return lines


def format_value(value, operation):
    if operation == "multiply":
        return f"x{value:g}"
    return f"{value:+g}"


class BagScreen:
    """Made when opened; each frame ``handle(events?)`` then ``draw()``; ``closed`` ends it."""

    def __init__(self, runtime):
        self.rt = runtime
        self.index = 0  # position in the bag grid; -1 row = worn strip (see ``row_worn``)
        self.in_worn = False
        self.worn_index = 0
        self.closed = False
        self.message, self.message_left = "", 0.0

    # -- data ------------------------------------------------------------------------------------
    @property
    def game(self):
        return self.rt.game

    @property
    def actor_id(self):
        game = self.game
        return game._actor_of(game.player) or (game.save.rpg_state.party_actor_ids or (None,))[0]

    def bag(self):
        return self.game.save.rpg_state.equipment_bag

    def worn_slots(self):
        """``[(slot_id, item or None)]`` in the loadout's slot order (one entry per piece)."""
        loadout = self.game.save.rpg_state.loadouts.get(self.actor_id)
        if loadout is None:
            return []
        out = []
        for slot_id in loadout.slot_ids():
            items = loadout.equipped(slot_id)
            out.append((slot_id, items[0] if items else None))
        return out

    def selected(self):
        """``(item, slot_id, is_worn)`` of the highlighted cell, or ``(None, None, False)``."""
        if self.in_worn:
            slots = self.worn_slots()
            if slots:
                slot_id, item = slots[min(self.worn_index, len(slots) - 1)]
                return item, slot_id, True
            return None, None, False
        bag = self.bag()
        if bag:
            item = bag[min(self.index, len(bag) - 1)]
            return item, item.equipment.slot, False
        return None, None, False

    def worn_in(self, slot_id):
        loadout = self.game.save.rpg_state.loadouts.get(self.actor_id)
        items = loadout.equipped(slot_id) if loadout is not None else ()
        return items[0] if items else None

    def set_info(self, item):
        """``(set definition, pieces worn, [(pieces, text)])`` for the set an item belongs to."""
        db = self.game.project.rpg_database
        for definition in db.equipment_sets.values():
            if item.equipment.equipment_id in definition.equipment_ids:
                loadout = self.game.save.rpg_state.loadouts.get(self.actor_id)
                worn = {i.equipment.equipment_id for i in loadout.equipped()} if loadout else set()
                have = len(worn & set(definition.equipment_ids))
                bonuses = []
                for bonus in definition.bonuses:
                    parts = [
                        f"{m.stat} {format_value(m.value, m.operation.value)}"
                        for m in bonus.modifiers
                    ]
                    parts += [f"tag {t}" for t in bonus.tags]
                    bonuses.append((bonus.pieces, ", ".join(parts) or "bonus"))
                return definition, have, bonuses
        return None, 0, []

    # -- input -----------------------------------------------------------------------------------
    def _say(self, text):
        self.message, self.message_left = text, 2.5

    def _move(self, dx, dy):
        bag = self.bag()
        if self.in_worn:
            count = len(self.worn_slots())
            if dy > 0 and bag:
                self.in_worn, self.index = False, min(self.worn_index, len(bag) - 1)
            elif dx:
                self.worn_index = max(0, min(count - 1, self.worn_index + dx))
            return
        if not bag:
            if dy < 0:
                self.in_worn = True
            return
        row, col = divmod(self.index, COLUMNS)
        if dy < 0 and row == 0:
            self.in_worn, self.worn_index = True, min(col, max(0, len(self.worn_slots()) - 1))
            return
        index = self.index + dx + dy * COLUMNS
        self.index = max(0, min(len(bag) - 1, index))

    def activate(self):
        game = self.game
        item, slot_id, worn = self.selected()
        if item is None:
            return
        try:
            if worn:
                game.unequip_to_bag(self.actor_id, slot_id)
                self._say(f"Unequipped {self._name(item)}")
            else:
                game.equip_from_bag(self.actor_id, self.index)
                self._say(f"Equipped {self._name(item)}")
                self.index = max(0, min(self.index, len(self.bag()) - 1))
        except Exception as exc:  # requirements not met: say why
            self._say(f"Cannot equip: {exc}")

    def _name(self, item):
        from asteria.rpg.loot import item_display_name

        return item_display_name(item, self.game.project.rpg_database.affixes, brief=True)

    def handle(self, dt=0.0):
        inp = self.rt.input
        self.message_left = max(0.0, self.message_left - dt)
        if inp.just_pressed("cancel") or inp.just_pressed("bag"):
            self.closed = True
            return
        for action, (dx, dy) in (
            ("move_left", (-1, 0)),
            ("move_right", (1, 0)),
            ("move_up", (0, -1)),
            ("move_down", (0, 1)),
        ):
            if inp.just_pressed(action):
                self._move(dx, dy)
        if inp.just_pressed("confirm") or inp.just_pressed("interact"):
            self.activate()

    # -- drawing ---------------------------------------------------------------------------------
    def _cell(self, x, y, item, *, selected, rarities, label=""):
        rt = self.rt
        pg, screen = rt.pg, rt.screen
        rect = pg.Rect(x, y, CELL, CELL)
        color = (60, 66, 84)
        fill = (24, 28, 42)
        if item is not None:
            rarity = rarities.get(item.rarity)
            if rarity is not None:
                color = rarity.rgb()
                fill = tuple(int(c * 0.22) + 14 for c in color)
        pg.draw.rect(screen, fill, rect, border_radius=6)
        pg.draw.rect(screen, color, rect, 2, border_radius=6)
        if item is not None:
            icon_id = getattr(item.equipment, "icon_id", "")
            if not (icon_id and rt._draw_icon(icon_id, x + 7, y + 7, CELL - 14)):
                words = item.equipment.display_name.split()
                text = "".join(w[0] for w in words[:2]).upper()
                rt.text(text, x + CELL / 2, y + CELL / 2, size=26, color=color, center=True)
        elif label:
            rt.text(label[:6], x + CELL / 2, y + CELL / 2, size=15, color=MUTED, center=True)
        if selected:
            pg.draw.rect(screen, TITLE, rect.inflate(6, 6), 3, border_radius=8)

    def draw(self):
        rt = self.rt
        screen = rt.screen
        game = self.game
        db = game.project.rpg_database
        rarities = db.loot_rarities()
        screen.fill((10, 12, 20))
        rt.text("Equipment", 36, 22, size=34, color=TITLE)
        rt.text(
            "Arrows: choose   Enter: equip / unequip   B / Esc: close",
            36,
            62,
            size=18,
            color=MUTED,
        )
        left, top = 36, 100
        rt.text("Worn", left, top, size=22, color=TITLE)
        slots = self.worn_slots()
        for k, (slot_id, item) in enumerate(slots):
            x = left + k * (CELL + GAP)
            self._cell(
                x,
                top + 28,
                item,
                selected=self.in_worn and k == self.worn_index,
                rarities=rarities,
                label=_label(slot_id),
            )
        bag = self.bag()
        grid_top = top + 28 + CELL + 54
        rt.text(f"Bag  ({len(bag)})", left, grid_top - 28, size=22, color=TITLE)
        rows = max(4, -(-len(bag) // COLUMNS))
        for r in range(rows):
            for c in range(COLUMNS):
                k = r * COLUMNS + c
                item = bag[k] if k < len(bag) else None
                self._cell(
                    left + c * (CELL + GAP),
                    grid_top + r * (CELL + GAP),
                    item,
                    selected=(not self.in_worn) and k == self.index and item is not None,
                    rarities=rarities,
                )
        self._tooltip(rarities)
        if self.message_left > 0:
            rt.text(
                self.message,
                rt.width / 2,
                rt.height - 28,
                size=20,
                color=(175, 235, 255),
                center=True,
            )

    def _tooltip(self, rarities):
        rt = self.rt
        game = self.game
        item, slot_id, worn = self.selected()
        x, y, w = rt.width - 380, 100, 344
        rt.panel((x, y, w, rt.height - 100 - 56), fill=(16, 20, 32, 240))
        if item is None:
            rt.text("Nothing here.", x + 16, y + 16, size=20, color=MUTED)
            return
        rarity = rarities.get(item.rarity)
        color = rarity.rgb() if rarity is not None else (230, 230, 230)
        rt.text(self._name(item), x + 16, y + 14, size=26, color=color)
        kind = rarity.display_name if rarity is not None else item.rarity or "Common"
        rt.text(
            f"{kind}  ·  item level {item.item_level}  ·  {_label(item.equipment.slot)}",
            x + 16,
            y + 46,
            size=18,
            color=MUTED,
        )
        row = y + 80
        other = None if worn else self.worn_in(slot_id)
        header = "Worn" if worn else ("Compared with the worn piece" if other else "Stats")
        rt.text(header, x + 16, row, size=18, color=TITLE)
        row += 26
        for stat, value, delta, operation in compare(item, other):
            rt.text(f"{_label(stat)}  {format_value(value, operation)}", x + 16, row, size=20)
            if delta is not None and abs(delta) > 1e-9:
                rt.text(
                    f"({delta:+g})",
                    x + w - 96,
                    row,
                    size=18,
                    color=GOOD if delta > 0 else BAD,
                )
            row += 24
        if other is not None:
            rt.text(f"(replaces {self._name(other)})", x + 16, row + 2, size=16, color=MUTED)
            row += 26
        affixes = db.affixes if (db := game.project.rpg_database) else {}
        names = [
            affixes[a.affix_id].display_name for a in item.rolled_affixes if a.affix_id in affixes
        ]
        if names:
            row += 8
            rt.text("Affixes", x + 16, row, size=18, color=TITLE)
            row += 24
            rt.text(", ".join(names), x + 16, row, size=18)
            row += 26
        definition, have, bonuses = self.set_info(item)
        if definition is not None:
            row += 8
            total = len(definition.equipment_ids)
            rt.text(
                f"{definition.display_name}  ({have}/{total})",
                x + 16,
                row,
                size=20,
                color=(120, 230, 150),
            )
            row += 26
            for pieces, text in bonuses:
                active = have >= pieces
                rt.text(
                    f"({pieces}) {text}",
                    x + 24,
                    row,
                    size=18,
                    color=(120, 230, 150) if active else MUTED,
                )
                row += 22


__all__ = ["BagScreen", "compare", "format_value", "stat_totals"]
