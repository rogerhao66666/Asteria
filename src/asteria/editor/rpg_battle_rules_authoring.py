from __future__ import annotations
from dataclasses import dataclass

from asteria.rpg import (
    ActionSequenceDefinition,
    ActionTimingDefinition,
    ActionTransactionPolicy,
    BattleEscapeRule,
    BattleObjectiveDefinition,
    BattleResourceDefinition,
    BattleSchedulerDefinition,
    BattleSessionRules,
    BattleStatePolicy,
    BattleTargetingDefinition,
    GaugeCompositionDefinition,
    InteractionRule,
    OutcomeCheckDefinition,
    ReactionDefinition,
)


class RpgBattleRulesAuthoringError(RuntimeError):
    pass


@dataclass(slots=True)
class _MapCommand:
    mapping: dict
    key: str
    new_value: object | None
    old_value: object | None
    description: str

    @property
    def label(self):
        return self.description

    def redo(self):
        if self.new_value is None:
            self.mapping.pop(self.key, None)
        else:
            self.mapping[self.key] = self.new_value

    def undo(self):
        if self.old_value is None:
            self.mapping.pop(self.key, None)
        else:
            self.mapping[self.key] = self.old_value


@dataclass(frozen=True, slots=True)
class BattleRuleKind:
    kind_id: str
    label: str
    mapping_name: str
    definition_type: type
    key_attr: str
    detail_groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BattleRuleGroup:
    group_id: str
    label: str
    kind_ids: tuple[str, ...]


class BattleRulesInformationArchitecture:
    """Battle authoring hierarchy: mechanisms stay complete without one-screen sprawl."""

    def __init__(self):
        self.kinds = (
            BattleRuleKind(
                "resources",
                "Resources",
                "battle_resources",
                BattleResourceDefinition,
                "resource_id",
                ("Bounds", "Start / End Policy", "Rules"),
            ),
            BattleRuleKind(
                "states",
                "States / Status",
                "battle_state_policies",
                BattleStatePolicy,
                "state_id",
                ("Application", "Immunity", "Duration", "Ability Blocking", "Ticks"),
            ),
            BattleRuleKind(
                "interactions",
                "Interactions",
                "interaction_rules",
                InteractionRule,
                "rule_id",
                ("Source Conditions", "Target Conditions", "Value Resolution", "Outcome Tags", "Priority"),
            ),
            BattleRuleKind(
                "outcome_checks",
                "Outcome Checks",
                "outcome_checks",
                OutcomeCheckDefinition,
                "check_id",
                ("Base Chance", "Stat Terms", "Tag Conditions", "Success / Failure"),
            ),
            BattleRuleKind(
                "targeting",
                "Targeting",
                "battle_targeting",
                BattleTargetingDefinition,
                "ability_id",
                ("Relation", "Selection", "Target Count", "Tags", "Metrics", "Adjacency"),
            ),
            BattleRuleKind(
                "schedulers",
                "Schedulers",
                "battle_schedulers",
                BattleSchedulerDefinition,
                "scheduler_id",
                ("Mode", "Timeline", "Ready Policy"),
            ),
            BattleRuleKind(
                "timing",
                "Action Timing",
                "action_timings",
                ActionTimingDefinition,
                "ability_id",
                ("Startup", "Cast / Recovery", "Interruptibility", "Priority"),
            ),
            BattleRuleKind(
                "sequences",
                "Action Sequences",
                "action_sequences",
                ActionSequenceDefinition,
                "sequence_id",
                ("Participants", "Steps", "Selected Step", "Target Policy", "Interruption"),
            ),
            BattleRuleKind(
                "gauges",
                "Gauge Composition",
                "gauge_compositions",
                GaugeCompositionDefinition,
                "composition_id",
                ("Impacts", "Selected Impact", "Thresholds", "Selected Threshold", "Consequences"),
            ),
            BattleRuleKind(
                "reactions",
                "Reactions",
                "reactions",
                ReactionDefinition,
                "reaction_id",
                ("Trigger", "Reactor / Target Selection", "Ability", "Tags", "Chain Policy"),
            ),
            BattleRuleKind(
                "objectives",
                "Objectives",
                "battle_objectives",
                BattleObjectiveDefinition,
                "objective_id",
                ("Success Conditions", "Failure Conditions", "Winning / Defeated Sides"),
            ),
            BattleRuleKind(
                "escape",
                "Escape Rules",
                "escape_rules",
                BattleEscapeRule,
                "rule_id",
                ("Side", "Base Chance", "Source Terms", "Opponent Terms", "Bounds"),
            ),
            BattleRuleKind(
                "transactions",
                "Action Transactions",
                "action_transactions",
                ActionTransactionPolicy,
                "ability_id",
                ("Cost Commit", "Interrupt Cost"),
            ),
            BattleRuleKind(
                "session",
                "Session Rules",
                "battle_session_rules",
                BattleSessionRules,
                "rules_id",
                ("Knockout", "Hit Trigger", "Boost"),
            ),
        )
        self.groups = (
            BattleRuleGroup(
                "combat_model", "Combat Model", ("resources", "states", "interactions", "outcome_checks", "targeting")
            ),
            BattleRuleGroup("turn_flow", "Turn Flow", ("schedulers", "timing")),
            BattleRuleGroup("action_logic", "Action Logic", ("sequences", "gauges", "reactions")),
            BattleRuleGroup("battle_flow", "Battle Flow", ("objectives", "escape", "session")),
            BattleRuleGroup("execution", "Execution / Costs", ("transactions",)),
        )
        self.primary_navigation = "rule_group_sidebar"
        self.secondary_navigation = "rule_kind_tabs"
        self.browser_pattern = "search_filter_list"
        self.inspector_pattern = "contextual_detail"
        self.progressive_disclosure = True
        self.show_all_rule_kinds_simultaneously = False
        self.show_all_details_simultaneously = False

    def kind(self, kind_id):
        return next((x for x in self.kinds if x.kind_id == str(kind_id)), None)

    def group(self, group_id):
        return next((x for x in self.groups if x.group_id == str(group_id)), None)


