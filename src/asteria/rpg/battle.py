from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite

from asteria.core.lifecycle import emit_hook
from asteria.gameplay import AbilityRuntime, AbilityTarget, GameplaySubject

from .action_sequences import ActionSequenceRuntime
from .battle_lifecycle import (
    BattleEscapeRule,
    BattleObjectiveRuntime,
    CombatantLifecycleRuntime,
    attempt_escape,
)
from .battle_resources import BattleResourceRuntime
from .battle_scheduler import BattleScheduler, BattleSchedulerDefinition, BattleSchedulerMode
from .battle_snapshot import capture_battle_snapshot, restore_battle_snapshot
from .battle_states import BattleStateRuntime
from .battle_timing import BattleActionTimingRuntime
from .battle_transactions import BattleTransactionRuntime
from .enemy_ai import EnemyAIRuntime
from .gauge_composition import BattleGaugeCompositionRuntime
from .interactions import InteractionResolver
from .reactions import ReactionRuntime
from .targeting import BattleFormationRuntime, BattleTargetingRuntime


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _number(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class PartyMember:
    member_id: str
    side: str
    subject: GameplaySubject
    ability_ids: tuple[str, ...] = ()
    initiative: float = 0.0
    initiative_stat: str = ""

    def __init__(self, member_id, side, subject, *, ability_ids=(), initiative=0.0, initiative_stat=""):
        if not isinstance(subject, GameplaySubject):
            raise TypeError("subject must be GameplaySubject")
        object.__setattr__(self, "member_id", _id(member_id, "member_id"))
        object.__setattr__(self, "side", _id(side, "side"))
        object.__setattr__(self, "subject", subject)
        object.__setattr__(
            self,
            "ability_ids",
            tuple(dict.fromkeys(_id(x, "ability_id") for x in ability_ids)),
        )
        object.__setattr__(self, "initiative", _number(initiative, "initiative"))
        object.__setattr__(self, "initiative_stat", str(initiative_stat or ""))

    @property
    def current_initiative(self):
        """Initiative now: the ``initiative_stat`` of the subject when named (so speed changes in battle -
        haste, slow - move later turns), else the fixed ``initiative``."""
        stats = self.subject.stats
        if self.initiative_stat and stats.contains(self.initiative_stat):
            return float(stats.get(self.initiative_stat))
        return self.initiative


class TurnOrderPolicy(str, Enum):
    FIXED_INITIATIVE = "fixed_initiative"


@dataclass(slots=True)
class Party:
    side: str
    members: list[PartyMember] = field(default_factory=list)
    hooks: object = None

    def __init__(self, side, members=(), *, hooks=None):
        self.side = _id(side, "side")
        self.members = []
        self.hooks = hooks
        for member in members:
            self.add(member)

    def add(self, member):
        if not isinstance(member, PartyMember):
            raise TypeError("member must be PartyMember")
        if member.side != self.side:
            raise ValueError("party member side mismatch")
        if any(x.member_id == member.member_id for x in self.members):
            raise ValueError(f"duplicate party member: {member.member_id}")
        emit_hook(
            self.hooks,
            "rpg.party.before_add",
            source=self.side,
            data={"member": member},
        )
        self.members.append(member)
        emit_hook(self.hooks, "rpg.party.after_add", source=self.side, data={"member": member})
        return member

    def remove(self, member_id):
        member_id = str(member_id)
        for i, m in enumerate(self.members):
            if m.member_id == member_id:
                emit_hook(
                    self.hooks,
                    "rpg.party.before_remove",
                    source=self.side,
                    data={"member": m},
                )
                removed = self.members.pop(i)
                emit_hook(
                    self.hooks,
                    "rpg.party.after_remove",
                    source=self.side,
                    data={"member": removed},
                )
                return removed
        raise KeyError(member_id)

    def ids(self):
        return tuple(x.member_id for x in self.members)


@dataclass(frozen=True, slots=True)
class TurnEntry:
    member_id: str
    side: str
    initiative: float


class TurnQueue:
    """Deterministic round queue. Higher initiative acts first; ID breaks ties."""

    def __init__(self, members=(), policy=TurnOrderPolicy.FIXED_INITIATIVE):
        self.policy = TurnOrderPolicy(policy)
        self._source = tuple(members)
        self._round = 0
        self._pending = []
        self.start_round()

    @property
    def round_index(self):
        return self._round

    def start_round(self):
        self._round += 1
        self._pending = [
            TurnEntry(m.member_id, m.side, m.initiative)
            for m in sorted(self._source, key=lambda x: (-x.initiative, x.member_id))
        ]
        return tuple(self._pending)

    def peek(self):
        return self._pending[0] if self._pending else None

    def pop(self):
        return self._pending.pop(0) if self._pending else None

    def pending(self):
        return tuple(self._pending)

    def exhausted(self):
        return not self._pending

    def register_member(self, member, *, join_current_round=False):
        if any(x.member_id == member.member_id for x in self._source):
            raise ValueError(f"duplicate turn queue member: {member.member_id}")
        self._source = (*self._source, member)
        if join_current_round:
            self._pending.append(TurnEntry(member.member_id, member.side, member.initiative))
            self._pending.sort(key=lambda x: (-x.initiative, x.member_id))

    def replace_member(self, member):
        found = False
        source = []
        for current in self._source:
            if current.member_id == member.member_id:
                source.append(member)
                found = True
            else:
                source.append(current)
        if not found:
            raise KeyError(member.member_id)
        self._source = tuple(source)
        self._pending = [
            TurnEntry(x.member_id, x.side, member.initiative) if x.member_id == member.member_id else x
            for x in self._pending
        ]

    def remove_pending(self, member_id):
        member_id = str(member_id)
        self._pending = [x for x in self._pending if x.member_id != member_id]

    def to_data(self):
        return {
            "schema": "asteria.rpg.turn_queue",
            "version": 1,
            "policy": self.policy.value,
            "round_index": self._round,
            "pending": [{"member_id": x.member_id, "side": x.side, "initiative": x.initiative} for x in self._pending],
        }

    @classmethod
    def from_data(cls, data, members):
        if data.get("schema") != "asteria.rpg.turn_queue" or data.get("version") != 1:
            raise ValueError("unsupported turn queue")
        result = cls.__new__(cls)
        result.policy = TurnOrderPolicy(data["policy"])
        result._source = tuple(members)
        result._round = int(data["round_index"])
        result._pending = [TurnEntry(x["member_id"], x["side"], x["initiative"]) for x in data["pending"]]
        return result


@dataclass(frozen=True, slots=True)
class BattleAction:
    actor_id: str
    ability_id: str
    target_ids: tuple[str, ...]

    def __init__(self, actor_id, ability_id, target_ids):
        object.__setattr__(self, "actor_id", _id(actor_id, "actor_id"))
        object.__setattr__(self, "ability_id", _id(ability_id, "ability_id"))
        object.__setattr__(self, "target_ids", tuple(_id(x, "target_id") for x in target_ids))


@dataclass(frozen=True, slots=True)
class BattleActionResult:
    action: BattleAction
    execution_result: object
    # (target_id, resource_id, ValueResolutionResult) for every harmful resource
    # delta the project's interaction rules resolved during this action.
    interactions: tuple = ()


@dataclass(frozen=True, slots=True)
class BattleActionPreview:
    """Predicted result of an action, computed by the same pipeline as execute.

    ``resource_deltas`` maps member id -> {resource id: change}; nothing in the
    battle is mutated.
    """

    action: BattleAction
    executable: bool
    errors: tuple[str, ...]
    resource_deltas: dict
    interactions: tuple = ()


@dataclass(frozen=True, slots=True)
class BattleOutcome:
    finished: bool
    winning_sides: tuple[str, ...] = ()
    defeated_sides: tuple[str, ...] = ()
    escaped_sides: tuple[str, ...] = ()
    objective_ids: tuple[str, ...] = ()


class BattleRuntime:
    """Thin RPG coordinator over Phase 6 AbilityRuntime plus lifecycle hooks.

    Outcome semantics are injected through `is_active`; BattleRuntime never
    assumes HP, death tags, or any specific defeat rule.
    """

    def __init__(
        self,
        parties,
        ability_runtime,
        *,
        turn_policy=TurnOrderPolicy.FIXED_INITIATIVE,
        hooks=None,
        is_active: Callable[[PartyMember], bool] | None = None,
        resource_definitions=(),
        interaction_rules=(),
        outcome_checks=(),
        state_policies=(),
        targeting_definitions=(),
        formations=None,
        objective_definitions=(),
        escape_rules=(),
        scheduler_definition=None,
        action_timing_definitions=(),
        action_sequence_definitions=(),
        gauge_composition_definitions=(),
        reaction_definitions=(),
        enemy_ai_definitions=(),
        ai_condition_resolvers=None,
        ai_target_resolvers=None,
        ai_action_handlers=None,
        transaction_policies=(),
        rng_seed=0,
    ):
        parties = tuple(parties)
        if not parties:
            raise ValueError("battle requires at least one party")
        if any(not isinstance(x, Party) for x in parties):
            raise TypeError("parties must be Party values")
        if not isinstance(ability_runtime, AbilityRuntime):
            raise TypeError("ability_runtime must be AbilityRuntime")
        if is_active is not None and not callable(is_active):
            raise TypeError("is_active must be callable")
        self.hooks = hooks
        self.is_active = is_active or (lambda member: True)
        self.parties = {p.side: p for p in parties}
        if len(self.parties) != len(parties):
            raise ValueError("duplicate party side")
        members = []
        for p in parties:
            members.extend(p.members)
        if len({m.member_id for m in members}) != len(members):
            raise ValueError("duplicate battle member id")
        self.members = {m.member_id: m for m in members}
        self._base_is_active = self.is_active
        self.combatants = CombatantLifecycleRuntime(members, hooks=hooks, initial_active=self._base_is_active)
        self.is_active = lambda member: self.combatants.is_active(member) and self._base_is_active(member)
        self.objectives = BattleObjectiveRuntime(objective_definitions, hooks=hooks)
        self.escape_rules = {}
        for rule in escape_rules:
            if not isinstance(rule, BattleEscapeRule):
                raise TypeError("escape_rules must be BattleEscapeRule values")
            if rule.rule_id in self.escape_rules:
                raise ValueError(f"duplicate escape rule: {rule.rule_id}")
            self.escape_rules[rule.rule_id] = rule
        self._escaped_sides = set()
        self._transform_stacks = {}
        self.ability_runtime = ability_runtime
        self.cooldowns = {}  # member id -> {ability id: turns left} (AbilityDefinition.cooldown_turns)
        self._used_this_turn = set()
        self.battle_resources = BattleResourceRuntime(resource_definitions, members, hooks=hooks)
        self.interactions = InteractionResolver(interaction_rules, outcome_checks, hooks=hooks)
        self.battle_states = BattleStateRuntime(state_policies, hooks=hooks)
        self.battle_states.periodic_transform = self._periodic_interaction_transform
        self.periodic_interactions = []
        formation_runtimes = {}
        for side, value in dict(formations or {}).items():
            if isinstance(value, BattleFormationRuntime):
                runtime = value
            else:
                runtime = BattleFormationRuntime(value)
            formation_runtimes[str(side)] = runtime
        self.formations = formation_runtimes
        self.targeting = BattleTargetingRuntime(
            self.members,
            definitions=targeting_definitions,
            formations=self.formations,
            is_active=self.is_active,
            is_targetable=lambda member: self.combatants.is_targetable(member),
        )
        if scheduler_definition is None:
            self.scheduler = None
            self.turn_queue = TurnQueue(members, turn_policy)
        else:
            if not isinstance(scheduler_definition, BattleSchedulerDefinition):
                raise TypeError("scheduler_definition must be BattleSchedulerDefinition")
            self.scheduler = BattleScheduler(members, scheduler_definition)
            self.turn_queue = self.scheduler
        self.action_timing = BattleActionTimingRuntime(action_timing_definitions)
        self.action_sequences = ActionSequenceRuntime(action_sequence_definitions)
        self.gauge_compositions = BattleGaugeCompositionRuntime(gauge_composition_definitions, hooks=hooks)
        self.reactions = ReactionRuntime(reaction_definitions, hooks=hooks)
        self.enemy_ai = EnemyAIRuntime(
            enemy_ai_definitions,
            hooks=hooks,
            condition_resolvers=ai_condition_resolvers,
            target_resolvers=ai_target_resolvers,
            action_handlers=ai_action_handlers,
        )
        self.transactions = BattleTransactionRuntime(transaction_policies)
        self.rng = random.Random(rng_seed)
        self._resource_ready_entry = None
        self._resources_finished = False
        self.battle_resources.apply_trigger("rpg.battle.started")
        emit_hook(self.hooks, "rpg.battle.started", data={"battle": self})
        self.battle_resources.apply_trigger("rpg.battle.round_started")
        emit_hook(
            self.hooks,
            "rpg.battle.round_started",
            data={"round_index": self.turn_queue.round_index},
        )

    def member(self, member_id):
        return self.members[str(member_id)]

    def can_act(self, member_id):
        member = self.member(member_id)
        return self.combatants.can_act(member_id) and self._base_is_active(member)

    def incapacitate(self, member_id, *, state_id="incapacitated", targetable=True, reason=""):
        state = self.combatants.incapacitate(member_id, state_id=state_id, targetable=targetable, reason=reason)
        self.turn_queue.remove_pending(member_id)
        return state

    def revive(self, member_id, *, state_id="active", targetable=True, reason=""):
        return self.combatants.revive(member_id, state_id=state_id, targetable=targetable, reason=reason)

    def remove_combatant(self, member_id, *, state_id="removed", reason=""):
        state = self.combatants.remove(member_id, state_id=state_id, reason=reason)
        self.turn_queue.remove_pending(member_id)
        formation = self.formations.get(self.member(member_id).side)
        if formation is not None and formation.slot_id_for(member_id) is not None:
            formation.remove(member_id)
        return state

    def summon(self, member, *, slot_id=None, owner_id=None, join_current_round=False):
        if not isinstance(member, PartyMember):
            raise TypeError("member must be PartyMember")
        if member.member_id in self.members:
            raise ValueError(f"duplicate battle member id: {member.member_id}")
        if member.side not in self.parties:
            raise ValueError(f"unknown battle side: {member.side}")
        if owner_id is not None and str(owner_id) not in self.members:
            raise ValueError(f"unknown summon owner: {owner_id}")
        formation = self.formations.get(member.side)
        if slot_id is not None:
            if formation is None:
                raise ValueError("summon slot requires a formation for the member side")
            formation.definition.slot(slot_id)
            if formation.member_at(slot_id) is not None:
                raise ValueError(f"formation slot occupied: {slot_id}")
        self.parties[member.side].add(member)
        self.members[member.member_id] = member
        generation = 1
        if owner_id is not None:
            owner_state = self.combatants.state(owner_id)
            generation = owner_state.summon_generation + 1
        self.combatants.register(member.member_id, summon_owner_id=owner_id, summon_generation=generation)
        self.battle_resources.register_member(member)
        self.targeting.members[member.member_id] = member
        self.turn_queue.register_member(member, join_current_round=join_current_round)
        if slot_id is not None:
            formation.place(member.member_id, slot_id)
        emit_hook(
            self.hooks,
            "rpg.battle.combatant_summoned",
            source=member.member_id,
            data={"member": member, "owner_id": owner_id, "slot_id": slot_id},
        )
        return member

    def transform(self, member_id, replacement, *, form_id, reason=""):
        member_id = str(member_id)
        current = self.member(member_id)
        if not isinstance(replacement, PartyMember):
            raise TypeError("replacement must be PartyMember")
        if replacement.member_id != current.member_id or replacement.side != current.side:
            raise ValueError("transformation replacement must preserve member_id and side")
        prior_form_id = self.combatants.state(member_id).form_id
        self._transform_stacks.setdefault(member_id, []).append((current, prior_form_id))
        self.members[member_id] = replacement
        party = self.parties[current.side]
        party.members = [replacement if x.member_id == member_id else x for x in party.members]
        self.targeting.members[member_id] = replacement
        self.turn_queue.replace_member(replacement)
        self.combatants.set_form(member_id, form_id, reason=reason)
        return replacement

    def revert_transform(self, member_id, *, reason=""):
        member_id = str(member_id)
        stack = self._transform_stacks.get(member_id) or []
        if not stack:
            raise ValueError(f"combatant has no previous form: {member_id}")
        previous, prior_form_id = stack.pop()
        current = self.member(member_id)
        self.members[member_id] = previous
        party = self.parties[current.side]
        party.members = [previous if x.member_id == member_id else x for x in party.members]
        self.targeting.members[member_id] = previous
        self.turn_queue.replace_member(previous)
        if prior_form_id is not None:
            self.combatants.set_form(member_id, prior_form_id, reason=reason)
        else:
            self.combatants.clear_form(member_id, reason=reason)
        return previous

    def set_objective_flag(self, flag_id, value=True):
        self.objectives.set_flag(flag_id, value)

    def attempt_escape(self, rule_id, *, rng=None):
        rule = self.escape_rules[str(rule_id)]
        result = attempt_escape(rule, self, rng=rng)
        if result.succeeded:
            self._escaped_sides.add(rule.side)
            for member in tuple(self.parties[rule.side].members):
                if member.member_id in self.members and self.combatants.state(member.member_id).present:
                    self.remove_combatant(member.member_id, state_id="escaped", reason=rule.rule_id)
            self.set_objective_flag(f"escape.{rule.side}", True)
        return result

    def ability_availability(self, actor_id, ability_id):
        actor = self.member(actor_id)
        definition = self.ability_runtime.registry.require(ability_id)
        return self.battle_states.ability_availability(actor.subject, definition.tags)

    def apply_state(self, state_id, source_id, target_id, *, rng=None):
        source = self.member(source_id)
        target = self.member(target_id)
        return self.battle_states.apply(
            state_id, source.member_id, source.subject, target.member_id, target.subject, rng=rng
        )

    def resolve_targets(self, actor_id, ability_id, requested_ids=(), *, rng=None):
        return self.targeting.resolve(actor_id, ability_id, requested_ids, rng=rng)

    def _validate_action(self, action, *, rng=None):
        if not isinstance(action, BattleAction):
            raise TypeError("action must be BattleAction")
        actor = self.member(action.actor_id)
        if not self.can_act(actor.member_id):
            raise ValueError("actor cannot act in current combatant lifecycle state")
        if action.ability_id not in actor.ability_ids:
            raise ValueError("actor does not know ability")
        availability = self.ability_availability(actor.member_id, action.ability_id)
        if not availability.allowed:
            raise ValueError(f"ability blocked by active state: {', '.join(availability.blocking_states)}")
        left = self.cooldown_remaining(actor.member_id, action.ability_id)
        if left and (actor.member_id, action.ability_id) not in self._used_this_turn:  # repeats in one turn (boost)
            raise ValueError(f"ability cooling down: {action.ability_id} ({left} turns)")
        target_resolution = self.resolve_targets(actor.member_id, action.ability_id, action.target_ids, rng=rng)
        if not target_resolution.valid:
            raise ValueError("invalid battle targets: " + ", ".join(target_resolution.errors))
        if target_resolution.selected_ids != action.target_ids:
            action = BattleAction(action.actor_id, action.ability_id, target_resolution.selected_ids)
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
            current_time = max(current_time, float(getattr(ready_entry, "ready_time", current_time)))
        pending = self.action_timing.begin(action, current_time=current_time)
        if pending is None:
            result = self.execute(action, rng=rng)
            self.advance_turn(recovery=definition.recovery)
            return result
        actor = self.member(action.actor_id)
        target_subject = self.member(action.target_ids[0]).subject if action.target_ids else None
        committed = self.transactions.commit_start(
            pending.token, action.actor_id, action.ability_id, actor.subject, target_subject, self.ability_runtime
        )
        emit_hook(
            self.hooks,
            "rpg.battle.action_cast_started",
            source=action.actor_id,
            data={"action": action, "pending": pending, "timing": definition, "committed_costs": committed},
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
            if self.scheduler is not None and self.scheduler.mode == BattleSchedulerMode.CONTINUOUS:
                self.scheduler.advance_time(pending.resolve_at)
            if pending.actor_id not in self.members or not self.combatants.state(pending.actor_id).present:
                reservation = self.transactions.cancel(pending.token, self.member(pending.actor_id).subject)
                emit_hook(
                    self.hooks,
                    "rpg.battle.action_cancelled",
                    source=pending.actor_id,
                    data={"pending": pending, "reason": "actor_not_present", "reservation": reservation},
                )
                continue
            action = BattleAction(pending.actor_id, pending.ability_id, pending.target_ids)
            # Targets are revalidated at resolution because battle state may have changed during cast.
            try:
                action = self._validate_action(action, rng=rng)
            except ValueError as exc:
                reservation = self.transactions.cancel(pending.token, self.member(pending.actor_id).subject)
                emit_hook(
                    self.hooks,
                    "rpg.battle.action_cancelled",
                    source=pending.actor_id,
                    data={"pending": pending, "reason": str(exc), "reservation": reservation},
                )
                continue
            reservation = self.transactions.consume(pending.token)
            wrapped = self.execute(action, rng=rng, prepaid_costs=None if reservation is None else reservation.costs)
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
        scheduled = self.scheduler.shift_member(member_id, delta) if self.scheduler is not None else tuple()
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
        from asteria.gameplay.effects import EffectOperationKind

        from .interactions import InteractionDisposition

        if not self.interactions.rules:
            return None
        tags = self.ability_runtime.registry.require(ability_id).tags

        def transform(target_id, operation, value):
            if operation.kind != EffectOperationKind.RESOURCE_DELTA or value >= 0:
                return value
            resolved = self.interactions.resolve_value(
                -float(value), subjects[0], subjects[1][target_id], action_tags=tags
            )
            record.append((target_id, operation.target, resolved))
            if resolved.disposition == InteractionDisposition.NULLIFY:
                return 0.0
            if resolved.disposition == InteractionDisposition.ABSORB:
                return resolved.resolved_value
            if resolved.disposition == InteractionDisposition.REFLECT:
                return (0.0, -resolved.resolved_value)
            return -resolved.resolved_value

        return transform

    def _periodic_interaction_transform(self, member, active, policy):
        """Damage-over-time opt-in (BattleStatePolicy.interaction_tags).

        The tick's own magnitude is resolved once with the policy's tags; the
        multiplier of the attack that applied the state is never reapplied.
        The state's source (or the afflicted member itself) is the source subject.
        """
        from asteria.gameplay.effects import EffectOperationKind

        from .interactions import InteractionDisposition

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
            self.periodic_interactions.append((member.member_id, active.state_id, operation.target, resolved))
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
        from asteria.gameplay.abilities import _clone_subject

        probe = random.Random()
        probe.setstate((self.rng if rng is None else rng).getstate())
        try:
            effective = self._validate_action(action, rng=probe)
        except ValueError as exc:
            return BattleActionPreview(action, False, (str(exc),), {})
        actor = self.member(effective.actor_id)
        ids = (actor.member_id, *effective.target_ids)
        clones = {member_id: _clone_subject(self.member(member_id).subject) for member_id in dict.fromkeys(ids)}
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
            effective, result.executed, tuple(result.errors), deltas, tuple(record) if result.executed else ()
        )

    def execute(self, action, *, rng=None, prepaid_costs=None):
        rng = self.rng if rng is None else rng
        effective_action = self._validate_action(action, rng=rng)
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
            actor, action.ability_id, (actor.subject, {x.member_id: x.subject for x in targets}), record
        )
        result = self.ability_runtime.execute(
            action.ability_id, source, target_values, prepaid_costs=prepaid_costs, value_transform=transform
        )
        wrapped = BattleActionResult(effective_action, result, tuple(record) if result.executed else ())
        if result.executed:
            self._start_cooldown(actor.member_id, action.ability_id)
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
        rng = self.rng if rng is None else rng
        """Execute a generic multi-hit/chain/cooperative plan.

        Game-authored interruption_policy decides failure behavior. Asteria only
        guarantees deterministic planning, validation, hooks and safe execution.
        Participant turn reservation/cost policy remains project-owned rather than
        silently imposed by this convenience execution path.
        """
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
            data={"plan": plan, "results": tuple(results), "failures": tuple(failures), "completed": completed},
        )
        return plan, tuple(results), tuple(failures)

    def execute_ai_turn(self, ai_id, actor_id, *, rng=None, advance_turn=False):
        rng = self.rng if rng is None else rng
        """Run one AI ready-window through the generic AI/action hook layer.

        Custom `action_kind` handlers may bridge any battle-adjacent system: alchemy,
        summoning, transformations, stance systems, plugins, or project scripts.
        Asteria does not prescribe those game rules; it only provides the stable hook.
        """
        actor_id = str(actor_id)
        if actor_id not in self.members:
            raise KeyError(actor_id)
        if not self.can_act(actor_id):
            return ()
        emit_hook(self.hooks, "rpg.battle.ai.turn_started", source=actor_id, data={"battle": self, "ai_id": str(ai_id)})
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

    def snapshot(self):
        return capture_battle_snapshot(self)

    def restore_snapshot(self, snapshot):
        restore_battle_snapshot(self, snapshot)
        emit_hook(self.hooks, "rpg.battle.snapshot_restored", data={"battle": self})
        return self

    def apply_gauge_impact(
        self, composition_id, source_id, target_id, *, trigger, outcome=None, outcome_tags=(), value=None, rng=None
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

    def next_actor(self):
        skipped = 0
        while True:
            entry = self.turn_queue.peek()
            if (
                self.scheduler is not None
                and self.scheduler.mode == BattleSchedulerMode.CONTINUOUS
                and entry is not None
            ):
                self.resolve_due_actions(entry.ready_time)
                entry = self.turn_queue.peek()
            while entry is not None and not self.can_act(entry.member_id):
                self.turn_queue.pop()
                entry = self.turn_queue.peek()
            if entry is None:
                return None
            actor = self.member(entry.member_id)
            ready_key = (self.turn_queue.round_index, entry.member_id, getattr(entry, "ready_time", None))
            if self._resource_ready_entry != ready_key:
                self.battle_resources.apply_trigger("rpg.battle.turn_ready", (actor.member_id,))
                self.battle_states.apply_trigger("rpg.battle.turn_ready", (actor,))
                self._resource_ready_entry = ready_key
            availability = self.battle_states.ability_availability(actor.subject, ())
            if not availability.allowed:
                emit_hook(
                    self.hooks,
                    "rpg.battle.turn_skipped",
                    source=actor.member_id,
                    data={
                        "actor": actor,
                        "blocking_states": availability.blocking_states,
                        "round_index": self.turn_queue.round_index,
                    },
                )
                self.advance_turn()
                skipped += 1
                if skipped > 10000:
                    raise RuntimeError("battle scheduler could not find an actionable combatant")
                continue
            emit_hook(
                self.hooks,
                "rpg.battle.turn_ready",
                source=actor.member_id,
                data={
                    "actor": actor,
                    "round_index": self.turn_queue.round_index,
                    "timeline_time": getattr(self.turn_queue, "current_time", None),
                },
            )
            return actor

    def cooldown_remaining(self, member_id, ability_id):
        """Turns of ``member_id`` before ``ability_id`` can be used again (0 = ready)."""
        return self.cooldowns.get(str(member_id), {}).get(str(ability_id), 0)

    def _start_cooldown(self, member_id, ability_id):
        definition = self.ability_runtime.registry.get(ability_id)
        turns = getattr(definition, "cooldown_turns", 0) if definition is not None else 0
        if turns and (member_id, ability_id) not in self._used_this_turn:
            self.cooldowns.setdefault(member_id, {})[ability_id] = int(turns)
        self._used_this_turn.add((member_id, ability_id))

    def _tick_cooldowns(self, member_id):
        """End of ``member_id``'s turn: its cooldowns count down, except those started in this turn."""
        member_id = str(member_id)
        waiting = self.cooldowns.get(member_id, {})
        for ability_id in list(waiting):
            if (member_id, ability_id) not in self._used_this_turn:
                waiting[ability_id] -= 1
                if waiting[ability_id] <= 0:
                    del waiting[ability_id]
        self._used_this_turn = {x for x in self._used_this_turn if x[0] != member_id}

    def advance_turn(self, *, recovery=0.0):
        entry = self.turn_queue.pop()
        if entry is not None:
            self._tick_cooldowns(entry.member_id)
        if entry is not None and recovery and self.scheduler is not None:
            self.scheduler.shift_member(entry.member_id, float(recovery))
        if entry is not None:
            self._resource_ready_entry = None
            self.battle_resources.apply_trigger("rpg.battle.turn_ended", (entry.member_id,))
            self.battle_states.apply_trigger("rpg.battle.turn_ended", (self.member(entry.member_id),))
            emit_hook(
                self.hooks,
                "rpg.battle.turn_ended",
                source=entry.member_id,
                data={"entry": entry, "round_index": self.turn_queue.round_index},
            )
        return entry

    def start_next_round(self):
        self.battle_resources.apply_trigger("rpg.battle.round_ended")
        self.battle_states.apply_trigger("rpg.battle.round_ended", tuple(self.members.values()))
        emit_hook(
            self.hooks,
            "rpg.battle.round_ended",
            data={"round_index": self.turn_queue.round_index},
        )
        entries = self.turn_queue.start_round()
        self._resource_ready_entry = None
        self.battle_resources.apply_trigger("rpg.battle.round_started")
        self.battle_states.apply_trigger("rpg.battle.round_started", tuple(self.members.values()))
        emit_hook(
            self.hooks,
            "rpg.battle.round_started",
            data={"round_index": self.turn_queue.round_index},
        )
        return entries

    def resolve_outcome(self):
        objective_results = self.objectives.evaluate(self)
        completed = []
        for objective_id, status in objective_results:
            if status not in {"succeeded", "failed"}:
                continue
            definition = self.objectives.definitions[objective_id]
            if status == "succeeded":
                outcome = BattleOutcome(
                    True,
                    tuple(sorted(definition.winning_sides)),
                    tuple(sorted(definition.defeated_sides)),
                    tuple(sorted(self._escaped_sides)),
                    (objective_id,),
                )
            else:
                outcome = BattleOutcome(
                    True,
                    tuple(sorted(definition.failure_winning_sides)),
                    tuple(sorted(definition.failure_defeated_sides)),
                    tuple(sorted(self._escaped_sides)),
                    (objective_id,),
                )
            completed.append(outcome)
        if completed:
            outcome = completed[0]
        elif self._escaped_sides:
            outcome = BattleOutcome(
                True,
                (),
                (),
                tuple(sorted(self._escaped_sides)),
                (),
            )
        elif self.objectives.definitions:
            outcome = BattleOutcome(False, (), (), (), ())
        else:
            active_sides = []
            defeated = []
            for side, party in self.parties.items():
                if any(member.member_id in self.members and self.is_active(member) for member in party.members):
                    active_sides.append(side)
                else:
                    defeated.append(side)
            finished = len(active_sides) <= 1
            outcome = BattleOutcome(
                finished,
                tuple(sorted(active_sides)) if finished else (),
                tuple(sorted(defeated)),
                tuple(sorted(self._escaped_sides)),
                (),
            )
        emit_hook(self.hooks, "rpg.battle.outcome_resolved", data={"outcome": outcome})
        if outcome.finished and not self._resources_finished:
            self.battle_resources.apply_trigger("rpg.battle.finished")
            self.battle_resources.finish()
            self._resources_finished = True
            emit_hook(self.hooks, "rpg.battle.finished", data={"outcome": outcome})
        return outcome
