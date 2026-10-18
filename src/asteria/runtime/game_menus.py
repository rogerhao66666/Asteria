"""Backend-free models for the in-game shop, quest log, pause and game-over screens (ASTERIA_SPEC
§29).

A presentation layer draws these rows and forwards named input actions; the
models talk only to :class:`GameSessionRuntime`, so they are testable
without a window.
"""

from __future__ import annotations

from dataclasses import dataclass

PAUSE_OPTIONS = (
    ("resume", "Resume"),
    ("status", "Status / Items / Equipment / Skills"),
    ("quests", "Quest Log"),
    ("crafting", "Crafting"),
    ("achievements", "Achievements"),
    ("bestiary", "Bestiary"),
    ("settings", "Settings"),
    ("save", "Save Game"),
    ("load", "Load Game"),
    ("title", "Return to Title"),
    ("quit", "Quit"),
)
GAME_OVER_OPTIONS = (("load", "Load Last Save"), ("title", "Return to Title"))


def _price_text(prices):
    return (
        " + ".join(f"{amount:g} {currency}" for currency, amount in sorted(prices.items())) or "—"
    )


class MenuCursor:
    def __init__(self, options, icons=None):
        self.options = tuple(options)
        self.index = 0
        self.icons = dict(icons or {})  # option id -> icon id: rows that show a picture

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
        shops = self.game.shops
        for entry in shops.visible_entries(shop.shop_id):
            prices = shops.prices(shop.shop_id, entry.item_id, self.tab)
            if not prices:
                continue
            remaining = self.game.shops.remaining(shop.shop_id, entry.item_id)
            owned = state.inventory.count(entry.item_id)
            if self.tab == "buy":
                available = (remaining is None or remaining > 0) and self.game.shops.can_afford(
                    prices, 1
                )
            else:
                available = owned > 0
            item = items.get(entry.item_id)
            rows.append(
                ShopRow(
                    entry.item_id,
                    item.display_name if item else entry.item_id,
                    _price_text(prices),
                    "-" if remaining is None else str(remaining),
                    owned,
                    available,
                )
            )
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
    for quest_id, progress in sorted(
        game.save.rpg_state.quests.items(), key=lambda kv: (order[kv[1].status], kv[0])
    ):
        quest = quests[quest_id]
        objectives = []
        for objective in quest.objectives:
            required = 1 if objective.kind == "switch" else objective.required
            value = min(required, log.objective_value(quest_id, objective))
            objectives.append(
                (
                    objective.description or objective.objective_id,
                    value,
                    required,
                    value >= required,
                )
            )
        rows.append(QuestRow(quest_id, quest.display_name, progress.status, tuple(objectives)))
    return tuple(rows)


# --- crafting (recipe discovery), achievements, bestiary, settings --------------


@dataclass(frozen=True, slots=True)
class CraftingRow:
    recipe_id: str
    name: str
    outputs: str
    materials: tuple  # (item name, needed, owned)
    craftable: bool


class CraftingScreen:
    """Known recipes usable at ``station`` (empty: recipes without a station)."""

    def __init__(self, game, station=""):
        self.game = game
        self.station = str(station or "")
        self.index = 0
        self.message = ""

    def _name(self, item_id):
        item = self.game.project.rpg_database.items.get(item_id)
        return item.display_name if item else item_id

    def rows(self):
        inventory = self.game.save.rpg_state.inventory
        rows = []
        for recipe in self.game.known_recipes(self.station):
            if recipe.station and recipe.station != self.station:
                continue
            needed = {}
            for selection in recipe.selections:
                for item_id in selection.item_ids:
                    needed[item_id] = needed.get(item_id, 0) + 1
            materials = tuple(
                (self._name(k), n, inventory.count(k)) for k, n in sorted(needed.items())
            )
            outputs = ", ".join(f"{self._name(o.item_id)} x{o.amount}" for o in recipe.outputs)
            rows.append(
                CraftingRow(
                    recipe.recipe_id,
                    recipe.display_name,
                    outputs,
                    materials,
                    all(have >= need for _, need, have in materials),
                )
            )
        return tuple(rows)

    def undiscovered(self):
        recipes = self.game.project.rpg_database.composition_recipes
        return sum(1 for k in recipes if not self.game.recipe_known(k))

    def move(self, delta):
        rows = self.rows()
        if rows:
            self.index = (self.index + int(delta)) % len(rows)

    def confirm(self, rng=None):
        rows = self.rows()
        if not rows:
            return None
        row = rows[min(self.index, len(rows) - 1)]
        recipe = self.game.project.rpg_database.composition_recipes[row.recipe_id]
        payload = {s.step_id: list(s.item_ids) for s in recipe.selections}
        try:
            result = self.game.craft(payload, station=self.station, rng=rng)
        except ValueError as exc:
            self.message = str(exc)
            return None
        made = ", ".join(f"{self._name(k)} x{n}" for k, n in result.produced) or "nothing"
        if result.success:
            self.message = f"Crafted {made}" + (f" ({result.quality})" if result.quality else "")
        else:
            self.message = f"Crafting failed — got {made}"
        return result

    def close(self):
        self.game.open_crafting_station = None


