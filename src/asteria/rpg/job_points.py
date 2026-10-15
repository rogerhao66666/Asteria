"""Job points: earn points for the class an actor fights as, to spend in that class's tree.

Points are allocation balances named ``<prefix>.<class id>`` (a skill-tree node can cost them like
any currency). Project data says how much a battle and each defeated enemy give.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class JobPointRules:
    rules_id: str
    prefix: str = "jp"
    per_battle: float = 0.0
    per_enemy: float = 0.0
    bonus_for_secondary: float = 0.5  # share given to each class beyond the first

    def __init__(self, rules_id, *, prefix="jp", per_battle=0.0, per_enemy=0.0, secondary=0.5):
        for value, label in ((per_battle, "per_battle"), (per_enemy, "per_enemy")):
            if not isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"{label} must be finite and >= 0")
        secondary = float(secondary)
        if not isfinite(secondary) or not 0.0 <= secondary <= 1.0:
            raise ValueError("secondary must be between 0 and 1")
        rules_id, prefix = str(rules_id).strip(), str(prefix).strip()
        if not rules_id or not prefix or "." in prefix:
            raise ValueError("rules_id and a dot-free prefix are required")
        object.__setattr__(self, "rules_id", rules_id)
        object.__setattr__(self, "prefix", prefix)
        object.__setattr__(self, "per_battle", float(per_battle))
        object.__setattr__(self, "per_enemy", float(per_enemy))
        object.__setattr__(self, "bonus_for_secondary", secondary)

    def balance_id(self, class_id):
        return f"{self.prefix}.{class_id}"

    def award(self, class_ids, enemies_defeated):
        """``{balance id: points}`` for one actor's active classes after a battle."""
        total = self.per_battle + self.per_enemy * max(0, int(enemies_defeated))
        result = {}
        for index, class_id in enumerate(class_ids):
            share = total if index == 0 else total * self.bonus_for_secondary
            if share > 0:
                result[self.balance_id(class_id)] = share
        return result

    def to_data(self):
        return {
            "schema": "asteria.rpg.job_point_rules",
            "version": 1,
            "rules_id": self.rules_id,
            "prefix": self.prefix,
            "per_battle": self.per_battle,
            "per_enemy": self.per_enemy,
            "secondary": self.bonus_for_secondary,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.job_point_rules" or data.get("version") != 1:
            raise ValueError("unsupported job point rules")
        return cls(
            data["rules_id"],
            prefix=data.get("prefix", "jp"),
            per_battle=data.get("per_battle", 0.0),
            per_enemy=data.get("per_enemy", 0.0),
            secondary=data.get("secondary", 0.5),
        )
