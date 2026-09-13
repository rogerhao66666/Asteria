from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import random

from asteria.core.lifecycle import emit_hook


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
class CombatantLifecycleState:
    member_id: str
    state_id: str
    present: bool = True
    can_act: bool = True
    targetable: bool = True
    defeated: bool = False
    form_id: str | None = None
    summon_owner_id: str | None = None
    summon_generation: int = 0
    reason: str = ""

    @property
    def active(self):
        return self.present and not self.defeated


class CombatantLifecycleRuntime:
    """Battle-local participation state without imposing HP/death semantics.

    `state_id` and `reason` are open project vocabulary. Convenience operations
    (incapacitate/revive/remove) only manipulate generic participation flags.
    """

    def __init__(self, members=(), *, hooks=None, initial_active=None):
        self.hooks = hooks
        self._states = {}
        self._form_stacks = {}
        predicate = initial_active or (lambda _member: True)
        for member in members:
            active = bool(predicate(member))
            self.register(
                member.member_id,
                state_id="active" if active else "inactive",
                present=True,
                can_act=active,
                targetable=True,
                defeated=not active,
            )

    def register(
        self,
        member_id,
        *,
        state_id="active",
        present=True,
        can_act=True,
        targetable=True,
        defeated=False,
        form_id=None,
        summon_owner_id=None,
        summon_generation=0,
        reason="",
    ):
        member_id = _id(member_id, "member_id")
        if member_id in self._states:
            raise ValueError(f"duplicate combatant lifecycle member: {member_id}")
        state = CombatantLifecycleState(
            member_id,
            _id(state_id, "state_id"),
            bool(present),
            bool(can_act),
            bool(targetable),
            bool(defeated),
            None if form_id is None else _id(form_id, "form_id"),
            None if summon_owner_id is None else _id(summon_owner_id, "summon_owner_id"),
            int(summon_generation),
            str(reason),
        )
        if state.summon_generation < 0:
            raise ValueError("summon_generation must be >= 0")
        self._states[member_id] = state
        emit_hook(self.hooks, "rpg.battle.combatant_registered", source=member_id, data={"state": state})
        return state

    def state(self, member_id):
        return self._states[_id(member_id, "member_id")]

    def states(self):
        return tuple(self._states[k] for k in sorted(self._states))

    def _replace(self, member_id, **changes):
        current = self.state(member_id)
        data = {
            "member_id": current.member_id,
            "state_id": current.state_id,
            "present": current.present,
            "can_act": current.can_act,
            "targetable": current.targetable,
            "defeated": current.defeated,
            "form_id": current.form_id,
            "summon_owner_id": current.summon_owner_id,
            "summon_generation": current.summon_generation,
            "reason": current.reason,
        }
        data.update(changes)
        next_state = CombatantLifecycleState(**data)
        self._states[current.member_id] = next_state
        emit_hook(
            self.hooks,
            "rpg.battle.combatant_state_changed",
            source=current.member_id,
            data={"previous": current, "current": next_state},
        )
        return next_state

    def is_active(self, member_or_id):
        member_id = getattr(member_or_id, "member_id", member_or_id)
        return self.state(member_id).active

    def can_act(self, member_or_id):
        member_id = getattr(member_or_id, "member_id", member_or_id)
        state = self.state(member_id)
        return state.present and state.can_act and not state.defeated

    def is_targetable(self, member_or_id):
        member_id = getattr(member_or_id, "member_id", member_or_id)
        state = self.state(member_id)
        return state.present and state.targetable

    def incapacitate(self, member_id, *, state_id="incapacitated", targetable=True, reason=""):
        state = self._replace(
            member_id,
            state_id=_id(state_id, "state_id"),
            present=True,
            can_act=False,
            targetable=bool(targetable),
            defeated=True,
            reason=str(reason),
        )
        emit_hook(self.hooks, "rpg.battle.combatant_incapacitated", source=state.member_id, data={"state": state})
        return state

    def revive(self, member_id, *, state_id="active", targetable=True, reason=""):
        state = self._replace(
            member_id,
            state_id=_id(state_id, "state_id"),
            present=True,
            can_act=True,
            targetable=bool(targetable),
            defeated=False,
            reason=str(reason),
        )
        emit_hook(self.hooks, "rpg.battle.combatant_revived", source=state.member_id, data={"state": state})
        return state

    def remove(self, member_id, *, state_id="removed", reason=""):
        state = self._replace(
            member_id,
            state_id=_id(state_id, "state_id"),
            present=False,
            can_act=False,
            targetable=False,
            defeated=True,
            reason=str(reason),
        )
        emit_hook(self.hooks, "rpg.battle.combatant_removed", source=state.member_id, data={"state": state})
        return state

    def set_form(self, member_id, form_id, *, reason=""):
        state = self._replace(member_id, form_id=_id(form_id, "form_id"), reason=str(reason))
        emit_hook(self.hooks, "rpg.battle.combatant_transformed", source=state.member_id, data={"state": state})
        return state

    def clear_form(self, member_id, *, reason=""):
        state = self._replace(member_id, form_id=None, reason=str(reason))
        emit_hook(self.hooks, "rpg.battle.combatant_form_reverted", source=state.member_id, data={"state": state})
        return state

    def to_data(self):
        return {
            "schema": "asteria.rpg.combatant_lifecycle_runtime",
            "version": 1,
            "states": [
                {
                    "member_id": x.member_id,
                    "state_id": x.state_id,
                    "present": x.present,
                    "can_act": x.can_act,
                    "targetable": x.targetable,
                    "defeated": x.defeated,
                    "form_id": x.form_id,
                    "summon_owner_id": x.summon_owner_id,
                    "summon_generation": x.summon_generation,
                    "reason": x.reason,
                }
                for x in self.states()
            ],
        }

    @classmethod
    def from_data(cls, data, *, hooks=None):
        if data.get("schema") != "asteria.rpg.combatant_lifecycle_runtime" or data.get("version") != 1:
            raise ValueError("unsupported combatant lifecycle runtime")
        result = cls.__new__(cls)
        result.hooks = hooks
        result._states = {}
        result._form_stacks = {}
        for raw in data["states"]:
            state = CombatantLifecycleState(**raw)
            result._states[state.member_id] = state
        return result


