from __future__ import annotations

import random
from dataclasses import dataclass, field
from math import isfinite

from asteria.gameplay import ResourcePool, StatBlock, TagSet


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _finite(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def _tags(values):
    return tuple(sorted({_id(x, "tag").lower() for x in values}))


@dataclass(frozen=True, slots=True)
class LootEntry:
    """One possible drop.

    ``required_switch`` makes the drop conditional on an event switch being
    on; ``luck_bonus`` is added to ``chance`` per point of the luck the
    caller passes to :func:`roll_reward` (difficulty or luck modifiers).
    """

    item_id: str
    chance: float = 1.0
    minimum: int = 1
    maximum: int = 1
    required_switch: str = ""
    luck_bonus: float = 0.0

    def __init__(
        self, item_id, *, chance=1.0, minimum=1, maximum=1, required_switch="", luck_bonus=0.0
    ):
        chance = _finite(chance, "chance")
        minimum = int(minimum)
        maximum = int(maximum)
        luck_bonus = _finite(luck_bonus, "luck_bonus")
        if not 0.0 <= chance <= 1.0:
            raise ValueError("chance must be between 0 and 1")
        if minimum < 0 or maximum < minimum:
            raise ValueError("invalid loot quantity")
        object.__setattr__(self, "item_id", _id(item_id, "item_id"))
        object.__setattr__(self, "chance", chance)
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)
        object.__setattr__(self, "required_switch", str(required_switch).strip())
        object.__setattr__(self, "luck_bonus", luck_bonus)

    def effective_chance(self, luck=0.0):
        return min(1.0, max(0.0, self.chance + float(luck) * self.luck_bonus))

    def to_data(self):
        data = {
            "item_id": self.item_id,
            "chance": self.chance,
            "minimum": self.minimum,
            "maximum": self.maximum,
        }
        if self.required_switch:
            data["required_switch"] = self.required_switch
        if self.luck_bonus:
            data["luck_bonus"] = self.luck_bonus
        return data

    @classmethod
    def from_data(cls, data):
        return cls(**data)


@dataclass(frozen=True, slots=True)
class RewardDefinition:
    currencies: dict[str, float] = field(default_factory=dict)
    experience: dict[str, float] = field(default_factory=dict)
    loot: tuple[LootEntry, ...] = ()
    drop_table_id: str = (
        ""  # RPG-04: a weighted / guaranteed / pity DropTable rolled with this reward
    )

    def __init__(self, *, currencies=None, experience=None, loot=(), drop_table_id=""):
        def vals(raw, label):
            out = {}
            for k, v in dict(raw or {}).items():
                k = _id(k, label)
                v = _finite(v, label)
                if v < 0:
                    raise ValueError(f"{label} reward must be >= 0")
                out[k] = v
            return out

        loot = tuple(loot)
        if any(not isinstance(x, LootEntry) for x in loot):
            raise TypeError("loot must be LootEntry values")
        object.__setattr__(self, "currencies", vals(currencies, "currency"))
        object.__setattr__(self, "experience", vals(experience, "experience"))
        object.__setattr__(self, "loot", loot)
        object.__setattr__(self, "drop_table_id", str(drop_table_id or "").strip())

    def to_data(self):
        data = {
            "currencies": dict(sorted(self.currencies.items())),
            "experience": dict(sorted(self.experience.items())),
            "loot": [x.to_data() for x in self.loot],
        }
        if self.drop_table_id:
            data["drop_table_id"] = self.drop_table_id
        return data

    @classmethod
    def from_data(cls, data):
        return cls(
            currencies=data["currencies"],
            experience=data["experience"],
            loot=[LootEntry.from_data(x) for x in data["loot"]],
            drop_table_id=data.get("drop_table_id", ""),
        )


