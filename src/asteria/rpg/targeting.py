from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from math import isfinite

from asteria.gameplay import GameplaySubject


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _tag_values(values):
    return tuple(sorted({_id(x, "tag") for x in values}))


class TargetRelation(str, Enum):
    SELF = "self"
    ALLY = "ally"
    OPPONENT = "opponent"
    ANY = "any"


class TargetSelectionMode(str, Enum):
    MANUAL = "manual"
    ALL = "all"
    RANDOM_N = "random_n"
    FIRST_N = "first_n"


@dataclass(frozen=True, slots=True)
class FormationSlotDefinition:
    slot_id: str
    x: float = 0.0
    y: float = 0.0
    tags: tuple[str, ...] = ()
    adjacent_to: tuple[str, ...] = ()

    def __init__(self, slot_id, *, x=0.0, y=0.0, tags=(), adjacent_to=()):
        x = float(x)
        y = float(y)
        if not isfinite(x) or not isfinite(y):
            raise ValueError("slot coordinates must be finite")
        object.__setattr__(self, "slot_id", _id(slot_id, "slot_id"))
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "tags", _tag_values(tags))
        object.__setattr__(
            self,
            "adjacent_to",
            tuple(sorted({_id(x, "adjacent slot_id") for x in adjacent_to})),
        )

    def to_data(self):
        return {
            "slot_id": self.slot_id,
            "x": self.x,
            "y": self.y,
            "tags": list(self.tags),
            "adjacent_to": list(self.adjacent_to),
        }

    @classmethod
    def from_data(cls, data):
        expected = {"slot_id", "x", "y", "tags", "adjacent_to"}
        if set(data) != expected:
            raise ValueError("invalid formation slot")
        return cls(**data)