@dataclass(frozen=True, slots=True)
class BattleObjectiveCondition:
    kind: str
    subject_id: str
    operator: str
    value: float | bool

    def __init__(self, kind, subject_id, operator="==", value=True):
        kind = _id(kind, "kind")
        if kind not in {"side_active_count", "member_active", "round_index", "flag"}:
            raise ValueError("unsupported battle objective condition kind")
        operator = str(operator).strip()
        if operator not in {"<", "<=", "==", "!=", ">=", ">"}:
            raise ValueError("unsupported battle objective operator")
        if kind in {"side_active_count", "round_index"}:
            value = _number(value, "value")
        else:
            value = bool(value)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "subject_id", _id(subject_id, "subject_id"))
        object.__setattr__(self, "operator", operator)
        object.__setattr__(self, "value", value)

    def _compare(self, actual):
        return {
            "<": actual < self.value,
            "<=": actual <= self.value,
            "==": actual == self.value,
            "!=": actual != self.value,
            ">=": actual >= self.value,
            ">": actual > self.value,
        }[self.operator]

    def evaluate(self, battle, flags):
        if self.kind == "side_active_count":
            actual = sum(
                1 for m in battle.parties[self.subject_id].members
                if m.member_id in battle.members and battle.is_active(m)
            )
        elif self.kind == "member_active":
            actual = battle.is_active(battle.member(self.subject_id))
        elif self.kind == "round_index":
            actual = battle.turn_queue.round_index
        else:
            actual = bool(flags.get(self.subject_id, False))
        return self._compare(actual)

    def to_data(self):
        return {"kind": self.kind, "subject_id": self.subject_id, "operator": self.operator, "value": self.value}

    @classmethod
    def from_data(cls, data):
        if set(data) != {"kind", "subject_id", "operator", "value"}:
            raise ValueError("invalid battle objective condition")
        return cls(**data)


