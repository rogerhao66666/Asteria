"""The game menu's pages, as the author sets them (D87): Game Systems ▸ Menu Pages.

``MenuRules`` (the project's first, by id; none = the engine's defaults):

* ``pause_entries`` - the built-in pause entries in their order (``PAUSE_ENTRIES``); an entry a
  game cannot use (Pets without pet species...) is left out. Empty: the engine's order, where
  Status, Items, Equipment and Skills are pages of their own.
* ``stat_graph`` - the progression graph whose ranks the Status page's stat table spends
  points on (STR, DEX, INT, LUK...: one row and one + each). Empty: the first graph tagged
  ``attributes``; ``-`` turns the + off.
* ``stat_columns`` - the stat table's columns, in order (D89): ``rank`` (ranks taken / the
  node's highest), ``total``, ``base``, ``points``, ``gear``, ``gain`` (what one more point
  adds). Empty: every one.
* ``stat_rows`` - the stats of the Status page's detail table, in order. Empty: every stat
  formula's stat (Game Systems ▸ Stat Formulas), then the build's other stats.
* ``stat_groups`` / ``stat_lines`` - the detail table as a table of groups (D89): each line is
  a stat in a group, shown as a ``number``, a ``percent`` (``12%``) or a ``range`` (the value
  ``spread`` percent either way: ``148 ~ 181``, for a damage that rolls), with its own name
  when ``label`` is set. Lines win over ``stat_rows``; a line's group not in ``stat_groups``
  is shown under its id. ``chance`` writes the battle chance the stat gives through the outcome
  check ``check`` (Battle Rules ▸ Outcome Checks): a stat that raises the check's chance shows
  the chance (crit 5% + 0.3% a point), one that lowers it (a defender's evasion) shows how much
  it takes off.
* ``item_categories`` - the Items page's tabs: an item belongs to a tab when it carries any of
  its tags; a tab without tags holds every item. Every bag entry also carries ``item`` or
  ``equipment`` (what kind of record it is). Empty: All, and Items and Equipment when the game
  has both.
* ``item_filters`` - what the Items page's F key narrows the tab to: items with all of the
  filter's tags, and only those usable from the menu when ``usable`` is on. The page always
  starts on "no filter". Empty: one filter, "usable".
* ``item_details`` - how the Items page shows the chosen thing's picture, description and
  facts (D88): ``panel`` beside the list, ``button`` a Details button (and D) that opens it
  over the list, ``off`` not at all.
"""

from __future__ import annotations

from dataclasses import dataclass

# the built-in pause entries (an id the author orders) - project entries (Pause Menu Entries)
# come after them, before Settings
PAUSE_ENTRIES = (
    "resume",
    "status",
    "items",
    "equipment",
    "enhance",
    "skills",
    "pets",
    "quests",
    "crafting",
    "achievements",
    "bestiary",
    "backlog",
    "skill_slots",
    "music",
    "credits",
    "settings",
    "save",
    "load",
    "title",
    "quit",
)
NO_STAT_GRAPH = "-"
ITEM_DETAILS = ("panel", "button", "off")
# share: a 0..1 stat (lifesteal 0.12) written as a percent, 12% (D91)
STAT_FORMATS = ("number", "percent", "range", "chance", "share")
STAT_COLUMNS = ("rank", "total", "base", "points", "gear", "gain")


def _text(value):
    return str(value or "").strip()


def _tags(values):
    if isinstance(values, str):
        values = values.split(",")
    return tuple(dict.fromkeys(t for t in (_text(v) for v in values or ()) if t))


@dataclass(frozen=True, slots=True)
class ItemCategory:
    """A tab of the Items page: the items with any of ``tags`` (none: every item)."""

    category_id: str
    display_name: str = ""
    tags: tuple[str, ...] = ()
    icon_id: str = ""

    def __init__(self, category_id, display_name="", tags=(), icon_id=""):
        category_id = _text(category_id)
        if not category_id:
            raise ValueError("an item category needs an id")
        object.__setattr__(self, "category_id", category_id)
        object.__setattr__(self, "display_name", _text(display_name) or category_id)
        object.__setattr__(self, "tags", _tags(tags))
        object.__setattr__(self, "icon_id", _text(icon_id))

    def holds(self, tags):
        return not self.tags or bool(set(self.tags) & set(tags))

    def to_data(self):
        data = {"category_id": self.category_id, "display_name": self.display_name}
        if self.tags:
            data["tags"] = list(self.tags)
        if self.icon_id:
            data["icon_id"] = self.icon_id
        return data

    @classmethod
    def from_data(cls, data):
        return cls(
            data["category_id"],
            data.get("display_name", ""),
            data.get("tags", ()),
            data.get("icon_id", ""),
        )