@dataclass(frozen=True, slots=True)
class FormationDefinition:
    formation_id: str
    slots: tuple[FormationSlotDefinition, ...]

    def __init__(self, formation_id, slots=()):
        slots = tuple(slots)
        if any(not isinstance(x, FormationSlotDefinition) for x in slots):
            raise TypeError("slots must be FormationSlotDefinition values")
        ids = [x.slot_id for x in slots]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate formation slot")
        known = set(ids)
        for slot in slots:
            unknown = set(slot.adjacent_to) - known
            if unknown:
                raise ValueError(
                    f"formation slot {slot.slot_id} references unknown adjacent slots: "
                    + ", ".join(sorted(unknown))
                )
            if slot.slot_id in slot.adjacent_to:
                raise ValueError("formation slot cannot be adjacent to itself")
        object.__setattr__(self, "formation_id", _id(formation_id, "formation_id"))
        object.__setattr__(self, "slots", slots)

    def slot(self, slot_id):
        slot_id = str(slot_id)
        for slot in self.slots:
            if slot.slot_id == slot_id:
                return slot
        raise KeyError(slot_id)

    def to_data(self):
        return {
            "schema": "asteria.rpg.formation_definition",
            "version": 1,
            "formation_id": self.formation_id,
            "slots": [x.to_data() for x in self.slots],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.formation_definition" or data.get("version") != 1:
            raise ValueError("unsupported formation definition")
        expected = {"schema", "version", "formation_id", "slots"}
        if set(data) != expected:
            raise ValueError("invalid formation definition")
        return cls(
            data["formation_id"], [FormationSlotDefinition.from_data(x) for x in data["slots"]]
        )


@dataclass(frozen=True, slots=True)
class BattlePlacement:
    member_id: str
    slot_id: str

    def __init__(self, member_id, slot_id):
        object.__setattr__(self, "member_id", _id(member_id, "member_id"))
        object.__setattr__(self, "slot_id", _id(slot_id, "slot_id"))


class BattleFormationRuntime:
    """Runtime placement over a project-defined logical formation.

    Slot tags carry semantics such as front/back/airborne/body-part if a game wants
    them. The engine only understands stable slot IDs and explicit adjacency.
    """

    def __init__(self, definition: FormationDefinition, placements=()):
        if not isinstance(definition, FormationDefinition):
            raise TypeError("definition must be FormationDefinition")
        self.definition = definition
        self._member_to_slot = {}
        self._slot_to_member = {}
        for placement in placements:
            self.place(placement.member_id, placement.slot_id)

    def place(self, member_id, slot_id):
        member_id = _id(member_id, "member_id")
        slot_id = _id(slot_id, "slot_id")
        self.definition.slot(slot_id)
        prior_member = self._slot_to_member.get(slot_id)
        if prior_member is not None and prior_member != member_id:
            raise ValueError(f"formation slot occupied: {slot_id}")
        prior_slot = self._member_to_slot.get(member_id)
        if prior_slot is not None:
            self._slot_to_member.pop(prior_slot, None)
        self._member_to_slot[member_id] = slot_id
        self._slot_to_member[slot_id] = member_id
        return BattlePlacement(member_id, slot_id)

    def remove(self, member_id):
        member_id = str(member_id)
        slot_id = self._member_to_slot.pop(member_id)
        self._slot_to_member.pop(slot_id, None)
        return BattlePlacement(member_id, slot_id)

    def slot_id_for(self, member_id):
        return self._member_to_slot.get(str(member_id))

    def slot_for(self, member_id):
        slot_id = self.slot_id_for(member_id)
        return None if slot_id is None else self.definition.slot(slot_id)

    def member_at(self, slot_id):
        return self._slot_to_member.get(str(slot_id))

    def adjacent_member_ids(self, member_id):
        slot = self.slot_for(member_id)
        if slot is None:
            return ()
        result = []
        for adjacent_slot in slot.adjacent_to:
            other = self.member_at(adjacent_slot)
            if other is not None:
                result.append(other)
        return tuple(sorted(result))

    def placements(self):
        return tuple(
            BattlePlacement(member_id, slot_id)
            for member_id, slot_id in sorted(self._member_to_slot.items())
        )

    def to_data(self):
        return {
            "schema": "asteria.rpg.battle_formation_runtime",
            "version": 1,
            "definition_id": self.definition.formation_id,
            "placements": [
                {"member_id": x.member_id, "slot_id": x.slot_id} for x in self.placements()
            ],
        }

    def restore_from_data(self, data):
        if (
            data.get("schema") != "asteria.rpg.battle_formation_runtime"
            or data.get("version") != 1
        ):
            raise ValueError("unsupported battle formation runtime")
        if data.get("definition_id") != self.definition.formation_id:
            raise ValueError("formation definition mismatch")
        self._member_to_slot = {}
        self._slot_to_member = {}
        for raw in data.get("placements", ()):
            self.place(raw["member_id"], raw["slot_id"])
        return self


@dataclass(frozen=True, slots=True)
class TargetMetricCondition:
    kind: str
    key: str
    operator: str
    value: float

    def __init__(self, kind, key, operator, value):
        kind = _id(kind, "kind")
        if kind not in {"stat", "resource", "resource_fraction"}:
            raise ValueError("target metric kind must be stat, resource, or resource_fraction")
        operator = str(operator).strip()
        if operator not in {"<", "<=", "==", ">=", ">"}:
            raise ValueError("unsupported target metric operator")
        value = float(value)
        if not isfinite(value):
            raise ValueError("target metric value must be finite")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "key", _id(key, "key"))
        object.__setattr__(self, "operator", operator)
        object.__setattr__(self, "value", value)

    def matches(self, subject: GameplaySubject):
        if self.kind == "stat":
            actual = subject.stats.get(self.key, 0.0)
        else:
            if not subject.resources.contains(self.key):
                return False
            resource = subject.resources.get(self.key)
            if self.kind == "resource":
                actual = resource.current
            else:
                actual = 0.0 if resource.maximum == 0 else resource.current / resource.maximum
        return {
            "<": actual < self.value,
            "<=": actual <= self.value,
            "==": actual == self.value,
            ">=": actual >= self.value,
            ">": actual > self.value,
        }[self.operator]

    def to_data(self):
        return {
            "kind": self.kind,
            "key": self.key,
            "operator": self.operator,
            "value": self.value,
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"kind", "key", "operator", "value"}:
            raise ValueError("invalid target metric condition")
        return cls(**data)


