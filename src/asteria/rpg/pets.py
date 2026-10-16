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


@dataclass(frozen=True, slots=True)
class PetEvolution:
    """One way a species turns into another. A pet qualifies when every set condition holds:
    ``min_level``, ``min_affinity`` and the bag item ``item_id`` (spent when ``consume_item``).
    ``automatic`` evolutions happen as soon as the conditions hold (after a battle); others
    wait for ``evolve_pet`` (an item, a menu)."""

    to_species_id: str
    min_level: int = 0
    min_affinity: float = 0.0
    item_id: str = ""
    consume_item: bool = True
    automatic: bool = True

    def __post_init__(self):
        object.__setattr__(self, "to_species_id", _text(self.to_species_id, "to_species_id"))
        object.__setattr__(self, "min_level", max(0, int(self.min_level)))
        object.__setattr__(self, "min_affinity", max(0.0, float(self.min_affinity)))
        object.__setattr__(self, "item_id", _text(self.item_id, "item_id", required=False))

    def to_data(self):
        return {
            "to_species_id": self.to_species_id,
            **({"min_level": self.min_level} if self.min_level else {}),
            **({"min_affinity": self.min_affinity} if self.min_affinity else {}),
            **({"item_id": self.item_id} if self.item_id else {}),
            **({"consume_item": False} if not self.consume_item else {}),
            **({"automatic": False} if not self.automatic else {}),
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["to_species_id"],
            data.get("min_level", 0),
            data.get("min_affinity", 0.0),
            data.get("item_id", ""),
            data.get("consume_item", True),
            data.get("automatic", True),
        )


@dataclass(frozen=True, slots=True)
class PetMove:
    """An ability a pet learns: at ``level`` (and ``min_affinity``) it joins the pet's known
    abilities. An ability that appears in a species' learnset can only be used while the active
    pet of that species knows it."""

    ability_id: str
    level: int = 1
    min_affinity: float = 0.0

    def __post_init__(self):
        object.__setattr__(self, "ability_id", _text(self.ability_id, "ability_id"))
        object.__setattr__(self, "level", max(1, int(self.level)))
        object.__setattr__(self, "min_affinity", max(0.0, float(self.min_affinity)))

    def to_data(self):
        return {
            "ability_id": self.ability_id,
            **({"level": self.level} if self.level != 1 else {}),
            **({"min_affinity": self.min_affinity} if self.min_affinity else {}),
        }

    @classmethod
    def from_data(cls, data):
        return cls(data["ability_id"], data.get("level", 1), data.get("min_affinity", 0.0))


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
    evolutions: tuple = ()
    learnset: tuple = ()
    affinity_per_battle: float = 0.0
    max_affinity: float = 100.0
    battle_unit: bool = False
    resources: dict = None
    battle_abilities: tuple = ()

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
        evolutions=(),
        learnset=(),
        affinity_per_battle=0.0,
        max_affinity=100.0,
        battle_unit=False,
        resources=None,
        battle_abilities=(),
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
        evolutions = tuple(
            e if isinstance(e, PetEvolution) else PetEvolution.from_data(e) for e in evolutions
        )
        learnset = tuple(m if isinstance(m, PetMove) else PetMove.from_data(m) for m in learnset)
        object.__setattr__(self, "evolutions", evolutions)
        object.__setattr__(
            self, "learnset", tuple(sorted(learnset, key=lambda m: (m.level, m.ability_id)))
        )
        max_affinity = float(max_affinity)
        affinity_per_battle = float(affinity_per_battle)
        if not isfinite(max_affinity) or max_affinity < 0:
            raise ValueError("max_affinity must be >= 0")
        if not isfinite(affinity_per_battle):
            raise ValueError("affinity_per_battle must be finite")
        object.__setattr__(self, "max_affinity", max_affinity)
        object.__setattr__(self, "affinity_per_battle", affinity_per_battle)
        object.__setattr__(self, "battle_unit", bool(battle_unit))
        object.__setattr__(self, "resources", _numbers(resources, "resource"))
        object.__setattr__(
            self, "battle_abilities", tuple(dict.fromkeys(str(a) for a in battle_abilities if a))
        )

    def resources_at(self, level):
        """Resource maximums when the pet fights as a unit: ``resources[name]``, or the pet stat
        ``max_<name>`` at ``level`` when the species defines one (so it can grow)."""
        stats = self.stats_at(level)
        return {name: stats.get(f"max_{name}", base) for name, base in self.resources.items()}

    def knows(self, ability_id, level, affinity=0.0):
        """Whether a pet of ``level`` and ``affinity`` has learned ``ability_id``."""
        return any(
            m.ability_id == ability_id and level >= m.level and affinity >= m.min_affinity
            for m in self.learnset
        )

    def known_abilities(self, level, affinity=0.0):
        return tuple(
            dict.fromkeys(
                m.ability_id
                for m in self.learnset
                if level >= m.level and affinity >= m.min_affinity
            )
        )

    def gated(self, ability_id):
        """True when ``ability_id`` is in this species' learnset (so it must be learned)."""
        return any(m.ability_id == ability_id for m in self.learnset)

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
            **({"evolutions": [e.to_data() for e in self.evolutions]} if self.evolutions else {}),
            **({"learnset": [m.to_data() for m in self.learnset]} if self.learnset else {}),
            **(
                {"affinity_per_battle": self.affinity_per_battle}
                if self.affinity_per_battle
                else {}
            ),
            **({"max_affinity": self.max_affinity} if self.max_affinity != 100.0 else {}),
            **({"battle_unit": True} if self.battle_unit else {}),
            **({"resources": dict(sorted(self.resources.items()))} if self.resources else {}),
            **({"battle_abilities": list(self.battle_abilities)} if self.battle_abilities else {}),
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
            evolutions=data.get("evolutions", ()),
            learnset=data.get("learnset", ()),
            affinity_per_battle=data.get("affinity_per_battle", 0.0),
            max_affinity=data.get("max_affinity", 100.0),
            battle_unit=data.get("battle_unit", False),
            resources=data.get("resources"),
            battle_abilities=data.get("battle_abilities", ()),
        )


