from __future__ import annotations

import random
from dataclasses import dataclass


def _id(v, label):
    v = str(v).strip()
    if not v:
        raise ValueError(f"{label} is required")
    return v


@dataclass(frozen=True, slots=True)
class CompositionSelection:
    step_id: str
    item_ids: tuple[str, ...]

    def __init__(self, step_id, item_ids=()):
        object.__setattr__(self, "step_id", _id(step_id, "step_id"))
        object.__setattr__(self, "item_ids", tuple(_id(x, "item_id") for x in item_ids))

    def to_data(self):
        return {"step_id": self.step_id, "item_ids": list(self.item_ids)}

    @classmethod
    def from_data(cls, data):
        if set(data) != {"step_id", "item_ids"}:
            raise ValueError("invalid composition selection")
        return cls(data["step_id"], data["item_ids"])


@dataclass(frozen=True, slots=True)
class CompositionOutput:
    item_id: str
    amount: int = 1

    def __init__(self, item_id, amount=1):
        amount = int(amount)
        if amount < 1:
            raise ValueError("composition output amount must be >= 1")
        object.__setattr__(self, "item_id", _id(item_id, "item_id"))
        object.__setattr__(self, "amount", amount)

    def to_data(self):
        return {"item_id": self.item_id, "amount": self.amount}

    @classmethod
    def from_data(cls, data):
        if set(data) != {"item_id", "amount"}:
            raise ValueError("invalid composition output")
        return cls(data["item_id"], data["amount"])


@dataclass(frozen=True, slots=True)
class CompositionQualityTier:
    """Outputs that replace a recipe's normal outputs when the quality roll reaches
    ``threshold``."""

    quality: str
    threshold: float
    outputs: tuple[CompositionOutput, ...]

    def __init__(self, quality, threshold, outputs):
        threshold = float(threshold)
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("quality threshold must be between 0 and 1")
        outputs = tuple(
            x if isinstance(x, CompositionOutput) else CompositionOutput.from_data(x)
            for x in outputs
        )
        if not outputs:
            raise ValueError("quality tier requires outputs")
        object.__setattr__(self, "quality", _id(quality, "quality"))
        object.__setattr__(self, "threshold", threshold)
        object.__setattr__(self, "outputs", outputs)

    def to_data(self):
        return {
            "quality": self.quality,
            "threshold": self.threshold,
            "outputs": [x.to_data() for x in self.outputs],
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["quality"],
            data["threshold"],
            [CompositionOutput.from_data(x) for x in data["outputs"]],
        )


@dataclass(frozen=True, slots=True)
class CompositionRecipeDefinition:
    """A crafting recipe.

    ``station`` names the workstation the recipe needs (empty: anywhere).
    ``success_chance`` below 1 can fail: materials are consumed and
    ``failure_outputs`` produced instead. On success a quality roll (plus the
    caller's bonus) picks the highest ``quality_tiers`` entry it reaches,
    whose outputs replace ``outputs``; ``experience`` maps progression tracks
    to the experience a success grants. ``requires_discovery`` hides the
    recipe from crafting menus until the player learns or discovers it.
    """

    recipe_id: str
    display_name: str
    selections: tuple[CompositionSelection, ...]
    outputs: tuple[CompositionOutput, ...]
    tags: tuple[str, ...] = ()
    station: str = ""
    success_chance: float = 1.0
    failure_outputs: tuple[CompositionOutput, ...] = ()
    quality_tiers: tuple[CompositionQualityTier, ...] = ()
    experience: dict = None
    requires_discovery: bool = False

    def __init__(
        self,
        recipe_id,
        display_name=None,
        *,
        selections,
        outputs,
        tags=(),
        station="",
        success_chance=1.0,
        failure_outputs=(),
        quality_tiers=(),
        experience=None,
        requires_discovery=False,
    ):
        selections = tuple(
            x if isinstance(x, CompositionSelection) else CompositionSelection.from_data(x)
            for x in selections
        )
        outputs = tuple(
            x if isinstance(x, CompositionOutput) else CompositionOutput.from_data(x)
            for x in outputs
        )
        failure_outputs = tuple(
            x if isinstance(x, CompositionOutput) else CompositionOutput.from_data(x)
            for x in failure_outputs
        )
        quality_tiers = tuple(
            sorted(
                (
                    x
                    if isinstance(x, CompositionQualityTier)
                    else CompositionQualityTier.from_data(x)
                    for x in quality_tiers
                ),
                key=lambda x: x.threshold,
            )
        )
        if not selections:
            raise ValueError("composition recipe requires selections")
        if not outputs:
            raise ValueError("composition recipe requires outputs")
        ids = [x.step_id for x in selections]
        if len(ids) != len(set(ids)):
            raise ValueError("composition step ids must be unique")
        success_chance = float(success_chance)
        if not 0.0 <= success_chance <= 1.0:
            raise ValueError("success_chance must be between 0 and 1")
        if len({x.quality for x in quality_tiers}) != len(quality_tiers):
            raise ValueError("quality names must be unique")
        experience = {
            _id(k, "progression track"): float(v) for k, v in dict(experience or {}).items()
        }
        if any(v < 0 for v in experience.values()):
            raise ValueError("experience must be >= 0")
        object.__setattr__(self, "recipe_id", _id(recipe_id, "recipe_id"))
        object.__setattr__(self, "display_name", str(display_name or recipe_id))
        object.__setattr__(self, "selections", selections)
        object.__setattr__(self, "outputs", outputs)
        object.__setattr__(self, "tags", tuple(sorted({_id(x, "tag").lower() for x in tags})))
        object.__setattr__(self, "station", str(station).strip())
        object.__setattr__(self, "success_chance", success_chance)
        object.__setattr__(self, "failure_outputs", failure_outputs)
        object.__setattr__(self, "quality_tiers", quality_tiers)
        object.__setattr__(self, "experience", experience)
        object.__setattr__(self, "requires_discovery", bool(requires_discovery))

    def matches(self, payload):
        selected = {str(k): tuple(sorted(str(x) for x in v)) for k, v in dict(payload).items()}
        required = {x.step_id: tuple(sorted(x.item_ids)) for x in self.selections}
        return selected == required

    @property
    def _extended(self):
        return bool(
            self.station
            or self.success_chance < 1.0
            or self.failure_outputs
            or self.quality_tiers
            or self.experience
            or self.requires_discovery
        )

    def all_output_item_ids(self):
        ids = [x.item_id for x in self.outputs + self.failure_outputs]
        ids.extend(o.item_id for tier in self.quality_tiers for o in tier.outputs)
        return tuple(dict.fromkeys(ids))

    def to_data(self):
        data = {
            "schema": "asteria.rpg.composition_recipe",
            "version": 2 if self._extended else 1,
            "recipe_id": self.recipe_id,
            "display_name": self.display_name,
            "selections": [x.to_data() for x in self.selections],
            "outputs": [x.to_data() for x in self.outputs],
            "tags": list(self.tags),
        }
        if self._extended:
            data.update(
                {
                    "station": self.station,
                    "success_chance": self.success_chance,
                    "failure_outputs": [x.to_data() for x in self.failure_outputs],
                    "quality_tiers": [x.to_data() for x in self.quality_tiers],
                    "experience": dict(sorted(self.experience.items())),
                    "requires_discovery": self.requires_discovery,
                }
            )
        return data

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.composition_recipe" or data.get("version") not in {
            1,
            2,
        }:
            raise ValueError("unsupported composition recipe")
        return cls(
            data["recipe_id"],
            data["display_name"],
            selections=[CompositionSelection.from_data(x) for x in data["selections"]],
            outputs=[CompositionOutput.from_data(x) for x in data["outputs"]],
            tags=data["tags"],
            station=data.get("station", ""),
            success_chance=data.get("success_chance", 1.0),
            failure_outputs=[
                CompositionOutput.from_data(x) for x in data.get("failure_outputs", ())
            ],
            quality_tiers=[
                CompositionQualityTier.from_data(x) for x in data.get("quality_tiers", ())
            ],
            experience=data.get("experience"),
            requires_discovery=data.get("requires_discovery", False),
        )


