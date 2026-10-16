"""Shops: buying and selling items for project-defined currencies (ASTERIA_SPEC §23)."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _prices(raw, label):
    out = {}
    for key, value in dict(raw or {}).items():
        value = float(value)
        if not isfinite(value) or value < 0:
            raise ValueError(f"{label} must be finite and >= 0")
        out[_id(key, "currency id")] = value
    return out


class ShopError(ValueError):
    pass


_CONDITION_OPERATORS = ("==", "!=", "<=", ">=", "<", ">")  # two-character ones first


def _conditions(raw):
    """Switch / variable conditions: ``{"source", "name", "operator", "value"}``."""
    result = []
    for item in raw or ():
        item = dict(item)
        if item.get("source") not in ("switch", "variable") or not str(item.get("name", "")):
            raise ValueError("a condition needs a switch / variable source and a name")
        if item.get("operator", "==") not in ("==", "!=", "<", "<=", ">", ">="):
            raise ValueError("unsupported condition operator")
        result.append(
            {
                "source": item["source"],
                "name": str(item["name"]),
                "operator": item.get("operator", "=="),
                "value": item.get("value", True),
            }
        )
    return tuple(result)


@dataclass(frozen=True, slots=True)
class PriceRule:
    """While every condition holds, buy prices are multiplied by ``buy_multiplier`` and sell
    prices by ``sell_multiplier`` (a sale, a faction discount, a festival...). Matching rules
    multiply together."""

    conditions: tuple
    buy_multiplier: float = 1.0
    sell_multiplier: float = 1.0

    def __post_init__(self):
        object.__setattr__(self, "conditions", _conditions(self.conditions))
        for name in ("buy_multiplier", "sell_multiplier"):
            value = float(getattr(self, name))
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and >= 0")
            object.__setattr__(self, name, value)

    def to_data(self):
        return {
            "conditions": [dict(c) for c in self.conditions],
            "buy_multiplier": self.buy_multiplier,
            "sell_multiplier": self.sell_multiplier,
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data.get("conditions", ()),
            data.get("buy_multiplier", 1.0),
            data.get("sell_multiplier", 1.0),
        )


@dataclass(frozen=True, slots=True)
class ShopEntry:
    """One item a shop deals in.

    ``buy_prices`` is what the player pays per unit (empty: the shop does not
    sell it); ``sell_prices`` is what the player receives per unit (empty: the
    shop does not buy it back). ``stock`` limits how many the shop can sell;
    ``None`` is unlimited.
    """

    item_id: str
    buy_prices: dict
    sell_prices: dict
    stock: int | None = None
    visible_when: tuple = ()
    price_rules: tuple = ()

    def __init__(
        self,
        item_id,
        *,
        buy_prices=None,
        sell_prices=None,
        stock=None,
        visible_when=(),
        price_rules=(),
    ):
        if stock is not None:
            stock = int(stock)
            if stock < 0:
                raise ValueError("stock must be >= 0")
        object.__setattr__(self, "item_id", _id(item_id, "item_id"))
        object.__setattr__(self, "buy_prices", _prices(buy_prices, "buy price"))
        object.__setattr__(self, "sell_prices", _prices(sell_prices, "sell price"))
        object.__setattr__(self, "stock", stock)
        object.__setattr__(self, "visible_when", _conditions(visible_when))
        rules = tuple(
            r if isinstance(r, PriceRule) else PriceRule.from_data(r) for r in price_rules
        )
        object.__setattr__(self, "price_rules", rules)

    def to_data(self):
        return {
            "item_id": self.item_id,
            "buy_prices": dict(sorted(self.buy_prices.items())),
            "sell_prices": dict(sorted(self.sell_prices.items())),
            "stock": self.stock,
            **(
                {"visible_when": [dict(c) for c in self.visible_when]} if self.visible_when else {}
            ),
            **(
                {"price_rules": [r.to_data() for r in self.price_rules]}
                if self.price_rules
                else {}
            ),
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["item_id"],
            buy_prices=data["buy_prices"],
            sell_prices=data["sell_prices"],
            stock=data["stock"],
            visible_when=data.get("visible_when", ()),
            price_rules=data.get("price_rules", ()),
        )


@dataclass(frozen=True, slots=True)
class ShopDefinition:
    shop_id: str
    display_name: str
    entries: tuple[ShopEntry, ...]

    def __init__(self, shop_id, display_name=None, entries=()):
        entries = tuple(entries)
        if any(not isinstance(x, ShopEntry) for x in entries):
            raise TypeError("entries must be ShopEntry values")
        ids = [x.item_id for x in entries]
        if len(ids) != len(set(ids)):
            raise ValueError("shop entries must have unique item ids")
        object.__setattr__(self, "shop_id", _id(shop_id, "shop_id"))
        object.__setattr__(self, "display_name", str(display_name or shop_id))
        object.__setattr__(self, "entries", entries)

    def entry(self, item_id):
        for entry in self.entries:
            if entry.item_id == item_id:
                return entry
        return None

    def to_data(self):
        return {
            "schema": "asteria.rpg.shop",
            "version": 1,
            "shop_id": self.shop_id,
            "display_name": self.display_name,
            "entries": [x.to_data() for x in self.entries],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.shop" or data.get("version") != 1:
            raise ValueError("unsupported shop")
        return cls(
            data["shop_id"],
            data["display_name"],
            [ShopEntry.from_data(x) for x in data["entries"]],
        )


@dataclass(frozen=True, slots=True)
class ShopTransaction:
    shop_id: str
    item_id: str
    quantity: int
    currencies: dict  # signed change to the player's currencies


class ShopRuntime:
    """Applies purchases and sales to a player's inventory, currencies and the shop stock.

    ``stock`` is the caller-owned ``{shop_id: {item_id: remaining}}`` mapping
    kept in the save; limited entries start at their defined stock.
    """

    def __init__(self, shops, *, inventory, currencies, stock, condition=None):
        self.shops = shops
        self.inventory = inventory
        self.currencies = currencies
        self.stock = stock
        # ``condition(conditions) -> bool`` evaluates switch / variable conditions; without it
        # every condition holds (plain prices, every entry visible)
        self.condition = condition

    def _holds(self, conditions):
        return all(self.condition([c]) for c in conditions) if self.condition else True

    def visible(self, shop_id, item_id):
        """Whether the entry is offered right now (its ``visible_when`` holds)."""
        return self._holds(self._entry(self._shop(shop_id), item_id).visible_when)

    def visible_entries(self, shop_id):
        return tuple(e for e in self._shop(shop_id).entries if self._holds(e.visible_when))

    def prices(self, shop_id, item_id, side="buy"):
        """Current prices after the entry's matching price rules."""
        entry = self._entry(self._shop(shop_id), item_id)
        base = entry.buy_prices if side == "buy" else entry.sell_prices
        factor = 1.0
        for rule in entry.price_rules:
            if self._holds(rule.conditions):
                factor *= rule.buy_multiplier if side == "buy" else rule.sell_multiplier
        return {k: v * factor for k, v in base.items()}

    def _shop(self, shop_id):
        try:
            return self.shops[str(shop_id)]
        except KeyError:
            raise ShopError(f"unknown shop: {shop_id}") from None

    def _entry(self, shop, item_id):
        entry = shop.entry(str(item_id))
        if entry is None:
            raise ShopError(f"{shop.shop_id} does not deal in {item_id}")
        return entry

    def remaining(self, shop_id, item_id):
        entry = self._entry(self._shop(shop_id), item_id)
        if entry.stock is None:
            return None
        return self.stock.get(shop_id, {}).get(entry.item_id, entry.stock)

    def can_afford(self, prices, quantity):
        return all(self.currencies.get(k, 0.0) >= v * quantity for k, v in prices.items())

    def buy(self, shop_id, item_id, quantity=1):
        shop = self._shop(shop_id)
        entry = self._entry(shop, item_id)
        quantity = int(quantity)
        if quantity < 1:
            raise ShopError("quantity must be >= 1")
        if not entry.buy_prices:
            raise ShopError(f"{shop.shop_id} does not sell {entry.item_id}")
        remaining = self.remaining(shop.shop_id, entry.item_id)
        if remaining is not None and remaining < quantity:
            raise ShopError(f"{shop.shop_id} has only {remaining} {entry.item_id}")
        if not self.visible(shop.shop_id, entry.item_id):
            raise ShopError(f"{shop.shop_id} is not offering {entry.item_id} now")
        buy_prices = self.prices(shop.shop_id, entry.item_id, "buy")
        if not self.can_afford(buy_prices, quantity):
            raise ShopError(f"cannot afford {quantity} {entry.item_id}")
        room = (
            self.inventory.room_for(entry.item_id) if hasattr(self.inventory, "room_for") else None
        )
        if (
            room is not None and room < quantity
        ):  # never charge for items the bag cannot hold (RPG-01 rules)
            raise ShopError(f"no room for {quantity} {entry.item_id} (room for {room})")
        change = {k: -v * quantity for k, v in buy_prices.items()}
        for key, delta in change.items():
            self.currencies[key] = self.currencies.get(key, 0.0) + delta
        self.inventory.add(entry.item_id, quantity)
        if remaining is not None:
            self.stock.setdefault(shop.shop_id, {})[entry.item_id] = remaining - quantity
        return ShopTransaction(shop.shop_id, entry.item_id, quantity, change)

    def sell(self, shop_id, item_id, quantity=1):
        shop = self._shop(shop_id)
        entry = self._entry(shop, item_id)
        quantity = int(quantity)
        if quantity < 1:
            raise ShopError("quantity must be >= 1")
        if not entry.sell_prices:
            raise ShopError(f"{shop.shop_id} does not buy {entry.item_id}")
        if not self.inventory.remove(entry.item_id, quantity):
            raise ShopError(f"not enough {entry.item_id} to sell")
        change = {
            k: v * quantity for k, v in self.prices(shop.shop_id, entry.item_id, "sell").items()
        }
        for key, delta in change.items():
            self.currencies[key] = self.currencies.get(key, 0.0) + delta
        if entry.stock is not None:
            self.stock.setdefault(shop.shop_id, {})[entry.item_id] = (
                self.remaining(shop.shop_id, entry.item_id) + quantity
            )
        return ShopTransaction(shop.shop_id, entry.item_id, quantity, change)
