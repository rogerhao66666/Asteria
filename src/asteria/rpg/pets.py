"""Pets: creatures the player owns, names, levels up and sends out (Pokemon-style).

A **species** (:class:`PetSpeciesDefinition`, project data) gives base stats and growth per level;
an **owned pet** (:class:`PetRecord`, save data) is one creature: its species, a nickname, a level
and experience. A pet is not a battle unit: abilities that name it (``requires_pet``) are sent out
by a character and read its stats as ``pet_<stat>`` (plus ``pet_level``) in their formulas, so a
higher-level pet hits harder. Which pet is sent is the *active pet*.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _text(value, label, *, required=True):
    value = str(value or "").strip()
    if required and not value:
        raise ValueError(f"{label} is required")
    return value


def _numbers(values, label):
    result = {}
    for key, value in dict(values or {}).items():
        key = _text(key, f"{label} name")
        value = float(value)
        if not isfinite(value):
            raise ValueError(f"{label} {key} must be finite")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class PetSpeciesDefinition:
    """``stats[name] + growth[name] * (level - 1)`` is a pet stat at ``level``; reaching the next
    level takes ``exp_base * level`` experience; ``max_level`` stops growth; a pet sent out in a
    won battle gains ``exp_per_battle``."""

    species_id: str
    display_name: str
    stats: dict
    growth: dict
    max_level: int = 50
    exp_base: float = 40.0
    exp_per_battle: float = 30.0
    icon_id: str = ""
    tags: tuple = ()

    def __init__(
        self,
        species_id,
        display_name="",
        *,
        stats=None,
        growth=None,
        max_level=50,
        exp_base=40.0,
        exp_per_battle=30.0,
        icon_id="",
        tags=(),
    ):
        species_id = _text(species_id, "species_id")
        max_level, exp_base = int(max_level), float(exp_base)
        if max_level < 1:
            raise ValueError("max_level must be >= 1")
        if not isfinite(exp_base) or exp_base <= 0:
            raise ValueError("exp_base must be > 0")
        object.__setattr__(self, "species_id", species_id)
        object.__setattr__(self, "display_name", _text(display_name or species_id, "display_name"))
        object.__setattr__(self, "stats", _numbers(stats, "stat"))
        object.__setattr__(self, "growth", _numbers(growth, "growth"))
        object.__setattr__(self, "max_level", max_level)
        object.__setattr__(self, "exp_base", exp_base)
        exp_per_battle = float(exp_per_battle)
        if not isfinite(exp_per_battle) or exp_per_battle < 0:
            raise ValueError("exp_per_battle must be >= 0")
        object.__setattr__(self, "exp_per_battle", exp_per_battle)
        object.__setattr__(self, "icon_id", _text(icon_id, "icon_id", required=False))
        object.__setattr__(self, "tags", tuple(sorted({str(t).strip() for t in tags if str(t)})))

    def stats_at(self, level):
        level = max(1, min(self.max_level, int(level)))
        names = set(self.stats) | set(self.growth)
        return {
            name: self.stats.get(name, 0.0) + self.growth.get(name, 0.0) * (level - 1)
            for name in sorted(names)
        }

    def exp_to_next(self, level):
        return self.exp_base * max(1, int(level))

    def to_data(self):
        return {
            "schema": "asteria.rpg.pet_species",
            "version": 1,
            "species_id": self.species_id,
            "display_name": self.display_name,
            "stats": dict(sorted(self.stats.items())),
            "growth": dict(sorted(self.growth.items())),
            "max_level": self.max_level,
            "exp_base": self.exp_base,
            "exp_per_battle": self.exp_per_battle,
            **({"icon_id": self.icon_id} if self.icon_id else {}),
            **({"tags": list(self.tags)} if self.tags else {}),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.pet_species" or data.get("version") != 1:
            raise ValueError("unsupported pet species")
        return cls(
            data["species_id"],
            data.get("display_name", ""),
            stats=data.get("stats"),
            growth=data.get("growth"),
            max_level=data.get("max_level", 50),
            exp_base=data.get("exp_base", 40.0),
            exp_per_battle=data.get("exp_per_battle", 30.0),
            icon_id=data.get("icon_id", ""),
            tags=data.get("tags", ()),
        )


@dataclass(slots=True)
class PetRecord:
    """One owned creature (save data)."""

    instance_id: str
    species_id: str
    nickname: str = ""
    level: int = 1
    experience: float = 0.0

    def __post_init__(self):
        self.instance_id = _text(self.instance_id, "instance_id")
        self.species_id = _text(self.species_id, "species_id")
        self.nickname = str(self.nickname or "").strip()[:24]
        self.level = max(1, int(self.level))
        self.experience = max(0.0, float(self.experience))

    def name(self, species=None):
        """What the pet is called: its nickname, else its species' name."""
        if self.nickname:
            return self.nickname
        return species.display_name if species is not None else self.species_id

    def gain(self, species, amount):
        """Add experience; returns how many levels it gained."""
        gained = 0
        self.experience += max(0.0, float(amount))
        while self.level < species.max_level and self.experience >= species.exp_to_next(
            self.level
        ):
            self.experience -= species.exp_to_next(self.level)
            self.level += 1
            gained += 1
        if self.level >= species.max_level:
            self.experience = 0.0
        return gained

    def to_data(self):
        return {
            "instance_id": self.instance_id,
            "species_id": self.species_id,
            "nickname": self.nickname,
            "level": self.level,
            "experience": self.experience,
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["instance_id"],
            data["species_id"],
            data.get("nickname", ""),
            data.get("level", 1),
            data.get("experience", 0.0),
        )


PET_STAT_PREFIX = "pet_"
