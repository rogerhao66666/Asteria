"""Economy, quests, recipes and the world record (reputation, relationships, counters,
achievements, bestiary)."""

from __future__ import annotations

import random

from asteria.rpg import (
    RewardRuntime,
    roll_reward,
)
from asteria.rpg.economy import ShopRuntime
from asteria.rpg.enemies import RewardDefinition
from asteria.rpg.quests import QuestLog

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)


class EconomyMixin:
    # --- economy and quests -------------------------------------------------

    def _reward_runtime(self):
        return RewardRuntime(
            inventory=self.save.rpg_state.inventory,
            progression=self.save.rpg_state.progression,
            currencies=self.save.rpg_state.currencies,
        )

    @property
    def shops(self):
        state = self.save.rpg_state
        return ShopRuntime(
            self.project.rpg_database.shops,
            inventory=state.inventory,
            currencies=state.currencies,
            stock=state.shop_stock,
            condition=self._conditions_hold,
            receive_equipment=self.gain_equipment,  # gear bought goes to the equipment bag
            equipment=self.project.rpg_database.equipment,
        )

    def _conditions_hold(self, conditions):
        """Switch / variable conditions (``{"source", "name", "operator", "value"}``) all hold."""
        from asteria.events.conditions import EventCondition

        ctx = self.save.event_context
        return all(
            EventCondition(c["source"], c["name"], c["operator"], c["value"]).evaluate(ctx)
            for c in conditions
        )

    @property
    def quest_log(self):
        def grant(reward: RewardDefinition):
            self._reward_runtime().apply(roll_reward(reward, random.Random(0)))

        return QuestLog(
            self.project.rpg_database.quests,
            self.save.rpg_state.quests,
            inventory=self.save.rpg_state.inventory,
            switches=self.save.event_context.get_switch,
            grant_reward=grant,
        )

    def recipe_known(self, recipe_id):
        recipe = self.project.rpg_database.composition_recipes[str(recipe_id)]
        return not recipe.requires_discovery or recipe.recipe_id in self.world.known_recipes

    def known_recipes(self, station=None):
        """Recipes the player can see, optionally only those usable at ``station``."""
        recipes = self.project.rpg_database.composition_recipes
        return tuple(
            r
            for k, r in sorted(recipes.items())
            if self.recipe_known(k) and (station is None or not r.station or r.station == station)
        )

    def learn_recipe(self, recipe_id):
        recipe_id = str(recipe_id)
        if recipe_id not in self.project.rpg_database.composition_recipes:
            raise GameSessionError(f"unknown recipe: {recipe_id}")
        newly = recipe_id not in self.world.known_recipes
        if newly:
            self.world.known_recipes.append(recipe_id)
            self.save.event_context.set_switch(f"recipe.{recipe_id}.known", True)
        return newly

    def craft(self, payload, *, station="", quality_bonus=0.0, rng=None):
        """Craft with the project's recipes against the saved inventory and progression.

        Crafting the exact materials of an undiscovered recipe discovers it.
        """
        from asteria.rpg import CompositionRuntime

        runtime = CompositionRuntime(self.project.rpg_database.composition_recipes.values())
        state = self.save.rpg_state
        result = runtime.craft(
            state.inventory,
            payload,
            station=station,
            rng=rng,
            quality_bonus=quality_bonus,
            progression=state.progression,
        )
        self.learn_recipe(result.recipe_id)
        self.refresh_quests()
        return result

    def open_shop(self, shop_id):
        shop_id = str(shop_id)
        if shop_id not in self.project.rpg_database.shops:
            raise GameSessionError(f"unknown shop: {shop_id}")
        self.open_shop_id = shop_id
        return shop_id

    def close_shop(self):
        self.open_shop_id = None

    def buy(self, item_id, quantity=1, *, shop_id=None):
        result = self.shops.buy(shop_id or self.open_shop_id, item_id, quantity)
        self.refresh_quests()
        return result

    def sell(self, item_id, quantity=1, *, shop_id=None):
        result = self.shops.sell(shop_id or self.open_shop_id, item_id, quantity)
        self.refresh_quests()
        return result

    def _quest_switches(self):
        for quest_id, progress in self.save.rpg_state.quests.items():
            for status in ("active", "completed", "failed"):
                self.save.event_context.set_switch(
                    f"quest.{quest_id}.{status}", progress.status == status
                )

    def _quest_call(self, method, *args):
        log = self.quest_log
        result = getattr(log, method)(*args)
        self._quest_switches()
        self.refresh_achievements()
        return result

    # --- world record: reputation, relationships, counters, achievements, bestiary

    @property
    def world(self):
        return self.save.rpg_state.world

    def refresh_achievements(self):
        db = self.project.rpg_database
        log = QuestLog(db.quests, self.save.rpg_state.quests)
        unlocked = self.world.unlock_ready(
            db.achievements,
            factions=db.factions,
            switches=self.save.event_context.get_switch,
            quest_status=log.status,
        )
        for achievement_id in unlocked:
            self.save.event_context.set_switch(f"achievement.{achievement_id}.unlocked", True)
        return unlocked