@dataclass(frozen=True, slots=True)
class CompositionResult:
    recipe_id: str
    consumed: tuple[tuple[str, int], ...]
    produced: tuple[tuple[str, int], ...]
    success: bool = True
    quality: str = ""
    experience: tuple[tuple[str, float], ...] = ()


class CompositionRuntime:
    def __init__(self, recipes=()):
        self.recipes = {x.recipe_id: x for x in recipes}
        if len(self.recipes) != len(tuple(recipes)):
            raise ValueError("duplicate composition recipe")

    def resolve(self, payload):
        return next((x for x in self.recipes.values() if x.matches(payload)), None)

    def craft(
        self, inventory, payload, *, station="", rng=None, quality_bonus=0.0, progression=None
    ):
        """Consume materials and produce outputs; ``rng`` drives success and quality rolls."""
        recipe = self.resolve(payload)
        if recipe is None:
            raise ValueError("no matching composition recipe")
        if recipe.station and recipe.station != str(station or ""):
            raise ValueError(f"recipe {recipe.recipe_id} requires station {recipe.station}")
        needed = {}
        for values in dict(payload).values():
            for item_id in values:
                item_id = str(item_id)
                needed[item_id] = needed.get(item_id, 0) + 1
        missing = [
            (k, n, inventory.count(k)) for k, n in sorted(needed.items()) if inventory.count(k) < n
        ]
        if missing:
            raise ValueError(
                "insufficient materials: "
                + ", ".join(f"{k} requires {n}, owned {o}" for k, n, o in missing)
            )
        rng = rng or random.Random()
        success = recipe.success_chance >= 1.0 or rng.random() < recipe.success_chance
        quality = ""
        outputs = recipe.outputs if success else recipe.failure_outputs
        if success and recipe.quality_tiers:
            roll = rng.random() + float(quality_bonus)
            for tier in recipe.quality_tiers:
                if roll >= tier.threshold:
                    quality, outputs = tier.quality, tier.outputs
        experience = tuple(sorted(recipe.experience.items())) if success else ()
        if experience and progression is None:
            raise ValueError("recipe grants experience but no ProgressionRuntime was supplied")
        before = inventory.to_data()
        progress_before = None if progression is None else progression.to_data()
        try:
            for k, n in sorted(needed.items()):
                if not inventory.remove(k, n):
                    raise RuntimeError("inventory changed during composition")
            for out in outputs:
                inventory.add(out.item_id, out.amount)
            for track_id, amount in experience:
                progression.add(track_id, amount)
        except Exception:
            inventory.replace_from_data(before)
            if progress_before is not None:
                progression.replace_from_data(progress_before)
            raise
        return CompositionResult(
            recipe.recipe_id,
            tuple(sorted(needed.items())),
            tuple((x.item_id, x.amount) for x in outputs),
            success,
            quality,
            experience,
        )
