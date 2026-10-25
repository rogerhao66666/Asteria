"""A shop in a creature game's own art (``field.creature_shop``): the BUY / SELL / QUIT
window over the field, a buy screen (the goods and prices over the map, the chosen item's
picture and description, how many and the total, a YES / NO before paying) and selling from
the bag. Drawn at the game's own resolution (240 x 160) like the start menu
(``creature_menu``), whose windows, fonts, bag and message window it uses.

``field.creature_shop`` (every key optional):

* ``background``: the buy screen's picture (see-through where the map shows);
  ``money_label``: a picture drawn in the money window; ``places``: ``{name: [x, y]}`` over
  ``PLACES`` (window insides and text spots, in the screen's pixels).
* ``map_front_at``: where the cell the player faces shows on the buy screen's map (the
  runtime moves the field's camera so; shop.c: 4 cells in from the top left);
  ``rows``: goods shown at once; ``currency``: the money's mark.
* ``buy_sound`` (a purchase), ``bonus`` (``{"item", "every", "gift"}``: buying ``every`` of
  ``item`` gives one ``gift``, as POKé BALLS bring a PREMIER BALL).
* ``words``: the shopkeeper's lines over the built-in ones (``creature.shop.*``).
"""

from __future__ import annotations

from asteria.presentation.creature_screens import creature_settings
from asteria.runtime.creature_battle import H, W
from asteria.runtime.creature_menu import CreatureMenuScreen

PLACES = {  # shop.c's window templates (insides) and print spots, in 240 x 160 pixels
    "menu": (24, 16),  # BUY / SELL / QUIT
    "money": (8, 8, 80, 16),
    "money_label": (3, 3),
    "money_right": (87, 9),
    "list": (112, 16, 120, 128),
    "description": (3, 105),
    "icon": (8, 72),
    "in_bag": (8, 88, 96, 16),
    "quantity": (144, 88, 80, 16),
    "yes_no": (168, 72),
}
OVERLAY_PHASES = ("menu",)  # the field shows around the BUY / SELL / QUIT window
MAP_PHASES = ("buy", "buy_count", "buy_confirm", "buy_note")  # the map behind the goods


