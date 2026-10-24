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

    ``mode`` ``linear`` (default): chance = ``base_chance`` + ``low_health_bonus`` x (1 -
    knockout resource ratio), clamped to [0, 1]. ``item_id`` (optional) is consumed by every
    attempt.

    ``mode`` ``rate``: chance = (3 - 2 x ratio) x rate x item bonus x state bonus / (3 x
    ``divisor``) - the creature-game formula where ``rate`` is ``capture_rate`` (0 = the pet
    species' own ``capture_rate``), the **item bonus** is the multiplier ``item_bonuses`` gives
    the capture item used (each listed item is a usable "ball"; ``item_id`` stays the default
    one) and the **state bonus** the largest multiplier ``state_bonuses`` gives a state the
    target has (a sleeping foe is easier).

    ``enemy_id`` names an enemy, a pet species (foes generated from a species by an
    encounter) or ``*`` (any species foe without its own rule).

    A capture gives the actor a place in the roster (``actor_id``) and / or a **pet**:
    ``pet_item_id`` is an item added to the bag, not a unit; abilities that list it in
    ``requires_items`` can then be used (a hunter sending the pet to attack); a species foe
    becomes an owned pet of its own species (``pet_species_id`` may stay empty for ``*``).
    """

    enemy_id: str
    actor_id: str
    base_chance: float = 0.25
    low_health_bonus: float = 0.5
    item_id: str = ""
    pet_item_id: str = ""
    pet_species_id: str = ""
    pet_level: int = 1
    mode: str = "linear"
    capture_rate: float = 0.0
    divisor: float = 255.0
    item_bonuses: dict = None
    state_bonuses: dict = None
    # 0: one roll against the chance; N: N checks each passed with chance ** (1/N) - the same
    # odds overall, and how many passed before one failed is the number of shakes shown
    shake_checks: int = 0

    MODES = ("linear", "rate")

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
        mode="linear",
        capture_rate=0.0,
        divisor=255.0,
        item_bonuses=None,
        state_bonuses=None,
        shake_checks=0,
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
        if not (actor_id or pet_item_id or pet_species_id or self.enemy_id == "*"):
            raise ValueError("a capture rule needs an actor_id, a pet_item_id or a pet_species_id")
        object.__setattr__(self, "pet_species_id", pet_species_id)
        object.__setattr__(self, "pet_level", max(1, int(pet_level)))
        object.__setattr__(self, "actor_id", actor_id)
        object.__setattr__(self, "pet_item_id", pet_item_id)
        object.__setattr__(self, "base_chance", base_chance)
        object.__setattr__(self, "low_health_bonus", low_health_bonus)
        object.__setattr__(self, "item_id", str(item_id).strip())
        if str(mode) not in self.MODES:
            raise ValueError(f"capture mode must be one of {self.MODES}")
        object.__setattr__(self, "mode", str(mode))
        capture_rate, divisor = float(capture_rate), float(divisor)
        if not isfinite(capture_rate) or capture_rate < 0:
            raise ValueError("capture_rate must be >= 0")
        if not isfinite(divisor) or divisor <= 0:
            raise ValueError("divisor must be > 0")
        object.__setattr__(self, "capture_rate", capture_rate)
        object.__setattr__(self, "divisor", divisor)
        bonuses = []
        for label, raw in (("item", item_bonuses), ("state", state_bonuses)):
            values = {}
            for key, value in dict(raw or {}).items():
                value = float(value)
                if not isfinite(value) or value < 0:
                    raise ValueError(f"{label} bonus must be >= 0")
                values[_id(key, f"{label} bonus")] = value
            bonuses.append(values)
        object.__setattr__(self, "item_bonuses", bonuses[0])
        object.__setattr__(self, "state_bonuses", bonuses[1])
        shake_checks = int(shake_checks)
        if shake_checks < 0:
            raise ValueError("shake_checks must be >= 0")
        object.__setattr__(self, "shake_checks", shake_checks)

    def roll(self, chance, rng):
        """``(caught, shakes)``: one throw at ``chance`` (shakes: the checks passed)."""
        chance = min(1.0, max(0.0, float(chance)))
        if not self.shake_checks:
            caught = rng.random() < chance
            return caught, int(caught)
        each = chance ** (1.0 / self.shake_checks)
        shakes = 0
        while shakes < self.shake_checks and rng.random() < each:
            shakes += 1
        return shakes == self.shake_checks, shakes

    def capture_items(self):
        """Every item that can be thrown under this rule: the default ``item_id`` and the
        bonus items, each with its multiplier (the default's is 1 unless listed)."""
        items = {}
        if self.item_id:
            items[self.item_id] = self.item_bonuses.get(self.item_id, 1.0)
        for item_id, bonus in self.item_bonuses.items():
            items.setdefault(item_id, bonus)
        return items

    def chance(self, health_ratio, *, rate=None, item_id=None, state_ids=()):
        ratio = min(1.0, max(0.0, float(health_ratio)))
        if self.mode == "linear":
            return min(1.0, max(0.0, self.base_chance + self.low_health_bonus * (1.0 - ratio)))
        rate = self.capture_rate or float(rate or 0.0)
        item_bonus = 1.0 if item_id is None else self.item_bonuses.get(str(item_id), 1.0)
        state_bonus = max(
            (self.state_bonuses[s] for s in state_ids if s in self.state_bonuses), default=1.0
        )
        value = (3.0 - 2.0 * ratio) * rate * item_bonus * state_bonus / (3.0 * self.divisor)
        return min(1.0, max(0.0, value))

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
            **({"mode": self.mode} if self.mode != "linear" else {}),
            **({"capture_rate": self.capture_rate} if self.capture_rate else {}),
            **({"divisor": self.divisor} if self.divisor != 255.0 else {}),
            **({"item_bonuses": dict(self.item_bonuses)} if self.item_bonuses else {}),
            **({"state_bonuses": dict(self.state_bonuses)} if self.state_bonuses else {}),
            **({"shake_checks": self.shake_checks} if self.shake_checks else {}),
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
            mode=data.get("mode", "linear"),
            capture_rate=data.get("capture_rate", 0.0),
            divisor=data.get("divisor", 255.0),
            item_bonuses=data.get("item_bonuses"),
            state_bonuses=data.get("state_bonuses"),
            shake_checks=data.get("shake_checks", 0),
        )
