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

    def capture_rule_for(self, target_id):
        """The capture rule of an enemy unit: its kind's rule, a species foe's species rule or
        the ``*`` rule; ``None`` when it cannot be captured (no rule, or an encounter tagged
        ``no_capture``)."""
        encounter = self.project.rpg_database.encounters.get(self.encounter_id or "")
        if encounter is not None and "no_capture" in encounter.tags:
            return None
        rules = self.project.rpg_database.capture_rules
        kind = str(target_id).rsplit(":", 1)[0]
        rule = rules.get(kind)
        if rule is None and self.foe_record(target_id) is not None:
            rule = rules.get("*")
        return rule

    def capture_chance(self, target_id, item_id=None):
        """Chance (0–1) that capturing ``target_id`` succeeds now (thrown with ``item_id``,
        default the rule's item), or None if it cannot be captured."""
        if self.mode != "battle" or str(target_id) not in self.active_enemy_ids():
            return None
        rule = self.capture_rule_for(target_id)
        if rule is None:
            return None
        encounter = self.project.rpg_database.encounters.get(self.encounter_id or "")
        if encounter is not None and "sure_capture" in encounter.tags:
            return 1.0  # a battle that always ends in the catch (a tutorial)
        member = self.battle.member(str(target_id))
        resources = member.subject.resources
        resource = self.rules.knockout_resource_id
        ratio = 1.0
        if (
            resource
            and resource in resources.to_data()["values"]
            and resources.maximum(resource) > 0
        ):
            ratio = resources.current(resource) / resources.maximum(resource)
        rate = 0.0
        record = self.foe_record(target_id)
        species = self.pet_species(record) if record is not None else None
        if species is None and rule.pet_species_id:
            species = self.project.rpg_database.pet_species.get(rule.pet_species_id)
        if species is not None:
            rate = species.capture_rate
        states = member.subject.states
        state_ids = tuple(a.state_id for a in states.active_states()) if states else ()
        item = rule.item_id if item_id is None else str(item_id)
        return rule.chance(ratio, rate=rate, item_id=item or None, state_ids=state_ids)

    def capture_targets(self):
        """``(member_id, chance, item_id)`` for every enemy that can be captured right now."""
        result = []
        for member_id in self.active_enemy_ids():
            chance = self.capture_chance(member_id)
            if chance is not None:
                result.append((member_id, chance, self.capture_rule_for(member_id).item_id))
        return tuple(result)

    def capture_items(self, target_id):
        """``(item_id, chance)`` for every capture item the bag holds that the target's rule
        allows (the rule's own item and its bonus items); empty when the rule needs none."""
        rule = self.capture_rule_for(target_id)
        if rule is None or self.capture_chance(target_id) is None:
            return ()
        inventory = self.save.rpg_state.inventory
        return tuple(
            (item_id, self.capture_chance(target_id, item_id))
            for item_id in rule.capture_items()
            if inventory.count(item_id) > 0
        )

    def attempt_capture(self, actor_id, target_id, *, rng=None, item_id=None):
        """Try to capture enemy ``target_id`` (throwing ``item_id``, default the rule's item);
        on success it leaves battle and its actor joins the roster or it becomes an owned
        pet (a species foe keeps its level, health, moves and genes)."""
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        target_id = str(target_id)
        if target_id not in self.active_enemy_ids():
            raise GameSessionError(f"{target_id} cannot be captured now")
        enemy_id = target_id.rsplit(":", 1)[0]
        rule = self.capture_rule_for(target_id)
        if rule is None:
            raise GameSessionError(f"{enemy_id} cannot be captured")
        state = self.save.rpg_state
        item = rule.item_id if item_id is None else str(item_id)
        if item and item not in rule.capture_items():
            raise GameSessionError(f"{item} cannot capture {enemy_id}")
        if item and not state.inventory.remove(item, 1):
            raise GameSessionError(
                self.tr("battle.capture.needs", "capturing needs {item}", item=item)
            )
        chance = self.capture_chance(target_id, item or None)
        success, shakes = rule.roll(chance, rng or self.battle.rng)
        self._log(
            "capture",
            member_id=str(actor_id),
            target_ids=(target_id,),
            data={
                "success": success,
                "actor_id": rule.actor_id,
                "item_id": item,
                "shakes": shakes,
            },
        )
        if not success:
            return False
        unit = self.battle.member(target_id)
        self.battle.remove_combatant(target_id, state_id="captured", reason="captured")
        self._captured.add(target_id)
        self.world.note_enemy(enemy_id, "captured")
        if rule.pet_item_id:  # a pet item: kept in the bag, sent out by an ability that needs it
            state.inventory.add(rule.pet_item_id, 1)
        record = self.foe_record(target_id)
        if record is not None:  # the creature as it stood: health, states, moves, genes
            pool = unit.subject.resources
            record.resources = {n: float(pool.current(n)) for n in pool.to_data()["values"]}
            states = unit.subject.states
            record.states = [a.state_id for a in states.active_states()] if states else []
            self.add_pet(record.species_id, record=record)
        elif rule.pet_species_id:  # an owned creature with its own level and nickname
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
