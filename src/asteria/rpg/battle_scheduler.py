from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _positive(value, label):
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite and > 0")
    return value


class BattleSchedulerMode(str, Enum):
    ROUND = "round"
    SPEED_ORDERED = "speed_ordered"
    CONTINUOUS = "continuous"


@dataclass(frozen=True, slots=True)
class BattleSchedulerDefinition:
    scheduler_id: str
    mode: BattleSchedulerMode = BattleSchedulerMode.SPEED_ORDERED
    timeline_scale: float = 100.0
    minimum_speed: float = 1.0

    def __init__(
        self, scheduler_id, *, mode=BattleSchedulerMode.SPEED_ORDERED, timeline_scale=100.0, minimum_speed=1.0
    ):
        object.__setattr__(self, "scheduler_id", _id(scheduler_id, "scheduler_id"))
        object.__setattr__(self, "mode", BattleSchedulerMode(mode))
        object.__setattr__(self, "timeline_scale", _positive(timeline_scale, "timeline_scale"))
        object.__setattr__(self, "minimum_speed", _positive(minimum_speed, "minimum_speed"))

    def to_data(self):
        return {
            "schema": "asteria.rpg.battle_scheduler_definition",
            "version": 1,
            "scheduler_id": self.scheduler_id,
            "mode": self.mode.value,
            "timeline_scale": self.timeline_scale,
            "minimum_speed": self.minimum_speed,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.battle_scheduler_definition" or data.get("version") != 1:
            raise ValueError("unsupported battle scheduler definition")
        return cls(
            data["scheduler_id"],
            mode=data["mode"],
            timeline_scale=data["timeline_scale"],
            minimum_speed=data["minimum_speed"],
        )


@dataclass(frozen=True, slots=True)
class ScheduledTurn:
    member_id: str
    side: str
    ready_time: float
    speed: float
    sequence: int


class BattleScheduler:
    """Deterministic battle scheduling independent of presentation/runtime backend.

    ROUND: project order (member id), one action per member per round.
    SPEED_ORDERED: higher speed first, one action per member per round.
    CONTINUOUS: next action time is timeline_scale/speed, allowing fast actors
    to act multiple times before slower actors. Stable member id breaks ties.
    """

    def __init__(self, members=(), definition=None):
        self.definition = definition or BattleSchedulerDefinition("default")
        if not isinstance(self.definition, BattleSchedulerDefinition):
            raise TypeError("definition must be BattleSchedulerDefinition")
        self._members = {m.member_id: m for m in members}
        if len(self._members) != len(tuple(members)):
            raise ValueError("duplicate scheduler member id")
        self._time = 0.0
        self._round = 1
        self._sequence = 0
        self._pending = []
        self._acted_this_round = set()
        self._initialize()

    @property
    def round_index(self):
        return self._round

    @property
    def current_time(self):
        return self._time

    @property
    def mode(self):
        return self.definition.mode

    def _speed(self, member):
        return max(self.definition.minimum_speed, float(member.initiative))

    def _initialize(self):
        if self.mode == BattleSchedulerMode.CONTINUOUS:
            for member in self._members.values():
                self._schedule_continuous(member, from_time=self._time)
        else:
            self._build_round()

    def _build_round(self):
        values = list(self._members.values())
        if self.mode == BattleSchedulerMode.ROUND:
            values.sort(key=lambda m: m.member_id)
        else:
            values.sort(key=lambda m: (-self._speed(m), m.member_id))
        self._pending = []
        for m in values:
            self._sequence += 1
            self._pending.append(ScheduledTurn(m.member_id, m.side, self._time, self._speed(m), self._sequence))

    def _schedule_continuous(self, member, *, from_time):
        speed = self._speed(member)
        self._sequence += 1
        self._pending.append(
            ScheduledTurn(
                member.member_id, member.side, from_time + self.definition.timeline_scale / speed, speed, self._sequence
            )
        )
        self._pending.sort(key=lambda x: (x.ready_time, x.member_id, x.sequence))

    def peek(self):
        return self._pending[0] if self._pending else None

    def pending(self):
        return tuple(self._pending)

    def exhausted(self):
        return not self._pending

    def advance_time(self, target_time):
        target_time = float(target_time)
        if target_time < self._time:
            raise ValueError("scheduler time cannot move backwards")
        self._time = target_time
        return self._time

    def shift_member(self, member_id, delta):
        """Shift a member's next readiness in continuous mode. Negative advances.

        Readiness is clamped to the current scheduler time so timeline-advance
        effects cannot schedule an actor in the past.
        """
        if self.mode != BattleSchedulerMode.CONTINUOUS:
            return tuple()
        member_id = str(member_id)
        delta = float(delta)
        changed = []
        for i, entry in enumerate(self._pending):
            if entry.member_id != member_id:
                continue
            replacement = ScheduledTurn(
                entry.member_id,
                entry.side,
                max(self._time, entry.ready_time + delta),
                entry.speed,
                entry.sequence,
            )
            self._pending[i] = replacement
            changed.append(replacement)
        self._pending.sort(key=lambda x: (x.ready_time, x.member_id, x.sequence))
        return tuple(changed)

    def pop(self):
        if not self._pending:
            return None
        entry = self._pending.pop(0)
        self._time = max(self._time, entry.ready_time)
        self._acted_this_round.add(entry.member_id)
        if self.mode == BattleSchedulerMode.CONTINUOUS and entry.member_id in self._members:
            self._schedule_continuous(self._members[entry.member_id], from_time=self._time)
            if self._members and self._acted_this_round.issuperset(self._members):
                self._round += 1
                self._acted_this_round.clear()
        return entry

    def start_next_round(self):
        if self.mode == BattleSchedulerMode.CONTINUOUS:
            return tuple(self._pending)
        self._round += 1
        self._acted_this_round.clear()
        self._build_round()
        return tuple(self._pending)

    # TurnQueue compatibility used by BattleRuntime's legacy round API.
    def start_round(self):
        return self.start_next_round()

    def register_member(self, member, *, join_current_round=False):
        if member.member_id in self._members:
            raise ValueError(f"duplicate scheduler member: {member.member_id}")
        self._members[member.member_id] = member
        if self.mode == BattleSchedulerMode.CONTINUOUS:
            self._schedule_continuous(member, from_time=self._time)
        elif join_current_round:
            self._sequence += 1
            self._pending.append(
                ScheduledTurn(member.member_id, member.side, self._time, self._speed(member), self._sequence)
            )
            if self.mode == BattleSchedulerMode.SPEED_ORDERED:
                self._pending.sort(key=lambda x: (-x.speed, x.member_id))
            else:
                self._pending.sort(key=lambda x: x.member_id)

    def replace_member(self, member):
        if member.member_id not in self._members:
            raise KeyError(member.member_id)
        self._members[member.member_id] = member
        # Existing ready time is preserved; new speed applies on next schedule.

    def remove_pending(self, member_id):
        member_id = str(member_id)
        self._pending = [x for x in self._pending if x.member_id != member_id]
        self._members.pop(member_id, None)
        self._acted_this_round.discard(member_id)

    def to_data(self):
        return {
            "schema": "asteria.rpg.battle_scheduler",
            "version": 1,
            "definition": self.definition.to_data(),
            "round_index": self._round,
            "current_time": self._time,
            "sequence": self._sequence,
            "acted_this_round": sorted(self._acted_this_round),
            "pending": [
                {
                    "member_id": x.member_id,
                    "side": x.side,
                    "ready_time": x.ready_time,
                    "speed": x.speed,
                    "sequence": x.sequence,
                }
                for x in self._pending
            ],
        }

    @classmethod
    def from_data(cls, data, members):
        if data.get("schema") != "asteria.rpg.battle_scheduler" or data.get("version") != 1:
            raise ValueError("unsupported battle scheduler")
        result = cls.__new__(cls)
        result.definition = BattleSchedulerDefinition.from_data(data["definition"])
        result._members = {m.member_id: m for m in members}
        result._time = float(data["current_time"])
        result._round = int(data["round_index"])
        result._sequence = int(data["sequence"])
        result._acted_this_round = set(data.get("acted_this_round", ()))
        result._pending = [
            ScheduledTurn(x["member_id"], x["side"], float(x["ready_time"]), float(x["speed"]), int(x["sequence"]))
            for x in data["pending"]
        ]
        return result
