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

    A capture gives the actor a place in the roster (``actor_id``) and / or a **pet**:
    ``pet_item_id`` is an item added to the bag, not a unit; abilities that list it in
    ``requires_items`` can then be used (a hunter sending the pet to attack). At least one of
    the two is required.
    """

    enemy_id: str
    actor_id: str
    base_chance: float = 0.25
    low_health_bonus: float = 0.5
    item_id: str = ""
    pet_item_id: str = ""
    pet_species_id: str = ""
    pet_level: int = 1

    def __init__(
        self,
        enemy_id,
        actor_id="",
        *,
        base_chance=0.25,
        low_health_bonus=0.5,
        item_id="",
        pet_item_id="",
        pet_species_id="",
        pet_level=1,
    ):
        base_chance, low_health_bonus = float(base_chance), float(low_health_bonus)
        if (
            not (isfinite(base_chance) and isfinite(low_health_bonus))
            or not 0.0 <= base_chance <= 1.0
        ):
            raise ValueError("capture chances are invalid")
        object.__setattr__(self, "enemy_id", _id(enemy_id, "enemy_id"))
        actor_id, pet_item_id = str(actor_id or "").strip(), str(pet_item_id or "").strip()
        pet_species_id = str(pet_species_id or "").strip()
        if not (actor_id or pet_item_id or pet_species_id):
            raise ValueError("a capture rule needs an actor_id, a pet_item_id or a pet_species_id")
        object.__setattr__(self, "pet_species_id", pet_species_id)
        object.__setattr__(self, "pet_level", max(1, int(pet_level)))
        object.__setattr__(self, "actor_id", actor_id)
        object.__setattr__(self, "pet_item_id", pet_item_id)
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
            **({"pet_item_id": self.pet_item_id} if self.pet_item_id else {}),
            **({"pet_species_id": self.pet_species_id} if self.pet_species_id else {}),
            **({"pet_level": self.pet_level} if self.pet_level != 1 else {}),
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
            pet_item_id=data.get("pet_item_id", ""),
            pet_species_id=data.get("pet_species_id", ""),
            pet_level=data.get("pet_level", 1),
        )