@dataclass(frozen=True, slots=True)
class BattleObjectiveDefinition:
    objective_id: str
    success_conditions: tuple[BattleObjectiveCondition, ...]
    failure_conditions: tuple[BattleObjectiveCondition, ...]
    success_mode: str
    failure_mode: str
    winning_sides: tuple[str, ...]
    defeated_sides: tuple[str, ...]
    failure_winning_sides: tuple[str, ...]
    failure_defeated_sides: tuple[str, ...]
    priority: int

    def __init__(
        self,
        objective_id,
        *,
        success_conditions=(),
        failure_conditions=(),
        success_mode="all",
        failure_mode="any",
        winning_sides=(),
        defeated_sides=(),
        failure_winning_sides=None,
        failure_defeated_sides=None,
        priority=0,
    ):
        success_conditions = tuple(success_conditions)
        failure_conditions = tuple(failure_conditions)
        if any(not isinstance(x, BattleObjectiveCondition) for x in success_conditions + failure_conditions):
            raise TypeError("objective conditions must be BattleObjectiveCondition values")
        success_mode = str(success_mode).strip().lower()
        failure_mode = str(failure_mode).strip().lower()
        if success_mode not in {"all", "any"} or failure_mode not in {"all", "any"}:
            raise ValueError("objective mode must be all or any")
        success_winners = tuple(dict.fromkeys(_id(x, "winning_side") for x in winning_sides))
        success_defeated = tuple(dict.fromkeys(_id(x, "defeated_side") for x in defeated_sides))
        if failure_winning_sides is None:
            failure_winning_sides = success_defeated
        if failure_defeated_sides is None:
            failure_defeated_sides = success_winners
        object.__setattr__(self, "objective_id", _id(objective_id, "objective_id"))
        object.__setattr__(self, "success_conditions", success_conditions)
        object.__setattr__(self, "failure_conditions", failure_conditions)
        object.__setattr__(self, "success_mode", success_mode)
        object.__setattr__(self, "failure_mode", failure_mode)
        object.__setattr__(self, "winning_sides", success_winners)
        object.__setattr__(self, "defeated_sides", success_defeated)
        object.__setattr__(self, "failure_winning_sides", tuple(dict.fromkeys(_id(x, "failure_winning_side") for x in failure_winning_sides)))
        object.__setattr__(self, "failure_defeated_sides", tuple(dict.fromkeys(_id(x, "failure_defeated_side") for x in failure_defeated_sides)))
        object.__setattr__(self, "priority", int(priority))

    def _matches(self, conditions, mode, battle, flags):
        if not conditions:
            return False
        values = [x.evaluate(battle, flags) for x in conditions]
        return all(values) if mode == "all" else any(values)

    def evaluate(self, battle, flags):
        # Failure wins ties inside one objective: protect/survival constraints should
        # not be silently converted into success when both conditions become true.
        if self._matches(self.failure_conditions, self.failure_mode, battle, flags):
            return "failed"
        if self._matches(self.success_conditions, self.success_mode, battle, flags):
            return "succeeded"
        return "pending"

    def to_data(self):
        return {
            "schema": "asteria.rpg.battle_objective_definition",
            "version": 1,
            "objective_id": self.objective_id,
            "success_conditions": [x.to_data() for x in self.success_conditions],
            "failure_conditions": [x.to_data() for x in self.failure_conditions],
            "success_mode": self.success_mode,
            "failure_mode": self.failure_mode,
            "winning_sides": list(self.winning_sides),
            "defeated_sides": list(self.defeated_sides),
            "failure_winning_sides": list(self.failure_winning_sides),
            "failure_defeated_sides": list(self.failure_defeated_sides),
            "priority": self.priority,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.battle_objective_definition" or data.get("version") != 1:
            raise ValueError("unsupported battle objective definition")
        return cls(
            data["objective_id"],
            success_conditions=[BattleObjectiveCondition.from_data(x) for x in data["success_conditions"]],
            failure_conditions=[BattleObjectiveCondition.from_data(x) for x in data["failure_conditions"]],
            success_mode=data["success_mode"],
            failure_mode=data["failure_mode"],
            winning_sides=data["winning_sides"],
            defeated_sides=data["defeated_sides"],
            failure_winning_sides=data.get("failure_winning_sides"),
            failure_defeated_sides=data.get("failure_defeated_sides"),
            priority=data.get("priority", 0),
        )


@dataclass(frozen=True, slots=True)
class BattleEscapeRule:
    rule_id: str
    side: str
    base_chance: float
    source_stat: str | None = None
    source_scale: float = 0.0
    opponent_stat: str | None = None
    opponent_scale: float = 0.0
    minimum_chance: float = 0.0
    maximum_chance: float = 1.0

    def __init__(
        self,
        rule_id,
        side,
        *,
        base_chance=1.0,
        source_stat=None,
        source_scale=0.0,
        opponent_stat=None,
        opponent_scale=0.0,
        minimum_chance=0.0,
        maximum_chance=1.0,
    ):
        minimum_chance = _number(minimum_chance, "minimum_chance")
        maximum_chance = _number(maximum_chance, "maximum_chance")
        if not 0 <= minimum_chance <= maximum_chance <= 1:
            raise ValueError("escape chance bounds must satisfy 0 <= min <= max <= 1")
        object.__setattr__(self, "rule_id", _id(rule_id, "rule_id"))
        object.__setattr__(self, "side", _id(side, "side"))
        object.__setattr__(self, "base_chance", _number(base_chance, "base_chance"))
        object.__setattr__(self, "source_stat", None if source_stat is None else _id(source_stat, "source_stat"))
        object.__setattr__(self, "source_scale", _number(source_scale, "source_scale"))
        object.__setattr__(self, "opponent_stat", None if opponent_stat is None else _id(opponent_stat, "opponent_stat"))
        object.__setattr__(self, "opponent_scale", _number(opponent_scale, "opponent_scale"))
        object.__setattr__(self, "minimum_chance", minimum_chance)
        object.__setattr__(self, "maximum_chance", maximum_chance)

    def to_data(self):
        return {
            "schema": "asteria.rpg.battle_escape_rule",
            "version": 1,
            "rule_id": self.rule_id,
            "side": self.side,
            "base_chance": self.base_chance,
            "source_stat": self.source_stat,
            "source_scale": self.source_scale,
            "opponent_stat": self.opponent_stat,
            "opponent_scale": self.opponent_scale,
            "minimum_chance": self.minimum_chance,
            "maximum_chance": self.maximum_chance,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.battle_escape_rule" or data.get("version") != 1:
            raise ValueError("unsupported battle escape rule")
        return cls(
            data["rule_id"], data["side"], base_chance=data["base_chance"],
            source_stat=data["source_stat"], source_scale=data["source_scale"],
            opponent_stat=data["opponent_stat"], opponent_scale=data["opponent_scale"],
            minimum_chance=data["minimum_chance"], maximum_chance=data["maximum_chance"],
        )


@dataclass(frozen=True, slots=True)
class BattleEscapeResult:
    rule_id: str
    side: str
    chance: float
    roll: float
    succeeded: bool


class BattleObjectiveRuntime:
    def __init__(self, definitions=(), *, hooks=None):
        self.hooks = hooks
        self.definitions = {}
        self.flags = {}
        for definition in definitions:
            if not isinstance(definition, BattleObjectiveDefinition):
                raise TypeError("definitions must be BattleObjectiveDefinition values")
            if definition.objective_id in self.definitions:
                raise ValueError(f"duplicate battle objective: {definition.objective_id}")
            self.definitions[definition.objective_id] = definition

    def set_flag(self, flag_id, value=True):
        flag_id = _id(flag_id, "flag_id")
        self.flags[flag_id] = bool(value)
        emit_hook(self.hooks, "rpg.battle.objective_flag_changed", source=flag_id, data={"value": bool(value)})

    def evaluate(self, battle):
        ordered = sorted(
            self.definitions.values(), key=lambda x: (-x.priority, x.objective_id)
        )
        return tuple((definition.objective_id, definition.evaluate(battle, self.flags)) for definition in ordered)


def resolve_escape_chance(rule, battle):
    source_members = [
        m for m in battle.parties[rule.side].members
        if m.member_id in battle.members and battle.is_active(m)
    ]
    opponents = [
        m for side, party in battle.parties.items() if side != rule.side
        for m in party.members if m.member_id in battle.members and battle.combatants.is_active(m.member_id)
    ]
    chance = rule.base_chance
    if rule.source_stat and source_members:
        chance += sum(m.subject.stats.get(rule.source_stat, 0.0) for m in source_members) / len(source_members) * rule.source_scale
    if rule.opponent_stat and opponents:
        chance -= sum(m.subject.stats.get(rule.opponent_stat, 0.0) for m in opponents) / len(opponents) * rule.opponent_scale
    return max(rule.minimum_chance, min(rule.maximum_chance, chance))


def attempt_escape(rule, battle, *, rng=None):
    if not isinstance(rule, BattleEscapeRule):
        raise TypeError("rule must be BattleEscapeRule")
    if rule.side not in battle.parties:
        raise ValueError(f"unknown escape side: {rule.side}")
    chance = resolve_escape_chance(rule, battle)
    engine = rng if rng is not None else random.Random()
    roll = float(engine.random())
    result = BattleEscapeResult(rule.rule_id, rule.side, chance, roll, roll < chance)
    emit_hook(
        battle.hooks,
        "rpg.battle.escape_resolved",
        source=rule.side,
        data={"result": result},
    )
    return result
