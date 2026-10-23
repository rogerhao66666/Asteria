"""World interactions (RPG-07): performing one, reputation, relationships, counters, captures and
quest steps."""

from __future__ import annotations

import random

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)


class InteractionsMixin:
    # -- world interactions (RPG-07) --------------------------------------------------------------
    def perform_interaction(self, interaction_id):
        """Run a world interaction: capability, requirements, cost, check, outcome, follow-up
        event.

        Returns ``(outcome, detail)`` with outcome ``success`` / ``failure`` / ``refused``; the
        outcome is
        also stored in the event variable ``interaction.<id>`` so the calling event can branch on
        it.
        """

        from asteria.events.conditions import EventCondition

        db = self.project.rpg_database
        interaction = db.world_interactions.get(str(interaction_id))
        if interaction is None:
            raise GameSessionError(f"unknown world interaction {interaction_id}")
        ctx = self.save.event_context
        state = self.save.rpg_state
        key = f"interaction.{interaction.interaction_id}"

        def finish(outcome, detail=""):
            ctx.set_variable(key, outcome)
            return outcome, detail

        if not interaction.repeatable and ctx.get_switch(f"{key}.done"):
            return finish("refused", "already done")
        party = [a for a in state.party_active_actor_ids if a in db.actors]
        if interaction.actor_tag and not any(
            interaction.actor_tag in db.actors[a].tags for a in party
        ):
            return finish("refused", f"needs a party member with {interaction.actor_tag}")
        if interaction.required_item and state.inventory.count(interaction.required_item) < 1:
            return finish("refused", f"needs {interaction.required_item}")
        for requirement in interaction.requirements:
            condition = EventCondition(
                requirement["source"],
                requirement["name"],
                requirement["operator"],
                requirement["value"],
            )
            if not condition.evaluate(ctx):
                return finish(
                    "refused",
                    f"requires {requirement['name']} {requirement['operator']} "
                    f"{requirement['value']}",
                )
        for item_id, quantity in interaction.cost_items.items():
            if state.inventory.count(item_id) < quantity:
                return finish("refused", f"not enough {item_id}")
        for currency_id, amount in interaction.cost_currencies.items():
            if state.currencies.get(currency_id, 0.0) < amount:
                return finish("refused", f"not enough {currency_id}")
        for item_id, quantity in interaction.cost_items.items():
            state.inventory.remove(item_id, int(quantity))
        for currency_id, amount in interaction.cost_currencies.items():
            state.currencies[currency_id] = state.currencies.get(currency_id, 0.0) - amount
        best = 0.0
        if interaction.check_stat:
            values = [
                state.actor_snapshots[a].stats["values"].get(interaction.check_stat, 0.0)
                for a in party
                if a in state.actor_snapshots
            ]
            best = max(values, default=0.0)
        attempts = int(ctx.get_variable(f"{key}.attempts", 0) or 0) + 1
        ctx.set_variable(f"{key}.attempts", attempts)
        roll = random.Random(
            f"{interaction.interaction_id}:{attempts}"
        ).random()  # deterministic per attempt
        if roll < interaction.chance(best):
            for item_id, quantity in interaction.success_items.items():
                state.inventory.add(item_id, int(quantity))
            for currency_id, amount in interaction.success_currencies.items():
                state.currencies[currency_id] = state.currencies.get(currency_id, 0.0) + amount
            for faction_id, amount in interaction.reputation.items():
                self.change_reputation(faction_id, amount)
            if interaction.success_switch:
                ctx.set_switch(interaction.success_switch, True)
            if not interaction.repeatable:
                ctx.set_switch(f"{key}.done", True)
            if interaction.success_event:
                self.pending_followups.append(interaction.success_event)
            self.refresh_quests()
            return finish("success")
        if interaction.failure_switch:
            ctx.set_switch(interaction.failure_switch, True)
        if interaction.failure_event:
            self.pending_followups.append(interaction.failure_event)
        self.refresh_quests()
        return finish("failure")

    def change_reputation(self, faction_id, amount):
        faction = self.project.rpg_database.factions.get(str(faction_id))
        if faction is None:
            raise GameSessionError(f"unknown faction: {faction_id}")
        value = self.world.change_reputation(faction, amount)
        self.save.event_context.set_variable(f"reputation.{faction.faction_id}", value)
        self.refresh_achievements()
        return value

    def change_relationship(self, subject_id, amount):
        value = self.world.change_relationship(subject_id, amount)
        self.save.event_context.set_variable(f"relationship.{subject_id}", value)
        return value

    def add_counter(self, counter_id, amount=1):
        value = self.world.add_counter(counter_id, amount)
        self.refresh_achievements()
        return value

    def capture_chance(self, target_id):
        """Chance (0–1) that capturing ``target_id`` succeeds now, or None if it cannot be
        captured."""
        if self.mode != "battle" or str(target_id) not in self.active_enemy_ids():
            return None
        rule = self.project.rpg_database.capture_rules.get(str(target_id).rsplit(":", 1)[0])
        if rule is None:
            return None
        resources = self.battle.member(str(target_id)).subject.resources
        resource = self.rules.knockout_resource_id
        ratio = 1.0
        if (
            resource
            and resource in resources.to_data()["values"]
            and resources.maximum(resource) > 0
        ):
            ratio = resources.current(resource) / resources.maximum(resource)
        return rule.chance(ratio)

    def capture_targets(self):
        """``(member_id, chance, item_id)`` for every enemy that can be captured right now."""
        result = []
        for member_id in self.active_enemy_ids():
            chance = self.capture_chance(member_id)
            if chance is not None:
                rule = self.project.rpg_database.capture_rules[member_id.rsplit(":", 1)[0]]
                result.append((member_id, chance, rule.item_id))
        return tuple(result)

    def attempt_capture(self, actor_id, target_id, *, rng=None):
        """Try to capture enemy ``target_id``; on success it leaves battle and its actor joins the
        roster."""
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        target_id = str(target_id)
        if target_id not in self.active_enemy_ids():
            raise GameSessionError(f"{target_id} cannot be captured now")
        enemy_id = target_id.rsplit(":", 1)[0]
        rule = self.project.rpg_database.capture_rules.get(enemy_id)
        if rule is None:
            raise GameSessionError(f"{enemy_id} cannot be captured")
        state = self.save.rpg_state
        if rule.item_id and not state.inventory.remove(rule.item_id, 1):
            raise GameSessionError(
                self.tr("battle.capture.needs", "capturing needs {item}", item=rule.item_id)
            )
        roll = (rng or self.battle.rng).random()
        success = roll < self.capture_chance(target_id)
        self._log(
            "capture",
            member_id=str(actor_id),
            target_ids=(target_id,),
            data={"success": success, "actor_id": rule.actor_id},
        )
        if not success:
            return False
        self.battle.remove_combatant(target_id, state_id="captured", reason="captured")
        self._captured.add(target_id)
        self.world.note_enemy(enemy_id, "captured")
        if rule.pet_item_id:  # a pet item: kept in the bag, sent out by an ability that needs it
            state.inventory.add(rule.pet_item_id, 1)
        if rule.pet_species_id:  # an owned creature with its own level and nickname
            self.add_pet(rule.pet_species_id, level=rule.pet_level)
        if rule.actor_id and rule.actor_id not in state.party_actor_ids:
            state.party_actor_ids = state.party_actor_ids + (rule.actor_id,)
        if rule.actor_id:
            self.ensure_actor_progression(rule.actor_id)
        self.refresh_achievements()
        return True

    def start_quest(self, quest_id):
        return self._quest_call("start", quest_id)

    def advance_quest(self, quest_id, objective_id, amount=1):
        return self._quest_call("advance", quest_id, objective_id, amount)

    def complete_quest(self, quest_id):
        return self._quest_call("complete", quest_id)

    def fail_quest(self, quest_id):
        return self._quest_call("fail", quest_id)

    def refresh_quests(self):
        return self._quest_call("refresh")
