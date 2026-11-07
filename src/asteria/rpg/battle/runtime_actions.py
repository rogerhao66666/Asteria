"""What a battle does with an action: checking and queueing it, timed and interrupted actions,
previews, carrying it out with its reactions, sequences, an AI's turn, gauges and interactions."""

from __future__ import annotations

import random

from asteria.core.lifecycle import emit_hook
from asteria.gameplay import AbilityTarget
from asteria.gameplay.abilities import _clone_subject
from asteria.gameplay.effects import EffectOperationKind
from asteria.gameplay.expressions import SubjectView, evaluate
from asteria.rpg.battle.runtime_types import BattleAction, BattleActionPreview, BattleActionResult
from asteria.rpg.battle.scheduler import BattleSchedulerMode


class BattleActionsMixin:
    """``BattleRuntime``'s actions: submit, preview, execute, reactions, sequences, AI turns."""

    # defaults until something sets them (code may read them first)
    action_scale = 1.0
    granted_abilities = ()

    def _validate_action(self, action, *, rng=None, continuation=False):
        if not isinstance(action, BattleAction):
            raise TypeError("action must be BattleAction")
        actor = self.member(action.actor_id)
        if not self.can_act(actor.member_id):
            raise ValueError("actor cannot act in current combatant lifecycle state")
        granted = self.granted_abilities  # e.g. the ability of an item used in battle
        if (
            action.ability_id not in actor.ability_ids
            and (actor.member_id, action.ability_id) not in granted
        ):
            raise ValueError("actor does not know ability")
        if action.ability_id in self.blocked_abilities.get(actor.member_id, ()):
            raise ValueError(f"ability unavailable: {action.ability_id} (its source is broken)")
        availability = self.ability_availability(actor.member_id, action.ability_id)
        if not availability.allowed:
            raise ValueError(
                f"ability blocked by active state: {', '.join(availability.blocking_states)}"
            )
        left = self.cooldown_remaining(actor.member_id, action.ability_id)
        if (
            left and (actor.member_id, action.ability_id) not in self._used_this_turn
        ):  # repeats in one turn (boost)
            raise ValueError(f"ability cooling down: {action.ability_id} ({left} turns)")
        if self.extensions is not None and not continuation:  # later hits of one cast: no re-check
            self.extensions.validate(self, action)
        if action.forced:
            for target_id in action.target_ids:
                self.member(target_id)  # it must be somebody in this battle
            return action
        target_resolution = self.resolve_targets(
            actor.member_id, action.ability_id, action.target_ids, rng=rng
        )
        if not target_resolution.valid:
            raise ValueError("invalid battle targets: " + ", ".join(target_resolution.errors))
        if target_resolution.selected_ids != action.target_ids:
            action = BattleAction(
                action.actor_id, action.ability_id, target_resolution.selected_ids
            )
        return action

    def submit_action(self, action, *, rng=None):
        """Submit an action through the timing layer.

        Immediate actions resolve now. Windup/cast actions become pending and
        resolve when the battle timeline reaches their resolve_at timestamp.
        Ability costs/effects currently commit on resolution; Batch 92's battle
        transaction layer is the extension point for projects that need
        start-time cost commitment.
        """
        rng = self.rng if rng is None else rng
        action = self._validate_action(action, rng=rng)
        definition = self.action_timing.definition_for(action.ability_id)
        current_time = float(getattr(self.turn_queue, "current_time", 0.0) or 0.0)
        ready_entry = self.turn_queue.peek()
        if ready_entry is not None and ready_entry.member_id == action.actor_id:
            current_time = max(
                current_time, float(getattr(ready_entry, "ready_time", current_time))
            )
        pending = self.action_timing.begin(action, current_time=current_time)
        if pending is None:
            result = self.execute(action, rng=rng)
            self.advance_turn(recovery=definition.recovery)
            return result
        actor = self.member(action.actor_id)
        target_subject = self.member(action.target_ids[0]).subject if action.target_ids else None
        committed = self.transactions.commit_start(
            pending.token,
            action.actor_id,
            action.ability_id,
            actor.subject,
            target_subject,
            self.ability_runtime,
        )
        emit_hook(
            self.hooks,
            "rpg.battle.action_cast_started",
            source=action.actor_id,
            data={
                "action": action,
                "pending": pending,
                "timing": definition,
                "committed_costs": committed,
            },
        )
        self.advance_turn(recovery=definition.windup + definition.recovery)
        return pending

    def resolve_due_actions(self, through_time=None, *, rng=None):
        rng = self.rng if rng is None else rng
        if through_time is None:
            next_entry = self.turn_queue.peek()
            through_time = (
                getattr(next_entry, "ready_time", getattr(self.turn_queue, "current_time", 0.0))
                if next_entry is not None
                else getattr(self.turn_queue, "current_time", 0.0)
            )
        results = []
        for pending in self.action_timing.pop_due(float(through_time)):
            if (
                self.scheduler is not None
                and self.scheduler.mode == BattleSchedulerMode.CONTINUOUS
            ):
                self.scheduler.advance_time(pending.resolve_at)
            if (
                pending.actor_id not in self.members
                or not self.combatants.state(pending.actor_id).present
            ):
                reservation = self.transactions.cancel(
                    pending.token, self.member(pending.actor_id).subject
                )
                emit_hook(
                    self.hooks,
                    "rpg.battle.action_cancelled",
                    source=pending.actor_id,
                    data={
                        "pending": pending,
                        "reason": "actor_not_present",
                        "reservation": reservation,
                    },
                )
                continue
            action = BattleAction(pending.actor_id, pending.ability_id, pending.target_ids)
            # Targets are revalidated at resolution because battle state may have changed during
            # cast.
            try:
                action = self._validate_action(action, rng=rng)
            except ValueError as exc:
                reservation = self.transactions.cancel(
                    pending.token, self.member(pending.actor_id).subject
                )
                emit_hook(
                    self.hooks,
                    "rpg.battle.action_cancelled",
                    source=pending.actor_id,
                    data={"pending": pending, "reason": str(exc), "reservation": reservation},
                )
                continue
            reservation = self.transactions.consume(pending.token)
            wrapped = self.execute(
                action, rng=rng, prepaid_costs=None if reservation is None else reservation.costs
            )
            results.append(wrapped)
            emit_hook(
                self.hooks,
                "rpg.battle.action_cast_resolved",
                source=pending.actor_id,
                data={"pending": pending, "result": wrapped},
            )
        return tuple(results)

    def interrupt_action(self, actor_id, *, power=0.0, reason="interrupted", force=False):
        result = self.action_timing.interrupt(actor_id, power=power, reason=reason, force=force)
        if result.interrupted:
            reservation = self.transactions.cancel(result.token, self.member(actor_id).subject)
            emit_hook(
                self.hooks,
                "rpg.battle.action_interrupted",
                source=str(actor_id),
                data={"result": result, "reservation": reservation},
            )
        return result

    def cancel_action(self, actor_id, *, reason="cancelled"):
        removed = self.action_timing.cancel(actor_id, reason=reason)
        for pending in removed:
            reservation = self.transactions.cancel(pending.token, self.member(actor_id).subject)
            emit_hook(
                self.hooks,
                "rpg.battle.action_cancelled",
                source=str(actor_id),
                data={"pending": pending, "reason": reason, "reservation": reservation},
            )
        return removed

    def shift_timeline(self, member_id, delta, *, include_cast=True):
        scheduled = (
            self.scheduler.shift_member(member_id, delta)
            if self.scheduler is not None
            else tuple()
        )
        casting = self.action_timing.shift(member_id, delta) if include_cast else tuple()
        emit_hook(
            self.hooks,
            "rpg.battle.timeline_shifted",
            source=str(member_id),
            data={"delta": float(delta), "scheduled": scheduled, "casting": casting},
        )
        return scheduled, casting

    def _interaction_transform(self, actor, ability_id, subjects, record):
        """Route harmful resource deltas through the project's interaction rules.

        A negative RESOURCE_DELTA on a selected target is damage: its magnitude
        is resolved by ``InteractionResolver`` (weakness/resistance multipliers,
        flat and stat terms) with the ability's tags as action tags. NULLIFY
        drops it, ABSORB turns it into healing, REFLECT sends it to the actor.
        Other operations pass through unchanged.
        """

        from asteria.rpg.battle.interactions import InteractionDisposition

        scale = float(self.action_scale)  # a hit's power (ability "hits")
        final = self.final_damage_expression

        def finish(target_id, magnitude):
            """The damage after the rules, through the battle's final expression."""
            if not final or magnitude <= 0:
                return magnitude

            names = {
                "value": float(magnitude),
                "source": SubjectView(subjects[0]),
                "target": SubjectView(subjects[1].get(target_id)),
            }
            return max(0.0, evaluate(final, names, self.rng))

        if not self.interactions.rules:
            if scale == 1.0 and not final:
                return None

            def scaled(target_id, operation, value):
                harmful = operation.kind == EffectOperationKind.RESOURCE_DELTA and value < 0
                if not harmful:
                    return value
                health = self.knockout_resource_id
                if health and operation.target != health:
                    return value * scale
                return -finish(target_id, -value * scale)

            return scaled
        tags = self.ability_runtime.registry.require(ability_id).tags

        def transform(target_id, operation, value):
            if operation.kind != EffectOperationKind.RESOURCE_DELTA or value >= 0:
                return value
            resolved = self.interactions.resolve_value(
                -float(value) * scale, subjects[0], subjects[1][target_id], action_tags=tags
            )
            record.append((target_id, operation.target, resolved))
            if resolved.disposition == InteractionDisposition.NULLIFY:
                return 0.0
            if resolved.disposition == InteractionDisposition.ABSORB:
                return resolved.resolved_value
            if resolved.disposition == InteractionDisposition.REFLECT:
                return (0.0, -resolved.resolved_value)
            if operation.target != self.knockout_resource_id and self.knockout_resource_id:
                return -resolved.resolved_value  # only the knockout resource is "damage"
            return -finish(target_id, resolved.resolved_value)

        return transform

    def _periodic_interaction_transform(self, member, active, policy):
        """Damage-over-time opt-in (BattleStatePolicy.interaction_tags).

        The tick's own magnitude is resolved once with the policy's tags; the
        multiplier of the attack that applied the state is never reapplied.
        The state's source (or the afflicted member itself) is the source subject.
        """

        from asteria.rpg.battle.interactions import InteractionDisposition

        if not self.interactions.rules:
            return None
        source_id = active.source_id if active.source_id in self.members else member.member_id
        source = self.member(source_id).subject

        def transform(operation, value):
            if operation.kind != EffectOperationKind.RESOURCE_DELTA or value >= 0:
                return value
            resolved = self.interactions.resolve_value(
                -float(value), source, member.subject, action_tags=policy.interaction_tags
            )
            self.periodic_interactions.append(
                (member.member_id, active.state_id, operation.target, resolved)
            )
            if resolved.disposition == InteractionDisposition.NULLIFY:
                return 0.0
            if resolved.disposition == InteractionDisposition.ABSORB:
                return resolved.resolved_value
            if resolved.disposition == InteractionDisposition.REFLECT:
                return 0.0
            return -resolved.resolved_value

        return transform

    def preview_action(self, action, *, rng=None):
        """Predict ``action`` without mutating the battle (same pipeline as :meth:`execute`)."""

        probe = random.Random()
        probe.setstate((self.rng if rng is None else rng).getstate())
        try:
            effective = self._validate_action(action, rng=probe)
        except ValueError as exc:
            return BattleActionPreview(action, False, (str(exc),), {})
        actor = self.member(effective.actor_id)
        ids = (actor.member_id, *effective.target_ids)
        clones = {
            member_id: _clone_subject(self.member(member_id).subject)
            for member_id in dict.fromkeys(ids)
        }
        record = []
        transform = self._interaction_transform(
            actor,
            effective.ability_id,
            (actor.subject, {x: self.member(x).subject for x in effective.target_ids}),
            record,
        )
        result = self.ability_runtime.execute(
            effective.ability_id,
            AbilityTarget(actor.member_id, clones[actor.member_id]),
            tuple(AbilityTarget(x, clones[x]) for x in effective.target_ids),
            value_transform=transform,
        )
        deltas = {}
        for member_id, clone in clones.items():
            before = self.member(member_id).subject.resources
            changes = {}
            for resource_id in clone.resources.to_data()["values"]:
                delta = clone.resources.current(resource_id) - before.current(resource_id)
                if delta:
                    changes[resource_id] = delta
            if changes:
                deltas[member_id] = changes
        return BattleActionPreview(
            effective,
            result.executed,
            tuple(result.errors),
            deltas,
            tuple(record) if result.executed else (),
        )

    def execute(self, action, *, rng=None, prepaid_costs=None, waive_costs=False):
        rng = self.rng if rng is None else rng
        effective_action = self._validate_action(action, rng=rng, continuation=waive_costs)
        actor = self.member(effective_action.actor_id)
        targets = [self.member(x) for x in effective_action.target_ids]
        emit_hook(
            self.hooks,
            "rpg.battle.before_action",
            source=actor.member_id,
            data={"action": effective_action, "actor": actor, "targets": tuple(targets)},
        )
        source = AbilityTarget(actor.member_id, actor.subject)
        target_values = tuple(AbilityTarget(x.member_id, x.subject) for x in targets)
        record = []
        transform = self._interaction_transform(
            actor,
            action.ability_id,
            (actor.subject, {x.member_id: x.subject for x in targets}),
            record,
        )
        extensions = self.extensions
        snapshot = None
        if extensions is not None:
            snapshot = extensions.before_action(self, effective_action)
            transform = extensions.wrap_transform(transform)
        result = self.ability_runtime.execute(
            action.ability_id,
            source,
            target_values,
            prepaid_costs=prepaid_costs,
            waive_costs=waive_costs,
            skip_targeting=effective_action.forced,
            value_transform=transform,
        )
        wrapped = BattleActionResult(
            effective_action, result, tuple(record) if result.executed else ()
        )
        if result.executed:
            self._start_cooldown(actor.member_id, action.ability_id)
        if extensions is not None:
            extensions.after_action(
                self, effective_action, snapshot, result.executed, counted=not waive_costs
            )
        emit_hook(
            self.hooks,
            "rpg.battle.after_action",
            source=actor.member_id,
            data={"result": wrapped, "actor": actor, "targets": tuple(targets)},
        )
        return wrapped

    def resolve_reactions(self, trigger, source_id, target_ids=(), *, tags=(), rng=None):
        return self.reactions.resolve(
            self, trigger, source_id, target_ids, tags=tags, rng=self.rng if rng is None else rng
        )

    def execute_with_reactions(self, action, *, rng=None, tags=()):
        """Execute one authored action, then drain the generic post-action reaction queue.

        Pre-action cover/intercept style rules may be run explicitly with
        `resolve_reactions("rpg.battle.before_action", ...)` so projects decide
        whether target replacement happens before costs, cast start, or resolution.
        """
        result = self.execute(action, rng=rng)
        chain = self.resolve_reactions(
            "rpg.battle.after_action",
            result.action.actor_id,
            result.action.target_ids,
            tags=tags,
            rng=rng,
        )
        return result, chain

    def execute_sequence(self, sequence_id, participant_ids, target_ids=(), *, rng=None):
        """Execute a generic multi-hit/chain/cooperative plan.

        Game-authored interruption_policy decides failure behavior. Asteria only
        guarantees deterministic planning, validation, hooks and safe execution.
        Participant turn reservation/cost policy remains project-owned rather than
        silently imposed by this convenience execution path.
        """
        rng = self.rng if rng is None else rng
        plan = self.action_sequences.plan(sequence_id, participant_ids, target_ids)
        definition = self.action_sequences.definitions[plan.sequence_id]
        for participant_id in plan.participant_ids:
            if participant_id not in self.members:
                raise ValueError(f"unknown sequence participant: {participant_id}")
        emit_hook(
            self.hooks,
            "rpg.battle.sequence_started",
            source=plan.participant_ids[0],
            data={"plan": plan, "definition": definition},
        )
        results = []
        failures = []
        for step in plan.steps:
            action = BattleAction(step.actor_id, step.ability_id, step.target_ids)
            try:
                result = self.execute(action, rng=rng)
            except (ValueError, KeyError) as exc:
                failures.append((step, str(exc)))
                emit_hook(
                    self.hooks,
                    "rpg.battle.sequence_step_failed",
                    source=step.actor_id,
                    data={"plan": plan, "step": step, "reason": str(exc)},
                )
                policy = definition.interruption_policy
                if policy in {"skip_step", "continue"}:
                    continue
                if policy == "raise":
                    raise
                break
            results.append((step, result))
            emit_hook(
                self.hooks,
                "rpg.battle.sequence_step_resolved",
                source=step.actor_id,
                data={"plan": plan, "step": step, "result": result},
            )
        completed = len(results) == len(plan.steps)
        emit_hook(
            self.hooks,
            "rpg.battle.sequence_finished",
            source=plan.participant_ids[0],
            data={
                "plan": plan,
                "results": tuple(results),
                "failures": tuple(failures),
                "completed": completed,
            },
        )
        return plan, tuple(results), tuple(failures)

    def execute_ai_turn(self, ai_id, actor_id, *, rng=None, advance_turn=False):
        """Run one AI ready-window through the generic AI/action hook layer.

        Custom `action_kind` handlers may bridge any battle-adjacent system: alchemy,
        summoning, transformations, stance systems, plugins, or project scripts.
        Asteria does not prescribe those game rules; it only provides the stable hook.
        """
        rng = self.rng if rng is None else rng
        actor_id = str(actor_id)
        if actor_id not in self.members:
            raise KeyError(actor_id)
        if not self.can_act(actor_id):
            return ()
        emit_hook(
            self.hooks,
            "rpg.battle.ai.turn_started",
            source=actor_id,
            data={"battle": self, "ai_id": str(ai_id)},
        )
        results = self.enemy_ai.run_ready(self, ai_id, actor_id, rng=rng)
        emit_hook(
            self.hooks,
            "rpg.battle.ai.turn_finished",
            source=actor_id,
            data={"battle": self, "ai_id": str(ai_id), "results": results},
        )
        if advance_turn:
            self.advance_turn()
        return results

    def apply_gauge_impact(
        self,
        composition_id,
        source_id,
        target_id,
        *,
        trigger,
        outcome=None,
        outcome_tags=(),
        value=None,
        rng=None,
    ):
        """Compose interaction outcomes into arbitrary battle gauges.

        `outcome` may be an OutcomeResolutionResult; callers may alternatively
        provide tags/value directly for scripted or non-damage mechanics.
        """
        if outcome is not None:
            if hasattr(outcome, "outcome_tags"):
                outcome_tags = outcome.outcome_tags
            if value is None and hasattr(outcome, "value"):
                value = getattr(outcome.value, "resolved_value", 0.0)
        if value is None:
            value = 0.0
        return self.gauge_compositions.apply(
            self,
            composition_id,
            source_id,
            target_id,
            trigger=trigger,
            outcome_tags=outcome_tags,
            value=value,
            rng=rng,
        )

    def resolve_interaction(self, action, target_id, base_value, *, check_ids=(), rng=None):
        """Resolve battle semantics without mutating gameplay state.

        Presentation/effect application can inspect the returned disposition and
        trace. Later battle transaction batches will own final mutation routing.
        """
        if not isinstance(action, BattleAction):
            raise TypeError("action must be BattleAction")
        actor = self.member(action.actor_id)
        target = self.member(target_id)
        definition = self.ability_runtime.registry.require(action.ability_id)
        return self.interactions.resolve(
            base_value,
            actor.subject,
            target.subject,
            action_tags=definition.tags,
            check_ids=check_ids,
            rng=rng,
        )