@dataclass(frozen=True, slots=True)
class ItemFilter:
    """A narrowing of the Items page: items with all of ``tags``; ``usable`` keeps only those
    the menu can use."""

    filter_id: str
    display_name: str = ""
    tags: tuple[str, ...] = ()
    usable: bool = False

    def __init__(self, filter_id, display_name="", tags=(), usable=False):
        filter_id = _text(filter_id)
        if not filter_id:
            raise ValueError("an item filter needs an id")
        object.__setattr__(self, "filter_id", filter_id)
        object.__setattr__(self, "display_name", _text(display_name) or filter_id)
        object.__setattr__(self, "tags", _tags(tags))
        object.__setattr__(self, "usable", bool(usable))

    def keeps(self, tags, usable):
        return set(self.tags) <= set(tags) and (usable or not self.usable)

    def to_data(self):
        data = {"filter_id": self.filter_id, "display_name": self.display_name}
        if self.tags:
            data["tags"] = list(self.tags)
        if self.usable:
            data["usable"] = True
        return data

    @classmethod
    def from_data(cls, data):
        return cls(
            data["filter_id"],
            data.get("display_name", ""),
            data.get("tags", ()),
            data.get("usable", False),
        )


@dataclass(frozen=True, slots=True)
class StatGroup:
    """A heading of the Status page's detail table (Attack, Defence, Battle...)."""

    group_id: str
    display_name: str = ""

    def __init__(self, group_id, display_name=""):
        group_id = _text(group_id)
        if not group_id:
            raise ValueError("a stat group needs an id")
        object.__setattr__(self, "group_id", group_id)
        object.__setattr__(self, "display_name", _text(display_name) or group_id)

    def to_data(self):
        return {"group_id": self.group_id, "display_name": self.display_name}

    @classmethod
    def from_data(cls, data):
        return cls(data["group_id"], data.get("display_name", ""))


@dataclass(frozen=True, slots=True)
class StatLine:
    """One stat of the Status page's detail table: its group, how it is written (``number``,
    ``percent``, ``range`` of ``spread`` percent either way, ``chance`` through the outcome
    check ``check``) and its own name (``label``)."""

    stat_id: str
    group: str = ""
    format: str = "number"
    spread: float = 0.0
    label: str = ""
    check: str = ""

    def __init__(self, stat_id, group="", format="number", spread=0.0, label="", check=""):
        stat_id = _text(stat_id)
        if not stat_id:
            raise ValueError("a stat line needs a stat")
        format = _text(format) or "number"
        if format not in STAT_FORMATS:
            raise ValueError(f"a stat line's format must be one of {STAT_FORMATS}")
        spread = float(spread or 0.0)
        if not 0.0 <= spread < 100.0:
            raise ValueError("a stat line's spread must be from 0 to below 100 (percent)")
        object.__setattr__(self, "stat_id", stat_id)
        object.__setattr__(self, "group", _text(group))
        object.__setattr__(self, "format", format)
        object.__setattr__(self, "spread", spread)
        object.__setattr__(self, "label", _text(label))
        check = _text(check)
        if format == "chance" and not check:
            raise ValueError("a chance line needs an outcome check")
        object.__setattr__(self, "check", check)

    def text(self, value, check=None):
        """``value`` as this line writes it (``check``: the OutcomeCheck of a chance line)."""
        if self.format == "chance":
            return f"{_short(self.chance(value, check) * 100)}%"
        if self.format == "percent":
            return f"{_short(value)}%"
        if self.format == "share":
            return f"{_short(value * 100)}%"
        if self.format == "range":
            low = value * (1 - self.spread / 100.0)
            high = value * (1 + self.spread / 100.0)
            return f"{_short(low, 0)} ~ {_short(high, 0)}"
        return _short(value)

    def chance(self, value, check):
        """The chance (0..1) ``value`` of this stat gives through ``check``: the check's chance
        when the stat raises it, how much it takes off when the stat lowers it."""
        if check is None:
            return 0.0
        for terms in (check.source_stat_terms, check.target_stat_terms):
            coefficient = (terms or {}).get(self.stat_id)
            if coefficient is None:
                continue
            if coefficient < 0:
                return min(1.0, abs(coefficient * value))
            chance = check.base_chance + coefficient * value
            return max(check.minimum_chance, min(check.maximum_chance, chance))
        return check.base_chance

    def to_data(self):
        data = {"stat_id": self.stat_id}
        if self.group:
            data["group"] = self.group
        if self.format != "number":
            data["format"] = self.format
        if self.spread:
            data["spread"] = self.spread
        if self.label:
            data["label"] = self.label
        if self.check:
            data["check"] = self.check
        return data

    @classmethod
    def from_data(cls, data):
        return cls(
            data["stat_id"],
            data.get("group", ""),
            data.get("format", "number"),
            data.get("spread", 0.0),
            data.get("label", ""),
            data.get("check", ""),
        )


def _short(value, digits=1):
    """A number as a menu writes it: whole numbers plain, else ``digits`` decimals."""
    value = round(float(value), digits)
    return f"{value:g}" if digits else f"{int(round(value))}"


