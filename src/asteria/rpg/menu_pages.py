"""Menu pages built from blocks (D96): Game Systems ▸ Menu Pages.

A ``MenuPage`` is one screen of the game menu: a name, an icon and its ``blocks`` in order.
Each ``MenuBlock`` is a kind of content with its own settings and a ``place`` on the page
(``left`` / ``right`` column, or ``full`` width) and a ``height`` (0: share what is left of its
column):

* ``profile`` - the member: name, level and jobs, experience and a bar per resource.
* ``stat_points`` - the stat table with a + per stat: ``stat_graph`` (the progression graph the
  points are spent in; empty: the first graph tagged ``attributes``; ``-``: no +) and
  ``stat_columns`` (``rpg.menu_rules.STAT_COLUMNS``; empty: every one).
* ``stat_details`` - the detail table: ``stat_rows`` or ``stat_groups`` / ``stat_lines``.
* ``item_list`` - the bag: ``item_categories`` (tabs), ``item_filters`` (F) and
  ``item_details`` (``panel`` / ``button`` / ``off``).

The Status and Items entries of the pause menu open the pages ``status`` and ``items``; every
other page is a pause entry of its own (``page:<id>``), ordered by Game Systems ▸ Pause Menu
like the built-in ones. A project without pages uses ``default_pages`` - the same screens the
engine drew before pages existed - and D87-D89 settings written on the Pause Menu record
(``MenuRules``) still fill them (``menu_pages``).
"""

from __future__ import annotations

from dataclasses import dataclass

from .menu_rules import (
    ITEM_DETAILS,
    PAUSE_ENTRIES,
    STAT_COLUMNS,
    ItemCategory,
    ItemFilter,
    MenuRules,
    StatGroup,
    StatLine,
    menu_rules,
    pause_order,
)

BLOCK_KINDS = ("profile", "stat_points", "stat_details", "item_list")
BLOCK_PLACES = ("left", "right", "full")
# the settings each kind reads; a block keeps only its own kind's
BLOCK_SETTINGS = {
    "profile": (),
    "stat_points": ("stat_graph", "stat_columns"),
    "stat_details": ("stat_rows", "stat_groups", "stat_lines"),
    "item_list": ("item_categories", "item_filters", "item_details"),
}
# the blocks a page's cursor and keys work in (one per page: the first of these)
INTERACTIVE = ("item_list", "stat_points")
PAGE_ENTRY = "page:"  # a pause entry that opens a project page: ``page:<id>``
MENU_ENTRY = "entry:"  # a Pause Menu Entry (runs an event program): ``entry:<id>``
# the built-in pause entries a game shows only when it has what they open (D97)
PAUSE_NEEDS = {
    "equipment": "the party has equipment slots",
    "enhance": "equipment has refining, sockets or growth",
    "skills": "the game has skills or progression graphs",
    "pets": "the game has pet species",
    "backlog": "Message Settings keep a backlog",
    "skill_slots": "the game has Ability Slot Rules",
    "music": "the game has music tracks",
    "credits": "the game has credits pages",
}
BUILT_IN_PAGES = ("status", "items")


def _text(value):
    return str(value or "").strip()


def _ids(values):
    if isinstance(values, str):
        values = values.split(",")
    return tuple(dict.fromkeys(t for t in (_text(v) for v in values or ()) if t))


def _records(values, cls):
    return tuple(v if isinstance(v, cls) else cls.from_data(v) for v in values or ())


