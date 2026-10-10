"""Parameter-driven animation state machines (ASTERIA_SPEC §11 state machines, transitions).

States name clips. Transitions move between states when all of their
conditions hold; ``source="*"`` means "from any state". A transition with
``when_finished`` waits until the current (non-looping) clip has ended.
Parameters are numbers or booleans; triggers are booleans consumed when a
transition that tests them fires.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field

_OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


@dataclass(frozen=True, slots=True)
class AnimationCondition:
    parameter: str
    operator: str = "=="
    value: object = True

    def __post_init__(self):
        if self.operator not in _OPERATORS:
            raise ValueError(f"unsupported operator: {self.operator}")

    def holds(self, parameters):
        if self.parameter not in parameters:
            return False
        return _OPERATORS[self.operator](parameters[self.parameter], self.value)

    def to_data(self):
        return {"parameter": self.parameter, "operator": self.operator, "value": self.value}

    @classmethod
    def from_data(cls, data):
        return cls(data["parameter"], data.get("operator", "=="), data.get("value", True))


@dataclass(frozen=True, slots=True)
class AnimationTransition:
    source: str
    target: str
    conditions: tuple[AnimationCondition, ...] = ()
    when_finished: bool = False
    priority: int = 0

    def to_data(self):
        return {
            "source": self.source,
            "target": self.target,
            "conditions": [c.to_data() for c in self.conditions],
            "when_finished": self.when_finished,
            "priority": self.priority,
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["source"],
            data["target"],
            tuple(AnimationCondition.from_data(c) for c in data.get("conditions", ())),
            bool(data.get("when_finished", False)),
            int(data.get("priority", 0)),
        )


@dataclass(frozen=True, slots=True)
class AnimationStateMachineDefinition:
    states: dict  # state id -> clip name
    initial: str
    transitions: tuple[AnimationTransition, ...] = ()
    parameters: dict = field(default_factory=dict)  # name -> default value
    triggers: tuple[str, ...] = ()

    def __post_init__(self):
        if self.initial not in self.states:
            raise ValueError(f"initial state {self.initial!r} is not a state")
        for t in self.transitions:
            if t.target not in self.states or (t.source != "*" and t.source not in self.states):
                raise ValueError(f"transition {t.source}->{t.target} names an unknown state")
            for c in t.conditions:
                if c.parameter not in self.parameters and c.parameter not in self.triggers:
                    raise ValueError(f"transition {t.source}->{t.target} tests unknown parameter {c.parameter}")

    def validate_clips(self, clip_set):
        missing = sorted(clip for clip in self.states.values() if clip_set.get(clip) is None)
        if missing:
            raise ValueError(f"state machine clips missing from clip set: {', '.join(missing)}")

    def to_data(self):
        return {
            "schema": "asteria.animation_state_machine",
            "version": 1,
            "states": dict(self.states),
            "initial": self.initial,
            "transitions": [t.to_data() for t in self.transitions],
            "parameters": dict(self.parameters),
            "triggers": list(self.triggers),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.animation_state_machine" or data.get("version") != 1:
            raise ValueError("unsupported animation state machine")
        return cls(
            dict(data["states"]),
            data["initial"],
            tuple(AnimationTransition.from_data(t) for t in data.get("transitions", ())),
            dict(data.get("parameters", {})),
            tuple(data.get("triggers", ())),
        )


class AnimationStateMachine:
    """Drives an ``AnimatorState`` from parameters; one instance per entity."""

    def __init__(self, definition, clip_set, animator):
        definition.validate_clips(clip_set)
        self.definition = definition
        self.clip_set = clip_set
        self.animator = animator
        self.parameters = dict(definition.parameters)
        self.parameters.update({name: False for name in definition.triggers})
        self.state = definition.initial
        self.animator.set_clip(clip_set.get(definition.states[self.state]), restart=True)

    def set(self, name, value):
        if name not in self.parameters:
            raise KeyError(f"unknown animation parameter: {name}")
        self.parameters[name] = value

    def trigger(self, name):
        if name not in self.definition.triggers:
            raise KeyError(f"unknown animation trigger: {name}")
        self.parameters[name] = True

    def _candidates(self):
        ordered = sorted(
            (t for t in self.definition.transitions if t.source in (self.state, "*") and t.target != self.state),
            key=lambda t: (-t.priority, t.source == "*"),
        )
        return ordered

    def evaluate(self):
        """Take at most one transition; returns the new state id or None."""
        for transition in self._candidates():
            if transition.when_finished and not self.animator.finished:
                continue
            if all(c.holds(self.parameters) for c in transition.conditions):
                for c in transition.conditions:
                    if c.parameter in self.definition.triggers:
                        self.parameters[c.parameter] = False
                self.state = transition.target
                self.animator.set_clip(self.clip_set.get(self.definition.states[self.state]), restart=True)
                return self.state
        return None

    def update(self, dt):
        self.evaluate()
        self.animator.update(dt)
        return self.state