@dataclass(frozen=True, slots=True)
class BattleTargetingDefinition:
    ability_id: str
    relation: TargetRelation = TargetRelation.OPPONENT
    selection_mode: TargetSelectionMode = TargetSelectionMode.MANUAL
    minimum_targets: int = 1
    maximum_targets: int = 1
    selection_count: int | None = None
    required_subject_tags: tuple[str, ...] = ()
    blocked_subject_tags: tuple[str, ...] = ()
    required_slot_tags: tuple[str, ...] = ()
    blocked_slot_tags: tuple[str, ...] = ()
    metric_conditions: tuple[TargetMetricCondition, ...] = ()
    adjacent_to_actor: bool = False
    active_only: bool = True

    def __init__(
        self,
        ability_id,
        *,
        relation=TargetRelation.OPPONENT,
        selection_mode=TargetSelectionMode.MANUAL,
        minimum_targets=1,
        maximum_targets=1,
        selection_count=None,
        required_subject_tags=(),
        blocked_subject_tags=(),
        required_slot_tags=(),
        blocked_slot_tags=(),
        metric_conditions=(),
        adjacent_to_actor=False,
        active_only=True,
    ):
        relation = TargetRelation(relation)
        selection_mode = TargetSelectionMode(selection_mode)
        minimum_targets = int(minimum_targets)
        maximum_targets = int(maximum_targets)
        if minimum_targets < 0 or maximum_targets < minimum_targets:
            raise ValueError("invalid target count range")
        if selection_count is not None:
            selection_count = int(selection_count)
            if selection_count < 0:
                raise ValueError("selection_count must be >= 0")
        metric_conditions = tuple(metric_conditions)
        if any(not isinstance(x, TargetMetricCondition) for x in metric_conditions):
            raise TypeError("metric_conditions must be TargetMetricCondition values")
        object.__setattr__(self, "ability_id", _id(ability_id, "ability_id"))
        object.__setattr__(self, "relation", relation)
        object.__setattr__(self, "selection_mode", selection_mode)
        object.__setattr__(self, "minimum_targets", minimum_targets)
        object.__setattr__(self, "maximum_targets", maximum_targets)
        object.__setattr__(self, "selection_count", selection_count)
        object.__setattr__(self, "required_subject_tags", _tag_values(required_subject_tags))
        object.__setattr__(self, "blocked_subject_tags", _tag_values(blocked_subject_tags))
        object.__setattr__(self, "required_slot_tags", _tag_values(required_slot_tags))
        object.__setattr__(self, "blocked_slot_tags", _tag_values(blocked_slot_tags))
        object.__setattr__(self, "metric_conditions", metric_conditions)
        object.__setattr__(self, "adjacent_to_actor", bool(adjacent_to_actor))
        object.__setattr__(self, "active_only", bool(active_only))

    def to_data(self):
        return {
            "schema": "asteria.rpg.battle_targeting_definition",
            "version": 1,
            "ability_id": self.ability_id,
            "relation": self.relation.value,
            "selection_mode": self.selection_mode.value,
            "minimum_targets": self.minimum_targets,
            "maximum_targets": self.maximum_targets,
            "selection_count": self.selection_count,
            "required_subject_tags": list(self.required_subject_tags),
            "blocked_subject_tags": list(self.blocked_subject_tags),
            "required_slot_tags": list(self.required_slot_tags),
            "blocked_slot_tags": list(self.blocked_slot_tags),
            "metric_conditions": [x.to_data() for x in self.metric_conditions],
            "adjacent_to_actor": self.adjacent_to_actor,
            "active_only": self.active_only,
        }

    @classmethod
    def from_data(cls, data):
        if (
            data.get("schema") != "asteria.rpg.battle_targeting_definition"
            or data.get("version") != 1
        ):
            raise ValueError("unsupported battle targeting definition")
        return cls(
            data["ability_id"],
            relation=data["relation"],
            selection_mode=data["selection_mode"],
            minimum_targets=data["minimum_targets"],
            maximum_targets=data["maximum_targets"],
            selection_count=data["selection_count"],
            required_subject_tags=data["required_subject_tags"],
            blocked_subject_tags=data["blocked_subject_tags"],
            required_slot_tags=data["required_slot_tags"],
            blocked_slot_tags=data["blocked_slot_tags"],
            metric_conditions=[
                TargetMetricCondition.from_data(x) for x in data["metric_conditions"]
            ],
            adjacent_to_actor=data["adjacent_to_actor"],
            active_only=data["active_only"],
        )


@dataclass(frozen=True, slots=True)
class TargetResolution:
    ability_id: str
    actor_id: str
    candidate_ids: tuple[str, ...]
    selected_ids: tuple[str, ...]
    valid: bool
    errors: tuple[str, ...] = ()