@dataclass(frozen=True, slots=True)
class EnemyDefinition:
    enemy_id: str
    display_name: str
    stats: dict[str, float]
    resources: dict[str, float]
    tags: tuple[str, ...]
    abilities: tuple[str, ...]
    reward: RewardDefinition

    def __init__(
        self,
        enemy_id,
        display_name=None,
        *,
        stats=None,
        resources=None,
        tags=(),
        abilities=(),
        reward=None,
    ):
        enemy_id = _id(enemy_id, "enemy_id")

        def vals(raw, label):
            out = {}
            for k, v in dict(raw or {}).items():
                k = _id(k, label)
                v = _finite(v, label)
                if label == "resource" and v < 0:
                    raise ValueError("resource maximum must be >= 0")
                out[k] = v
            return out

        if reward is None:
            reward = RewardDefinition()
        if not isinstance(reward, RewardDefinition):
            raise TypeError("reward must be RewardDefinition")
        object.__setattr__(self, "enemy_id", enemy_id)
        object.__setattr__(self, "display_name", str(display_name or enemy_id))
        object.__setattr__(self, "stats", vals(stats, "stat"))
        object.__setattr__(self, "resources", vals(resources, "resource"))
        object.__setattr__(self, "tags", _tags(tags))
        object.__setattr__(
            self,
            "abilities",
            tuple(dict.fromkeys(_id(x, "ability_id") for x in abilities)),
        )
        object.__setattr__(self, "reward", reward)

    def instantiate(self):
        resources = ResourcePool()
        for k, v in self.resources.items():
            resources.define(k, v)
        return EnemyRuntime(self, StatBlock(self.stats), resources, TagSet(self.tags))

    def to_data(self):
        return {
            "schema": "asteria.rpg.enemy",
            "version": 1,
            "enemy_id": self.enemy_id,
            "display_name": self.display_name,
            "stats": dict(sorted(self.stats.items())),
            "resources": dict(sorted(self.resources.items())),
            "tags": list(self.tags),
            "abilities": list(self.abilities),
            "reward": self.reward.to_data(),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.enemy" or data.get("version") != 1:
            raise ValueError("unsupported enemy definition")
        return cls(
            data["enemy_id"],
            data["display_name"],
            stats=data["stats"],
            resources=data["resources"],
            tags=data["tags"],
            abilities=data["abilities"],
            reward=RewardDefinition.from_data(data["reward"]),
        )


@dataclass(slots=True)
class EnemyRuntime:
    definition: EnemyDefinition
    stats: StatBlock
    resources: ResourcePool
    tags: TagSet

    @property
    def abilities(self):
        return self.definition.abilities


@dataclass(frozen=True, slots=True)
class EncounterMember:
    """One kind of foe in an encounter: an enemy definition (``enemy_id``) or, in a creature
    game, ``count`` creatures of a pet species (``pet_species_id``) at ``level`` (up to
    ``level_max`` when set, rolled per creature) with the species' moves (or ``moves``) and
    ``genes`` - a wild creature or a trainer's team member. ``reserve`` members wait on the
    bench and come in when a stage slot of their side empties (PetRules.battle_slots)."""

    enemy_id: str
    count: int = 1
    weight: float = 1.0
    pet_species_id: str = ""
    level: int = 1
    level_max: int = 0
    reserve: bool = False
    moves: tuple = ()
    genes: dict = None

    OPTIONAL_DATA = {
        "pet_species_id": "",
        "level": 1,
        "level_max": 0,
        "reserve": False,
        "moves": [],
        "genes": {},
    }

    def __init__(
        self,
        enemy_id="",
        *,
        count=1,
        weight=1.0,
        pet_species_id="",
        level=1,
        level_max=0,
        reserve=False,
        moves=(),
        genes=None,
    ):
        count = int(count)
        weight = _finite(weight, "weight")
        if count < 1:
            raise ValueError("count must be >= 1")
        if weight <= 0:
            raise ValueError("weight must be > 0")
        enemy_id, pet_species_id = str(enemy_id or "").strip(), str(pet_species_id or "").strip()
        if not enemy_id and not pet_species_id:
            raise ValueError("an encounter member needs an enemy_id or a pet_species_id")
        object.__setattr__(self, "enemy_id", enemy_id)
        object.__setattr__(self, "pet_species_id", pet_species_id)
        object.__setattr__(self, "count", count)
        object.__setattr__(self, "weight", weight)
        level, level_max = int(level), int(level_max)
        if level < 1 or level_max < 0:
            raise ValueError("level must be >= 1 and level_max >= 0")
        object.__setattr__(self, "level", level)
        object.__setattr__(self, "level_max", max(level, level_max) if level_max else 0)
        object.__setattr__(self, "reserve", bool(reserve))
        object.__setattr__(self, "moves", tuple(dict.fromkeys(str(x) for x in moves if x)))
        genes = {str(k): _finite(v, "gene") for k, v in dict(genes or {}).items() if str(k)}
        object.__setattr__(self, "genes", genes)

    @property
    def kind_id(self):
        """What the foe is called by: the enemy id, or the species id of a species foe."""
        return self.enemy_id or self.pet_species_id

    def to_data(self):
        return {
            "enemy_id": self.enemy_id,
            "count": self.count,
            "weight": self.weight,
            **({"pet_species_id": self.pet_species_id} if self.pet_species_id else {}),
            **({"level": self.level} if self.level != 1 else {}),
            **({"level_max": self.level_max} if self.level_max else {}),
            **({"reserve": True} if self.reserve else {}),
            **({"moves": list(self.moves)} if self.moves else {}),
            **({"genes": dict(sorted(self.genes.items()))} if self.genes else {}),
        }

    @classmethod
    def from_data(cls, data):
        return cls(**data)


@dataclass(frozen=True, slots=True)
class EncounterDefinition:
    encounter_id: str
    members: tuple[EncounterMember, ...]
    tags: tuple[str, ...] = ()

    NESTED_OPTIONAL = {"members": EncounterMember}  # the editor shows the members' options

    def __init__(self, encounter_id, *, members, tags=()):
        members = tuple(members)
        if not members:
            raise ValueError("encounter requires at least one member")
        if any(not isinstance(x, EncounterMember) for x in members):
            raise TypeError("members must be EncounterMember values")
        object.__setattr__(self, "encounter_id", _id(encounter_id, "encounter_id"))
        object.__setattr__(self, "members", members)
        object.__setattr__(self, "tags", _tags(tags))

    def to_data(self):
        return {
            "schema": "asteria.rpg.encounter",
            "version": 1,
            "encounter_id": self.encounter_id,
            "members": [x.to_data() for x in self.members],
            "tags": list(self.tags),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.encounter" or data.get("version") != 1:
            raise ValueError("unsupported encounter definition")
        return cls(
            data["encounter_id"],
            members=[EncounterMember.from_data(x) for x in data["members"]],
            tags=data["tags"],
        )


@dataclass(frozen=True, slots=True)
class RewardRoll:
    currencies: dict[str, float]
    experience: dict[str, float]
    items: dict[str, int]


def roll_reward(reward, rng=None, *, luck=0.0, switches=None):
    """Roll a reward's loot; ``switches`` (``name -> bool``) gates conditional drops."""
    if not isinstance(reward, RewardDefinition):
        raise TypeError("reward must be RewardDefinition")
    rng = rng or random.Random()
    items = {}
    for entry in reward.loot:
        if entry.required_switch and not (
            switches is not None and switches(entry.required_switch)
        ):
            continue
        if rng.random() <= entry.effective_chance(luck):
            amount = rng.randint(entry.minimum, entry.maximum)
            if amount:
                items[entry.item_id] = items.get(entry.item_id, 0) + amount
    return RewardRoll(dict(reward.currencies), dict(reward.experience), items)
