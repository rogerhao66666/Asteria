"""The game menu's pages, as the author sets them (D87): Game Systems ▸ Menu Pages.

``MenuRules`` (the project's first, by id; none = the engine's defaults):

* ``pause_entries`` - the built-in pause entries in their order (``PAUSE_ENTRIES``); an entry a
  game cannot use (Pets without pet species...) is left out. Empty: the engine's order, where
  Status, Items, Equipment and Skills are pages of their own.
* ``stat_graph`` - the progression graph whose ranks the Status page's stat table spends
  points on (STR, DEX, INT, LUK...: one row and one + each). Empty: the first graph tagged
  ``attributes``; ``-`` turns the + off.
* ``stat_rows`` - the stats of the Status page's detail table, in order. Empty: every stat
  formula's stat (Game Systems ▸ Stat Formulas), then the build's other stats.
* ``item_categories`` - the Items page's tabs: an item belongs to a tab when it carries any of
  its tags; a tab without tags holds every item. Every bag entry also carries ``item`` or
  ``equipment`` (what kind of record it is). Empty: All, and Items and Equipment when the game
  has both.
* ``item_filters`` - what the Items page's F key narrows the tab to: items with all of the
  filter's tags, and only those usable from the menu when ``usable`` is on. The page always
  starts on "no filter". Empty: one filter, "usable".
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
class MenuRules:
    rules_id: str
    display_name: str = ""
    pause_entries: tuple[str, ...] = ()
    stat_graph: str = ""
    stat_rows: tuple[str, ...] = ()
    item_categories: tuple[ItemCategory, ...] = ()
    item_filters: tuple[ItemFilter, ...] = ()

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
        for label, ids in (
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
        )


def menu_rules(database):
    """The project's menu rules (its first, by id), or None."""
    store = getattr(database, "menu_rules", None) or {}
    return store[sorted(store)[0]] if store else None


__all__ = [
    "NO_STAT_GRAPH",
    "PAUSE_ENTRIES",
    "ItemCategory",
    "ItemFilter",
    "MenuRules",
    "menu_rules",
]