@dataclass(frozen=True, slots=True)
class MenuBlock:
    kind: str
    place: str = "full"
    height: int = 0  # pixels of a 720-high screen; 0: share what is left of its column
    stat_graph: str = ""
    stat_columns: tuple[str, ...] = ()
    stat_rows: tuple[str, ...] = ()
    stat_groups: tuple[StatGroup, ...] = ()
    stat_lines: tuple[StatLine, ...] = ()
    item_categories: tuple[ItemCategory, ...] = ()
    item_filters: tuple[ItemFilter, ...] = ()
    item_details: str = "panel"

    def __init__(
        self,
        kind,
        place="full",
        height=0,
        *,
        stat_graph="",
        stat_columns=(),
        stat_rows=(),
        stat_groups=(),
        stat_lines=(),
        item_categories=(),
        item_filters=(),
        item_details="panel",
    ):
        kind = _text(kind)
        if kind not in BLOCK_KINDS:
            raise ValueError(f"a menu block's kind must be one of {', '.join(BLOCK_KINDS)}")
        place = _text(place) or "full"
        if place not in BLOCK_PLACES:
            raise ValueError(f"a menu block's place must be one of {', '.join(BLOCK_PLACES)}")
        height = int(height or 0)
        if height < 0:
            raise ValueError("a menu block's height cannot be negative")
        columns = _ids(stat_columns)
        unknown = [c for c in columns if c not in STAT_COLUMNS]
        if unknown:
            raise ValueError(f"unknown stat table columns: {', '.join(unknown)}")
        details = _text(item_details) or "panel"
        if details not in ITEM_DETAILS:
            raise ValueError(f"item_details must be one of {ITEM_DETAILS}")
        s = object.__setattr__
        s(self, "kind", kind)
        s(self, "place", place)
        s(self, "height", height)
        own = BLOCK_SETTINGS[kind]  # another kind's settings are not kept
        s(self, "stat_graph", _text(stat_graph) if "stat_graph" in own else "")
        s(self, "stat_columns", columns if "stat_columns" in own else ())
        s(self, "stat_rows", _ids(stat_rows) if "stat_rows" in own else ())
        groups = _records(stat_groups, StatGroup) if "stat_groups" in own else ()
        s(self, "stat_groups", groups)
        s(self, "stat_lines", _records(stat_lines, StatLine) if "stat_lines" in own else ())
        tabs = _records(item_categories, ItemCategory) if "item_categories" in own else ()
        s(self, "item_categories", tabs)
        filters = _records(item_filters, ItemFilter) if "item_filters" in own else ()
        s(self, "item_filters", filters)
        s(self, "item_details", details if "item_details" in own else "panel")
        for label, ids in (
            ("stat group", [g.group_id for g in self.stat_groups]),
            ("item category", [c.category_id for c in self.item_categories]),
            ("item filter", [f.filter_id for f in self.item_filters]),
        ):
            if len(set(ids)) != len(ids):
                raise ValueError(f"two of the {label} ids are the same")

    def to_data(self):
        data = {"kind": self.kind, "place": self.place}
        if self.height:
            data["height"] = self.height
        for key in BLOCK_SETTINGS[self.kind]:
            value = getattr(self, key)
            if key == "item_details":
                if value != "panel":
                    data[key] = value
            elif isinstance(value, tuple) and value and hasattr(value[0], "to_data"):
                data[key] = [v.to_data() for v in value]
            elif value:
                data[key] = list(value) if isinstance(value, tuple) else value
        return data

    @classmethod
    def from_data(cls, data):
        return cls(
            data["kind"],
            data.get("place", "full"),
            data.get("height", 0),
            **{k: data[k] for k in BLOCK_SETTINGS.get(data["kind"], ()) if k in data},
        )


@dataclass(frozen=True, slots=True)
class MenuPage:
    page_id: str
    display_name: str = ""
    icon_id: str = ""
    blocks: tuple[MenuBlock, ...] = ()

    SCHEMA = "asteria.rpg.menu_page"
    VERSION = 1

    def __init__(self, page_id, display_name="", icon_id="", blocks=()):
        page_id = _text(page_id)
        if not page_id:
            raise ValueError("a menu page needs an id")
        s = object.__setattr__
        s(self, "page_id", page_id)
        s(self, "display_name", _text(display_name) or page_id)
        s(self, "icon_id", _text(icon_id))
        s(self, "blocks", _records(blocks, MenuBlock))

    def block(self, kind):
        """The page's first block of ``kind``, or None."""
        return next((b for b in self.blocks if b.kind == kind), None)

    def interactive(self):
        """The kind of block the page's cursor and keys work in (``item_list`` first), or
        ``""`` for a page only to look at."""
        return next((k for k in INTERACTIVE if self.block(k) is not None), "")

    def rules(self, pause=None):
        """The page's settings as one ``MenuRules`` (what the menu screen reads): each setting
        from the page's first block of its kind; ``pause``'s entries kept."""
        values = {}
        for kind, keys in BLOCK_SETTINGS.items():
            block = self.block(kind)
            for key in keys:
                if block is not None:
                    values[key] = getattr(block, key)
        entries = pause.pause_entries if pause is not None else ()
        return MenuRules(self.page_id, self.display_name, pause_entries=entries, **values)

    def to_data(self):
        data = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "page_id": self.page_id,
            "display_name": self.display_name,
        }
        if self.icon_id:
            data["icon_id"] = self.icon_id
        data["blocks"] = [b.to_data() for b in self.blocks]
        return data

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported menu page")
        return cls(
            data["page_id"],
            data.get("display_name", ""),
            data.get("icon_id", ""),
            data.get("blocks", ()),
        )


def default_pages(rules=None):
    """The Status and Items pages as the engine drew them before pages (D87-D89), filled from
    ``rules``' settings when given (a project written before D96)."""
    r = rules or MenuRules("default")
    status = MenuPage(
        "status",
        "Status",
        blocks=(
            MenuBlock("profile", "left", 190),
            MenuBlock("stat_points", "left", stat_graph=r.stat_graph, stat_columns=r.stat_columns),
            MenuBlock(
                "stat_details",
                "right",
                stat_rows=r.stat_rows,
                stat_groups=r.stat_groups,
                stat_lines=r.stat_lines,
            ),
        ),
    )
    items = MenuPage(
        "items",
        "Items",
        blocks=(
            MenuBlock(
                "item_list",
                item_categories=r.item_categories,
                item_filters=r.item_filters,
                item_details=r.item_details,
            ),
        ),
    )
    return {"status": status, "items": items}


