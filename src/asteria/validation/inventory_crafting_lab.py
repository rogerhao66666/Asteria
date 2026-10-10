from __future__ import annotations

from dataclasses import dataclass

from asteria.presentation import BattleActionWorkflowRuntime, BattleWorkflowOption
from asteria.rpg import ItemDefinition

from .playable_rpg import ReferenceActorScenario, build_reference_actor_scenario


@dataclass(frozen=True, slots=True)
class CompositionRecipe:
    recipe_id: str
    selections: tuple[tuple[str, tuple[str, ...]], ...]
    outputs: tuple[tuple[str, int], ...]

    def matches(self, payload):
        selected = {str(step_id): tuple(sorted(str(x) for x in values)) for step_id, values in dict(payload).items()}
        required = {str(step_id): tuple(sorted(values)) for step_id, values in self.selections}
        return selected == required


@dataclass(frozen=True, slots=True)
class CompositionResult:
    recipe_id: str
    consumed: tuple[tuple[str, int], ...]
    produced: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class InventoryCraftingLabSnapshot:
    counts: tuple[tuple[str, int], ...]
    completed_recipes: tuple[str, ...]


class InventoryCraftingLab:
    """Operable generic composition controller over canonical Inventory.

    The workflow runtime collects selections only. Recipe lookup, inventory
    validation, consumption, and production remain controller/project policy.
    """

    def __init__(self, scenario: ReferenceActorScenario | None = None):
        self.scenario = scenario or build_reference_actor_scenario()
        self.inventory = self.scenario.inventory
        self.item_catalog = {x.item_id: x for x in self.scenario.item_catalog}
        self.item_catalog.update(
            {
                "healing_tonic": ItemDefinition("healing_tonic", "Healing Tonic", tags=("crafted", "restorative")),
                "spark_tonic": ItemDefinition("spark_tonic", "Spark Tonic", tags=("crafted", "volatile")),
            }
        )
        self.workflow = BattleActionWorkflowRuntime()
        self.completed_recipes = []

        self.recipes = (
            CompositionRecipe(
                "healing_tonic_recipe",
                (
                    ("base", ("red_herb",)),
                    ("reagent", ("glass_vial",)),
                    ("catalyst", ()),
                ),
                (("healing_tonic", 1),),
            ),
            CompositionRecipe(
                "spark_tonic_recipe",
                (
                    ("base", ("red_herb",)),
                    ("reagent", ("spark_dust",)),
                    ("catalyst", ("glass_vial",)),
                ),
                (("spark_tonic", 1),),
            ),
        )

    def _option(self, item_id):
        definition = self.item_catalog[item_id]
        count = self.inventory.count(item_id)
        return BattleWorkflowOption(
            item_id,
            definition.display_name,
            enabled=count > 0,
            detail=f"Owned: {count}",
            tags=definition.tags,
        )

    def options_for_step(self, step_id):
        step_id = str(step_id)
        if step_id == "base":
            ids = ("red_herb",)
        elif step_id == "reagent":
            ids = ("glass_vial", "spark_dust")
        elif step_id == "catalyst":
            ids = ("glass_vial",)
        else:
            ids = ()
        return tuple(self._option(x) for x in ids)

    def begin(self):
        return self.workflow.begin(
            self.scenario.alchemy_workflow,
            self.options_for_step("base"),
        )

    def select(self, item_id):
        return self.workflow.select(item_id)

    def advance(self):
        current = self.workflow.view
        if current is None:
            raise RuntimeError("no active workflow")
        next_index = current.step_index + 1
        next_options = ()
        if next_index < len(self.scenario.alchemy_workflow.steps):
            next_step = self.scenario.alchemy_workflow.steps[next_index]
            next_options = self.options_for_step(next_step.step_id)
        return self.workflow.advance(next_options)

    def resolve_recipe(self):
        view = self.workflow.view
        if view is None or not view.complete:
            raise ValueError("composition workflow is incomplete")
        payload = self.workflow.selection_payload()["selections"]
        for recipe in self.recipes:
            if recipe.matches(payload):
                return recipe
        return None

    def craft(self):
        recipe = self.resolve_recipe()
        if recipe is None:
            raise ValueError("no matching composition recipe")

        # Count every selected ingredient occurrence by canonical item ID.
        payload = self.workflow.selection_payload()["selections"]
        needed = {}
        for values in payload.values():
            for item_id in values:
                needed[item_id] = needed.get(item_id, 0) + 1

        missing = tuple(
            (item_id, amount, self.inventory.count(item_id))
            for item_id, amount in sorted(needed.items())
            if self.inventory.count(item_id) < amount
        )
        if missing:
            text = ", ".join(f"{item_id} requires {amount}, owned {owned}" for item_id, amount, owned in missing)
            raise ValueError("insufficient materials: " + text)

        before = self.inventory.to_data()
        try:
            for item_id, amount in sorted(needed.items()):
                if not self.inventory.remove(item_id, amount):
                    raise RuntimeError("inventory changed during composition")
            for item_id, amount in recipe.outputs:
                self.inventory.add(item_id, amount)
        except Exception:
            self.inventory.replace_from_data(before)
            raise

        consumed = tuple(sorted(needed.items()))
        produced = tuple(recipe.outputs)
        self.completed_recipes.append(recipe.recipe_id)
        self.workflow.cancel()
        return CompositionResult(recipe.recipe_id, consumed, produced)

    def snapshot(self):
        return InventoryCraftingLabSnapshot(
            tuple(sorted(self.inventory._counts.items())),
            tuple(self.completed_recipes),
        )
