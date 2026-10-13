from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _nonnegative(value, label):
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and >= 0")
    return value


@dataclass(frozen=True, slots=True)
class ActionSequenceStep:
    """One authored step. participant_index makes the same model cover solo and N-person
    actions."""

    ability_id: str
    participant_index: int = 0
    repeat: int = 1
    delay: float = 0.0
    target_policy: str = "inherit"
    required_previous_tags: tuple[str, ...] = ()
    emitted_tags: tuple[str, ...] = ()

    def __init__(
        self,
        ability_id,
        *,
        participant_index=0,
        repeat=1,
        delay=0.0,
        target_policy="inherit",
        required_previous_tags=(),
        emitted_tags=(),
    ):
        if int(participant_index) < 0:
            raise ValueError("participant_index must be >= 0")
        if int(repeat) < 1:
            raise ValueError("repeat must be >= 1")
        object.__setattr__(self, "ability_id", _id(ability_id, "ability_id"))
        object.__setattr__(self, "participant_index", int(participant_index))
        object.__setattr__(self, "repeat", int(repeat))
        object.__setattr__(self, "delay", _nonnegative(delay, "delay"))
        object.__setattr__(self, "target_policy", _id(target_policy, "target_policy"))
        object.__setattr__(
            self,
            "required_previous_tags",
            tuple(dict.fromkeys(str(x) for x in required_previous_tags)),
        )
        object.__setattr__(
            self, "emitted_tags", tuple(dict.fromkeys(str(x) for x in emitted_tags))
        )

    def to_data(self):
        return {
            "ability_id": self.ability_id,
            "participant_index": self.participant_index,
            "repeat": self.repeat,
            "delay": self.delay,
            "target_policy": self.target_policy,
            "required_previous_tags": list(self.required_previous_tags),
            "emitted_tags": list(self.emitted_tags),
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["ability_id"],
            participant_index=data.get("participant_index", 0),
            repeat=data.get("repeat", 1),
            delay=data.get("delay", 0.0),
            target_policy=data.get("target_policy", "inherit"),
            required_previous_tags=data.get("required_previous_tags", ()),
            emitted_tags=data.get("emitted_tags", ()),
        )


@dataclass(frozen=True, slots=True)
class ActionSequenceDefinition:
    sequence_id: str
    steps: tuple[ActionSequenceStep, ...]
    min_participants: int = 1
    max_participants: int | None = 1
    participant_policy: str = "all_available"
    interruption_policy: str = "cancel_remaining"
    tags: tuple[str, ...] = ()

    def __init__(
        self,
        sequence_id,
        steps,
        *,
        min_participants=1,
        max_participants=1,
        participant_policy="all_available",
        interruption_policy="cancel_remaining",
        tags=(),
    ):
        steps = tuple(steps)
        if not steps:
            raise ValueError("action sequence requires at least one step")
        lo = int(min_participants)
        hi = None if max_participants is None else int(max_participants)
        if lo < 1 or (hi is not None and hi < lo):
            raise ValueError("invalid participant bounds")
        if any(not isinstance(x, ActionSequenceStep) for x in steps):
            raise TypeError("steps must be ActionSequenceStep values")
        if hi is not None and any(x.participant_index >= hi for x in steps):
            raise ValueError("step participant_index exceeds max_participants")
        object.__setattr__(self, "sequence_id", _id(sequence_id, "sequence_id"))
        object.__setattr__(self, "steps", steps)
        object.__setattr__(self, "min_participants", lo)
        object.__setattr__(self, "max_participants", hi)
        object.__setattr__(
            self, "participant_policy", _id(participant_policy, "participant_policy")
        )
        object.__setattr__(
            self, "interruption_policy", _id(interruption_policy, "interruption_policy")
        )
        object.__setattr__(self, "tags", tuple(dict.fromkeys(str(x) for x in tags)))

    def to_data(self):
        return {
            "schema": "asteria.rpg.action_sequence_definition",
            "version": 1,
            "sequence_id": self.sequence_id,
            "steps": [x.to_data() for x in self.steps],
            "min_participants": self.min_participants,
            "max_participants": self.max_participants,
            "participant_policy": self.participant_policy,
            "interruption_policy": self.interruption_policy,
            "tags": list(self.tags),
        }

    @classmethod
    def from_data(cls, data):
        if (
            data.get("schema") != "asteria.rpg.action_sequence_definition"
            or data.get("version") != 1
        ):
            raise ValueError("unsupported action sequence definition")
        return cls(
            data["sequence_id"],
            (ActionSequenceStep.from_data(x) for x in data["steps"]),
            min_participants=data.get("min_participants", 1),
            max_participants=data.get("max_participants", 1),
            participant_policy=data.get("participant_policy", "all_available"),
            interruption_policy=data.get("interruption_policy", "cancel_remaining"),
            tags=data.get("tags", ()),
        )


@dataclass(frozen=True, slots=True)
class PlannedSequenceStep:
    step_index: int
    hit_index: int
    actor_id: str
    ability_id: str
    target_ids: tuple[str, ...]
    offset: float


@dataclass(frozen=True, slots=True)
class ActionSequencePlan:
    sequence_id: str
    participant_ids: tuple[str, ...]
    steps: tuple[PlannedSequenceStep, ...]
    tags: tuple[str, ...]


class ActionSequenceRuntime:
    """Pure deterministic planner for multi-hit, chains and cooperative actions.

    The planner deliberately does not invent game rules for KO/stun/cost/interrupt.
    BattleRuntime validates each concrete action at execution time; authored policy
    strings and later hooks decide whether a project cancels, skips or substitutes.
    """

    def __init__(self, definitions=()):
        self.definitions = {}
        for value in definitions:
            if not isinstance(value, ActionSequenceDefinition):
                raise TypeError("definitions must be ActionSequenceDefinition")
            if value.sequence_id in self.definitions:
                raise ValueError(f"duplicate action sequence: {value.sequence_id}")
            self.definitions[value.sequence_id] = value

    def plan(self, sequence_id, participant_ids, target_ids=()):
        definition = self.definitions[str(sequence_id)]
        participants = tuple(_id(x, "participant_id") for x in participant_ids)
        if len(set(participants)) != len(participants):
            raise ValueError("duplicate action sequence participant")
        if len(participants) < definition.min_participants:
            raise ValueError("not enough action sequence participants")
        if (
            definition.max_participants is not None
            and len(participants) > definition.max_participants
        ):
            raise ValueError("too many action sequence participants")
        targets = tuple(_id(x, "target_id") for x in target_ids)
        emitted = set()
        offset = 0.0
        planned = []
        for step_index, step in enumerate(definition.steps):
            if step.participant_index >= len(participants):
                raise ValueError(f"missing participant for step {step_index}")
            if not set(step.required_previous_tags).issubset(emitted):
                raise ValueError(f"sequence prerequisites not met at step {step_index}")
            offset += step.delay
            for hit in range(step.repeat):
                planned.append(
                    PlannedSequenceStep(
                        step_index,
                        hit,
                        participants[step.participant_index],
                        step.ability_id,
                        targets,
                        offset,
                    )
                )
            emitted.update(step.emitted_tags)
        return ActionSequencePlan(
            definition.sequence_id, participants, tuple(planned), definition.tags
        )
