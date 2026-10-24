"""Workstations: the places the player crafts at (U4).

A workstation is project data: an alchemy table, a forge, a cooking pot... each the author's own.
``station_id`` is what recipes name in their ``station`` and what ``OPEN_CRAFTING`` opens. The
station's screen has a tab per category (recipes with any of the category's tags; a category
without tags holds every recipe left), optionally a disassembly tab (the project's disassembly
recipes), lets the player craft several at once up to ``max_quantity`` and shows undiscovered
recipes as ``???`` rows when ``show_undiscovered`` is on.

``craft_sound`` / ``fail_sound`` play on a success or a failure; ``success_image`` is a
picture flashed over the screen for ``success_seconds`` after a success; ``music`` plays while
the station is open; ``layout`` names the menu layout the screen draws through (empty: the
station's own ``crafting.<station_id>`` when the project has one, else ``crafting``).

A station the project does not define still opens: it has one tab with every recipe it can
make, no disassembly and quantities up to 99.
"""

from __future__ import annotations

from dataclasses import dataclass


def _text(value):
    return str(value or "").strip()


def _tags(values):
    return tuple(sorted({_text(v).lower() for v in values or () if _text(v)}))


@dataclass(frozen=True, slots=True)
class WorkstationCategory:
    """One tab of a station: the recipes with any of ``tags`` (no tags: every recipe the
    other tabs leave)."""

    category_id: str
    display_name: str = ""
    tags: tuple[str, ...] = ()
    icon_id: str = ""

    def __init__(self, category_id, display_name="", tags=(), icon_id=""):
        category_id = _text(category_id)
        if not category_id:
            raise ValueError("a workstation category needs an id")
        object.__setattr__(self, "category_id", category_id)
        object.__setattr__(self, "display_name", _text(display_name) or category_id)
        object.__setattr__(self, "tags", _tags(tags))
        object.__setattr__(self, "icon_id", _text(icon_id))

    def to_data(self):
        return {
            "category_id": self.category_id,
            "display_name": self.display_name,
            "tags": list(self.tags),
            "icon_id": self.icon_id,
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["category_id"],
            data.get("display_name", ""),
            data.get("tags", ()),
            data.get("icon_id", ""),
        )


@dataclass(frozen=True, slots=True)
class WorkstationDefinition:
    station_id: str
    display_name: str = ""
    icon_id: str = ""
    description: str = ""
    categories: tuple[WorkstationCategory, ...] = ()
    show_undiscovered: bool = True
    max_quantity: int = 99
    disassembly: bool = False
    disassembly_tags: tuple[str, ...] = ()
    craft_sound: str = ""
    fail_sound: str = ""
    success_image: str = ""
    success_seconds: float = 0.6
    music: str = ""
    layout: str = ""

    def __init__(
        self,
        station_id,
        display_name="",
        *,
        icon_id="",
        description="",
        categories=(),
        show_undiscovered=True,
        max_quantity=99,
        disassembly=False,
        disassembly_tags=(),
        craft_sound="",
        fail_sound="",
        success_image="",
        success_seconds=0.6,
        music="",
        layout="",
    ):
        station_id = _text(station_id)
        if not station_id:
            raise ValueError("a workstation needs a station_id")
        categories = tuple(
            c if isinstance(c, WorkstationCategory) else WorkstationCategory.from_data(c)
            for c in categories
        )
        ids = [c.category_id for c in categories]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate categories in workstation {station_id}")
        max_quantity = int(max_quantity)
        if max_quantity < 1:
            raise ValueError("max_quantity must be at least 1")
        success_seconds = float(success_seconds)
        if success_seconds < 0:
            raise ValueError("success_seconds must be >= 0")
        object.__setattr__(self, "station_id", station_id)
        object.__setattr__(self, "display_name", _text(display_name) or station_id)
        object.__setattr__(self, "icon_id", _text(icon_id))
        object.__setattr__(self, "description", str(description or ""))
        object.__setattr__(self, "categories", categories)
        object.__setattr__(self, "show_undiscovered", bool(show_undiscovered))
        object.__setattr__(self, "max_quantity", max_quantity)
        object.__setattr__(self, "disassembly", bool(disassembly))
        object.__setattr__(self, "disassembly_tags", _tags(disassembly_tags))
        object.__setattr__(self, "craft_sound", _text(craft_sound))
        object.__setattr__(self, "fail_sound", _text(fail_sound))
        object.__setattr__(self, "success_image", _text(success_image))
        object.__setattr__(self, "success_seconds", success_seconds)
        object.__setattr__(self, "music", _text(music))
        object.__setattr__(self, "layout", _text(layout))

    def category_of(self, recipe):
        """The id of the first category holding ``recipe`` (by its tags), else the first
        category without tags, else None (the station has no category for it)."""
        tags = set(recipe.tags)
        for category in self.categories:
            if category.tags and tags & set(category.tags):
                return category.category_id
        return next((c.category_id for c in self.categories if not c.tags), None)

    def to_data(self):
        return {
            "schema": "asteria.rpg.workstation",
            "version": 1,
            "station_id": self.station_id,
            "display_name": self.display_name,
            "icon_id": self.icon_id,
            "description": self.description,
            "categories": [c.to_data() for c in self.categories],
            "show_undiscovered": self.show_undiscovered,
            "max_quantity": self.max_quantity,
            "disassembly": self.disassembly,
            "disassembly_tags": list(self.disassembly_tags),
            "craft_sound": self.craft_sound,
            "fail_sound": self.fail_sound,
            "success_image": self.success_image,
            "success_seconds": self.success_seconds,
            "music": self.music,
            "layout": self.layout,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema", "asteria.rpg.workstation") != "asteria.rpg.workstation":
            raise ValueError("unsupported workstation")
        keys = (
            "icon_id",
            "description",
            "categories",
            "show_undiscovered",
            "max_quantity",
            "disassembly",
            "disassembly_tags",
            "craft_sound",
            "fail_sound",
            "success_image",
            "success_seconds",
            "music",
            "layout",
        )
        return cls(
            data["station_id"],
            data.get("display_name", ""),
            **{k: data[k] for k in keys if k in data},
        )
