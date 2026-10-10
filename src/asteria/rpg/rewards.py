from __future__ import annotations

from dataclasses import dataclass

from asteria.core.lifecycle import emit_hook

from .enemies import RewardRoll
from .items import Inventory
from .progression import ProgressionRuntime


@dataclass(frozen=True, slots=True)
class RewardApplicationResult:
    currencies: dict[str, float]
    progression_results: tuple
    items: dict[str, int]


class RewardRuntime:
    """Applies a rolled reward to generic stores.

    Currency is a caller-owned mapping. Experience keys are interpreted as
    progression track IDs only because the caller supplied a ProgressionRuntime.
    """

    def __init__(self, *, inventory=None, progression=None, currencies=None, hooks=None):
        if inventory is not None and not isinstance(inventory, Inventory):
            raise TypeError("inventory must be Inventory")
        if progression is not None and not isinstance(progression, ProgressionRuntime):
            raise TypeError("progression must be ProgressionRuntime")
        self.inventory = inventory
        self.progression = progression
        self.currencies = currencies if currencies is not None else {}
        self.hooks = hooks

    def apply(self, reward):
        if not isinstance(reward, RewardRoll):
            raise TypeError("reward must be RewardRoll")

        # Validate the complete reward before mutating any caller-owned store.
        for key, amount in reward.currencies.items():
            key = str(key).strip()
            amount = float(amount)
            if not key or not __import__("math").isfinite(amount) or amount < 0:
                raise ValueError("invalid currency reward")
        if reward.experience:
            if self.progression is None:
                raise ValueError("reward contains progression values but no ProgressionRuntime was supplied")
            for track_id, amount in reward.experience.items():
                if str(track_id) not in self.progression.definitions:
                    raise KeyError(f"unknown progression track: {track_id}")
                amount = float(amount)
                if not __import__("math").isfinite(amount) or amount < 0:
                    raise ValueError("invalid progression reward")
        if reward.items:
            if self.inventory is None:
                raise ValueError("reward contains items but no Inventory was supplied")
            for item_id, amount in reward.items.items():
                if not str(item_id).strip() or int(amount) != amount or int(amount) < 1:
                    raise ValueError("invalid item reward")

        emit_hook(self.hooks, "rpg.reward.before_apply", data={"reward": reward})

        old_currencies = dict(self.currencies)
        old_progression = None if self.progression is None else self.progression.to_data()
        old_inventory = None if self.inventory is None else self.inventory.to_data()
        progression_results = []
        try:
            for key, amount in sorted(reward.currencies.items()):
                self.currencies[key] = float(self.currencies.get(key, 0.0)) + float(amount)

            if reward.experience:
                for track_id, amount in sorted(reward.experience.items()):
                    progression_results.append(self.progression.add(track_id, amount))

            if reward.items:
                for item_id, amount in sorted(reward.items.items()):
                    self.inventory.add(item_id, int(amount))
        except Exception:
            self.currencies.clear()
            self.currencies.update(old_currencies)
            if self.progression is not None:
                self.progression.replace_from_data(old_progression)
            if self.inventory is not None:
                self.inventory.replace_from_data(old_inventory)
            emit_hook(self.hooks, "rpg.reward.apply_failed", data={"reward": reward})
            raise

        result = RewardApplicationResult(dict(reward.currencies), tuple(progression_results), dict(reward.items))
        emit_hook(self.hooks, "rpg.reward.after_apply", data={"result": result})
        return result
