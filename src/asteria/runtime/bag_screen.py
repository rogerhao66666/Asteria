"""Equipment bag screen for real-time play (D23): a grid of items with a tooltip.

The grid shows the equipment bag (rarity-coloured cells, an icon when the equipment has one), the
worn pieces sit in a strip of slots above it. The tooltip of the highlighted piece shows its
rarity, item level, slot, every stat (rolled affixes included) compared with what is worn in that
slot (green better, red worse), the affixes by name, and the set it belongs to with the bonuses.

Arrows move, Enter equips (or unequips a worn piece), Esc / B close. Nothing here knows a game:
slots, rarities, affixes and sets all come from the project's data.
"""

from __future__ import annotations

from asteria.rpg.built_in_text import translated

COLUMNS = 8
CELL = 54
GAP = 6
GOOD, BAD, MUTED, TITLE = (130, 230, 150), (240, 130, 120), (150, 160, 180), (255, 220, 124)


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
                    game = self.game
                    parts = [
                        f"{game.stat_name(m.stat)} {format_value(m.value, m.operation.value)}"
                        for m in bonus.modifiers
                    ]
                    tr = game.tr
                    parts += [
                        tr("bag.set_tag", "tag {tag}", tag=game.tag_name(t)) for t in bonus.tags
                    ]
                    bonuses.append(
                        (bonus.pieces, ", ".join(parts) or tr("bag.set_bonus", "bonus"))
                    )
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
        columns = self.columns()
        row, col = divmod(self.index, columns)
        if dy < 0 and row == 0:
            self.in_worn, self.worn_index = True, min(col, max(0, len(self.worn_slots()) - 1))
            return
        index = self.index + dx + dy * columns
        self.index = max(0, min(len(bag) - 1, index))

    def _point(self, worn, index):
        """The mouse is over a worn piece (``worn``) or a piece in the bag (D85)."""
        if worn:
            self.in_worn, self.worn_index = True, index
        else:
            self.in_worn, self.index = False, index

    def activate(self):
        game = self.game
        item, slot_id, worn = self.selected()
        if item is None:
            return
        try:
            if worn:
                game.unequip_to_bag(self.actor_id, slot_id)
                self._say(game.tr("bag.unequipped", "Unequipped {name}", name=self._name(item)))
            else:
                game.equip_from_bag(self.actor_id, self.index)
                self._say(game.tr("bag.equipped", "Equipped {name}", name=self._name(item)))
                self.index = max(0, min(self.index, len(self.bag()) - 1))
        except Exception as exc:  # requirements not met: say why
            reason = translated(exc, game.tr)
            self._say(game.tr("bag.cannot_equip", "Cannot equip: {reason}", reason=reason))

    def _name(self, item):
        from asteria.rpg.loot import item_display_name

        affixes = self.game.project.rpg_database.affixes
        return item_display_name(item, affixes, brief=True, name_of=self.game.name_of)

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

    def columns(self):
        """Cells in a bag row: the layout's grid columns (U2), else ``COLUMNS``."""
        layout = self.rt.menu_layout("bag")
        element = layout.element("grid") if layout is not None else None
        return element.columns if element is not None and element.columns else COLUMNS

    # -- drawing ---------------------------------------------------------------------------------
    def _cell(self, x, y, item, *, selected, rarities, label="", cell=CELL, element=None):
        rt = self.rt
        pg, screen = rt.pg, rt.screen
        rect = pg.Rect(x, y, cell, cell)
        color = (60, 66, 84)
        fill = (24, 28, 42)
        if item is not None:
            rarity = rarities.get(_rarity(item))
            if rarity is not None:
                theme = rt.menu_theme()
                own = theme.rarity_color(rarity.rarity_id) if theme is not None else None
                color = tuple(own[:3]) if own else rarity.rgb()
                fill = tuple(int(c * 0.22) + 14 for c in color)
        look = element is not None and (element.skin or element.image)
        if look:  # the layout's cell picture, the rarity's colour around it
            if element.skin is not None and rt.skin_image(element.skin.asset_id) is not None:
                from asteria.presentation.ui_skin import draw_nine_patch

                image = rt.skin_image(element.skin.asset_id)
                draw_nine_patch(pg, screen, image, tuple(rect), element.skin)
            elif element.image and rt.skin_image(element.image) is not None:
                screen.blit(rt.scaled_image(rt.skin_image(element.image), rect.size), rect)
            if item is not None:
                pg.draw.rect(screen, color, rect, 2, border_radius=6)
        else:
            pg.draw.rect(screen, fill, rect, border_radius=6)
            pg.draw.rect(screen, color, rect, 2, border_radius=6)
        inset = round(cell * 7 / CELL)
        if item is not None:
            icon_id = getattr(item.equipment, "icon_id", "")
            if not (icon_id and rt._draw_icon(icon_id, x + inset, y + inset, cell - 2 * inset)):
                words = rt.game.name_of(item.equipment).split()
                text = "".join(w[0] for w in words[:2]).upper()
                rt.text(text, x + cell / 2, y + cell / 2, size=26, color=color, center=True)
        elif label:
            rt.text(label[:6], x + cell / 2, y + cell / 2, size=15, color=MUTED, center=True)
        if selected:
            skin = element.selection_skin if element is not None else None
            image = rt.skin_image(skin.asset_id) if skin is not None else None
            if image is not None:
                from asteria.presentation.ui_skin import draw_nine_patch

                draw_nine_patch(pg, screen, image, tuple(rect.inflate(6, 6)), skin)
            else:
                pg.draw.rect(screen, TITLE, rect.inflate(6, 6), 3, border_radius=8)

    def draw(self):
        rt = self.rt
        screen = rt.screen
        game = self.game
        db = game.project.rpg_database
        rarities = db.loot_rarities()
        bag = self.bag()
        actor = self.actor_id or ""
        canvas = self.canvas = rt.menu_canvas(
            "bag",
            {
                "member.name": lambda: game.name_of(db.actors.get(actor), actor),
                "bag.count": len(bag),
            },
        )
        layout = canvas.layout
        if layout is None or (layout.background_color is None and not layout.background_image):
            screen.fill((10, 12, 20))
        canvas.begin()
        tr = game.tr
        title = canvas.tone("title", TITLE)
        muted = canvas.tone("muted", MUTED)
        canvas.text("title", tr("bag.title", "Equipment"), 36, 22, size=34, color=title)
        canvas.text(
            "help",
            tr("bag.hint", "Arrows: choose   Enter: equip / unequip   B / Esc: close"),
            36,
            62,
            size=18,
            color=muted,
        )
        left, top = 36, 100
        canvas.text("worn_label", tr("bag.worn", "Worn"), left, top, size=22, color=title)
        slots = self.worn_slots()
        cell = canvas.number("worn", "cell", CELL)
        gap = canvas.number("worn", "gap", GAP)
        worn = canvas.place("worn", (left, top + 28, len(slots) * (cell + gap), cell))
        if canvas.shown("worn"):
            for k, (slot_id, item) in enumerate(slots):
                rt.hotspot(  # a click on a worn piece takes it off (Enter)
                    (worn.x(left) + k * (cell + gap), worn.y(top + 28), cell, cell),
                    lambda k=k: self._point(True, k),
                )
                self._cell(
                    worn.x(left) + k * (cell + gap),
                    worn.y(top + 28),
                    item,
                    selected=self.in_worn and k == self.worn_index,
                    rarities=rarities,
                    label=self.game.slot_name(slot_id),
                    cell=cell,
                    element=canvas.element("worn"),
                )
        grid_top = top + 28 + CELL + 54
        canvas.text(
            "bag_label",
            tr("bag.count", "Bag  ({count})", count=len(bag)),
            left,
            grid_top - 28,
            size=22,
            color=title,
        )
        columns = self.columns()
        cell = canvas.number("grid", "cell", CELL)
        gap = canvas.number("grid", "gap", GAP)
        rows = max(4, -(-len(bag) // columns))
        grid = canvas.place("grid", (left, grid_top, columns * (cell + gap), rows * (cell + gap)))
        for r in range(rows):
            for c in range(columns):
                k = r * columns + c
                item = bag[k] if k < len(bag) else None
                if item is not None:  # a click on a piece in the bag puts it on
                    box = (grid.x(left) + c * (cell + gap), grid.y(grid_top) + r * (cell + gap))
                    rt.hotspot((*box, cell, cell), lambda k=k: self._point(False, k))
                self._cell(
                    grid.x(left) + c * (cell + gap),
                    grid.y(grid_top) + r * (cell + gap),
                    item,
                    selected=(not self.in_worn) and k == self.index and item is not None,
                    rarities=rarities,
                    cell=cell,
                    element=canvas.element("grid"),
                )
        self._tooltip(rarities)
        if self.message_left > 0:
            canvas.text(
                "message",
                self.message,
                rt.width / 2,
                rt.height - 28,
                size=20,
                color=(175, 235, 255),
                center=True,
            )
        canvas.finish()

    def _tooltip(self, rarities):
        rt = self.rt
        game = self.game
        tr = game.tr
        item, slot_id, worn = self.selected()
        canvas = getattr(self, "canvas", None) or rt.menu_canvas("bag")
        if not canvas.shown("detail"):
            return
        default = (rt.width - 380, 100, 344, rt.height - 100 - 56)
        x, y, w, _h = canvas.panel("detail", default, fill=(16, 20, 32, 240))
        if item is None:
            rt.text(tr("bag.empty", "Nothing here."), x + 16, y + 16, size=20, color=MUTED)
            return
        rarity = rarities.get(_rarity(item))
        color = rarity.rgb() if rarity is not None else (230, 230, 230)
        rt.text(self._name(item), x + 16, y + 14, size=26, color=color)
        kind = game.name_of(rarity) if rarity is not None else _rarity(item)
        kind = kind or tr("bag.common", "Common")
        rt.text(
            tr(
                "bag.item_line",
                "{rarity}  ·  item level {level}  ·  {slot}",
                rarity=kind,
                level=item.item_level,
                slot=game.slot_name(item.equipment.slot),
            ),
            x + 16,
            y + 46,
            size=18,
            color=MUTED,
        )
        row = y + 80
        other = None if worn else self.worn_in(slot_id)
        if worn:
            header = tr("bag.worn", "Worn")
        elif other:
            header = tr("bag.compared", "Compared with the worn piece")
        else:
            header = tr("bag.stats", "Stats")
        rt.text(header, x + 16, row, size=18, color=TITLE)
        row += 26
        for stat, value, delta, operation in compare(item, other):
            line = f"{game.stat_name(stat)}  {format_value(value, operation)}"
            rt.text(line, x + 16, row, size=20)
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
            replaces = tr("bag.replaces", "(replaces {name})", name=self._name(other))
            rt.text(replaces, x + 16, row + 2, size=16, color=MUTED)
            row += 26
        affixes = db.affixes if (db := game.project.rpg_database) else {}
        names = [
            game.name_of(affixes[a.affix_id]) for a in item.rolled_affixes if a.affix_id in affixes
        ]
        if names:
            row += 8
            rt.text(tr("bag.affixes", "Affixes"), x + 16, row, size=18, color=TITLE)
            row += 24
            rt.text(", ".join(names), x + 16, row, size=18)
            row += 26
        definition, have, bonuses = self.set_info(item)
        if definition is not None:
            row += 8
            total = len(definition.equipment_ids)
            rt.text(
                f"{game.name_of(definition)}  ({have}/{total})",
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


def _rarity(item):
    """A rolled drop's rarity, else the one its equipment was authored with."""
    return item.rarity or getattr(item.equipment, "rarity", "")