class RpgBattleRulesAuthoringController:
    information_architecture = BattleRulesInformationArchitecture()

    def __init__(self, document):
        self.document = document

    @property
    def project(self):
        if self.document.project is None:
            raise RpgBattleRulesAuthoringError("project required")
        return self.document.project

    @property
    def database(self):
        return self.project.rpg_database

    def _execute(self, c):
        self.document.execute(c)
        return c

    def _kind(self, kind_id):
        kind = self.information_architecture.kind(kind_id)
        if kind is None:
            raise KeyError(f"unknown battle rule kind: {kind_id}")
        return kind

    def _mapping(self, kind):
        return getattr(self.database, kind.mapping_name)

    def _coerce(self, kind, value):
        if isinstance(value, kind.definition_type):
            return value
        if isinstance(value, dict):
            return kind.definition_type.from_data(value)
        raise TypeError(f"value must be {kind.definition_type.__name__} or serialized data")

    def _validate_refs(self, kind, value):
        abilities = set(self.project.gameplay_library.abilities.ids())
        missing = []
        if kind.kind_id in {"targeting", "timing", "transactions"}:
            if value.ability_id not in abilities:
                missing.append(value.ability_id)
        elif kind.kind_id == "sequences":
            missing.extend(x.ability_id for x in value.steps if x.ability_id not in abilities)
        elif kind.kind_id == "reactions":
            if value.ability_id is not None and value.ability_id not in abilities:
                missing.append(value.ability_id)
        if missing:
            raise RpgBattleRulesAuthoringError("unknown abilities: " + ", ".join(sorted(set(missing))))
        if kind.kind_id == "session" and value.boost_resource_id:
            if value.boost_resource_id not in self.database.battle_resources:
                raise RpgBattleRulesAuthoringError(f"unknown battle resources: {value.boost_resource_id}")
        if kind.kind_id == "gauges":
            resources = set(self.database.battle_resources)
            states = set(self.database.battle_state_policies)
            missing_resources = sorted(
                {x.resource_id for x in (*value.impacts, *value.thresholds) if x.resource_id not in resources}
            )
            if missing_resources:
                raise RpgBattleRulesAuthoringError("unknown battle resources: " + ", ".join(missing_resources))
            missing_states = sorted(
                {x.state_id for x in value.thresholds if x.state_id is not None and x.state_id not in states}
            )
            if missing_states:
                raise RpgBattleRulesAuthoringError("unknown battle states: " + ", ".join(missing_states))

    def create(self, kind_id, value):
        kind = self._kind(kind_id)
        value = self._coerce(kind, value)
        key = str(getattr(value, kind.key_attr))
        mapping = self._mapping(kind)
        if key in mapping:
            raise RpgBattleRulesAuthoringError(f"duplicate {kind.label}: {key}")
        self._validate_refs(kind, value)
        self._execute(_MapCommand(mapping, key, value, None, f"Add {kind.label} {key}"))
        return value

    def edit(self, kind_id, key, value):
        kind = self._kind(kind_id)
        key = str(key)
        mapping = self._mapping(kind)
        old = mapping.get(key)
        if old is None:
            raise RpgBattleRulesAuthoringError(f"unknown {kind.label}: {key}")
        value = self._coerce(kind, value)
        new_key = str(getattr(value, kind.key_attr))
        if new_key != key:
            raise RpgBattleRulesAuthoringError(f"{kind.label} key cannot change during edit")
        self._validate_refs(kind, value)
        self._execute(_MapCommand(mapping, key, value, old, f"Edit {kind.label} {key}"))
        return value

    def delete(self, kind_id, key):
        kind = self._kind(kind_id)
        key = str(key)
        mapping = self._mapping(kind)
        old = mapping.get(key)
        if old is None:
            raise RpgBattleRulesAuthoringError(f"unknown {kind.label}: {key}")
        refs = self._delete_references(kind.kind_id, key)
        if refs:
            raise RpgBattleRulesAuthoringError(f"{kind.label} {key} is referenced by " + ", ".join(sorted(refs)))
        self._execute(_MapCommand(mapping, key, None, old, f"Delete {kind.label} {key}"))

    def _delete_references(self, kind_id, key):
        refs = []
        if kind_id == "resources":
            for g in self.database.gauge_compositions.values():
                if any(x.resource_id == key for x in (*g.impacts, *g.thresholds)):
                    refs.append(f"gauge:{g.composition_id}")
        elif kind_id == "states":
            for g in self.database.gauge_compositions.values():
                if any(x.state_id == key for x in g.thresholds):
                    refs.append(f"gauge:{g.composition_id}")
        return refs

    def definitions(self, kind_id):
        kind = self._kind(kind_id)
        mapping = self._mapping(kind)
        return tuple(mapping[k] for k in sorted(mapping))

    def validate(self):
        try:
            self.project.validate()
            # Editor-level references not currently asserted by RpgDatabase.validate.
            for kind in self.information_architecture.kinds:
                for value in self._mapping(kind).values():
                    self._validate_refs(kind, value)
        except Exception as exc:
            return (str(exc),)
        return ()
