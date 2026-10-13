from __future__ import annotations

import random
from dataclasses import dataclass, field
from math import isfinite

from asteria.core.lifecycle import emit_hook

# Built-in vocabulary of EnemyAIRuntime (projects can add more through resolvers/handlers).
CONDITION_KINDS = (
    "always",
    "round_index",
    "resource",
    "resource_ratio",
    "stat",
    "memory",
    "phase",
    "can_act",
)
CONDITION_PARAMS = {
    "always": (),
    "round_index": ("op", "value"),
    "resource": ("resource_id", "op", "value"),
    "resource_ratio": ("resource_id", "op", "value"),
    "stat": ("stat_id", "op", "value"),
    "memory": ("key", "op", "value"),
    "phase": ("op", "value"),
    "can_act": (),
}
COMPARISONS = ("<", "<=", ">", ">=", "==", "!=")
TARGET_SELECTORS = ("self", "first_opponent", "all_opponents", "first_ally", "random_opponent")
TARGET_SELECTOR_PREFIXES = ("lowest_resource_ratio:",)
ACTION_KINDS = ("ability", "hook")


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _finite(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class AICondition:
    """Open condition contract. `kind` and `params` are project vocabulary."""

    kind: str
    params: dict[str, object] = field(default_factory=dict)
    negate: bool = False

    def __init__(self, kind, *, params=None, negate=False):
        object.__setattr__(self, "kind", _id(kind, "condition kind"))
        object.__setattr__(self, "params", dict(params or {}))
        object.__setattr__(self, "negate", bool(negate))

    def to_data(self):
        return {"kind": self.kind, "params": dict(self.params), "negate": self.negate}

    @classmethod
    def from_data(cls, data):
        return cls(data["kind"], params=data.get("params", {}), negate=data.get("negate", False))


@dataclass(frozen=True, slots=True)
class AIDecisionRule:
    rule_id: str
    action_kind: str
    payload: dict[str, object] = field(default_factory=dict)
    target_selector: str = "first_opponent"
    conditions: tuple[AICondition, ...] = ()
    priority: int = 0
    weight: float = 1.0
    tags: tuple[str, ...] = ()

    SCHEMA = "asteria.rpg.ai_decision_rule"
    VERSION = 1

    def __init__(
        self,
        rule_id,
        action_kind,
        *,
        payload=None,
        target_selector="first_opponent",
        conditions=(),
        priority=0,
        weight=1.0,
        tags=(),
    ):
        conditions = tuple(conditions)
        if any(not isinstance(x, AICondition) for x in conditions):
            raise TypeError("conditions must contain AICondition values")
        weight = _finite(weight, "weight")
        if weight < 0:
            raise ValueError("weight must be >= 0")
        object.__setattr__(self, "rule_id", _id(rule_id, "rule_id"))
        object.__setattr__(self, "action_kind", _id(action_kind, "action_kind"))
        object.__setattr__(self, "payload", dict(payload or {}))
        object.__setattr__(self, "target_selector", _id(target_selector, "target_selector"))
        object.__setattr__(self, "conditions", conditions)
        object.__setattr__(self, "priority", int(priority))
        object.__setattr__(self, "weight", weight)
        object.__setattr__(
            self, "tags", tuple(sorted({str(x).strip().lower() for x in tags if str(x).strip()}))
        )

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "rule_id": self.rule_id,
            "action_kind": self.action_kind,
            "payload": dict(self.payload),
            "target_selector": self.target_selector,
            "conditions": [x.to_data() for x in self.conditions],
            "priority": self.priority,
            "weight": self.weight,
            "tags": list(self.tags),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported AI decision rule")
        return cls(
            data["rule_id"],
            data["action_kind"],
            payload=data.get("payload", {}),
            target_selector=data.get("target_selector", "first_opponent"),
            conditions=[AICondition.from_data(x) for x in data.get("conditions", ())],
            priority=data.get("priority", 0),
            weight=data.get("weight", 1.0),
            tags=data.get("tags", ()),
        )


@dataclass(frozen=True, slots=True)
class BossPhaseDefinition:
    phase_id: str
    conditions: tuple[AICondition, ...] = ()
    priority: int = 0
    decision_rule_ids: tuple[str, ...] = ()
    actions_per_ready: int | None = None
    enter_hook: str | None = None
    exit_hook: str | None = None

    SCHEMA = "asteria.rpg.boss_phase_definition"
    VERSION = 1

    def __init__(
        self,
        phase_id,
        *,
        conditions=(),
        priority=0,
        decision_rule_ids=(),
        actions_per_ready=None,
        enter_hook=None,
        exit_hook=None,
    ):
        conditions = tuple(conditions)
        if any(not isinstance(x, AICondition) for x in conditions):
            raise TypeError("conditions must contain AICondition values")
        apr = None if actions_per_ready is None else int(actions_per_ready)
        if apr is not None and apr < 1:
            raise ValueError("actions_per_ready must be >= 1")
        object.__setattr__(self, "phase_id", _id(phase_id, "phase_id"))
        object.__setattr__(self, "conditions", conditions)
        object.__setattr__(self, "priority", int(priority))
        object.__setattr__(
            self,
            "decision_rule_ids",
            tuple(dict.fromkeys(_id(x, "decision_rule_id") for x in decision_rule_ids)),
        )
        object.__setattr__(self, "actions_per_ready", apr)
        object.__setattr__(
            self, "enter_hook", None if enter_hook is None else _id(enter_hook, "enter_hook")
        )
        object.__setattr__(
            self, "exit_hook", None if exit_hook is None else _id(exit_hook, "exit_hook")
        )

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "phase_id": self.phase_id,
            "conditions": [x.to_data() for x in self.conditions],
            "priority": self.priority,
            "decision_rule_ids": list(self.decision_rule_ids),
            "actions_per_ready": self.actions_per_ready,
            "enter_hook": self.enter_hook,
            "exit_hook": self.exit_hook,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported boss phase definition")
        return cls(
            data["phase_id"],
            conditions=[AICondition.from_data(x) for x in data.get("conditions", ())],
            priority=data.get("priority", 0),
            decision_rule_ids=data.get("decision_rule_ids", ()),
            actions_per_ready=data.get("actions_per_ready"),
            enter_hook=data.get("enter_hook"),
            exit_hook=data.get("exit_hook"),
        )


@dataclass(frozen=True, slots=True)
class EnemyAIDefinition:
    ai_id: str
    rules: tuple[AIDecisionRule, ...]
    phases: tuple[BossPhaseDefinition, ...] = ()
    initial_phase_id: str | None = None
    actions_per_ready: int = 1

    SCHEMA = "asteria.rpg.enemy_ai_definition"
    VERSION = 1

    def __init__(self, ai_id, *, rules, phases=(), initial_phase_id=None, actions_per_ready=1):
        rules = tuple(rules)
        phases = tuple(phases)
        apr = int(actions_per_ready)
        if not rules:
            raise ValueError("enemy AI requires at least one decision rule")
        if any(not isinstance(x, AIDecisionRule) for x in rules):
            raise TypeError("rules must contain AIDecisionRule values")
        if any(not isinstance(x, BossPhaseDefinition) for x in phases):
            raise TypeError("phases must contain BossPhaseDefinition values")
        if len({x.rule_id for x in rules}) != len(rules):
            raise ValueError("duplicate AI rule_id")
        if len({x.phase_id for x in phases}) != len(phases):
            raise ValueError("duplicate AI phase_id")
        if apr < 1:
            raise ValueError("actions_per_ready must be >= 1")
        phase_ids = {x.phase_id for x in phases}
        rule_ids = {x.rule_id for x in rules}
        if initial_phase_id is not None and str(initial_phase_id) not in phase_ids:
            raise ValueError("initial_phase_id must reference a phase")
        for phase in phases:
            unknown = set(phase.decision_rule_ids) - rule_ids
            if unknown:
                raise ValueError(
                    f"phase {phase.phase_id} references unknown rules: {sorted(unknown)}"
                )
        object.__setattr__(self, "ai_id", _id(ai_id, "ai_id"))
        object.__setattr__(self, "rules", rules)
        object.__setattr__(self, "phases", phases)
        object.__setattr__(
            self,
            "initial_phase_id",
            None if initial_phase_id is None else _id(initial_phase_id, "initial_phase_id"),
        )
        object.__setattr__(self, "actions_per_ready", apr)

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "ai_id": self.ai_id,
            "rules": [x.to_data() for x in self.rules],
            "phases": [x.to_data() for x in self.phases],
            "initial_phase_id": self.initial_phase_id,
            "actions_per_ready": self.actions_per_ready,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported enemy AI definition")
        return cls(
            data["ai_id"],
            rules=[AIDecisionRule.from_data(x) for x in data["rules"]],
            phases=[BossPhaseDefinition.from_data(x) for x in data.get("phases", ())],
            initial_phase_id=data.get("initial_phase_id"),
            actions_per_ready=data.get("actions_per_ready", 1),
        )


@dataclass(frozen=True, slots=True)
class AIDecision:
    ai_id: str
    actor_id: str
    rule_id: str
    action_kind: str
    payload: dict[str, object]
    target_ids: tuple[str, ...]
    phase_id: str | None
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AIExplanation:
    phase_id: str | None
    eligible_rule_ids: tuple[str, ...]
    chances: tuple[tuple[str, float], ...]  # (rule_id, probability) among the top-priority rules


class EnemyAIRuntime:
    """Seedable generic decision engine with open condition/target/action seams."""

    def __init__(
        self,
        definitions=(),
        *,
        hooks=None,
        condition_resolvers=None,
        target_resolvers=None,
        action_handlers=None,
    ):
        self.definitions = {}
        for d in definitions:
            if not isinstance(d, EnemyAIDefinition):
                raise TypeError("definitions must contain EnemyAIDefinition values")
            if d.ai_id in self.definitions:
                raise ValueError(f"duplicate enemy AI: {d.ai_id}")
            self.definitions[d.ai_id] = d
        self.hooks = hooks
        self.condition_resolvers = dict(condition_resolvers or {})
        self.target_resolvers = dict(target_resolvers or {})
        self.action_handlers = dict(action_handlers or {})
        self.memory = {}
        self.phases = {}

    def set_memory(self, actor_id, key, value):
        self.memory.setdefault(str(actor_id), {})[_id(key, "memory key")] = value

    def get_memory(self, actor_id, key, default=None):
        return self.memory.get(str(actor_id), {}).get(str(key), default)

    @staticmethod
    def _amount(battle, actor_id, resource_id):
        """Current amount; combat resources (rage, stagger...) live in the battle layer, others on
        the subject."""
        layer = getattr(battle, "battle_resources", None)
        if layer is not None and resource_id in layer.values.get(str(actor_id), {}):
            return layer.current(actor_id, resource_id)
        return battle.member(actor_id).subject.resources.get(resource_id).current

    def _ratio(self, member, resource_id):
        rv = member.subject.resources.get(str(resource_id))
        return 0.0 if rv.maximum == 0 else rv.current / rv.maximum

    @staticmethod
    def _compare(lhs, op, rhs):
        if op == "<":
            return lhs < rhs
        if op == "<=":
            return lhs <= rhs
        if op == ">":
            return lhs > rhs
        if op == ">=":
            return lhs >= rhs
        if op == "==":
            return lhs == rhs
        if op == "!=":
            return lhs != rhs
        raise KeyError(f"unknown comparison: {op}")

    def _condition(self, battle, actor_id, condition, phase_id):
        p = condition.params
        kind = condition.kind
        custom = self.condition_resolvers.get(kind)
        if custom is not None:
            value = bool(custom(battle, actor_id, p, self))
        elif kind == "always":
            value = True
        elif kind == "round_index":
            value = self._compare(
                battle.turn_queue.round_index, p.get("op", ">="), int(p.get("value", 0))
            )
        elif kind == "resource":
            value = self._compare(
                self._amount(battle, actor_id, str(p["resource_id"])),
                p.get("op", ">="),
                float(p["value"]),
            )
        elif kind == "resource_ratio":
            value = self._compare(
                self._ratio(battle.member(actor_id), p["resource_id"]),
                p.get("op", "<="),
                float(p["value"]),
            )
        elif kind == "stat":
            value = self._compare(
                battle.member(actor_id).subject.stats.value(p["stat_id"]),
                p.get("op", ">="),
                float(p["value"]),
            )
        elif kind == "memory":
            value = self._compare(
                self.get_memory(actor_id, p["key"]), p.get("op", "=="), p.get("value")
            )
        elif kind == "phase":
            value = self._compare(phase_id, p.get("op", "=="), p.get("value"))
        elif kind == "can_act":
            value = battle.can_act(actor_id)
        else:
            raise KeyError(f"unknown AI condition kind: {kind}")
        return not value if condition.negate else value

    def _conditions(self, battle, actor_id, conditions, phase_id):
        return all(self._condition(battle, actor_id, x, phase_id) for x in conditions)

    def _pick_phase(self, definition, battle, actor_id, current):
        eligible = [
            p
            for p in definition.phases
            if self._conditions(battle, actor_id, p.conditions, current)
        ]
        if eligible:
            return sorted(eligible, key=lambda x: (-x.priority, x.phase_id))[0].phase_id
        return current

    def _select_phase(self, definition, battle, actor_id):
        current = self.phases.get(actor_id, definition.initial_phase_id)
        selected = self._pick_phase(definition, battle, actor_id, current)
        if selected != current:
            old = next((p for p in definition.phases if p.phase_id == current), None)
            new = next((p for p in definition.phases if p.phase_id == selected), None)
            if old and old.exit_hook:
                emit_hook(
                    self.hooks,
                    old.exit_hook,
                    source=actor_id,
                    data={"battle": battle, "ai_id": definition.ai_id, "phase_id": old.phase_id},
                )
            emit_hook(
                self.hooks,
                "rpg.battle.ai.phase_changed",
                source=actor_id,
                data={
                    "battle": battle,
                    "ai_id": definition.ai_id,
                    "old_phase_id": current,
                    "phase_id": selected,
                },
            )
            if new and new.enter_hook:
                emit_hook(
                    self.hooks,
                    new.enter_hook,
                    source=actor_id,
                    data={"battle": battle, "ai_id": definition.ai_id, "phase_id": new.phase_id},
                )
        self.phases[actor_id] = selected
        return selected

    def _targets(self, battle, actor_id, selector, rng):
        custom = self.target_resolvers.get(selector)
        if custom is not None:
            return tuple(custom(battle, actor_id, self, rng))
        actor = battle.member(actor_id)
        present = [
            m for m in battle.members.values() if battle.combatants.state(m.member_id).present
        ]
        opponents = sorted(  # still standing: a knocked-out opponent is not a target
            (
                m
                for m in present
                if m.side != actor.side
                and battle.combatants.is_targetable(m.member_id)
                and battle.is_active(m)
            ),
            key=lambda x: x.member_id,
        )
        allies = sorted(
            (
                m
                for m in present
                if m.side == actor.side and battle.combatants.is_targetable(m.member_id)
            ),
            key=lambda x: x.member_id,
        )
        if selector == "self":
            return (actor_id,)
        if selector == "first_opponent":
            return tuple(x.member_id for x in opponents[:1])
        if selector == "all_opponents":
            return tuple(x.member_id for x in opponents)
        if selector == "first_ally":
            return tuple(x.member_id for x in allies[:1])
        if selector == "random_opponent":
            return () if not opponents else (rng.choice(opponents).member_id,)
        if selector.startswith("lowest_resource_ratio:"):
            rid = selector.split(":", 1)[1]
            candidates = allies if allies else []
            if not candidates:
                return ()
            chosen = min(candidates, key=lambda x: (self._ratio(x, rid), x.member_id))
            return (chosen.member_id,)
        raise KeyError(f"unknown AI target selector: {selector}")

    def _eligible_rules(self, definition, battle, actor_id, phase_id):
        phase = next((x for x in definition.phases if x.phase_id == phase_id), None)
        allowed_ids = set(phase.decision_rule_ids) if phase and phase.decision_rule_ids else None
        return [
            r
            for r in definition.rules
            if (allowed_ids is None or r.rule_id in allowed_ids)
            and self._conditions(battle, actor_id, r.conditions, phase_id)
        ]

    @staticmethod
    def _pool(eligible):
        if not eligible:
            return []
        best_priority = max(x.priority for x in eligible)
        return sorted(
            (x for x in eligible if x.priority == best_priority and x.weight > 0),
            key=lambda x: x.rule_id,
        )

    def explain(self, battle, ai_id, actor_id):
        """What ``decide`` would do now, without side effects: phase, eligible rules, pick chances.

        Used by the AI editor preview so it shows exactly the runtime's selection logic.
        """
        definition = self.definitions[str(ai_id)]
        actor_id = str(actor_id)
        current = self.phases.get(actor_id, definition.initial_phase_id)
        phase_id = self._pick_phase(definition, battle, actor_id, current)
        eligible = self._eligible_rules(definition, battle, actor_id, phase_id)
        pool = self._pool(eligible)
        total = sum(x.weight for x in pool)
        return AIExplanation(
            phase_id,
            tuple(x.rule_id for x in eligible),
            tuple((x.rule_id, x.weight / total) for x in pool) if total else (),
        )

    def decide(self, battle, ai_id, actor_id, *, rng=None):
        definition = self.definitions[str(ai_id)]
        actor_id = str(actor_id)
        rng = rng or random.Random()
        phase_id = self._select_phase(definition, battle, actor_id)
        eligible = self._eligible_rules(definition, battle, actor_id, phase_id)
        if not eligible:
            emit_hook(
                self.hooks,
                "rpg.battle.ai.no_decision",
                source=actor_id,
                data={"battle": battle, "ai_id": ai_id, "phase_id": phase_id},
            )
            return None
        pool = self._pool(eligible)
        if not pool:
            return None
        total = sum(x.weight for x in pool)
        roll = rng.random() * total
        acc = 0.0
        selected = pool[-1]
        for rule in pool:
            acc += rule.weight
            if roll < acc:
                selected = rule
                break
        targets = self._targets(battle, actor_id, selected.target_selector, rng)
        decision = AIDecision(
            definition.ai_id,
            actor_id,
            selected.rule_id,
            selected.action_kind,
            dict(selected.payload),
            targets,
            phase_id,
            selected.tags,
        )
        emit_hook(
            self.hooks,
            "rpg.battle.ai.decision",
            source=actor_id,
            data={"battle": battle, "decision": decision},
        )
        return decision

    def actions_per_ready(self, ai_id, actor_id):
        definition = self.definitions[str(ai_id)]
        phase_id = self.phases.get(str(actor_id), definition.initial_phase_id)
        phase = next((x for x in definition.phases if x.phase_id == phase_id), None)
        return (
            phase.actions_per_ready
            if phase and phase.actions_per_ready is not None
            else definition.actions_per_ready
        )

    def execute_decision(self, battle, decision, *, rng=None):
        from .battle import BattleAction

        if decision.action_kind == "ability":
            ability_id = _id(decision.payload.get("ability_id"), "ability_id")
            result = battle.execute_with_reactions(
                BattleAction(decision.actor_id, ability_id, decision.target_ids),
                rng=rng,
                tags=decision.tags,
            )
        elif decision.action_kind == "hook":
            hook_name = _id(decision.payload.get("hook"), "hook")
            emit_hook(
                self.hooks,
                hook_name,
                source=decision.actor_id,
                data={"battle": battle, "decision": decision, "payload": dict(decision.payload)},
            )
            result = None
        else:
            handler = self.action_handlers.get(decision.action_kind)
            if handler is None:
                raise KeyError(f"unknown AI action kind: {decision.action_kind}")
            result = handler(battle, decision, rng)
        self.set_memory(decision.actor_id, "last_rule_id", decision.rule_id)
        self.set_memory(
            decision.actor_id,
            "action_count",
            int(self.get_memory(decision.actor_id, "action_count", 0)) + 1,
        )
        emit_hook(
            self.hooks,
            "rpg.battle.ai.action_executed",
            source=decision.actor_id,
            data={"battle": battle, "decision": decision, "result": result},
        )
        return result

    def run_ready(self, battle, ai_id, actor_id, *, rng=None):
        rng = rng or random.Random()
        results = []
        count = self.actions_per_ready(ai_id, actor_id)
        for index in range(count):
            if not battle.can_act(actor_id):
                break
            decision = self.decide(battle, ai_id, actor_id, rng=rng)
            if decision is None:
                break
            result = self.execute_decision(battle, decision, rng=rng)
            results.append((decision, result))
            emit_hook(
                self.hooks,
                "rpg.battle.ai.multi_action_step",
                source=actor_id,
                data={"battle": battle, "index": index, "count": count, "decision": decision},
            )
        return tuple(results)

    def to_data(self):
        return {
            "schema": "asteria.rpg.enemy_ai_runtime",
            "version": 1,
            "memory": {k: dict(v) for k, v in sorted(self.memory.items())},
            "phases": dict(sorted(self.phases.items())),
        }

    def restore_data(self, data):
        if data.get("schema") != "asteria.rpg.enemy_ai_runtime" or data.get("version") != 1:
            raise ValueError("unsupported enemy AI runtime")
        self.memory = {str(k): dict(v) for k, v in data.get("memory", {}).items()}
        self.phases = {
            str(k): (None if v is None else str(v)) for k, v in data.get("phases", {}).items()
        }
        return self
