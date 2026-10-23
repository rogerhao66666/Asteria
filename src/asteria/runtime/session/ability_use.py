"""Using abilities in battle: sequence, targets, boost, forms, costs, what follows a use,
concoctions and battle items."""

from __future__ import annotations

import dataclasses

from asteria.gameplay.conditions import GameplayConditionContext
from asteria.rpg.targeting import TargetRelation

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)


class AbilityUseMixin:
    def battle_sequence(self, sequence_id, actor_id, target_id=""):
        """Run an action sequence (a combo): ``actor_id`` leads, the other active party
        members fill the remaining participant places in party order."""
        if self.battle is None:
            raise GameSessionError("no active battle")
        definitions = self.battle.action_sequences.definitions
        if sequence_id not in definitions:
            raise GameSessionError(f"unknown action sequence {sequence_id}")
        side = self.battle.member(actor_id).side
        others = [
            m.member_id
            for m in self.battle.parties[side].members
            if m.member_id != actor_id and self.battle.is_active(m)
        ]
        limit = max(1, int(definitions[sequence_id].max_participants))
        participants = (actor_id, *others)[:limit]
        targets = (target_id,) if target_id else ()
        plan, results, failures = self.battle.execute_sequence(sequence_id, participants, targets)
        for step, _result in results:  # each blow is logged like an action, so it plays
            self._log(
                "action",
                member_id=step.actor_id,
                ability_id=step.ability_id,
                target_ids=tuple(step.target_ids),
                outcomes=self._action_outcomes(
                    step.actor_id, step.ability_id, step.target_ids, None
                ),
            )
        return plan, results, failures

    def _is_conscious(self, member):
        resource = self.rules.knockout_resource_id
        if not resource or resource not in member.subject.resources.to_data()["values"]:
            return True
        return member.subject.resources.current(resource) > 0

    def ability_relation(self, ability_id):
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        definition = self.battle.targeting.definition_for(ability_id)
        return TargetRelation.OPPONENT if definition is None else definition.relation

    def default_targets(self, actor_id, ability_id):
        """Targets a manual selection would default to, from the ability's targeting data."""
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        definition = self.battle.targeting.definition_for(ability_id)
        if definition is not None and definition.relation == TargetRelation.SELF:
            return (str(actor_id),)
        candidates = self.battle.targeting.candidates(actor_id, ability_id)
        maximum = 1 if definition is None else max(1, definition.maximum_targets)
        return tuple(candidates[:maximum])

    def max_boost_level(self, actor_id):
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        rules = self.rules
        if not rules.boost_enabled:
            return 0
        available = self.battle.battle_resources.current(actor_id, rules.boost_resource_id)
        return min(rules.boost_max_level, int(available // rules.boost_cost_per_level))

    def use_ability(
        self, actor_id, ability_id, target_ids=None, *, boost_level=0, form=None, choices=None
    ):
        """Run one player action through project rules: targeting, boost and hit gauges.

        Each boost level spends ``boost_cost_per_level`` of the boost resource
        and repeats the action once more. ``choices`` (``{step_id: [option_id, ...]}``) answer the
        ability's Command Input Steps (its first options when left out). Every action against
        opponents emits ``hit_trigger`` into all project gauge compositions.
        """
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        rules = self.rules
        boost_level = int(boost_level)
        if boost_level < 0 or boost_level > self.max_boost_level(actor_id):
            raise GameSessionError(f"boost level {boost_level} is not available")
        definition = self.battle.ability_runtime.registry.get(ability_id)
        if definition is not None and definition.concoct_station:
            raise GameSessionError(
                f"{ability_id} concocts: use concoct() with the chosen ingredients"
            )
        if definition is not None and ability_id in self.battle.member(actor_id).ability_ids:
            reason = self.ability_unavailable(actor_id, ability_id)
            if reason and not reason.startswith(
                ("Ready in", "Blocked by")
            ):  # those keep their own errors
                raise GameSessionError(f"{ability_id}: {reason}")
        targets = (
            tuple(target_ids)
            if target_ids is not None
            else self.default_targets(actor_id, ability_id)
        )
        if not targets:
            raise GameSessionError(f"{ability_id} has no valid targets")
        offensive = self.ability_relation(ability_id) == TargetRelation.OPPONENT
        targets, forced = self._override_targets(actor_id, targets)
        battle_costs = dict(getattr(definition, "battle_costs", None) or {})
        if boost_level:  # boost and the ability's own battle costs come from the same gauges
            key = rules.boost_resource_id
            battle_costs[key] = (
                battle_costs.get(key, 0.0) + boost_level * rules.boost_cost_per_level
            )
        for resource_id, amount in battle_costs.items():
            have = self.battle.battle_resources.current(actor_id, resource_id)
            if have < amount:
                raise GameSessionError(f"{ability_id} needs {amount:g} {resource_id} ({have:g})")
        for resource_id, amount in (getattr(definition, "battle_costs", None) or {}).items():
            self.battle.battle_resources.spend(
                actor_id, resource_id, amount, trigger="rpg.session.ability_cost"
            )
        if boost_level:
            self.battle.battle_resources.spend(
                actor_id,
                rules.boost_resource_id,
                boost_level * rules.boost_cost_per_level,
                trigger="rpg.session.boost",
            )
        chosen = self._resolve_form(actor_id, definition, form)
        picked = self._resolve_choices(actor_id, definition, choices)
        if picked is not None:
            chosen = _merge_casts(chosen, picked)
            reason = self.form_unavailable(actor_id, chosen)
            if reason:
                raise GameSessionError(f"{ability_id}: {reason}")
        self._pay_spent_goods(definition)
        if chosen is not None:
            self._pay_form_costs(actor_id, chosen)
        timing = self.battle.action_timing.definition_for(ability_id)
        if (
            timing.windup > 0 and rules.action_timing == "timeline"
        ):  # GP-02: the cast resolves later
            return self._begin_cast(actor_id, ability_id, targets, timing)
        ability_tags = set(getattr(definition, "tags", ()) or ())
        repeats = boost_level + 1
        if "boost.power" in ability_tags or (
            rules.boost_mode == "power" and "boost.repeat" not in ability_tags
        ):
            repeats = 1  # one stronger action: interaction rules read the boost tags
        boost_tags = ("boost", f"boost.{boost_level}") if boost_level else ()
        if chosen is not None:
            boost_tags = (*boost_tags, *chosen.get("tags", ()))
        actor_tags = self.battle.member(actor_id).subject.tags
        added = [t for t in boost_tags if not actor_tags.contains(t)]
        for tag in added:
            actor_tags.add(tag)
        self._forced_cast = forced
        try:
            results = self._repeat_action(
                actor_id,
                ability_id,
                targets,
                offensive,
                repeats,
                power=float((chosen or {}).get("power", 1.0)),
            )
        finally:
            self._forced_cast = False
            for tag in added:
                actor_tags.remove(tag)
        if any(getattr(r, "success", True) for r in results):
            if chosen is not None and chosen.get("apply_states"):
                definition = dataclasses.replace(
                    definition,
                    apply_states=(*definition.apply_states, *chosen["apply_states"]),
                )
            self._after_ability(actor_id, definition, targets)
        return results

    def _override_targets(self, actor_id, targets):
        """Targets after the afflicted member's states have had their say (confusion, charm...):
        ``(targets, forced)``; the same number of targets, picked at random from who the state
        allows."""
        member = self.battle.member(actor_id)
        states = member.subject.states
        if states is None or not targets:
            return tuple(targets), False
        policies = self.battle.battle_states.policies
        rule = next(
            (
                policies[a.state_id].target_override
                for a in states.active_states()
                if a.state_id in policies and policies[a.state_id].target_override
            ),
            "",
        )
        if not rule:
            return tuple(targets), False
        alive = [m for m in self.battle.members.values() if self.battle.is_active(m)]
        if rule == "random_opponent":
            pool = [m.member_id for m in alive if m.side != member.side]
        elif rule == "random_ally":
            pool = [m.member_id for m in alive if m.side == member.side]
        else:
            pool = [m.member_id for m in alive]
        if not pool:
            return tuple(targets), False
        rng = self.battle.rng
        count = min(len(targets), len(pool))
        return tuple(rng.sample(sorted(pool), count)), True

    def _resolve_form(self, actor_id, definition, form):
        """The casting form chosen for ``definition`` (the first when none is named), checked
        against what the user can afford; ``None`` for a skill without forms."""
        forms = tuple(getattr(definition, "forms", ()) or ())
        if not forms:
            if form not in (None, ""):
                raise GameSessionError(f"{definition.ability_id} has no forms")
            return None
        if form in (None, ""):
            chosen = forms[0]
        else:
            chosen = next((f for f in forms if f["form_id"] == str(form)), None)
            if chosen is None:
                raise GameSessionError(f"{definition.ability_id} has no form {form}")
        reason = self.form_unavailable(actor_id, chosen)
        if reason:
            raise GameSessionError(f"{definition.ability_id}/{chosen['form_id']}: {reason}")
        return chosen

    def input_workflow(self, ability_id):
        """The Command Input Steps record an ability asks the player to walk, else None."""
        definition = self.battle.ability_runtime.registry.get(ability_id) if self.battle else None
        name = getattr(definition, "input_workflow", "") if definition is not None else ""
        library = self.project.battle_presentation_library
        if not name or name not in library.ids("action_workflows"):
            return None
        return library.require("action_workflows", name)

    def _resolve_choices(self, actor_id, definition, choices):
        """What the chosen options of the ability's input steps add to the cast (tags, power,
        costs) as one form-like dict; ``None`` for an ability without input steps."""
        workflow = self.input_workflow(definition.ability_id) if definition is not None else None
        if workflow is None:
            if choices:
                raise GameSessionError(f"{definition.ability_id} has no input steps")
            return None
        choices = {str(k): [str(x) for x in v] for k, v in dict(choices or {}).items()}
        picked = []
        for step in workflow.steps:
            by_id = {o.option_id: o for o in step.options if o.enabled}
            ids = choices.get(step.step_id)
            if ids is None:  # left out: the first options the step needs
                ids = list(by_id)[: step.minimum_selections]
            if not step.minimum_selections <= len(ids) <= step.maximum_selections:
                raise GameSessionError(
                    f"{definition.ability_id}/{step.step_id}: choose "
                    f"{step.minimum_selections}-{step.maximum_selections}"
                )
            for option_id in ids:
                if option_id not in by_id:
                    raise GameSessionError(f"{step.step_id} has no option {option_id}")
                picked.append(by_id[option_id])
        cast = {"form_id": workflow.workflow_id, "tags": [], "power": 1.0}
        for option in picked:
            payload = dict(option.payload)
            cast = _merge_casts(
                cast,
                {
                    "tags": list(option.tags),
                    "power": float(payload.get("power", 1.0)),
                    "resource_costs": dict(payload.get("resource_costs", {})),
                    "battle_costs": dict(payload.get("battle_costs", {})),
                },
            )
        return cast

    def form_unavailable(self, actor_id, form):
        """Why a form cannot be cast now ('' when it can): its extra costs against what the user
        has."""
        resources = self.battle.member(actor_id).subject.resources
        for resource, amount in form.get("resource_costs", {}).items():
            if not resources.contains(resource) or resources.current(resource) < amount:
                return self.tr(
                    "battle.reason.form_needs",
                    "needs {amount} {resource}",
                    amount=f"{amount:g}",
                    resource=resource,
                )
        for resource, amount in form.get("battle_costs", {}).items():
            have = self.battle.battle_resources.current(actor_id, resource)
            if have < amount:
                return self.tr(
                    "battle.reason.form_short",
                    "needs {amount} {resource} ({have})",
                    amount=f"{amount:g}",
                    resource=resource,
                    have=f"{have:g}",
                )
        return ""

    def _pay_form_costs(self, actor_id, form):
        resources = self.battle.member(actor_id).subject.resources
        for resource, amount in form.get("resource_costs", {}).items():
            resources.spend(resource, amount)
        for resource, amount in form.get("battle_costs", {}).items():
            self.battle.battle_resources.spend(
                actor_id, resource, amount, trigger="rpg.session.form_cost"
            )

    def _pay_spent_goods(self, definition):
        """Items and currency an ability spends, taken once per cast."""
        if definition is None:
            return
        inventory = self.save.rpg_state.inventory
        for item_id, count in (getattr(definition, "item_costs", None) or {}).items():
            inventory.remove(item_id, count)
        funds = self.save.rpg_state.currencies
        for currency, amount in (getattr(definition, "currency_costs", None) or {}).items():
            funds[currency] = funds.get(currency, 0.0) - amount
        for gauge_id, amount in (getattr(definition, "gauge_costs", None) or {}).items():
            self.change_party_gauge(gauge_id, -amount)

    def _after_ability(self, actor_id, definition, targets):
        """An ability's battle extras once it landed: battle resource gains (e.g. giving boost
        points to an
        ally) and world commands (e.g. SUMMON a companion)."""
        from asteria.events import WorldCommand

        if definition is None:
            return
        battle = self.battle
        side = battle.member(actor_id).side
        if "action.steal" in definition.tags:  # a skill that robs what it hits
            for target_id in targets:
                self.steal(actor_id, target_id)
        for gain in definition.battle_resource_gains:
            if gain["to"] == "self":
                members = (actor_id,)
            elif gain["to"] == "targets":
                members = tuple(targets)
            else:
                members = tuple(
                    m.member_id
                    for m in battle.members.values()
                    if m.side == side and battle.is_active(m)
                )
            for member_id in members:
                if battle.battle_resources.get(member_id, gain["resource"]) is not None:
                    battle.battle_resources.change(
                        member_id, gain["resource"], gain["amount"], trigger="rpg.session.gain"
                    )
                    self._log("resource_gain", member_id=str(member_id), data=dict(gain))
        for entry in definition.apply_states:
            if entry["to"] == "self":
                members = (actor_id,)
            elif entry["to"] == "targets":
                members = tuple(targets)
            else:
                members = tuple(
                    m.member_id
                    for m in battle.members.values()
                    if m.side == side and battle.is_active(m)
                )
            for member_id in members:
                if not battle.is_active(battle.member(member_id)):
                    continue
                if entry["remove"]:
                    states = battle.member(member_id).subject.states
                    if states is not None and states.get(entry["state"]) is not None:
                        states.remove(entry["state"])
                        self._log(
                            "state_removed",
                            member_id=str(member_id),
                            data={"state": entry["state"]},
                        )
                else:
                    result = battle.apply_state(entry["state"], actor_id, member_id)
                    self._log(
                        "state_applied",
                        member_id=str(member_id),
                        data={"state": entry["state"], "applied": result.applied},
                    )
        for command in definition.commands:
            first = targets[0] if targets else ""
            args = {
                k: (
                    v.replace("@actor", str(actor_id)).replace("@target", str(first))
                    if isinstance(v, str)
                    else v
                )
                for k, v in command["args"].items()
            }
            self.world_commands.dispatch(WorldCommand(command["command"], args))

    def ability_unavailable(self, actor_id, ability_id):
        """Why ``actor_id`` cannot use ``ability_id`` now ("" when it can): a blocking state, a
        cooldown,
        battle costs (boost points...), resource costs, unmet conditions (e.g. weapons it needs),
        or no
        ingredients to concoct. Menus show this as the disabled reason."""
        battle = self.battle
        if battle is None:
            return "Not in battle"
        definition = battle.ability_runtime.registry.get(ability_id)
        if definition is None:
            return f"Unknown ability {ability_id}"
        member = battle.member(actor_id)
        tr = self.tr  # the reasons are drawn: in the player's language (rpg.built_in_text)
        availability = battle.ability_availability(actor_id, ability_id)
        if not availability.allowed:
            states = ", ".join(availability.blocking_states)
            return tr("battle.reason.blocked", "Blocked by {states}", states=states)
        wait = battle.cooldown_remaining(actor_id, ability_id)
        if wait:
            key = "battle.reason.cooldown_one" if wait == 1 else "battle.reason.cooldown"
            return tr(key, "Ready in {turns} turn" + ("" if wait == 1 else "s"), turns=wait)
        short = "battle.reason.short", "Needs {amount} {resource} (has {have})"
        for resource_id, amount in definition.battle_costs.items():
            have = battle.battle_resources.current(actor_id, resource_id)
            if have < amount:
                name = resource_id.replace("_", " ")
                return tr(*short, amount=f"{amount:g}", resource=name, have=f"{have:g}")
        if (
            battle.extensions is not None
            and battle.extensions.uses_left(actor_id, ability_id) == 0
        ):
            return tr("battle.reason.no_uses", "No uses left this battle")
        wanted = getattr(definition, "requires_pet", "")
        if wanted:
            pet = self.active_pet()
            if pet is None or wanted not in ("any", pet.species_id):
                species = self.project.rpg_database.pet_species.get(wanted)
                name = species.display_name if species else tr("battle.reason.a_pet", "a pet")
                return tr("battle.reason.needs", "Needs {what}", what=name)
        pet_move = self._pet_move_missing(ability_id)
        if pet_move:
            return pet_move
        items = self.save.rpg_state.inventory
        needs_items = (
            *(getattr(definition, "requires_items", None) or {}).items(),
            *(getattr(definition, "item_costs", None) or {}).items(),
        )
        for item_id, count in needs_items:
            if items.count(item_id) < count:
                record = self.project.rpg_database.items.get(item_id)
                name = record.display_name if record is not None else item_id
                if count > 1:
                    return tr(
                        "battle.reason.needs_items",
                        "Needs {what} x{count}",
                        what=name,
                        count=count,
                    )
                return tr("battle.reason.needs", "Needs {what}", what=name)
        funds = self.save.rpg_state.currencies
        for currency, amount in (getattr(definition, "currency_costs", None) or {}).items():
            if funds.get(currency, 0.0) < amount:
                return tr(
                    "battle.reason.needs_amount",
                    "Needs {amount} {resource}",
                    amount=f"{amount:g}",
                    resource=currency,
                )
        for gauge_id, amount in (getattr(definition, "gauge_costs", None) or {}).items():
            have = self.party_gauge(gauge_id)
            if have < amount:
                name = gauge_id.replace("_", " ")
                return tr(*short, amount=f"{amount:g}", resource=name, have=f"{have:g}")
        resources = member.subject.resources
        for cost in definition.costs:
            terms = cost.amount.terms
            if not terms or any(t.source.value != "constant" for t in terms):
                continue  # formulas reading stats: the action itself checks them
            amount = sum(t.coefficient for t in terms)
            if resources.contains(cost.resource) and resources.current(cost.resource) < amount:
                return tr(
                    "battle.reason.needs_amount",
                    "Needs {amount} {resource}",
                    amount=f"{amount:g}",
                    resource=cost.resource.replace("_", " "),
                )
        try:
            met = definition.conditions.evaluate(GameplayConditionContext(member.subject, None))
        except Exception:  # conditions about a target are checked against the chosen target
            met = True
        if not met:
            what = describe_condition(definition.conditions, tr)
            return tr("battle.reason.needs", "Needs {what}", what=what)
        if definition.concoct_station and not self.concoct_ingredients(definition.concoct_station):
            return tr("battle.reason.no_ingredients", "No ingredients")
        return ""

    def concoct_ingredients(self, station):
        """Items in the bag that a recipe of ``station`` uses (what a concoct ability can pick
        from)."""
        db = self.project.rpg_database
        used = set()
        for recipe in db.composition_recipes.values():
            if recipe.station != station:
                continue
            for selection in recipe.selections:
                used.update(getattr(selection, "item_ids", ()) or ())
        inventory = self.save.rpg_state.inventory
        return tuple(sorted(i for i in used if inventory.count(i) > 0))

    def concoct(self, actor_id, ability_id, ingredients, target_ids=None, *, rng=None):
        """Use a concoct ability: the recipe of its station matching ``ingredients`` (``{slot:
        [item ids]}``)
        consumes them and its product - an item with a ``battle_ability`` - acts at once on the
        targets."""
        from asteria.rpg import CompositionRuntime

        definition = self.battle.ability_runtime.registry.require(ability_id)
        if not definition.concoct_station:
            raise GameSessionError(f"{ability_id} does not concoct")
        reason = self.ability_unavailable(actor_id, ability_id)
        if reason:
            raise GameSessionError(reason)
        recipes = [
            r
            for r in self.project.rpg_database.composition_recipes.values()
            if r.station == definition.concoct_station
        ]
        runtime = CompositionRuntime(recipes)
        recipe = runtime.resolve(ingredients)
        if recipe is None:
            raise GameSessionError("these ingredients make nothing")
        state = self.save.rpg_state
        before = {o.item_id: state.inventory.count(o.item_id) for o in recipe.outputs}
        result = runtime.craft(
            state.inventory, ingredients, station=definition.concoct_station, rng=rng
        )
        self.learn_recipe(result.recipe_id)
        made = [k for k, n in before.items() if state.inventory.count(k) > n]
        self._log(
            "concocted",
            member_id=str(actor_id),
            ability_id=str(ability_id),
            data={"recipe": recipe.recipe_id},
        )
        if not made:
            return ()  # the recipe failed (success chance): materials are gone, nothing acts
        return self.use_battle_item(actor_id, made[0], target_ids)

    def use_battle_item(self, actor_id, item_id, target_ids=None):
        """Use an item in battle: its ``battle_ability`` runs for ``actor_id`` (targets,
        interaction rules, gauges,
        VFX); the item is consumed. Items without one apply their use effects to the target
        member."""
        from asteria.gameplay.effects import apply_effect

        item = self.project.rpg_database.items.get(str(item_id))
        if item is None:
            raise GameSessionError(f"unknown item {item_id}")
        inventory = self.save.rpg_state.inventory
        if inventory.count(item.item_id) < 1:
            raise GameSessionError(
                self.tr("battle.item_none_left", "no {name} left", name=item.display_name)
            )
        battle = self.battle
        if item.battle_ability:
            targets = (
                tuple(target_ids)
                if target_ids
                else self.default_targets(actor_id, item.battle_ability)
            )
            offensive = self.ability_relation(item.battle_ability) == TargetRelation.OPPONENT
            inventory.remove(item.item_id, 1)
            battle.granted_abilities = {(str(actor_id), item.battle_ability)}
            try:
                results = self._repeat_action(actor_id, item.battle_ability, targets, offensive, 1)
            finally:
                battle.granted_abilities = set()
            if any(getattr(r, "success", True) for r in results):  # its states, gains, commands
                definition = battle.ability_runtime.registry.get(item.battle_ability)
                self._after_ability(actor_id, definition, targets)
            self._log("item_used", member_id=str(actor_id), data={"item": item.item_id})
            return results
        targets = tuple(target_ids) if target_ids else (actor_id,)
        inventory.remove(item.item_id, 1)
        for target_id in targets:
            subject = battle.member(target_id).subject
            for effect in item.use_effects:
                apply_effect(effect, subject.stats, subject.resources, subject.tags)
        self._log("item_used", member_id=str(actor_id), data={"item": item.item_id})
        return ()
