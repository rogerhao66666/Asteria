from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .battle import BattlePresentationEvent, BattlePresentationEventKind


def _nonnegative(value, label):
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and >= 0")
    return value


@dataclass(frozen=True, slots=True)
class BattlePresentationDirection:
    """Authored presentation choreography metadata for an already-resolved event."""

    beat: str = "default"
    delay: float = 0.0
    hold: float = 0.0
    priority: int = 0

    def __post_init__(self):
        object.__setattr__(self, "beat", str(self.beat).strip() or "default")
        object.__setattr__(self, "delay", _nonnegative(self.delay, "director delay"))
        object.__setattr__(self, "hold", _nonnegative(self.hold, "director hold"))
        object.__setattr__(self, "priority", int(self.priority))

    def to_data(self):
        return {
            "beat": self.beat,
            "delay": self.delay,
            "hold": self.hold,
            "priority": self.priority,
        }

    @classmethod
    def from_data(cls, data):
        return cls(**dict(data or {}))


@dataclass(frozen=True, slots=True)
class BattlePresentationDirectorRule:
    event_kind: str = "*"
    cue_kind: str = "*"
    direction: BattlePresentationDirection = BattlePresentationDirection()

    def __init__(self, event_kind="*", cue_kind="*", direction=None):
        object.__setattr__(self, "event_kind", str(event_kind).strip() or "*")
        object.__setattr__(self, "cue_kind", str(cue_kind).strip() or "*")
        if direction is None:
            direction = BattlePresentationDirection()
        elif not isinstance(direction, BattlePresentationDirection):
            direction = BattlePresentationDirection.from_data(direction)
        object.__setattr__(self, "direction", direction)

    def matches(self, event_kind, cue_kind):
        return self.event_kind in {"*", event_kind} and self.cue_kind in {"*", cue_kind}

    def to_data(self):
        return {
            "event_kind": self.event_kind,
            "cue_kind": self.cue_kind,
            "direction": self.direction.to_data(),
        }

    @classmethod
    def from_data(cls, data):
        return cls(data.get("event_kind", "*"), data.get("cue_kind", "*"), data.get("direction"))


@dataclass(frozen=True, slots=True)
class BattlePresentationDirectorProfile:
    rules: tuple[BattlePresentationDirectorRule, ...] = ()

    SCHEMA = "asteria.battle_presentation_director_profile"
    VERSION = 1

    def __init__(self, rules=()):
        rules = tuple(
            x
            if isinstance(x, BattlePresentationDirectorRule)
            else BattlePresentationDirectorRule.from_data(x)
            for x in rules
        )
        object.__setattr__(self, "rules", rules)

    def direction_for(self, event_kind, cue_kind=""):
        result = BattlePresentationDirection()
        for rule in self.rules:
            if rule.matches(str(event_kind), str(cue_kind)):
                result = rule.direction
        return result

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "rules": [x.to_data() for x in self.rules],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported battle presentation director profile")
        return cls(data.get("rules", ()))


@dataclass(frozen=True, slots=True)
class BattleDirectedEvent:
    event: BattlePresentationEvent
    release_time: float
    direction: BattlePresentationDirection


@dataclass(frozen=True, slots=True)
class BattlePresentationDirectorAdvance:
    released_events: tuple[BattlePresentationEvent, ...]
    presentation_dt: float
    holding: bool
    hold_remaining: float
    active_beat: str


