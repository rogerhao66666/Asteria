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
class ActionTimingDefinition:
    """Project-authored timing policy for one ability/action.

    startup and cast_time are both pre-resolution timeline delays. They stay
    separate because presentation commonly wants startup animation distinct
    from a sustained cast/channel window. recovery delays the actor's next
    scheduler readiness after the current turn is consumed.
    """

    ability_id: str
    startup: float = 0.0
    cast_time: float = 0.0
    recovery: float = 0.0
    priority: int = 0
    interruptible: bool = True
    interrupt_threshold: float = 0.0

    def __init__(
        self,
        ability_id,
        *,
        startup=0.0,
        cast_time=0.0,
        recovery=0.0,
        priority=0,
        interruptible=True,
        interrupt_threshold=0.0,
    ):
        object.__setattr__(self, "ability_id", _id(ability_id, "ability_id"))
        object.__setattr__(self, "startup", _nonnegative(startup, "startup"))
        object.__setattr__(self, "cast_time", _nonnegative(cast_time, "cast_time"))
        object.__setattr__(self, "recovery", _nonnegative(recovery, "recovery"))
        object.__setattr__(self, "priority", int(priority))
        object.__setattr__(self, "interruptible", bool(interruptible))
        object.__setattr__(self, "interrupt_threshold", _nonnegative(interrupt_threshold, "interrupt_threshold"))

    @property
    def windup(self):
        return self.startup + self.cast_time

    def to_data(self):
        return {
            "schema": "asteria.rpg.action_timing_definition",
            "version": 1,
            "ability_id": self.ability_id,
            "startup": self.startup,
            "cast_time": self.cast_time,
            "recovery": self.recovery,
            "priority": self.priority,
            "interruptible": self.interruptible,
            "interrupt_threshold": self.interrupt_threshold,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.action_timing_definition" or data.get("version") != 1:
            raise ValueError("unsupported action timing definition")
        return cls(
            data["ability_id"],
            startup=data.get("startup", 0.0),
            cast_time=data.get("cast_time", 0.0),
            recovery=data.get("recovery", 0.0),
            priority=data.get("priority", 0),
            interruptible=data.get("interruptible", True),
            interrupt_threshold=data.get("interrupt_threshold", 0.0),
        )


@dataclass(frozen=True, slots=True)
class PendingBattleAction:
    token: str
    actor_id: str
    ability_id: str
    target_ids: tuple[str, ...]
    started_at: float
    resolve_at: float
    priority: int
    sequence: int
    interruptible: bool
    interrupt_threshold: float

    def to_data(self):
        return {
            "token": self.token,
            "actor_id": self.actor_id,
            "ability_id": self.ability_id,
            "target_ids": list(self.target_ids),
            "started_at": self.started_at,
            "resolve_at": self.resolve_at,
            "priority": self.priority,
            "sequence": self.sequence,
            "interruptible": self.interruptible,
            "interrupt_threshold": self.interrupt_threshold,
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            str(data["token"]), str(data["actor_id"]), str(data["ability_id"]),
            tuple(str(x) for x in data.get("target_ids", ())),
            float(data["started_at"]), float(data["resolve_at"]),
            int(data.get("priority", 0)), int(data["sequence"]),
            bool(data.get("interruptible", True)), float(data.get("interrupt_threshold", 0.0)),
        )


@dataclass(frozen=True, slots=True)
class InterruptResult:
    actor_id: str
    interrupted: bool
    token: str | None = None
    reason: str = ""


class BattleActionTimingRuntime:
    """Deterministic queue for delayed action resolution.

    It does not mutate gameplay subjects. BattleRuntime owns validation and
    final ability execution, while this object owns temporal ordering,
    interrupt/cancel and snapshot state.
    """

    def __init__(self, definitions=()):
        self.definitions = {}
        for definition in definitions:
            if not isinstance(definition, ActionTimingDefinition):
                raise TypeError("timing definitions must be ActionTimingDefinition")
            if definition.ability_id in self.definitions:
                raise ValueError(f"duplicate timing definition: {definition.ability_id}")
            self.definitions[definition.ability_id] = definition
        self._pending = []
        self._sequence = 0

    def definition_for(self, ability_id):
        return self.definitions.get(str(ability_id), ActionTimingDefinition(str(ability_id)))

    def begin(self, action, *, current_time):
        definition = self.definition_for(action.ability_id)
        if definition.windup <= 0:
            return None
        self._sequence += 1
        token = f"action:{self._sequence}"
        pending = PendingBattleAction(
            token, str(action.actor_id), str(action.ability_id), tuple(action.target_ids),
            float(current_time), float(current_time) + definition.windup,
            definition.priority, self._sequence, definition.interruptible,
            definition.interrupt_threshold,
        )
        self._pending.append(pending)
        self._sort()
        return pending

    def _sort(self):
        self._pending.sort(key=lambda x: (x.resolve_at, -x.priority, x.sequence, x.actor_id))

    def pending(self):
        return tuple(self._pending)

    def next_pending(self):
        return self._pending[0] if self._pending else None

    def pop_due(self, through_time):
        through_time = float(through_time)
        due = []
        while self._pending and self._pending[0].resolve_at <= through_time:
            due.append(self._pending.pop(0))
        return tuple(due)

    def cancel(self, actor_id, *, reason="cancelled"):
        actor_id = str(actor_id)
        removed = [x for x in self._pending if x.actor_id == actor_id]
        self._pending = [x for x in self._pending if x.actor_id != actor_id]
        return tuple(removed)

    def interrupt(self, actor_id, *, power=0.0, reason="interrupted", force=False):
        actor_id = str(actor_id)
        candidate = next((x for x in self._pending if x.actor_id == actor_id), None)
        if candidate is None:
            return InterruptResult(actor_id, False, reason="no_pending_action")
        if not force:
            if not candidate.interruptible:
                return InterruptResult(actor_id, False, candidate.token, "not_interruptible")
            if float(power) < candidate.interrupt_threshold:
                return InterruptResult(actor_id, False, candidate.token, "below_threshold")
        self._pending.remove(candidate)
        return InterruptResult(actor_id, True, candidate.token, reason)

    def shift(self, actor_id, delta):
        actor_id = str(actor_id)
        delta = float(delta)
        changed = []
        for i, item in enumerate(self._pending):
            if item.actor_id != actor_id:
                continue
            replacement = PendingBattleAction(
                item.token, item.actor_id, item.ability_id, item.target_ids,
                item.started_at, max(item.started_at, item.resolve_at + delta),
                item.priority, item.sequence, item.interruptible, item.interrupt_threshold,
            )
            self._pending[i] = replacement
            changed.append(replacement)
        self._sort()
        return tuple(changed)

    def to_data(self):
        return {
            "schema": "asteria.rpg.battle_action_timing_runtime",
            "version": 1,
            "definitions": [self.definitions[k].to_data() for k in sorted(self.definitions)],
            "sequence": self._sequence,
            "pending": [x.to_data() for x in self._pending],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.battle_action_timing_runtime" or data.get("version") != 1:
            raise ValueError("unsupported battle action timing runtime")
        result = cls(ActionTimingDefinition.from_data(x) for x in data.get("definitions", ()))
        result._sequence = int(data.get("sequence", 0))
        result._pending = [PendingBattleAction.from_data(x) for x in data.get("pending", ())]
        result._sort()
        return result
