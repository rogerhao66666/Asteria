"""Tags, defined (D91): what each tag of the game means, written as project data.

A tag (``weapon.sword``, ``weak.fire``, ``no_escape``) is a word a record carries - gear, a
job, a passive, a state, an enemy, an encounter - and that rules read: a damage rule hits harder
``when target weak.fire``, a weapon needs ``capability.weapon.sword``, an encounter tagged
``no_escape`` cannot be fled. A definition gives the tag a name and says what it means.

``tag_id`` is one tag or a family: ending in ``*`` it covers every tag starting with the rest
(``rune.*``, ``scheduler:*``). An exact definition wins over a family, a longer family over a
shorter one.

``BUILT_IN`` lists the tags the engine itself reads (the rest mean only what the project's
rules make of them); the editor shows that meaning beside the definition.
"""

from __future__ import annotations

from dataclasses import dataclass

# tag or family the engine reads -> what it does (English; the editor translates it)
BUILT_IN = {
    "no_escape": "On an encounter: the party cannot run from this battle.",
    "scheduler:*": "On an encounter: scheduler:<id> runs the battle with that turn scheduler "
    "(Game Systems ▸ Battle Schedulers).",
    "objective:*": "On an encounter: objective:<id> gives the battle that objective; an "
    "objective some encounter names this way is used only there.",
    "rules:*": "On an encounter: rules:<id> runs the battle with those Battle Rules.",
    "escape:*": "On an encounter: escape:<id> uses those Escape Rules.",
    "stage:*": "On an encounter: stage:<id> lays the battle out with that battle stage.",
    "cures:*": "On an item: cures:<state> removes that state when the item is used.",
    "teaches:*": "On an item: teaches:<skill> teaches a pet that skill.",
    "capture": "On an item: it is a capture item (the creature bag's capture pocket).",
    "weather.*": "Carried in battle: weather.<id> is the battle's weather; rules may read it.",
    "equip.*": "In an event condition: equip.<tag> is true while the party leader wears gear "
    "with that tag.",
}


@dataclass(frozen=True, slots=True)
class TagDefinition:
    tag_id: str
    display_name: str = ""
    description: str = ""
    order: int = 0

    SCHEMA = "asteria.rpg.tag_definition"
    VERSION = 1

    def __init__(self, tag_id, display_name="", *, description="", order=0):
        tag_id = str(tag_id).strip().lower()
        if not tag_id:
            raise ValueError("tag_id is required")
        if "*" in tag_id[:-1]:
            raise ValueError("tag_id: '*' may only end a family (rune.*)")
        s = object.__setattr__
        s(self, "tag_id", tag_id)
        s(self, "display_name", str(display_name or ""))
        s(self, "description", str(description or ""))
        s(self, "order", int(order))

    @property
    def family(self):
        """The prefix a family covers (``rune.``), else ``None``."""
        return self.tag_id[:-1] if self.tag_id.endswith("*") else None

    def covers(self, tag):
        family = self.family
        return tag.startswith(family) if family is not None else tag == self.tag_id

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "tag_id": self.tag_id,
            "display_name": self.display_name,
            "description": self.description,
            "order": self.order,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported tag definition")
        return cls(
            data["tag_id"],
            data.get("display_name", ""),
            description=data.get("description", ""),
            order=data.get("order", 0),
        )


def definition_for(definitions, tag):
    """The definition covering ``tag``: its own, else the longest family; ``None`` if none."""
    tag = str(tag).lower()
    own = definitions.get(tag)
    if own is not None:
        return own
    families = [d for d in definitions.values() if d.family is not None and d.covers(tag)]
    return max(families, key=lambda d: len(d.family), default=None)


def built_in(tag):
    """What the engine itself does with ``tag``, else ``""``."""
    tag = str(tag).lower()
    if tag in BUILT_IN:
        return BUILT_IN[tag]
    for pattern, meaning in BUILT_IN.items():
        if pattern.endswith("*") and tag.startswith(pattern[:-1]):
            return meaning
    return ""


__all__ = ["BUILT_IN", "TagDefinition", "built_in", "definition_for"]