def achievement_rows(game):
    """``(name, description, unlocked)``; hidden locked achievements show as ???."""
    unlocked = set(game.world.achievements)
    rows = []
    for key, achievement in sorted(game.project.rpg_database.achievements.items()):
        done = key in unlocked
        if achievement.hidden and not done:
            rows.append(("???", "Hidden achievement", False))
        else:
            rows.append((achievement.display_name, achievement.description, done))
    return tuple(rows)


def bestiary_rows(game):
    """``(name, seen, defeated, captured, tags, resources, drops)`` per enemy. Unseen enemies
    show as ???; weaknesses / resistances (``tags``) and resources (``(resource_id, amount)``)
    unlock once one has been defeated; ``drops`` lists only what has really dropped
    (``(display name, times)``)."""
    db = game.project.rpg_database
    rows = []
    for enemy_id, enemy in sorted(db.enemies.items()):
        entry = game.world.bestiary.get(enemy_id)
        if not entry or not entry.get("seen"):
            rows.append(("???", 0, 0, 0, (), (), ()))
            continue
        known = entry.get("defeated", 0) > 0
        drops = []
        for key, times in sorted(entry.items()):
            if not key.startswith("drop:") or times <= 0:
                continue
            item_id = key[5:]
            record = db.items.get(item_id) or db.equipment.get(item_id)
            drops.append((getattr(record, "display_name", "") or item_id, times))
        rows.append(
            (
                enemy.display_name,
                entry.get("seen", 0),
                entry.get("defeated", 0),
                entry.get("captured", 0),
                tuple(t for t in getattr(enemy, "tags", ()) if "." in t) if known else (),
                tuple(sorted(enemy.resources.items())) if known else (),
                tuple(drops),
            )
        )
    return tuple(rows)


@dataclass(slots=True)
class GameSettings:
    """Player preferences, stored outside save files."""

    music_volume: float = 0.8
    effects_volume: float = 0.8
    show_battle_log: bool = True
    input_overrides: dict = (
        None  # ENG-15: action -> [binding data], laid over the project input map
    )

    OPTIONS = (
        ("music_volume", "Music Volume"),
        ("effects_volume", "Effects Volume"),
        ("show_battle_log", "Battle Messages"),
        ("controls", "Controls…"),
        ("back", "Back"),
    )

    def __post_init__(self):
        if self.input_overrides is None:
            self.input_overrides = {}

    def adjust(self, key, delta):
        if key in ("music_volume", "effects_volume"):
            setattr(self, key, round(min(1.0, max(0.0, getattr(self, key) + 0.1 * delta)), 2))
        elif key == "show_battle_log":
            self.show_battle_log = not self.show_battle_log
        return self

    def value_text(self, key):
        if key in ("music_volume", "effects_volume"):
            return f"{round(getattr(self, key) * 100):d}%"
        if key == "show_battle_log":
            return "On" if self.show_battle_log else "Off"
        return ""

    def apply(self, mixer):
        mixer.set_volume("bgm", self.music_volume)
        mixer.set_volume("ambient", self.music_volume)
        mixer.set_volume("sfx", self.effects_volume)

    def to_data(self):
        return {
            "schema": "asteria.game_settings",
            "version": 2,
            "music_volume": self.music_volume,
            "effects_volume": self.effects_volume,
            "show_battle_log": self.show_battle_log,
            "input_overrides": {k: list(v) for k, v in sorted(self.input_overrides.items())},
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.game_settings" or data.get("version") not in (1, 2):
            raise ValueError("unsupported game settings")
        return cls(
            float(data["music_volume"]),
            float(data["effects_volume"]),
            bool(data["show_battle_log"]),
            dict(data.get("input_overrides", {})),
        )

    def save(self, path):
        import json
        from pathlib import Path

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_data(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path):
        import json
        from pathlib import Path

        try:
            return cls.from_data(json.loads(Path(path).read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError):
            return cls()
