"""Enemy AI / boss phase editor API (EDT-07).

Granular, undoable edits of ``EnemyAIDefinition`` records — decision rules,
their conditions, boss phases, phase rule sets, actions per turn, the enemy
binding — through ``RpgEnemyEncounterAuthoringController`` (so its ability
validation and the shared command stack apply). The GUI and scripts use the
same calls. ``preview`` runs ``EnemyAIRuntime.explain`` — the battle's own
selection logic — against an editable scenario instead of a live battle.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import SimpleNamespace

from asteria.rpg.enemy_ai import (
    ACTION_KINDS,
    COMPARISONS,
    CONDITION_KINDS,
    CONDITION_PARAMS,
    TARGET_SELECTOR_PREFIXES,
    TARGET_SELECTORS,
    AICondition,
    AIDecisionRule,
    BossPhaseDefinition,
    EnemyAIDefinition,
    EnemyAIRuntime,
)

from .rpg_enemy_encounter_authoring import RpgEnemyEncounterAuthoringController


class EnemyAIEditorError(ValueError):
    pass


@dataclass(slots=True)
class AIScenario:
    """Battle state the preview evaluates the AI against."""

    round_index: int = 1
    resource_ratios: dict = field(default_factory=dict)  # resource_id -> 0..1 of its maximum
    resource_values: dict = field(default_factory=dict)  # resource_id -> current amount (overrides the ratio)
    resource_maxima: dict = field(default_factory=dict)  # resource_id -> maximum (default 100)
    stats: dict = field(default_factory=dict)
    memory: dict = field(default_factory=dict)
    can_act: bool = True
    phase_id: str | None = None  # current phase before this turn (None = the AI's initial phase)


class _Resource:
    def __init__(self, scenario, resource_id):
        self.maximum = float(scenario.resource_maxima.get(resource_id, 100.0))
        if resource_id in scenario.resource_values:
            self.current = float(scenario.resource_values[resource_id])
        else:
            self.current = float(scenario.resource_ratios.get(resource_id, 1.0)) * self.maximum


class _ScenarioBattle:
    def __init__(self, scenario):
        self.turn_queue = SimpleNamespace(round_index=int(scenario.round_index))
        resources = SimpleNamespace(get=lambda rid: _Resource(scenario, rid))
        stats = SimpleNamespace(value=lambda sid: float(scenario.stats.get(sid, 0.0)))
        self._member = SimpleNamespace(subject=SimpleNamespace(resources=resources, stats=stats))
        self._can_act = bool(scenario.can_act)

    def member(self, _member_id):
        return self._member

    def can_act(self, _member_id):
        return self._can_act


def condition(kind, *, negate=False, **params):
    """Build an ``AICondition`` with editor checks for the built-in kinds."""
    kind = str(kind)
    if kind in CONDITION_PARAMS:
        if params.get("op") is not None and params["op"] not in COMPARISONS:
            raise EnemyAIEditorError(f"comparison must be one of {COMPARISONS}")
        missing = [p for p in CONDITION_PARAMS[kind] if p != "op" and params.get(p) in (None, "")]
        if missing:
            raise EnemyAIEditorError(f"{kind} needs {', '.join(missing)}")
        if kind == "round_index":
            params["value"] = int(params["value"])
        elif kind in ("resource", "resource_ratio", "stat"):
            params["value"] = float(params["value"])
            if kind == "resource_ratio" and not 0.0 <= params["value"] <= 1.0:
                raise EnemyAIEditorError("resource ratio must be between 0 and 1")
    return AICondition(kind, params={k: v for k, v in params.items() if v is not None}, negate=negate)


def _conditions(values):
    result = []
    for value in values or ():
        if isinstance(value, AICondition):
            result.append(value)
        else:
            data = dict(value)
            result.append(condition(data.pop("kind"), negate=data.pop("negate", False), **data.pop("params", data)))
    return tuple(result)


class EnemyAIEditor:
    def __init__(self, document):
        self.document = document
        self.encounters = RpgEnemyEncounterAuthoringController(document)

    # -- lookup ---------------------------------------------------------------------
    @property
    def database(self):
        if self.document.project is None:
            raise EnemyAIEditorError("project required")
        return self.document.project.rpg_database

    def ai_ids(self):
        return tuple(sorted(self.database.enemy_ai))

    def get(self, ai_id):
        value = self.database.enemy_ai.get(str(ai_id))
        if value is None:
            raise EnemyAIEditorError(f"unknown enemy AI {ai_id}")
        return value

    def rule(self, ai_id, rule_id):
        found = next((r for r in self.get(ai_id).rules if r.rule_id == rule_id), None)
        if found is None:
            raise EnemyAIEditorError(f"{ai_id} has no rule {rule_id}")
        return found

    def phase(self, ai_id, phase_id):
        found = next((p for p in self.get(ai_id).phases if p.phase_id == phase_id), None)
        if found is None:
            raise EnemyAIEditorError(f"{ai_id} has no phase {phase_id}")
        return found

    def abilities(self):
        return tuple(sorted(self.document.project.gameplay_library.abilities.ids()))

    def bound_enemies(self, ai_id):
        return tuple(sorted(b.enemy_id for b in self.database.enemy_behavior_bindings.values() if b.ai_id == ai_id))

    def resources(self, ai_id):
        """Resource ids of the enemies using this AI (for resource_ratio conditions and preview sliders)."""
        ids = set()
        for enemy_id in self.bound_enemies(ai_id):
            ids.update(self.database.enemies[enemy_id].resources)
        return tuple(sorted(ids or {"vitality"}))

    def resource_maximum(self, ai_id, resource_id):
        """Battle-resource maximum if the project defines one, else the largest bound enemy's value."""
        battle_resource = self.database.battle_resources.get(resource_id)
        if battle_resource is not None and battle_resource.maximum is not None:
            return float(battle_resource.maximum)
        values = [self.database.enemies[e].resources.get(resource_id, 0) for e in self.bound_enemies(ai_id)]
        return float(max(values, default=0) or 100.0)

    # -- whole records ----------------------------------------------------------------
    def _replace(self, ai_id, **changes):
        old = self.get(ai_id)
        values = {
            "rules": old.rules,
            "phases": old.phases,
            "initial_phase_id": old.initial_phase_id,
            "actions_per_ready": old.actions_per_ready,
        }
        values.update(changes)
        try:
            value = EnemyAIDefinition(old.ai_id, **values)
        except (TypeError, ValueError) as exc:
            raise EnemyAIEditorError(str(exc)) from exc
        return self.encounters.edit_ai(old.ai_id, value)

    def create(self, ai_id, *, ability_id=None):
        ability_id = ability_id or (self.abilities()[0] if self.abilities() else None)
        if ability_id is None:
            raise EnemyAIEditorError("define an ability first — an AI needs one rule")
        rule = AIDecisionRule("basic_attack", "ability", payload={"ability_id": ability_id})
        return self.encounters.create_ai(EnemyAIDefinition(str(ai_id), rules=(rule,)))

    def delete(self, ai_id):
        return self.encounters.delete_ai(ai_id)

    def set_actions_per_ready(self, ai_id, count):
        return self._replace(ai_id, actions_per_ready=int(count))

    def set_initial_phase(self, ai_id, phase_id):
        return self._replace(ai_id, initial_phase_id=phase_id or None)

    def bind(self, enemy_id, ai_id):
        return self.encounters.bind_enemy_ai(enemy_id, ai_id)

    def unbind(self, enemy_id):
        return self.encounters.unbind_enemy_ai(enemy_id)

    # -- rules ------------------------------------------------------------------------
    @staticmethod
    def _payload(action_kind, ability_id, hook, payload):
        payload = dict(payload or {})
        if action_kind == "ability":
            payload = {k: v for k, v in payload.items() if k != "hook"}
            if ability_id is not None:
                payload["ability_id"] = str(ability_id)
            if not payload.get("ability_id"):
                raise EnemyAIEditorError("an ability rule needs ability_id")
        elif action_kind == "hook":
            payload = {k: v for k, v in payload.items() if k != "ability_id"}
            if hook is not None:
                payload["hook"] = str(hook)
            if not payload.get("hook"):
                raise EnemyAIEditorError("a hook rule needs a hook name")
        return payload

    @staticmethod
    def _check_selector(selector):
        if selector not in TARGET_SELECTORS and not any(selector.startswith(p) for p in TARGET_SELECTOR_PREFIXES):
            raise EnemyAIEditorError(f"unknown target selector {selector}")

    def add_rule(
        self,
        ai_id,
        rule_id,
        *,
        action_kind="ability",
        ability_id=None,
        hook=None,
        target_selector="first_opponent",
        priority=0,
        weight=1.0,
        tags=(),
        conditions=(),
    ):
        ai = self.get(ai_id)
        if any(r.rule_id == rule_id for r in ai.rules):
            raise EnemyAIEditorError(f"{ai_id} already has rule {rule_id}")
        self._check_selector(target_selector)
        rule = AIDecisionRule(
            rule_id,
            action_kind,
            payload=self._payload(action_kind, ability_id, hook, None),
            target_selector=target_selector,
            conditions=_conditions(conditions),
            priority=priority,
            weight=weight,
            tags=tags,
        )
        return self._replace(ai_id, rules=(*ai.rules, rule))

    def edit_rule(self, ai_id, rule_id, **changes):
        old = self.rule(ai_id, rule_id)
        action_kind = changes.pop("action_kind", old.action_kind)
        selector = changes.pop("target_selector", old.target_selector)
        self._check_selector(selector)
        payload = self._payload(action_kind, changes.pop("ability_id", None), changes.pop("hook", None), old.payload)
        unknown = set(changes) - {"priority", "weight", "tags", "conditions"}
        if unknown:
            raise EnemyAIEditorError(f"unknown rule fields: {sorted(unknown)}")
        rule = AIDecisionRule(
            rule_id,
            action_kind,
            payload=payload,
            target_selector=selector,
            conditions=_conditions(changes["conditions"]) if "conditions" in changes else old.conditions,
            priority=changes.get("priority", old.priority),
            weight=changes.get("weight", old.weight),
            tags=changes.get("tags", old.tags),
        )
        ai = self.get(ai_id)
        return self._replace(ai_id, rules=tuple(rule if r.rule_id == rule_id else r for r in ai.rules))

    def remove_rule(self, ai_id, rule_id):
        ai = self.get(ai_id)
        self.rule(ai_id, rule_id)
        if len(ai.rules) == 1:
            raise EnemyAIEditorError("an AI needs at least one rule")
        phases = tuple(
            _rebuild_phase(p, decision_rule_ids=tuple(x for x in p.decision_rule_ids if x != rule_id))
            for p in ai.phases
        )
        return self._replace(ai_id, rules=tuple(r for r in ai.rules if r.rule_id != rule_id), phases=phases)

    # -- phases -----------------------------------------------------------------------
    def add_phase(self, ai_id, phase_id, *, priority=0, rule_ids=(), actions_per_ready=None, conditions=()):
        ai = self.get(ai_id)
        if any(p.phase_id == phase_id for p in ai.phases):
            raise EnemyAIEditorError(f"{ai_id} already has phase {phase_id}")
        phase = BossPhaseDefinition(
            phase_id,
            conditions=_conditions(conditions),
            priority=priority,
            decision_rule_ids=rule_ids,
            actions_per_ready=actions_per_ready,
        )
        initial = ai.initial_phase_id or (phase_id if not ai.phases else None)
        return self._replace(ai_id, phases=(*ai.phases, phase), initial_phase_id=initial)

    def edit_phase(self, ai_id, phase_id, **changes):
        old = self.phase(ai_id, phase_id)
        allowed = {"priority", "rule_ids", "actions_per_ready", "conditions", "enter_hook", "exit_hook"}
        unknown = set(changes) - allowed
        if unknown:
            raise EnemyAIEditorError(f"unknown phase fields: {sorted(unknown)}")
        if "rule_ids" in changes:
            changes["decision_rule_ids"] = tuple(changes.pop("rule_ids"))
        if "conditions" in changes:
            changes["conditions"] = _conditions(changes["conditions"])
        for hook in ("enter_hook", "exit_hook"):
            if hook in changes and not changes[hook]:
                changes[hook] = None
        phase = _rebuild_phase(old, **changes)
        ai = self.get(ai_id)
        return self._replace(ai_id, phases=tuple(phase if p.phase_id == phase_id else p for p in ai.phases))

    def remove_phase(self, ai_id, phase_id):
        ai = self.get(ai_id)
        self.phase(ai_id, phase_id)
        phases = tuple(p for p in ai.phases if p.phase_id != phase_id)
        initial = ai.initial_phase_id if ai.initial_phase_id != phase_id else (phases[0].phase_id if phases else None)
        return self._replace(ai_id, phases=phases, initial_phase_id=initial)

    # -- conditions on a rule or phase --------------------------------------------------
    def _owner(self, ai_id, owner):
        kind, owner_id = owner
        if kind == "rule":
            return self.rule(ai_id, owner_id), lambda c: self.edit_rule(ai_id, owner_id, conditions=c)
        if kind == "phase":
            return self.phase(ai_id, owner_id), lambda c: self.edit_phase(ai_id, owner_id, conditions=c)
        raise EnemyAIEditorError("owner must be ('rule', id) or ('phase', id)")

    def add_condition(self, ai_id, owner, kind, *, negate=False, **params):
        item, save = self._owner(ai_id, owner)
        return save((*item.conditions, condition(kind, negate=negate, **params)))

    def replace_condition(self, ai_id, owner, index, kind, *, negate=False, **params):
        item, save = self._owner(ai_id, owner)
        values = list(item.conditions)
        values[int(index)] = condition(kind, negate=negate, **params)
        return save(tuple(values))

    def remove_condition(self, ai_id, owner, index):
        item, save = self._owner(ai_id, owner)
        values = list(item.conditions)
        del values[int(index)]
        return save(tuple(values))

    # -- checks and preview -----------------------------------------------------------
    def problems(self, ai_id):
        ai = self.get(ai_id)
        found = []
        abilities = set(self.abilities())
        for rule in ai.rules:
            where = f"rule {rule.rule_id}"
            if rule.action_kind not in ACTION_KINDS:
                found.append(f"{where}: action {rule.action_kind} needs a project action handler")
            if rule.action_kind == "ability" and rule.payload.get("ability_id") not in abilities:
                found.append(f"{where}: unknown ability {rule.payload.get('ability_id')}")
            try:
                self._check_selector(rule.target_selector)
            except EnemyAIEditorError:
                found.append(f"{where}: target {rule.target_selector} needs a project target resolver")
            found.extend(_condition_problems(where, rule.conditions))
        for phase in ai.phases:
            found.extend(_condition_problems(f"phase {phase.phase_id}", phase.conditions))
        if ai.phases and ai.initial_phase_id is None:
            found.append("boss phases defined but no initial phase")
        if not self.bound_enemies(ai_id):
            found.append("not used by any enemy")
        if all(r.weight == 0 for r in ai.rules):
            found.append("every rule has weight 0, so the AI never acts")
        return found

    def preview(self, ai_id, scenario=None):
        scenario = scenario or AIScenario()
        runtime = EnemyAIRuntime((self.get(ai_id),))
        if scenario.phase_id is not None:
            runtime.phases["preview"] = scenario.phase_id
        for key, value in scenario.memory.items():
            runtime.set_memory("preview", key, value)
        try:
            return runtime.explain(_ScenarioBattle(scenario), ai_id, "preview")
        except KeyError as exc:
            raise EnemyAIEditorError(f"preview needs a project resolver: {exc}") from exc

    def phase_by_ratio(self, ai_id, resource_id="vitality", steps=10, scenario=None):
        """[(ratio, phase_id)] from full to empty ``resource_id`` — how a boss moves through its phases."""
        base = scenario or AIScenario()
        result = []
        phase_id = base.phase_id
        for step in range(int(steps), -1, -1):
            ratio = step / int(steps)
            ratios = {**base.resource_ratios, resource_id: ratio}
            values = {k: v for k, v in base.resource_values.items() if k != resource_id}  # the sweep sets it
            current = replace(base, resource_ratios=ratios, resource_values=values, phase_id=phase_id)
            phase_id = self.preview(ai_id, current).phase_id
            result.append((ratio, phase_id))
        return result


def _rebuild_phase(old, **changes):
    values = {
        "conditions": old.conditions,
        "priority": old.priority,
        "decision_rule_ids": old.decision_rule_ids,
        "actions_per_ready": old.actions_per_ready,
        "enter_hook": old.enter_hook,
        "exit_hook": old.exit_hook,
    }
    values.update(changes)
    try:
        return BossPhaseDefinition(old.phase_id, **values)
    except (TypeError, ValueError) as exc:
        raise EnemyAIEditorError(str(exc)) from exc


def _condition_problems(where, conditions):
    found = []
    for index, value in enumerate(conditions, start=1):
        if value.kind not in CONDITION_KINDS:
            found.append(f"{where} condition {index}: {value.kind} needs a project condition resolver")
        elif value.params.get("op", "==") not in COMPARISONS:
            found.append(f"{where} condition {index}: unknown comparison {value.params.get('op')}")
    return found