class BattleTargetingRuntime:
    def __init__(
        self, members, *, definitions=(), formations=None, is_active=None, is_targetable=None
    ):
        self.members = dict(members)
        self.definitions = {}
        for definition in definitions:
            if not isinstance(definition, BattleTargetingDefinition):
                raise TypeError("definitions must be BattleTargetingDefinition values")
            if definition.ability_id in self.definitions:
                raise ValueError(f"duplicate battle targeting definition: {definition.ability_id}")
            self.definitions[definition.ability_id] = definition
        self.formations = dict(formations or {})
        self.is_active = is_active or (lambda member: True)
        self.is_targetable = is_targetable or (lambda member: True)

    def definition_for(self, ability_id):
        return self.definitions.get(str(ability_id))

    def _matches_relation(self, actor, candidate, relation):
        if relation is TargetRelation.SELF:
            return candidate.member_id == actor.member_id
        if relation is TargetRelation.ALLY:
            return candidate.side == actor.side
        if relation is TargetRelation.OPPONENT:
            return candidate.side != actor.side
        return True

    def _formation_for(self, side):
        return self.formations.get(str(side))

    def _slot_matches(self, candidate, definition):
        formation = self._formation_for(candidate.side)
        slot = None if formation is None else formation.slot_for(candidate.member_id)
        if definition.required_slot_tags:
            if slot is None or not set(definition.required_slot_tags).issubset(slot.tags):
                return False
        if definition.blocked_slot_tags and slot is not None:
            if set(definition.blocked_slot_tags).intersection(slot.tags):
                return False
        return True

    def _candidate_sort_key(self, member_id):
        member = self.members[str(member_id)]
        formation = self._formation_for(member.side)
        if formation is None:
            return (member.side, 1_000_000, member.member_id)
        slot_id = formation.slot_id_for(member.member_id)
        if slot_id is None:
            return (member.side, 999_999, member.member_id)
        order = {slot.slot_id: i for i, slot in enumerate(formation.definition.slots)}
        return (member.side, order.get(slot_id, 999_998), member.member_id)

    def candidates(self, actor_id, ability_id):
        actor = self.members[str(actor_id)]
        definition = self.definition_for(ability_id)
        if definition is None:
            return tuple(sorted(self.members))
        adjacent = None
        if definition.adjacent_to_actor:
            formation = self._formation_for(actor.side)
            adjacent = (
                set() if formation is None else set(formation.adjacent_member_ids(actor.member_id))
            )
        result = []
        for candidate in self.members.values():
            if not self.is_targetable(candidate):
                continue
            if not self._matches_relation(actor, candidate, definition.relation):
                continue
            if definition.active_only and not self.is_active(candidate):
                continue
            if adjacent is not None and candidate.member_id not in adjacent:
                continue
            if definition.required_subject_tags and not candidate.subject.tags.contains_all(
                definition.required_subject_tags
            ):
                continue
            if definition.blocked_subject_tags and candidate.subject.tags.contains_any(
                definition.blocked_subject_tags
            ):
                continue
            if not self._slot_matches(candidate, definition):
                continue
            if not all(
                condition.matches(candidate.subject) for condition in definition.metric_conditions
            ):
                continue
            result.append(candidate.member_id)
        return tuple(sorted(result, key=self._candidate_sort_key))

    def resolve(self, actor_id, ability_id, requested_ids=(), *, rng=None):
        definition = self.definition_for(ability_id)
        candidates = self.candidates(actor_id, ability_id)
        if definition is None:
            requested = tuple(dict.fromkeys(str(x) for x in requested_ids))
            return TargetResolution(
                str(ability_id), str(actor_id), candidates, requested, True, ()
            )
        candidate_set = set(candidates)
        raw_requested = tuple(str(x) for x in requested_ids)
        requested = tuple(dict.fromkeys(raw_requested))
        errors = []
        if len(raw_requested) != len(requested):
            errors.append("duplicate_target")
        if definition.selection_mode is TargetSelectionMode.MANUAL:
            selected = requested
        elif definition.selection_mode is TargetSelectionMode.ALL:
            selected = candidates
        elif definition.selection_mode is TargetSelectionMode.FIRST_N:
            count = (
                definition.selection_count
                if definition.selection_count is not None
                else definition.maximum_targets
            )
            selected = candidates[:count]
        else:
            count = (
                definition.selection_count
                if definition.selection_count is not None
                else definition.maximum_targets
            )
            count = min(count, len(candidates))
            engine = rng if rng is not None else random.Random()
            selected = tuple(sorted(engine.sample(list(candidates), count)))
        invalid = [x for x in selected if x not in candidate_set]
        if invalid:
            errors.extend(f"invalid_target:{x}" for x in invalid)
        if len(selected) < definition.minimum_targets:
            errors.append("too_few_targets")
        if len(selected) > definition.maximum_targets:
            errors.append("too_many_targets")
        return TargetResolution(
            definition.ability_id,
            str(actor_id),
            candidates,
            tuple(selected),
            not errors,
            tuple(errors),
        )