def menu_pages(database):
    """``{page_id: MenuPage}``: the project's pages (Game Systems ▸ Menu Pages), with the
    built-in Status and Items pages for those it leaves out."""
    pages = default_pages(menu_rules(database))
    pages.update(getattr(database, "menu_pages", None) or {})
    return pages


# what each built-in pause entry opens (Game Systems ▸ Pause Menu says it beside the entry)
PAUSE_OPENS = {
    "resume": "Closes the menu and goes back to the game.",
    "status": "Opens the menu page status: the member's profile, stat points and details.",
    "items": "Opens the menu page items: the bag with its tabs and filters.",
    "equipment": "Opens the equipment screen (paper doll) to change the party's gear.",
    "enhance": "Opens the enhance screen: refining, sockets and growth of equipment.",
    "skills": "Opens the member's skill tree, or the list of skills without one.",
    "pets": "Opens the pets screen.",
    "quests": "Opens the quest log.",
    "crafting": "Opens crafting with every recipe the party knows.",
    "achievements": "Opens the list of achievements.",
    "bestiary": "Opens the bestiary: the enemies met and what they drop.",
    "backlog": "Opens the log of the messages read so far.",
    "skill_slots": "Opens the ability slots: which skills each member has ready.",
    "music": "Opens the music room: the tracks heard so far.",
    "credits": "Opens the credits pages.",
    "settings": "Opens the settings: volume, text speed, language, controls.",
    "save": "Opens the save slots.",
    "load": "Opens the save slots to load one.",
    "title": "Goes back to the title screen.",
    "quit": "Closes the game.",
}


def usable_pause_entries(database, *, loadouts, backlog, abilities):
    """The pause entries the game shows (``PAUSE_NEEDS``): ``loadouts`` - the party has
    equipment slots, ``backlog`` - the message backlog's length, ``abilities`` - the game has
    skills. The project's own pages and entries are always usable."""
    db = database
    usable = set(PAUSE_ENTRIES) - set(PAUSE_NEEDS)
    if loadouts:
        usable.add("equipment")
        if db.refine_rules or any(e.sockets or e.growth_id for e in db.equipment.values()):
            usable.add("enhance")
    if db.progression_graphs or abilities:
        usable.add("skills")
    for entry, present in (
        ("pets", getattr(db, "pet_species", None)),
        ("backlog", backlog),
        ("skill_slots", db.ability_loadout_rules),
        ("music", db.music_tracks),
        ("credits", db.credits_pages),
    ):
        if present:
            usable.add(entry)
    usable.update(page_entries(db))
    usable.update(f"{MENU_ENTRY}{e}" for e in db.menu_entries)
    return usable


def engine_pause_order(database):
    """Every pause entry in the engine's order: the built-in ones, the project's own pages
    after Items and its Pause Menu Entries (by their Order) before Settings."""
    at = PAUSE_ENTRIES.index("items") + 1
    order = [*PAUSE_ENTRIES[:at], *page_entries(database), *PAUSE_ENTRIES[at:]]
    entries = sorted(database.menu_entries.values(), key=lambda e: (e.order, e.entry_id))
    at = order.index("settings")
    order[at:at] = [f"{MENU_ENTRY}{e.entry_id}" for e in entries]
    return order


def pause_menu(database, usable=None):
    """The pause menu's entries top to bottom (Game Systems ▸ Pause Menu): the author's order,
    without the hidden ones and, given ``usable``, those the game cannot use."""
    rules = menu_rules(database)
    entries, hidden = (rules.pause_entries, rules.pause_hidden) if rules else ((), ())
    order = pause_order(entries, engine_pause_order(database))
    return [e for e in order if e not in hidden and (usable is None or e in usable)]


def page_entries(database):
    """The pause entries of the project's own pages (not Status and Items): ``page:<id>``."""
    own = getattr(database, "menu_pages", None) or {}
    return [f"{PAGE_ENTRY}{k}" for k in sorted(own) if k not in BUILT_IN_PAGES]


__all__ = [
    "BLOCK_KINDS",
    "BLOCK_PLACES",
    "BLOCK_SETTINGS",
    "BUILT_IN_PAGES",
    "MENU_ENTRY",
    "PAGE_ENTRY",
    "PAUSE_NEEDS",
    "PAUSE_OPENS",
    "MenuBlock",
    "MenuPage",
    "default_pages",
    "engine_pause_order",
    "menu_pages",
    "page_entries",
    "pause_menu",
    "usable_pause_entries",
]
