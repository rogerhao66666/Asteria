"""Stats, defined (D91): what each number of the game is, written as project data.

A stat id (``str``, ``power``, ``boss_damage``) is any name the data gives a number. A
definition says what that number means: its name and short name (``Strength``, ``STR``), how
it is written (a plain number, a percent, or a 0..1 share written as a percent), the records
whose Base Stats set it (``set_on``: actors, classes, enemies) and a description. How it is
worked out is not kept here but found where it happens - a stat formula, a battle check, a
damage formula - and listed beside the definition by the editor (``Game Systems ▸ Stats``).

``set_on`` only narrows the editor's lists: a Base Stats table offers the stats set on that
kind of record (an actor: STR, DEX, INT, LUK, VIT, SPD), while a stat the data already holds
stays editable there. A project without definitions offers every stat, as before.
"""

from __future__ import annotations

from dataclasses import dataclass

STAT_DISPLAY = ("number", "percent", "share")  # share: 0..1, written x100 as a percent
SET_ON = ("actors", "classes", "enemies")


@dataclass(frozen=True, slots=True)
class StatDefinition:
    stat_id: str
    display_name: str = ""
    short_name: str = ""
    display: str = "number"
    set_on: tuple[str, ...] = ()
    order: int = 0
    description: str = ""

    SCHEMA = "asteria.rpg.stat_definition"
    VERSION = 1

    def __init__(
        self,
        stat_id,
        display_name="",
        *,
        short_name="",
        display="number",
        set_on=(),
        order=0,
        description="",
    ):
        stat_id = str(stat_id).strip()
        if not stat_id:
            raise ValueError("stat_id is required")
        if display not in STAT_DISPLAY:
            raise ValueError(f"display must be one of {', '.join(STAT_DISPLAY)}")
        set_on = tuple(dict.fromkeys(str(x) for x in set_on or ()))
        unknown = [x for x in set_on if x not in SET_ON]
        if unknown:
            raise ValueError(f"set_on: unknown records {', '.join(unknown)}")
        s = object.__setattr__
        s(self, "stat_id", stat_id)
        s(self, "display_name", str(display_name or stat_id))
        s(self, "short_name", str(short_name or ""))
        s(self, "display", display)
        s(self, "set_on", set_on)
        s(self, "order", int(order))
        s(self, "description", str(description or ""))

    @property
    def short(self):
        """The short name (``STR``), else the name."""
        return self.short_name or self.display_name

    def text(self, value):
        """``value`` written the stat's way: ``12`` or ``12.5%``."""
        value = float(value) * (100 if self.display == "share" else 1)
        number = f"{value:.1f}".rstrip("0").rstrip(".")
        return number if self.display == "number" else f"{number}%"

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "stat_id": self.stat_id,
            "display_name": self.display_name,
            "short_name": self.short_name,
            "display": self.display,
            "set_on": list(self.set_on),
            "order": self.order,
            "description": self.description,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported stat definition")
        return cls(
            data["stat_id"],
            data.get("display_name", ""),
            short_name=data.get("short_name", ""),
            display=data.get("display", "number"),
            set_on=data.get("set_on", ()),
            order=data.get("order", 0),
            description=data.get("description", ""),
        )


def ordered(definitions):
    """``definitions`` (a dict by id, or records) by order, then id."""
    values = definitions.values() if hasattr(definitions, "values") else definitions
    return sorted(values, key=lambda d: (d.order, d.stat_id))


def set_on(definitions, record_kind):
    """The stat ids a ``record_kind`` (``actors``...) sets in its Base Stats, in order; ``None``
    when the project defines no stats (every stat is offered then)."""
    if not definitions:
        return None
    return tuple(d.stat_id for d in ordered(definitions) if record_kind in d.set_on)


__all__ = ["SET_ON", "STAT_DISPLAY", "StatDefinition", "ordered", "set_on"]