@dataclass(frozen=True, slots=True)
class MenuRules:
    rules_id: str
    display_name: str = ""
    pause_entries: tuple[str, ...] = ()
    stat_graph: str = ""
    stat_rows: tuple[str, ...] = ()
    item_categories: tuple[ItemCategory, ...] = ()
    item_filters: tuple[ItemFilter, ...] = ()
    item_details: str = "panel"
    stat_groups: tuple[StatGroup, ...] = ()
    stat_lines: tuple[StatLine, ...] = ()
    stat_columns: tuple[str, ...] = ()

    def __init__(
        self,
        rules_id,
        display_name="",
        *,
        pause_entries=(),
        stat_graph="",
        stat_rows=(),
        item_categories=(),
        item_filters=(),
        item_details="panel",
        stat_groups=(),
        stat_lines=(),
        stat_columns=(),
    ):
        rules_id = _text(rules_id)
        if not rules_id:
            raise ValueError("menu rules need an id")
        entries = _tags(pause_entries)
        unknown = [e for e in entries if e not in PAUSE_ENTRIES]
        if unknown:
            raise ValueError(f"unknown pause entries: {', '.join(unknown)}")
        categories = tuple(
            c if isinstance(c, ItemCategory) else ItemCategory.from_data(c)
            for c in item_categories or ()
        )
        filters = tuple(
            f if isinstance(f, ItemFilter) else ItemFilter.from_data(f) for f in item_filters or ()
        )
        groups = tuple(
            g if isinstance(g, StatGroup) else StatGroup.from_data(g) for g in stat_groups or ()
        )
        lines = tuple(
            x if isinstance(x, StatLine) else StatLine.from_data(x) for x in stat_lines or ()
        )
        for label, ids in (
            ("stat group", [g.group_id for g in groups]),
            ("item category", [c.category_id for c in categories]),
            ("item filter", [f.filter_id for f in filters]),
        ):
            if len(set(ids)) != len(ids):
                raise ValueError(f"two of the {label} ids are the same")
        s = object.__setattr__
        s(self, "rules_id", rules_id)
        s(self, "display_name", _text(display_name) or rules_id)
        s(self, "pause_entries", entries)
        s(self, "stat_graph", _text(stat_graph))
        s(self, "stat_rows", _tags(stat_rows))
        s(self, "item_categories", categories)
        s(self, "item_filters", filters)
        details = _text(item_details) or "panel"
        if details not in ITEM_DETAILS:
            raise ValueError(f"item_details must be one of {ITEM_DETAILS}")
        s(self, "item_details", details)
        s(self, "stat_groups", groups)
        s(self, "stat_lines", lines)
        columns = _tags(stat_columns)
        unknown = [c for c in columns if c not in STAT_COLUMNS]
        if unknown:
            raise ValueError(f"unknown stat table columns: {', '.join(unknown)}")
        s(self, "stat_columns", columns)

    def columns(self):
        """The stat table's columns: ``stat_columns``, else every one."""
        return self.stat_columns or STAT_COLUMNS

    SCHEMA = "asteria.rpg.menu_rules"
    VERSION = 1

    def to_data(self):
        data = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "rules_id": self.rules_id,
            "display_name": self.display_name,
        }
        if self.pause_entries:
            data["pause_entries"] = list(self.pause_entries)
        if self.stat_graph:
            data["stat_graph"] = self.stat_graph
        if self.stat_rows:
            data["stat_rows"] = list(self.stat_rows)
        if self.item_categories:
            data["item_categories"] = [c.to_data() for c in self.item_categories]
        if self.item_filters:
            data["item_filters"] = [f.to_data() for f in self.item_filters]
        if self.item_details != "panel":
            data["item_details"] = self.item_details
        if self.stat_groups:
            data["stat_groups"] = [g.to_data() for g in self.stat_groups]
        if self.stat_lines:
            data["stat_lines"] = [x.to_data() for x in self.stat_lines]
        if self.stat_columns:
            data["stat_columns"] = list(self.stat_columns)
        return data

    @classmethod
    def from_data(cls, data):
        return cls(
            data["rules_id"],
            data.get("display_name", ""),
            pause_entries=data.get("pause_entries", ()),
            stat_graph=data.get("stat_graph", ""),
            stat_rows=data.get("stat_rows", ()),
            item_categories=data.get("item_categories", ()),
            item_filters=data.get("item_filters", ()),
            item_details=data.get("item_details", "panel"),
            stat_groups=data.get("stat_groups", ()),
            stat_lines=data.get("stat_lines", ()),
            stat_columns=data.get("stat_columns", ()),
        )


def menu_rules(database):
    """The project's menu rules (its first, by id), or None."""
    store = getattr(database, "menu_rules", None) or {}
    return store[sorted(store)[0]] if store else None


__all__ = [
    "ITEM_DETAILS",
    "NO_STAT_GRAPH",
    "PAUSE_ENTRIES",
    "STAT_COLUMNS",
    "STAT_FORMATS",
    "ItemCategory",
    "ItemFilter",
    "MenuRules",
    "StatGroup",
    "StatLine",
    "menu_rules",
]
