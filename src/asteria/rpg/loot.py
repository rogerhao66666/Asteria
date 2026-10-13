"""Loot (ASTERIA_SPEC §23, §35 ARPG loot): authored rarities, random affixes, rolled equipment.

Nothing here is one game's loot system. A project authors:

* ``RarityDefinition`` records — name, label colour, how many random affixes an item of that
  rarity rolls, its weight
  when a rarity is rolled, its sort order. A rarity with ``max_affixes`` 0 (a "unique" or a plain
  item) keeps exactly
  the equipment's authored modifiers.
* ``AffixDefinition`` records — a prefix or suffix (or any authored ``position``), which equipment
  it may appear on
  (``allowed_tags`` / ``slots``), the item levels it appears at, its weight, an exclusive
  ``group``, and modifiers whose
  values roll inside ``[minimum, maximum]`` (optionally whole numbers, optionally scaled by item
  level).

``roll_rarity`` and ``roll_equipment`` turn them into an ``EquippedItem`` carrying ``item_level``,
``rarity`` and
``rolled_affixes``; its stat modifiers join the build exactly like the equipment's own
(``EquippedItem.modifiers()``),
and the rolls are saved with the instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from asteria.gameplay.modifiers import ModifierOperation, StatModifier


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _num(value, label, *, minimum=None):
    value = float(value)
    if not isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError(
            f"{label} must be a finite number" + ("" if minimum is None else f" >= {minimum}")
        )
    return value


@dataclass(frozen=True, slots=True)
class RarityDefinition:
    rarity_id: str
    display_name: str = ""
    color: str = "#ffffff"  # label / name colour, "#rrggbb"
    min_affixes: int = 0
    max_affixes: int = 0
    weight: float = (
        1.0  # chance when a rarity is rolled (0 = never rolled, only given by drop entries)
    )
    order: int = 0  # sorting and "at least this rare" filters
    max_prefixes: int = -1  # -1 = no separate limit
    max_suffixes: int = -1

    def __post_init__(self):
        object.__setattr__(self, "rarity_id", _id(self.rarity_id, "rarity_id"))
        object.__setattr__(self, "display_name", str(self.display_name or self.rarity_id))
        color = str(self.color)
        if len(color) != 7 or not color.startswith("#"):
            raise ValueError("color must be #rrggbb")
        int(color[1:], 16)
        if not 0 <= int(self.min_affixes) <= int(self.max_affixes):
            raise ValueError("affix counts must satisfy 0 <= min_affixes <= max_affixes")
        object.__setattr__(self, "min_affixes", int(self.min_affixes))
        object.__setattr__(self, "max_affixes", int(self.max_affixes))
        object.__setattr__(self, "weight", _num(self.weight, "weight", minimum=0.0))
        object.__setattr__(self, "order", int(self.order))
        object.__setattr__(self, "max_prefixes", int(self.max_prefixes))
        object.__setattr__(self, "max_suffixes", int(self.max_suffixes))

    def rgb(self):
        return tuple(int(self.color[i : i + 2], 16) for i in (1, 3, 5))

    def to_data(self):
        return {
            "schema": "asteria.rpg.rarity",
            "version": 1,
            **{k: getattr(self, k) for k in self.__dataclass_fields__},
        }

    @classmethod
    def from_data(cls, data):
        data = dict(data)
        if data.pop("schema", None) != "asteria.rpg.rarity" or data.pop("version", None) != 1:
            raise ValueError("unsupported rarity")
        return cls(**data)


DEFAULT_RARITIES = (
    RarityDefinition("common", "Common", "#e6e6e6", 0, 0, 60.0, 0),
    RarityDefinition("uncommon", "Uncommon", "#6fd36f", 1, 2, 25.0, 1),
    RarityDefinition("rare", "Rare", "#5aa0ff", 3, 4, 10.0, 2),
    RarityDefinition("epic", "Epic", "#c070ff", 4, 5, 4.0, 3),
    RarityDefinition("legendary", "Legendary", "#ffa030", 5, 6, 1.0, 4),
)


@dataclass(frozen=True, slots=True)
class AffixModifier:
    stat: str
    operation: str = "add"  # ModifierOperation value
    minimum: float = 0.0
    maximum: float = 0.0
    integer: bool = False
    per_level: float = 0.0  # added to both ends per item level above 1

    def __post_init__(self):
        object.__setattr__(self, "stat", _id(self.stat, "affix modifier stat"))
        ModifierOperation(self.operation)
        lo, hi = _num(self.minimum, "minimum"), _num(self.maximum, "maximum")
        if hi < lo:
            raise ValueError("affix modifier maximum must be >= minimum")
        object.__setattr__(self, "minimum", lo)
        object.__setattr__(self, "maximum", hi)
        object.__setattr__(self, "integer", bool(self.integer))
        object.__setattr__(self, "per_level", _num(self.per_level, "per_level"))

    def roll(self, rng, item_level):
        bonus = self.per_level * max(0, int(item_level) - 1)
        lo, hi = self.minimum + bonus, self.maximum + bonus
        if self.integer:
            return float(rng.randint(int(round(lo)), int(round(hi))))
        return lo + (hi - lo) * rng.random()

    def to_data(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class AffixDefinition:
    affix_id: str
    display_name: str = ""  # shown before (prefix) or after (suffix) the base name
    position: str = "prefix"  # "prefix", "suffix" — or any authored position name
    modifiers: tuple = ()  # AffixModifier
    allowed_tags: tuple = ()  # equipment must carry one of these tags (empty = any)
    slots: tuple = ()  # equipment slot ids it may appear on (empty = any)
    min_level: int = 1
    max_level: int = 0  # 0 = no upper limit
    weight: float = 1.0
    group: str = ""  # one affix per group on an item (e.g. two "+life" tiers)
    rarities: tuple = ()  # only on items of these rarities (empty = any)

    def __post_init__(self):
        object.__setattr__(self, "affix_id", _id(self.affix_id, "affix_id"))
        object.__setattr__(self, "display_name", str(self.display_name or self.affix_id))
        object.__setattr__(self, "position", _id(self.position, "position"))
        modifiers = tuple(
            m if isinstance(m, AffixModifier) else AffixModifier(**dict(m)) for m in self.modifiers
        )
        object.__setattr__(self, "modifiers", modifiers)
        for name in ("allowed_tags", "slots", "rarities"):
            object.__setattr__(self, name, tuple(str(x) for x in getattr(self, name)))
        if int(self.min_level) < 0 or int(self.max_level) < 0:
            raise ValueError("affix levels must be >= 0")
        object.__setattr__(self, "min_level", int(self.min_level))
        object.__setattr__(self, "max_level", int(self.max_level))
        object.__setattr__(self, "weight", _num(self.weight, "weight", minimum=0.0))
        object.__setattr__(self, "group", str(self.group))

    def fits(self, equipment, item_level, rarity_id):
        if item_level < self.min_level or (self.max_level and item_level > self.max_level):
            return False
        if self.slots and equipment.slot not in self.slots:
            return False
        if self.allowed_tags and not set(self.allowed_tags) & set(equipment.tags):
            return False
        return not self.rarities or rarity_id in self.rarities

    def to_data(self):
        data = {"schema": "asteria.rpg.affix", "version": 1}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            data[name] = (
                [m.to_data() for m in value]
                if name == "modifiers"
                else list(value)
                if isinstance(value, tuple)
                else value
            )
        return data

    @classmethod
    def from_data(cls, data):
        data = dict(data)
        if data.pop("schema", None) != "asteria.rpg.affix" or data.pop("version", None) != 1:
            raise ValueError("unsupported affix")
        return cls(**data)


@dataclass(frozen=True, slots=True)
class RolledAffix:
    """One affix as it rolled on one item. It keeps its own ``(stat, operation, value)`` entries,
    so the item stays
    exactly as it dropped even if the affix is edited later (and saves need no lookup)."""

    affix_id: str
    entries: tuple  # ((stat, operation, value), ...)

    def modifiers(self, instance_id):
        return tuple(
            StatModifier(f"{instance_id}:{self.affix_id}:{index}", stat, operation, value)
            for index, (stat, operation, value) in enumerate(self.entries)
        )

    def to_data(self):
        return {"affix_id": self.affix_id, "entries": [list(e) for e in self.entries]}

    @classmethod
    def from_data(cls, data):
        return cls(
            str(data["affix_id"]), tuple((str(s), str(o), float(v)) for s, o, v in data["entries"])
        )


def _weighted(rng, entries):
    total = sum(w for _, w in entries)
    if total <= 0:
        return None
    pick = rng.random() * total
    for value, weight in entries:
        if pick < weight:
            return value
        pick -= weight
    return entries[-1][0]


def roll_rarity(rarities, rng, *, luck=0.0):
    """A rarity id by weight; ``luck`` multiplies the weight of rarer ones (order > 0) by ``1 +
    luck * order``."""
    entries = [
        (r.rarity_id, r.weight * (1.0 + luck * r.order if r.order > 0 else 1.0))
        for r in rarities.values()
    ]
    return _weighted(rng, sorted(entries))


def roll_affixes(equipment, item_level, rarity, affixes, rng):
    """Random affixes for ``equipment`` of ``rarity`` at ``item_level`` (respecting groups and
    per-position limits)."""
    count = rng.randint(rarity.min_affixes, rarity.max_affixes) if rarity.max_affixes else 0
    limits = {"prefix": rarity.max_prefixes, "suffix": rarity.max_suffixes}
    chosen, groups, per_position = [], set(), {}
    pool = sorted(
        (a for a in affixes.values() if a.fits(equipment, item_level, rarity.rarity_id)),
        key=lambda a: a.affix_id,
    )
    for _ in range(count):
        candidates = [
            (a, a.weight)
            for a in pool
            if a.affix_id not in {c.affix_id for c in chosen}
            and not (a.group and a.group in groups)
            and not (
                limits.get(a.position, -1) >= 0
                and per_position.get(a.position, 0) >= limits[a.position]
            )
        ]
        affix = _weighted(rng, candidates)
        if affix is None:
            break
        chosen.append(affix)
        if affix.group:
            groups.add(affix.group)
        per_position[affix.position] = per_position.get(affix.position, 0) + 1
    return tuple(
        RolledAffix(
            a.affix_id, tuple((m.stat, m.operation, m.roll(rng, item_level)) for m in a.modifiers)
        )
        for a in chosen
    )


def roll_equipment(
    equipment,
    rng,
    *,
    item_level=1,
    rarity_id=None,
    rarities=None,
    affixes=None,
    luck=0.0,
    instance_id,
):
    """A new ``EquippedItem`` of ``equipment``: rarity (given, or rolled by weight), item level and
    random affixes."""
    from .items import EquippedItem

    rarities = dict(rarities or {r.rarity_id: r for r in DEFAULT_RARITIES})
    if rarity_id is None:
        rarity_id = roll_rarity(rarities, rng, luck=luck)
    rarity = rarities.get(rarity_id) or RarityDefinition(str(rarity_id))
    rolled = roll_affixes(equipment, int(item_level), rarity, dict(affixes or {}), rng)
    return EquippedItem(
        equipment,
        instance_id=instance_id,
        item_level=int(item_level),
        rarity=rarity.rarity_id,
        rolled_affixes=rolled,
    )


def item_display_name(item, affixes):
    """``"<prefixes> <base> <suffixes>"`` from the rolled affixes' display names."""
    prefixes = [
        affixes[a.affix_id].display_name
        for a in item.rolled_affixes
        if affixes.get(a.affix_id) and affixes[a.affix_id].position == "prefix"
    ]
    suffixes = [
        affixes[a.affix_id].display_name
        for a in item.rolled_affixes
        if affixes.get(a.affix_id) and affixes[a.affix_id].position != "prefix"
    ]
    return " ".join([*prefixes, item.equipment.display_name, *suffixes])


__all__ = [
    "DEFAULT_RARITIES",
    "AffixDefinition",
    "AffixModifier",
    "RarityDefinition",
    "RolledAffix",
    "item_display_name",
    "roll_affixes",
    "roll_equipment",
    "roll_rarity",
]