class CreatureShopScreen(CreatureMenuScreen):
    def __init__(self, runtime):
        super().__init__(runtime, "menu")
        self.shop_settings = creature_settings(runtime, "field.creature_shop")
        places = {k: tuple(v) for k, v in (self.shop_settings.get("places") or {}).items()}
        self.places = {**PLACES, **places}
        self.menu_cursor = 0
        self.buy_cursor = self.buy_scroll = 0
        self.count = 1
        self.yes = 0
        self.after = ""  # the phase a shown line leads to
        self.selling = False
        self.message_text = self._greeting()

    # -- words and goods ------------------------------------------------------------------------
    def _tr(self, key, default, **values):
        """A shop word: the layout's own (``words`` by the key's last part), else the built-in
        ``creature.shop.*`` in the player's language."""
        own = (self.shop_settings.get("words") or {}).get(key.rsplit(".", 1)[-1])
        if own:
            text = self.game.expand_message(str(own), plain=True)
            return text.format(**values) if values else text
        return self.tr(key, default, **values)

    def _greeting(self):
        held = self.game.held_dialogue  # the clerk's line shown as the shop opens
        if held is not None:
            return self.game.expand_message(self.game.line_text(held.line), plain=True)
        return self._tr("creature.shop.greeting", "How may I serve you?")

    def goods(self):
        """``[(item id, name, price)]`` the shop sells, in its order."""
        shop_id = self.game.open_shop_id
        if not shop_id:
            return []
        items = self.game.project.rpg_database.items
        rows = []
        for entry in self.game.shops.visible_entries(shop_id):
            prices = self.game.shops.prices(shop_id, entry.item_id, "buy")
            item = items.get(entry.item_id)
            if not prices or item is None:
                continue
            rows.append((entry.item_id, self.game.name_of(item, entry.item_id),
                         int(next(iter(prices.values())))))  # fmt: skip
        return rows

    def money(self):
        return int(self.game.save.rpg_state.currencies.get("gold", 0.0))

    def currency(self):
        return str(self.shop_settings.get("currency", "¥"))

    def _sell_price(self, item_id):
        prices = self.game.shops.prices(self.game.open_shop_id, item_id, "sell")
        return int(next(iter(prices.values()))) if prices else 0

    # -- input ------------------------------------------------------------------------------------
    def menu_rows(self):
        return [
            ("buy", self._tr("creature.shop.buy", "BUY")),
            ("sell", self._tr("creature.shop.sell", "SELL")),
            ("quit", self._tr("creature.shop.quit", "QUIT")),
        ]

    def _close(self):
        self.game.close_shop()
        self.done = True

    def _input_menu(self):
        rows = self.menu_rows()
        if self._pressed("move_up"):
            self.menu_cursor = (self.menu_cursor - 1) % len(rows)
        if self._pressed("move_down"):
            self.menu_cursor = (self.menu_cursor + 1) % len(rows)
        if self._pressed("cancel"):
            self._close()
            return
        if not self._pressed("confirm"):
            return
        choice = rows[self.menu_cursor][0]
        if choice == "buy":
            self.phase, self.buy_cursor, self.buy_scroll = "buy", 0, 0
        elif choice == "sell":
            self.selling = True
            self.phase, self.list_cursor, self.pocket, self.bag_scroll = "bag", 0, 0, 0
            self.note = self._tr("creature.shop.what_to_sell", "What would you like to sell?")
        else:
            self._close()

    def _back_to_menu(self):
        self.phase, self.selling, self.note = "menu", False, ""
        self.message_text = self._tr(
            "creature.shop.anything_else", "Is there anything else I can help\nyou with?"
        )

    def _input_buy(self):
        goods = self.goods()
        count = len(goods) + 1  # + CANCEL
        rows = int(self.shop_settings.get("rows", 8))
        if self._pressed("move_up"):
            self.buy_cursor = max(0, self.buy_cursor - 1)
        if self._pressed("move_down"):
            self.buy_cursor = min(count - 1, self.buy_cursor + 1)
        self.buy_scroll = min(self.buy_scroll, self.buy_cursor)
        self.buy_scroll = max(self.buy_scroll, self.buy_cursor - rows + 1)
        if self._pressed("cancel") or (self._pressed("confirm") and self.buy_cursor >= len(goods)):
            self._back_to_menu()
            return
        if not self._pressed("confirm"):
            return
        _item_id, name, price = goods[self.buy_cursor]
        if self.money() < price:
            self._say(self._tr("creature.shop.no_money", "You don't have enough money."), "buy")
            return
        self.count = 1
        self.phase = "buy_count"
        self.note = self._tr(
            "creature.shop.how_many", "{item}? Certainly.\nHow many would you like?", item=name
        )

    def _max_count(self, price):
        return max(1, min(99, self.money() // max(1, price)))

    def _input_buy_count(self):
        _item_id, name, price = self.goods()[self.buy_cursor]
        top = self._max_count(price)
        for action, step in (("move_up", 1), ("move_down", -1),
                             ("move_right", 10), ("move_left", -10)):  # fmt: skip
            if self._pressed(action):  # shop.c: the count wraps around at the ends
                moved = self.count + step
                self.count = (
                    (moved if 1 <= moved <= top else (1 if moved > top else top))
                    if abs(step) == 1
                    else max(1, min(top, moved))
                )
        if self._pressed("cancel"):
            self.phase, self.note = "buy", ""
        elif self._pressed("confirm"):
            self.phase, self.yes = "buy_confirm", 0
            self.note = self._tr(
                "creature.shop.confirm",
                "{item}? And you wanted {count}?\nThat will be {money}.",
                item=name,
                count=self.count,
                money=f"{self.currency()}{price * self.count}",
            )

    def _input_buy_confirm(self):
        if self._pressed("move_up") or self._pressed("move_down"):
            self.yes = 1 - self.yes
        if self._pressed("cancel") or (self._pressed("confirm") and self.yes == 1):
            self.phase, self.note = "buy", ""
            return
        if not self._pressed("confirm"):
            return
        item_id, _name, _price = self.goods()[self.buy_cursor]
        from asteria.rpg.economy import ShopError

        try:
            self.game.buy(item_id, self.count)
        except ShopError:  # not enough money (or the shop ran out)
            self._say(self._tr("creature.shop.no_money", "You don't have enough money."), "buy")
            return
        self._sound(self.shop_settings.get("buy_sound"))
        lines = [self._tr("creature.shop.thank_you", "Here you go!\nThank you very much.")]
        bonus = self.shop_settings.get("bonus") or {}
        if bonus.get("item") == item_id and self.count >= int(bonus.get("every", 10) or 10):
            self.game.save.rpg_state.inventory.add(str(bonus.get("gift", "")), 1)
            lines.append(self._tr("creature.shop.bonus", "I'll throw in a PREMIER BALL, too."))
        self._say(lines, "buy")

    def _say(self, lines, after):
        """Lines in the message window, a key for each; then ``after``."""
        self.lines = [lines] if isinstance(lines, str) else list(lines)
        self.note, self.after = self.lines.pop(0), after
        self.phase = "buy_note" if after == "buy" else "sell_note"

    def _input_buy_note(self):
        if self._pressed("confirm") or self._pressed("cancel"):
            if self.lines:
                self.note = self.lines.pop(0)
            else:
                self.phase, self.note = self.after, ""
                if self.after == "bag":
                    self.note = self._tr(
                        "creature.shop.what_to_sell", "What would you like to sell?"
                    )

    _input_sell_note = _input_buy_note

    # -- selling from the bag --------------------------------------------------------------------
    def _input_bag(self):
        if not self.selling:
            return super()._input_bag()
        items = self.pocket_items()
        if self._pressed("cancel") or (
            self._pressed("confirm") and self.list_cursor >= len(items)
        ):
            self._back_to_menu()
            return
        if self._pressed("confirm"):
            item_id = items[self.list_cursor][0]
            name = self.game.name_of(self.game.project.rpg_database.items[item_id], item_id)
            if self._sell_price(item_id) <= 0:
                self._say(self._tr("creature.shop.cant_buy", "{item}? Oh, no.\nI can't buy that.",
                                     item=name), "bag")  # fmt: skip
                return
            self.count, self.sell_item = 1, item_id
            self.phase = "sell_count"
            self.note = self._tr(
                "creature.shop.how_many_sell",
                "{item}?\nHow many would you like to sell?",
                item=name,
            )
            return
        self.note = self._tr("creature.shop.what_to_sell", "What would you like to sell?")
        super()._input_bag()
        if self.phase != "bag":  # the bag's own item window is not used here
            self.phase = "bag"

    def _input_sell_count(self):
        held = self.game.save.rpg_state.inventory.count(self.sell_item)
        for action, step in (("move_up", 1), ("move_down", -1),
                             ("move_right", 10), ("move_left", -10)):  # fmt: skip
            if self._pressed(action):
                self.count = max(1, min(held, self.count + step))
        if self._pressed("cancel"):
            self.phase = "bag"
            self.note = self._tr("creature.shop.what_to_sell", "What would you like to sell?")
        elif self._pressed("confirm"):
            self.phase, self.yes = "sell_confirm", 0
            total = self._sell_price(self.sell_item) * self.count
            self.note = self._tr(
                "creature.shop.can_pay",
                "I can pay {money}.\nWould that be okay?",
                money=f"{self.currency()}{total}",
            )

    def _input_sell_confirm(self):
        if self._pressed("move_up") or self._pressed("move_down"):
            self.yes = 1 - self.yes
        if self._pressed("cancel") or (self._pressed("confirm") and self.yes == 1):
            self.phase = "bag"
            self.note = self._tr("creature.shop.what_to_sell", "What would you like to sell?")
            return
        if not self._pressed("confirm"):
            return
        total = self._sell_price(self.sell_item) * self.count
        item = self.game.project.rpg_database.items[self.sell_item]
        self.game.sell(self.sell_item, self.count)
        self._sound(self.shop_settings.get("buy_sound"))
        self.list_cursor = min(self.list_cursor, max(0, len(self.pocket_items())))
        self._say(self._tr("creature.shop.sold", "Turned over the {item}\nand received {money}.",
                             item=self.game.name_of(item, self.sell_item),
                             money=f"{self.currency()}{total}"), "bag")  # fmt: skip

    def _sound(self, asset_id):
        if asset_id:
            from asteria.events.world_commands import WorldCommand

            self.game.presentation_requests.append(
                WorldCommand("PLAY_SE", {"asset_id": str(asset_id)})
            )

    # -- drawing ----------------------------------------------------------------------------------
    def draw(self):
        s = self.surface
        see_through = self.phase in OVERLAY_PHASES or self.phase in MAP_PHASES
        s.fill((0, 0, 0, 0) if see_through else (0, 0, 0, 255))
        if self.phase == "menu":
            self._draw_menu()
        elif self.phase in MAP_PHASES:
            self._draw_buy()
        else:
            self._draw_bag()
            if self.phase in ("sell_count", "sell_confirm"):
                self._draw_count(self._sell_price(self.sell_item) * self.count, self.count)
            if self.phase == "sell_confirm":
                self._draw_yes_no_box()
            self._message_window(self.note or "")
        screen = self.rt.screen
        sw, sh = screen.get_size()
        scale = max(1, min(sw // W, sh // H))
        if not see_through:
            screen.fill((0, 0, 0, 255))
        big = self.pg.transform.scale(s, (W * scale, H * scale))
        screen.blit(big, ((sw - W * scale) // 2, (sh - H * scale) // 2))

    def _draw_menu(self):
        letter, shadow = self._menu_colours()
        rows = [label for _id, label in self.menu_rows()]
        x, y = self.places["menu"]
        width = (max(self.text_width(r) for r in rows) + 16 + 7) // 8 * 8
        self._frame((x - 8, y - 8, width + 8, 16 * len(rows)))
        for row, label in enumerate(rows):
            self._text(label, x, y - 8 + row * 16 + 1, letter, shadow)
            if row == self.menu_cursor:
                self._cursor(x - 8, y - 8 + row * 16 + 3)
        self._message_window(self.message_text)

    def _draw_buy(self):
        pg, s = self.pg, self.surface
        background = self._menu_picture(self.shop_settings.get("background"))
        if background is not None:
            s.blit(background, (0, 0))
        letter, shadow = self._menu_colours()
        mx, my, mw, mh = self.places["money"]
        self._frame((mx, my, mw, mh))
        label = self._menu_picture(self.shop_settings.get("money_label"))
        if label is not None:
            s.blit(label, self.places["money_label"])
        rx, ry = self.places["money_right"]
        self._text(f"{self.currency()}{self.money()}", rx, ry, letter, shadow, anchor="topright")
        goods = self.goods()
        lx, ly, lw, _lh = self.places["list"]
        rows = int(self.shop_settings.get("rows", 8))
        names = [*goods, ("", self._tr("creature.shop.cancel", "CANCEL"), None)]
        for row, (_item_id, name, price) in enumerate(names[self.buy_scroll :][:rows]):
            index = self.buy_scroll + row
            y = ly + row * 16 + 1
            self._text(name, lx + 8, y, letter, shadow)
            if price is not None:
                self._text(f"{self.currency()}{price}", lx + lw, y, letter, shadow,
                           anchor="topright")  # fmt: skip
            if index == self.buy_cursor:
                self._cursor(lx, y + 2)
        dx, dy = self.places["description"]
        if self.buy_cursor < len(goods):
            item_id = goods[self.buy_cursor][0]
            item = self.game.project.rpg_database.items.get(item_id)
            text = self.game.description_of(item, "") if item is not None else ""
            lines = [part for row in text.split("\n") for part in self.wrap(row, 104)]
            for n, line in enumerate(lines[:3]):  # the description's own lines first
                self._text(line, dx, dy + n * 16, letter, shadow)
            icon = self._image("item_icon", item_id, None)
            if icon is not None:
                s.blit(icon, self.places["icon"])
        else:
            words = self._tr("creature.shop.quit_shopping", "Quit shopping.")
            self._text(words, dx, dy, letter, shadow)
        if self.phase in ("buy_count", "buy_confirm"):
            item_id, _name, price = goods[self.buy_cursor]
            bx, by, bw, bh = self.places["in_bag"]
            self._frame((bx, by, bw, bh))
            held = self.game.save.rpg_state.inventory.count(item_id)
            self._text(self._tr("creature.shop.in_bag", "IN BAG: {count}", count=f"{held:3d}"),
                       bx, by + 1, letter, shadow)  # fmt: skip
            self._draw_count(price * self.count, self.count)
        if self.phase == "buy_confirm":
            self._draw_yes_no_box()
        if self.note:
            self._message_window(self.note)
        _ = pg

    def _draw_count(self, total, count):
        letter, shadow = self._menu_colours()
        qx, qy, qw, qh = self.places["quantity"]
        self._frame((qx, qy, qw, qh))
        self._text(f"×{count:02d}", qx, qy + 1, letter, shadow)
        self._text(f"{self.currency()}{total}", qx + qw - 1, qy + 1, letter, shadow,
                   anchor="topright")  # fmt: skip

    def _draw_yes_no_box(self):
        letter, shadow = self._menu_colours()
        x, y = self.places["yes_no"]
        rows = [self.tr("creature.yes", "YES"), self.tr("creature.no", "NO")]
        self._frame((x, y, 40, 32))
        for row, label in enumerate(rows):
            self._text(label, x + 8, y + row * 16 + 1, letter, shadow)
            if row == self.yes:
                self._cursor(x, y + row * 16 + 3)


__all__ = ["CreatureShopScreen", "MAP_PHASES", "OVERLAY_PHASES", "PLACES"]
