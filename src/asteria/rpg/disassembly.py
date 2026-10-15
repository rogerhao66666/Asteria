"""Disassembly: break an item down into materials (YEP ItemDisassemble).

A recipe is project data keyed by the item (or equipment) id it breaks down. Each yield has an
amount range and a chance; the whole operation is atomic - the item is taken and the materials
given only when the bag can take the item out.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _text(value):
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class DisassemblyYield:
    item_id: str
    minimum: int = 1
    maximum: int = 1
    chance: float = 1.0

    def __init__(self, item_id, minimum=1, maximum=None, chance=1.0):
        maximum = minimum if maximum is None else maximum
        if int(minimum) < 0 or int(maximum) < int(minimum):
            raise ValueError("yield amounts need 0 <= minimum <= maximum")
        chance = float(chance)
        if not isfinite(chance) or not 0.0 <= chance <= 1.0:
            raise ValueError("chance must be between 0 and 1")
        object.__setattr__(self, "item_id", _text(item_id) or _fail("item_id is required"))
        object.__setattr__(self, "minimum", int(minimum))
        object.__setattr__(self, "maximum", int(maximum))
        object.__setattr__(self, "chance", chance)


@dataclass(frozen=True, slots=True)
class DisassemblyRecipe:
    item_id: str
    yields: tuple[DisassemblyYield, ...] = ()
    fee_currency: str = ""
    fee: float = 0.0

    def __init__(self, item_id, yields=(), *, fee_currency="", fee=0.0):
        yields = tuple(yields)
        if any(not isinstance(x, DisassemblyYield) for x in yields):
            raise TypeError("yields must be DisassemblyYield values")
        fee = float(fee)
        if not isfinite(fee) or fee < 0:
            raise ValueError("fee must be finite and >= 0")
        object.__setattr__(self, "item_id", _text(item_id) or _fail("item_id is required"))
        object.__setattr__(self, "yields", yields)
        object.__setattr__(self, "fee_currency", _text(fee_currency))
        object.__setattr__(self, "fee", fee)

    def roll(self, rng):
        """The materials one disassembly gives: ``{item id: amount}``."""
        result = {}
        for entry in self.yields:
            if rng.random() < entry.chance:
                amount = rng.randint(entry.minimum, entry.maximum)
                if amount:
                    result[entry.item_id] = result.get(entry.item_id, 0) + amount
        return result

    def to_data(self):
        return {
            "item_id": self.item_id,
            "yields": [
                {
                    "item_id": y.item_id,
                    "minimum": y.minimum,
                    "maximum": y.maximum,
                    "chance": y.chance,
                }
                for y in self.yields
            ],
            "fee_currency": self.fee_currency,
            "fee": self.fee,
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["item_id"],
            tuple(DisassemblyYield(**y) for y in data.get("yields", ())),
            fee_currency=data.get("fee_currency", ""),
            fee=data.get("fee", 0.0),
        )


@dataclass(frozen=True, slots=True)
class DisassemblyResult:
    done: bool
    gained: tuple[tuple[str, int], ...] = ()
    reason: str = ""


def disassemble(recipe, inventory, currencies, rng):
    """Break one ``recipe.item_id`` out of ``inventory``; returns a ``DisassemblyResult``."""
    if inventory.count(recipe.item_id) < 1:
        return DisassemblyResult(False, reason="not_in_inventory")
    if recipe.fee and currencies.get(recipe.fee_currency, 0.0) < recipe.fee:
        return DisassemblyResult(False, reason="cannot_afford")
    gained = recipe.roll(rng)
    inventory.remove(recipe.item_id, 1)
    if recipe.fee:
        currencies[recipe.fee_currency] = currencies.get(recipe.fee_currency, 0.0) - recipe.fee
    for item_id, amount in gained.items():
        inventory.add(item_id, amount)
    return DisassemblyResult(True, tuple(sorted(gained.items())))


def _fail(message):
    raise ValueError(message)
