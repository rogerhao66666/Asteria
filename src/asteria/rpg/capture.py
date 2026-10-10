"""Capturing enemies as party members (ASTERIA_SPEC §25)."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


@dataclass(frozen=True, slots=True)
class CaptureRule:
    """How enemy ``enemy_id`` can be captured, and the actor it joins the roster as.

    chance = ``base_chance`` + ``low_health_bonus`` x (1 - knockout resource ratio),
    clamped to [0, 1]. ``item_id`` (optional) is consumed by every attempt.
    """

    enemy_id: str
    actor_id: str
    base_chance: float = 0.25
    low_health_bonus: float = 0.5
    item_id: str = ""

    def __init__(self, enemy_id, actor_id, *, base_chance=0.25, low_health_bonus=0.5, item_id=""):
        base_chance, low_health_bonus = float(base_chance), float(low_health_bonus)
        if not (isfinite(base_chance) and isfinite(low_health_bonus)) or not 0.0 <= base_chance <= 1.0:
            raise ValueError("capture chances are invalid")
        object.__setattr__(self, "enemy_id", _id(enemy_id, "enemy_id"))
        object.__setattr__(self, "actor_id", _id(actor_id, "actor_id"))
        object.__setattr__(self, "base_chance", base_chance)
        object.__setattr__(self, "low_health_bonus", low_health_bonus)
        object.__setattr__(self, "item_id", str(item_id).strip())

    def chance(self, health_ratio):
        ratio = min(1.0, max(0.0, float(health_ratio)))
        return min(1.0, max(0.0, self.base_chance + self.low_health_bonus * (1.0 - ratio)))

    def to_data(self):
        return {
            "schema": "asteria.rpg.capture_rule",
            "version": 1,
            "enemy_id": self.enemy_id,
            "actor_id": self.actor_id,
            "base_chance": self.base_chance,
            "low_health_bonus": self.low_health_bonus,
            "item_id": self.item_id,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.capture_rule" or data.get("version") != 1:
            raise ValueError("unsupported capture rule")
        return cls(
            data["enemy_id"],
            data["actor_id"],
            base_chance=data["base_chance"],
            low_health_bonus=data["low_health_bonus"],
            item_id=data["item_id"],
        )
