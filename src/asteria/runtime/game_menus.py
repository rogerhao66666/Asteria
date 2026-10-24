"""Backend-free models for the in-game shop, quest log, pause and game-over screens (ASTERIA_SPEC
§29).

A presentation layer draws these rows and forwards named input actions; the
models talk only to :class:`GameSessionRuntime`, so they are testable
without a window.
"""

from __future__ import annotations

from dataclasses import dataclass

from asteria.rpg.built_in_text import translated

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


def text_keys(prefix, options):
    """The translation key of each fixed menu option: ``pause.resume`` for ("resume", ...)
    (``rpg.built_in_text``); the option's own label is the English shown without one."""
    return {option_id: f"{prefix}.{option_id}" for option_id, _ in options}


def _price_text(prices, names=None):
    """``"30 gold + 2 gems"``; ``names`` words a currency id (D60: its translation)."""
    names = names or {}
    return (
        " + ".join(
            f"{amount:g} {names.get(currency, currency)}"
            for currency, amount in sorted(prices.items())
        )
        or "—"
    )


class MenuCursor:
    def __init__(self, options, icons=None, keys=None):
        self.options = tuple(options)
        self.index = 0
        self.icons = dict(icons or {})  # option id -> icon id: rows that show a picture
        self.keys = dict(keys or {})  # option id -> translation key (a built-in label)

    def labels(self, tr):
        """``(option id, label)`` as the player reads them: built-in labels through ``tr``
        (``GameSessionRuntime.tr``), a project's own (menu entries) as written."""
        return tuple(
            (key, tr(self.keys[key], label) if key in self.keys else label)
            for key, label in self.options
        )

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
        gear = self.game.project.rpg_database.equipment  # a shop may sell equipment (D61)
        names = self.game.currency_names()  # once per list, not once per row
        state = self.game.save.rpg_state
        rows = []
        shops = self.game.shops
        for entry in shops.visible_entries(shop.shop_id):
            prices = shops.prices(shop.shop_id, entry.item_id, self.tab)
            if not prices:
                continue
            remaining = self.game.shops.remaining(shop.shop_id, entry.item_id)
            if entry.item_id in gear:  # equipment: the pieces in the equipment bag
                owned = sum(
                    1 for g in state.equipment_bag if g.equipment.equipment_id == entry.item_id
                )
            else:
                owned = state.inventory.count(entry.item_id)
            if self.tab == "buy":
                available = (remaining is None or remaining > 0) and self.game.shops.can_afford(
                    prices, 1
                )
            else:
                available = owned > 0
            item = items.get(entry.item_id) or gear.get(entry.item_id)
            rows.append(
                ShopRow(
                    entry.item_id,
                    self.game.name_of(item, entry.item_id),
                    _price_text(prices, names),
                    "-" if remaining is None else str(remaining),
                    owned,
                    available,
                )
            )
        return tuple(rows)

    def wallet(self):
        currencies = self.game.save.rpg_state.currencies
        names = self.game.currency_names()
        return "  ".join(f"{currencies[k]:g} {names.get(k, k)}" for k in sorted(currencies))

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
            self.message = translated(exc, self.game.tr)
            return None
        if self.tab == "buy":
            self.message = self.game.tr("shop.bought", "Bought {name}", name=row.name)
        else:
            self.message = self.game.tr("shop.sold", "Sold {name}", name=row.name)
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


def objective_words(game, objective):
    """What an objective without a description asks, made from its kind and target:
    "Defeat Acolyte", "Collect Iron Ore", else its id in words (U1)."""
    from asteria.rpg.data_text import words

    db = game.project.rpg_database
    if objective.kind == "defeat_enemy" and objective.target in db.enemies:
        name = game.name_of(db.enemies[objective.target], objective.target)
        return game.tr("quests.objective.defeat", "Defeat {name}", name=name)
    if objective.kind == "item":
        record = db.items.get(objective.target) or db.equipment.get(objective.target)
        if record is not None:
            name = game.name_of(record, objective.target)
            return game.tr("quests.objective.item", "Collect {name}", name=name)
    return words(objective.objective_id)


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
                    game.description_of(objective) or objective_words(game, objective),
                    value,
                    required,
                    value >= required,
                )
            )
        name = game.name_of(quest)
        rows.append(QuestRow(quest_id, name, progress.status, tuple(objectives)))
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
        return self.game.name_of(item, item_id)

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
                    self.game.name_of(recipe),
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
            self.message = translated(exc, self.game.tr)
            return None
        tr = self.game.tr
        made = ", ".join(f"{self._name(k)} x{n}" for k, n in result.produced)
        made = made or tr("crafting.nothing", "nothing")
        if result.success and result.quality:
            self.message = tr(
                "crafting.crafted_quality",
                "Crafted {items} ({quality})",
                items=made,
                quality=result.quality,
            )
        elif result.success:
            self.message = tr("crafting.crafted", "Crafted {items}", items=made)
        else:
            self.message = tr("crafting.failed", "Crafting failed — got {items}", items=made)
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
            rows.append(
                (
                    game.tr("achievements.hidden_name", "???"),
                    game.tr("achievements.hidden", "Hidden achievement"),
                    False,
                )
            )
        else:
            rows.append((game.name_of(achievement), game.description_of(achievement), done))
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
            rows.append((game.tr("bestiary.unseen", "???"), 0, 0, 0, (), (), ()))
            continue
        known = entry.get("defeated", 0) > 0
        drops = []
        for key, times in sorted(entry.items()):
            if not key.startswith("drop:") or times <= 0:
                continue
            item_id = key[5:]
            record = db.items.get(item_id) or db.equipment.get(item_id)
            drops.append((game.name_of(record, item_id) or item_id, times))
        rows.append(
            (
                game.name_of(enemy),
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
    # U3: the build-test menu (C) only for a player who turns it on in Settings
    developer_menu: bool = False

    OPTIONS = (
        ("music_volume", "Music Volume"),
        ("effects_volume", "Effects Volume"),
        ("show_battle_log", "Battle Messages"),
        ("developer_menu", "Developer Menu"),
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
        elif key == "developer_menu":
            self.developer_menu = not self.developer_menu
        return self

    def value_text(self, key, tr=None):
        """The value shown beside an option; ``tr`` (``GameSessionRuntime.tr``) words On / Off
        in the player's language."""
        if key in ("music_volume", "effects_volume"):
            return f"{round(getattr(self, key) * 100):d}%"
        if key in ("show_battle_log", "developer_menu"):
            on = getattr(self, key)
            if tr is None:
                return "On" if on else "Off"
            return tr("settings.on", "On") if on else tr("settings.off", "Off")
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
            "developer_menu": self.developer_menu,
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
            bool(data.get("developer_menu", False)),
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
