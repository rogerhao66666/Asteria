"""Enemy levels and difficulty: scale an enemy's stats, resources and rewards by level.

Project data decides which stats and resources grow and how fast; the engine only applies
``base * (1 + growth * (level - 1))`` and a difficulty multiplier on top.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _growth(values, label):
    result = []
    for name, rate in dict(values or {}).items():
        rate = float(rate)
        if not isfinite(rate) or rate < 0:
            raise ValueError(f"{label} rates must be finite and >= 0")
        result.append((_id(name, label), rate))
    return tuple(sorted(result))


@dataclass(frozen=True, slots=True)
class DifficultyLevel:
    """One setting of a difficulty slider: multipliers on enemy strength and on rewards."""

    difficulty_id: str
    strength: float = 1.0
    reward: float = 1.0
    level_offset: int = 0

    def __init__(self, difficulty_id, strength=1.0, reward=1.0, level_offset=0):
        for value, label in ((strength, "strength"), (reward, "reward")):
            if not isfinite(float(value)) or float(value) <= 0:
                raise ValueError(f"{label} must be finite and positive")
        object.__setattr__(self, "difficulty_id", _id(difficulty_id, "difficulty_id"))
        object.__setattr__(self, "strength", float(strength))
        object.__setattr__(self, "reward", float(reward))
        object.__setattr__(self, "level_offset", int(level_offset))


@dataclass(frozen=True, slots=True)
class EnemyLevelRules:
    """How enemy level changes an enemy.

    - ``stat_growth`` / ``resource_growth``: id -> fraction added per level above 1 (a resource's
      growth raises its maximum and refills it).
    - ``reward_growth``: fraction added to every reward per level above 1.
    - ``map_levels``: map or area id -> (lowest, highest) level of enemies met there.
    - ``party_level_offset``: with no map entry, enemies are the party's level plus this.
    - ``difficulties``: the slider settings; ``default_difficulty`` names the one in force.
    """

    rules_id: str
    stat_growth: tuple[tuple[str, float], ...] = ()
    resource_growth: tuple[tuple[str, float], ...] = ()
    reward_growth: float = 0.0
    map_levels: tuple[tuple[str, int, int], ...] = ()
    party_level_offset: int = 0
    max_level: int = 99
    difficulties: tuple[DifficultyLevel, ...] = ()
    default_difficulty: str = ""

    def __init__(
        self,
        rules_id,
        *,
        stat_growth=None,
        resource_growth=None,
        reward_growth=0.0,
        map_levels=None,
        party_level_offset=0,
        max_level=99,
        difficulties=(),
        default_difficulty="",
    ):
        s = object.__setattr__
        s(self, "rules_id", _id(rules_id, "rules_id"))
        s(self, "stat_growth", _growth(stat_growth, "stat_growth"))
        s(self, "resource_growth", _growth(resource_growth, "resource_growth"))
        reward_growth = float(reward_growth)
        if not isfinite(reward_growth) or reward_growth < 0:
            raise ValueError("reward_growth must be finite and >= 0")
        s(self, "reward_growth", reward_growth)
        ranges = []
        for key, (low, high) in dict(map_levels or {}).items():
            low, high = int(low), int(high)
            if low < 1 or high < low:
                raise ValueError("map level ranges need 1 <= lowest <= highest")
            ranges.append((_id(key, "map id"), low, high))
        s(self, "map_levels", tuple(sorted(ranges)))
        s(self, "party_level_offset", int(party_level_offset))
        if int(max_level) < 1:
            raise ValueError("max_level must be >= 1")
        s(self, "max_level", int(max_level))
        difficulties = tuple(difficulties)
        if any(not isinstance(x, DifficultyLevel) for x in difficulties):
            raise TypeError("difficulties must be DifficultyLevel values")
        if len({x.difficulty_id for x in difficulties}) != len(difficulties):
            raise ValueError("duplicate difficulty id")
        s(self, "difficulties", difficulties)
        default_difficulty = str(default_difficulty or "")
        if default_difficulty and default_difficulty not in {
            x.difficulty_id for x in difficulties
        }:
            raise ValueError("default_difficulty is not one of the difficulties")
        s(self, "default_difficulty", default_difficulty)

    def difficulty(self, difficulty_id=None):
        wanted = self.default_difficulty if difficulty_id is None else str(difficulty_id)
        for item in self.difficulties:
            if item.difficulty_id == wanted:
                return item
        return DifficultyLevel("normal")

    def level_for(self, map_id="", rng=None, party_level=1, difficulty_id=None):
        """The level of an enemy met on ``map_id`` (random inside its range)."""
        ranges = {key: (low, high) for key, low, high in self.map_levels}
        if str(map_id) in ranges:
            low, high = ranges[str(map_id)]
            level = rng.randint(low, high) if rng is not None else low
        else:
            level = int(party_level) + self.party_level_offset
        level += self.difficulty(difficulty_id).level_offset
        return max(1, min(self.max_level, level))

    def stat_multiplier(self, rate, level, difficulty_id=None):
        return (1.0 + rate * (max(1, int(level)) - 1)) * self.difficulty(difficulty_id).strength

    def reward_multiplier(self, level, difficulty_id=None):
        grown = 1.0 + self.reward_growth * (max(1, int(level)) - 1)
        return grown * self.difficulty(difficulty_id).reward

    def apply(self, subject, level, difficulty_id=None):
        """Scale ``subject``'s stats and resource maxima to ``level`` (from its level-1 values)."""
        for name, rate in self.stat_growth:
            if subject.stats.contains(name):
                value = subject.stats.get(name) * self.stat_multiplier(rate, level, difficulty_id)
                subject.stats.set(name, value)
        for name, rate in self.resource_growth:
            if subject.resources.contains(name):
                top = subject.resources.maximum(name)
                scaled = top * self.stat_multiplier(rate, level, difficulty_id)
                subject.resources.get(name).set_maximum(scaled)
                subject.resources.set_current(name, scaled)
        return subject

    def to_data(self):
        return {
            "schema": "asteria.rpg.enemy_level_rules",
            "version": 1,
            "rules_id": self.rules_id,
            "stat_growth": dict(self.stat_growth),
            "resource_growth": dict(self.resource_growth),
            "reward_growth": self.reward_growth,
            "map_levels": {key: [low, high] for key, low, high in self.map_levels},
            "party_level_offset": self.party_level_offset,
            "max_level": self.max_level,
            "difficulties": [
                {
                    "difficulty_id": x.difficulty_id,
                    "strength": x.strength,
                    "reward": x.reward,
                    "level_offset": x.level_offset,
                }
                for x in self.difficulties
            ],
            "default_difficulty": self.default_difficulty,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.enemy_level_rules" or data.get("version") != 1:
            raise ValueError("unsupported enemy level rules")
        return cls(
            data["rules_id"],
            stat_growth=data.get("stat_growth"),
            resource_growth=data.get("resource_growth"),
            reward_growth=data.get("reward_growth", 0.0),
            map_levels={k: tuple(v) for k, v in data.get("map_levels", {}).items()},
            party_level_offset=data.get("party_level_offset", 0),
            max_level=data.get("max_level", 99),
            difficulties=tuple(DifficultyLevel(**x) for x in data.get("difficulties", ())),
            default_difficulty=data.get("default_difficulty", ""),
        )