@dataclass(slots=True)
class PetRecord:
    """One owned creature (save data)."""

    instance_id: str
    species_id: str
    nickname: str = ""
    level: int = 1
    experience: float = 0.0
    affinity: float = 0.0

    def __post_init__(self):
        self.instance_id = _text(self.instance_id, "instance_id")
        self.species_id = _text(self.species_id, "species_id")
        self.nickname = str(self.nickname or "").strip()[:24]
        self.level = max(1, int(self.level))
        self.experience = max(0.0, float(self.experience))
        self.affinity = max(0.0, float(self.affinity))

    def add_affinity(self, species, amount):
        """Change affinity (clamped to ``0..max_affinity``); returns the applied change."""
        before = self.affinity
        self.affinity = max(0.0, min(species.max_affinity, before + float(amount)))
        return self.affinity - before

    def evolution_for(self, species, *, item_id=""):
        """The first evolution whose conditions hold (``item_id`` is the item being used)."""
        for evolution in species.evolutions:
            if evolution.item_id and evolution.item_id != item_id:
                continue
            if self.level >= evolution.min_level and self.affinity >= evolution.min_affinity:
                return evolution
        return None

    def evolve(self, evolution):
        """Become ``evolution.to_species_id`` (nickname, level, affinity and experience stay)."""
        self.species_id = evolution.to_species_id

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
            **({"affinity": self.affinity} if self.affinity else {}),
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["instance_id"],
            data["species_id"],
            data.get("nickname", ""),
            data.get("level", 1),
            data.get("experience", 0.0),
            data.get("affinity", 0.0),
        )


PET_STAT_PREFIX = "pet_"
