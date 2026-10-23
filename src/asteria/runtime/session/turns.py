"""Running away, ending turns, objectives, enemy turns, the battle log, previews and casts."""

from __future__ import annotations

from dataclasses import replace

from asteria.rpg import (
    BattleAction,
    RpgActorSnapshot,
)
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


class TurnsMixin:
    # -- running away -----------------------------------------------------------------------
    def _escape_rule(self):
        """The escape rule an ``escape:<id>`` encounter tag names, else the first by id."""
        rules = self.battle.escape_rules if self.battle is not None else {}
        chosen = self._encounter_choice("escape", rules) if rules else None
        return chosen or (rules[sorted(rules)[0]] if rules else None)

    def escape_unavailable(self):
        """Why the party cannot run now ("" when it can): no rule, or an encounter tagged
        ``no_escape`` (a boss)."""
        if self.battle is None:
            return "Not in battle"
        if self._escape_rule() is None:
            return self.tr("battle.escape.no_rule", "The project defines no escape rule")
        encounter = self.project.rpg_database.encounters.get(self.encounter_id or "")
        if encounter is not None and "no_escape" in encounter.tags:
            return self.tr(
                "battle.escape.blocked", "This battle has no_escape: there is no running away"
            )
        return ""

    def escape_chance(self):
        from asteria.rpg.battle_lifecycle import resolve_escape_chance

        rule = self._escape_rule()
        return None if rule is None else resolve_escape_chance(rule, self.battle)

    def attempt_escape(self, actor_id, *, rng=None):
        """Try to run: on success the battle ends with no reward and the party is back on the
        field; a failure only costs the turn."""
        reason = self.escape_unavailable()
        if reason:
            raise GameSessionError("cannot escape: " + reason)
        rule = self._escape_rule()
        result = self.battle.attempt_escape(rule.rule_id, rng=rng or self.battle.rng)
        self._log(
            "escape",
            member_id=str(actor_id),
            data={"succeeded": result.succeeded, "chance": result.chance},
        )
        if result.succeeded:
            self._write_battle_heroes_to_save()
            self._log("battle_finished", data={"winning_sides": (), "defeated_sides": ()})
            self.mode = "field"
            self.battle = None
            self.encounter_id = None
            self._enemy_ids = ()
            self.interaction.reset()
        return result

    def end_turn(self):
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        self._logged_turn = None
        delay, self._turn_delay = getattr(self, "_turn_delay", 0.0), 0.0
        result = self.battle.advance_turn(recovery=delay)
        self.settle_objectives()
        return result

    def settle_objectives(self):
        """Let the battle's objectives decide the fight: when one succeeds or fails (a leader
        fell, a vigil was held, a ward broke), the side it defeats is knocked out, so the usual
        victory / defeat follows. Returns the deciding outcome, or None."""
        if self.battle is None:
            return None
        outcome = self.battle.resolve_outcome()
        if not outcome.finished or not outcome.objective_ids:
            return None
        resource = self.rules.knockout_resource_id
        for side in outcome.defeated_sides:
            party = self.battle.parties.get(side)
            for member in () if party is None else party.members:
                if resource and self.battle.is_active(member):
                    pool = member.subject.resources
                    if resource in pool.to_data()["values"]:
                        pool.set_current(resource, 0.0)
        return outcome

    def enemy_act(self, member_id):
        """One enemy action: its bound AI, else its first ability on default targets."""
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        enemy_id = str(member_id).split(":", 1)[0]
        binding = self.project.rpg_database.enemy_behavior_bindings.get(enemy_id)
        if binding is not None:
            return self.enemy_turn(member_id, binding.ai_id)
        definition = self.project.rpg_database.enemies.get(enemy_id)
        if definition is None or not definition.abilities:
            return None
        ability_id = definition.abilities[0]
        targets = self.default_targets(member_id, ability_id)
        if not targets:
            return None
        before = self._knockout_values(targets)
        result = self.execute(member_id, ability_id, targets)
        self._log(
            "action",
            member_id=str(member_id),
            ability_id=ability_id,
            target_ids=targets,
            outcomes=self._action_outcomes(member_id, ability_id, targets, before),
        )
        if getattr(
            result, "success", True
        ):  # enemy abilities apply their states, gains and commands too
            self._after_ability(
                member_id, self.battle.ability_runtime.registry.get(ability_id), targets
            )
        return result

    def run_enemy_turns(self, *, limit=1000):
        """Advance through enemy turns until a hero must act or the battle is decided.

        Returns ``(hero_id_or_None, ((enemy_member_id, result_or_error), ...))``.
        """
        log = []
        for _ in range(int(limit)):
            actor_id = self.current_turn_actor()
            if actor_id is None or self.battle.member(actor_id).side != "enemies":
                if not self.active_hero_ids():
                    self._log(
                        "battle_finished",
                        data={"winning_sides": ("enemies",), "defeated_sides": ("heroes",)},
                    )
                return actor_id, tuple(log)
            try:
                outcome = self.enemy_act(actor_id)
            except Exception as exc:
                outcome = exc
            log.append((actor_id, outcome))
            self.end_turn()
        raise GameSessionError("enemy turns did not yield to a hero")

    def _log(self, kind, **values):
        self._log_sequence += 1
        entry = BattleLogEntry(self._log_sequence, kind, **values)
        self.battle_log.append(entry)
        return entry

    def drain_battle_log(self):
        """Return and clear battle facts recorded since the last drain."""
        values = tuple(self.battle_log)
        self.battle_log.clear()
        return values

    def _knockout_values(self, target_ids):
        resource = self.rules.knockout_resource_id
        values = {}
        for target_id in target_ids:
            pool = self.battle.member(target_id).subject.resources
            if resource and resource in pool.to_data()["values"]:
                values[target_id] = pool.current(resource)
        return values

    def _action_outcomes(self, actor_id, ability_id, target_ids, before=None):
        """Interaction outcomes for opponent targets, valued by the observed knockout-resource
        change.

        Outcome tags/disposition come from the non-mutating interaction resolver;
        ``value.resolved_value`` is replaced by how much the knockout resource
        actually dropped (when ``before`` was measured), so presentation shows
        what happened rather than a multiplier.
        """
        if self.ability_relation(ability_id) != TargetRelation.OPPONENT:
            return ()
        action = BattleAction(actor_id, ability_id, tuple(target_ids))
        after = self._knockout_values(target_ids)
        outcomes = []
        for target_id in target_ids:
            outcome = self.battle.resolve_interaction(action, target_id, 1.0)
            if before is not None and target_id in before and target_id in after:
                observed = max(0.0, before[target_id] - after[target_id])
                outcome = replace(outcome, value=replace(outcome.value, resolved_value=observed))
            outcomes.append((target_id, outcome))
        return tuple(outcomes)

    def preview(self, actor_id, ability_id, target_ids):
        """Predicted resource changes of an action (same pipeline as execute; nothing mutates)."""
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        return self.battle.preview_action(BattleAction(actor_id, ability_id, tuple(target_ids)))

    def execute(self, actor_id, ability_id, target_ids, *, waive_costs=False):
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        result = self.battle.execute(
            BattleAction(actor_id, ability_id, target_ids, forced=self._forced_cast),
            waive_costs=waive_costs,
        )
        if self.rules.action_timing == "timeline":
            recovery = self.battle.action_timing.definition_for(ability_id).recovery
            self._turn_delay = max(
                getattr(self, "_turn_delay", 0.0), recovery
            )  # applied when the turn ends
        return result

    def _begin_cast(self, actor_id, ability_id, targets, timing):
        """Start a cast (ActionTimingDefinition startup + cast time): validated now, resolved
        later by
        ``resolve_casts``; the caster's next turn moves back by the cast time and recovery."""
        battle = self.battle
        action = battle._validate_action(BattleAction(actor_id, ability_id, targets))
        current = float(getattr(battle.turn_queue, "current_time", 0.0) or 0.0)
        ready = battle.turn_queue.peek()
        if ready is not None and ready.member_id == action.actor_id:
            current = max(current, float(getattr(ready, "ready_time", current)))
        pending = battle.action_timing.begin(action, current_time=current)
        self._turn_delay = max(getattr(self, "_turn_delay", 0.0), timing.windup + timing.recovery)
        self._log(
            "cast_started",
            member_id=str(actor_id),
            ability_id=str(ability_id),
            target_ids=tuple(action.target_ids),
            data={"resolve_at": pending.resolve_at, "cast_time": timing.windup},
        )
        return ()

    def resolve_casts(self):
        """Resolve every cast whose time has come (before the next member acts)."""
        if self.battle is None or not self.battle.action_timing.pending():
            return ()
        results = self.battle.resolve_due_actions()
        for result in results:
            action = result.action
            self._log(
                "action",
                member_id=action.actor_id,
                ability_id=action.ability_id,
                target_ids=action.target_ids,
            )
        return results

    def enemy_turn(self, member_id, ai_id):
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        decision = self.battle.enemy_ai.decide(self.battle, ai_id, member_id, rng=self.battle.rng)
        if decision is None:
            return None
        if decision.action_kind == "ability" and decision.payload.get("ability_id"):
            return self._enemy_ability_turn(member_id, decision)
        before = self._knockout_values(decision.target_ids)
        result = self.battle.enemy_ai.execute_decision(self.battle, decision, rng=self.battle.rng)
        ability_id = (
            decision.payload.get("ability_id") if decision.action_kind == "ability" else None
        )
        if ability_id:
            self._log(
                "action",
                member_id=str(member_id),
                ability_id=str(ability_id),
                target_ids=tuple(decision.target_ids),
                outcomes=self._action_outcomes(member_id, ability_id, decision.target_ids, before),
            )
            if self.battle is not None and getattr(result, "success", True):
                definition = self.battle.ability_runtime.registry.get(ability_id)
                self._after_ability(member_id, definition, tuple(decision.target_ids))
        return result

    def _enemy_ability_turn(self, member_id, decision):
        """An enemy's ability goes through the same per-hit path as a hero's: every hit rolls
        its own checks and instant-kill, and reactions answer it."""
        ability_id = str(decision.payload["ability_id"])
        targets = tuple(decision.target_ids)
        offensive = self.ability_relation(ability_id) == TargetRelation.OPPONENT
        targets, self._forced_cast = self._override_targets(member_id, targets)
        try:
            results = self._repeat_action(member_id, ability_id, targets, offensive, 1)
        finally:
            self._forced_cast = False
        result = results[-1] if results else None
        ai = self.battle.enemy_ai
        ai.set_memory(decision.actor_id, "last_rule_id", decision.rule_id)
        ai.set_memory(
            decision.actor_id,
            "action_count",
            int(ai.get_memory(decision.actor_id, "action_count", 0)) + 1,
        )
        if self.battle is not None and results:
            definition = self.battle.ability_runtime.registry.get(ability_id)
            self._after_ability(member_id, definition, targets)
        return result

    def active_enemy_ids(self):
        if self.battle is None:
            return ()
        return tuple(
            m.member_id for m in self.battle.parties["enemies"].members if self.battle.is_active(m)
        )

    def active_hero_ids(self):
        if self.battle is None:
            return ()
        return tuple(
            m.member_id for m in self.battle.parties["heroes"].members if self.battle.is_active(m)
        )

    def _write_battle_heroes_to_save(self):
        for member in self.battle.members.values():  # the weather tag lasts one battle
            tags = member.subject.tags
            for tag in [t for t in tags.values() if t.startswith(self.WEATHER_TAG_PREFIX)]:
                tags.remove(tag)
        for member in self.battle.parties["heroes"].members:
            if member.member_id not in self.project.rpg_database.actors:
                continue  # a pet unit is not an actor: its record is the owned pet
            old = self.save.rpg_state.actor_snapshots.get(member.member_id)
            ability_state = None if old is None else old.ability_state
            # keep the base, not the battle's build: the next build adds level growth, trees,
            # gear, passives and stat formulas again (storing them compounded every fight)
            base = self._actor_runtime(member.member_id)
            self.save.rpg_state.actor_snapshots[member.member_id] = RpgActorSnapshot(
                member.member_id,
                base.stats.to_data(),
                _base_relative(member.subject.resources, base.resources).to_data(),
                member.subject.tags.to_data(),
                ability_state,
            )