class BattlePresentationDirector:
    """Presentation-only choreography scheduler.

    It may delay already-resolved presentation events or temporarily pause
    presentation clocks. It never changes Battle Core time, scheduler state,
    resources, targets, action results or battle outcomes.
    """

    SCHEMA = "asteria.battle_presentation_director"
    VERSION = 1

    def __init__(self, profile=None):
        self.profile = profile or BattlePresentationDirectorProfile()
        if not isinstance(self.profile, BattlePresentationDirectorProfile):
            raise TypeError("profile must be BattlePresentationDirectorProfile")
        self.time = 0.0
        self.hold_remaining = 0.0
        self.active_beat = "default"
        self._pending: list[BattleDirectedEvent] = []
        self.last_sequence = 0

    def _metadata(self, event):
        if event.kind == BattlePresentationEventKind.TIMELINE_CUE:
            cue = dict(event.payload.get("cue", {}))
            cue_kind = str(cue.get("kind", ""))
            cue_payload = dict(cue.get("payload", {}) or {})
            authored = cue_payload.get("director")
        else:
            cue_kind = ""
            authored = event.payload.get("director")

        direction = self.profile.direction_for(event.kind.value, cue_kind)
        if authored is None:
            return direction

        authored = dict(authored)
        base = direction.to_data()
        base.update(authored)
        return BattlePresentationDirection.from_data(base)

    def ingest(self, events):
        """Accept a stable resolved event stream and immediately release due events."""
        for event in tuple(events):
            if not isinstance(event, BattlePresentationEvent):
                raise TypeError("director events must be BattlePresentationEvent")
            if event.sequence <= self.last_sequence:
                raise ValueError("director events must be applied in increasing sequence order")
            self.last_sequence = event.sequence
            direction = self._metadata(event)
            self._pending.append(
                BattleDirectedEvent(
                    event,
                    self.time + direction.delay,
                    direction,
                )
            )
        self._pending.sort(key=lambda x: x.event.sequence)
        return self.release_ready()

    def release_ready(self):
        """Release due events in sequence order: a delayed event holds back the events after
        it (every downstream runtime takes events in increasing sequence order), so a delay
        never lets a later event overtake an earlier one."""
        released = []
        while self._pending and self._pending[0].release_time <= self.time + 1e-12:
            item = self._pending.pop(0)
            released.append(item.event)
            self.active_beat = item.direction.beat
            if item.direction.hold > self.hold_remaining:
                self.hold_remaining = item.direction.hold
        return tuple(released)

    def update(self, dt):
        """Advance presentation time; authored holds consume dt before visual clocks."""
        dt = _nonnegative(dt, "dt")
        held = min(dt, self.hold_remaining)
        self.hold_remaining = max(0.0, self.hold_remaining - held)
        presentation_dt = dt - held
        self.time += presentation_dt
        released = self.release_ready()
        return BattlePresentationDirectorAdvance(
            released,
            presentation_dt,
            held > 0.0 or self.hold_remaining > 0.0,
            self.hold_remaining,
            self.active_beat,
        )

    @property
    def pending_count(self):
        return len(self._pending)

    def snapshot(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "profile": self.profile.to_data(),
            "time": self.time,
            "hold_remaining": self.hold_remaining,
            "active_beat": self.active_beat,
            "last_sequence": self.last_sequence,
            "pending": [
                {
                    "release_time": x.release_time,
                    "direction": x.direction.to_data(),
                    "event": {
                        "sequence": x.event.sequence,
                        "kind": x.event.kind.value,
                        "source_id": x.event.source_id,
                        "payload": dict(x.event.payload),
                    },
                }
                for x in self._pending
            ],
        }

    def restore(self, data):
        if data.get("schema") != self.SCHEMA or data.get("version") != self.VERSION:
            raise ValueError("unsupported battle presentation director snapshot")
        if BattlePresentationDirectorProfile.from_data(data["profile"]) != self.profile:
            raise ValueError("battle presentation director profile mismatch")
        self.time = _nonnegative(data["time"], "director time")
        self.hold_remaining = _nonnegative(data["hold_remaining"], "hold_remaining")
        self.active_beat = str(data.get("active_beat", "default"))
        self.last_sequence = int(data.get("last_sequence", 0))
        self._pending = []
        for raw in data.get("pending", ()):
            e = raw["event"]
            event = BattlePresentationEvent(
                int(e["sequence"]),
                BattlePresentationEventKind(e["kind"]),
                str(e["source_id"]),
                dict(e.get("payload", {})),
            )
            self._pending.append(
                BattleDirectedEvent(
                    event,
                    _nonnegative(raw["release_time"], "release_time"),
                    BattlePresentationDirection.from_data(raw["direction"]),
                )
            )
        self._pending.sort(key=lambda x: (x.release_time, -x.direction.priority, x.event.sequence))
        return self
