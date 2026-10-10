"""Backend-free models for the in-game shop, quest log, pause and game-over screens (ASTERIA_SPEC §29).

A presentation layer draws these rows and forwards named input actions; the
models talk only to :class:`GameSessionRuntime`, so they are testable
without a window.
"""
from __future__ import annotations

from dataclasses import dataclass

PAUSE_OPTIONS = (("resume", "Resume"), ("quests", "Quest Log"), ("save", "Save Game"),
                 ("load", "Load Game"), ("title", "Return to Title"), ("quit", "Quit"))
GAME_OVER_OPTIONS = (("load", "Load Last Save"), ("title", "Return to Title"))


def _price_text(prices):
    return " + ".join(f"{amount:g} {currency}" for currency, amount in sorted(prices.items())) or "—"


class MenuCursor:
    def __init__(self, options):
        self.options = tuple(options)
        self.index = 0

    def move(self, delta):
        if self.options:
            self.index = (self.index + int(delta)) % len(self.options)
        return self.selected

    @property
    def selected(self):
        return self.options[self.index][0] if self.options else None


@dataclass(frozen=True, slots=True)
class ShopRow:
    item_id: str
    name: str
    price: str
    stock: str
    owned: int
    available: bool


class ShopScreen:
    """Buy / sell tabs over the session's open shop."""

    def __init__(self, game):
        self.game = game
        self.tab = "buy"
        self.index = 0
        self.message = ""

    @property
    def shop(self):
        return self.game.project.rpg_database.shops.get(self.game.open_shop_id)

    def rows(self):
        shop = self.shop
        if shop is None:
            return ()
        items = self.game.project.rpg_database.items
        state = self.game.save.rpg_state
        rows = []
        for entry in shop.entries:
            prices = entry.buy_prices if self.tab == "buy" else entry.sell_prices
            if not prices:
                continue
            remaining = self.game.shops.remaining(shop.shop_id, entry.item_id)
            owned = state.inventory.count(entry.item_id)
            if self.tab == "buy":
                available = (remaining is None or remaining > 0) and self.game.shops.can_afford(prices, 1)
            else:
                available = owned > 0
            item = items.get(entry.item_id)
            rows.append(ShopRow(entry.item_id, item.display_name if item else entry.item_id, _price_text(prices),
                                "-" if remaining is None else str(remaining), owned, available))
        return tuple(rows)

    def wallet(self):
        currencies = self.game.save.rpg_state.currencies
        return "  ".join(f"{currencies[k]:g} {k}" for k in sorted(currencies))

    def switch_tab(self):
        self.tab = "sell" if self.tab == "buy" else "buy"
        self.index = 0

    def move(self, delta):
        rows = self.rows()
        if rows:
            self.index = (self.index + int(delta)) % len(rows)

    def confirm(self):
        from asteria.rpg import ShopError

        rows = self.rows()
        if not rows:
            return None
        row = rows[min(self.index, len(rows) - 1)]
        try:
            result = (self.game.buy if self.tab == "buy" else self.game.sell)(row.item_id)
        except ShopError as exc:
            self.message = str(exc)
            return None
        self.message = f"{'Bought' if self.tab == 'buy' else 'Sold'} {row.name}"
        self.index = min(self.index, max(0, len(self.rows()) - 1))
        return result

    def close(self):
        self.game.close_shop()


@dataclass(frozen=True, slots=True)
class QuestRow:
    quest_id: str
    name: str
    status: str
    objectives: tuple  # (description, value, required, done)


def quest_rows(game):
    """Active quests first, then completed and failed ones, with objective progress."""
    log = game.quest_log
    quests = game.project.rpg_database.quests
    order = {"active": 0, "completed": 1, "failed": 2}
    rows = []
    for quest_id, progress in sorted(game.save.rpg_state.quests.items(), key=lambda kv: (order[kv[1].status], kv[0])):
        quest = quests[quest_id]
        objectives = []
        for objective in quest.objectives:
            required = 1 if objective.kind == "switch" else objective.required
            value = min(required, log.objective_value(quest_id, objective))
            objectives.append((objective.description or objective.objective_id, value, required, value >= required))
        rows.append(QuestRow(quest_id, quest.display_name, progress.status, tuple(objectives)))
    return tuple(rows)
