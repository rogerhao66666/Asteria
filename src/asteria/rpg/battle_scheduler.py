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
        self,
        scheduler_id,
        *,
        mode=BattleSchedulerMode.SPEED_ORDERED,
        timeline_scale=100.0,
        minimum_speed=1.0,
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
        if (
            data.get("schema") != "asteria.rpg.battle_scheduler_definition"
            or data.get("version") != 1
        ):
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
        self._charge_from = {}  # continuous mode: member id -> time its current charge began
        self._sitting_out = set()  # continuous mode: members that lost the opening
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
        return max(
            self.definition.minimum_speed,
            float(getattr(member, "current_initiative", member.initiative)),
        )

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
            self._pending.append(
                ScheduledTurn(m.member_id, m.side, self._time, self._speed(m), self._sequence)
            )

    def _schedule_continuous(self, member, *, from_time):
        speed = self._speed(member)
        self._charge_from[member.member_id] = from_time
        self._sequence += 1
        self._pending.append(
            ScheduledTurn(
                member.member_id,
                member.side,
                from_time + self.definition.timeline_scale / speed,
                speed,
                self._sequence,
            )
        )
        self._pending.sort(key=lambda x: (x.ready_time, x.member_id, x.sequence))

    def peek(self):
        return self._pending[0] if self._pending else None

    def gauge(self, member_id):
        """How full the member's turn gauge is, 0..1 (continuous mode; 1 when ready, 0 otherwise).

        This is the ATB bar: the share of the member's charge time that has passed.
        """
        member_id = str(member_id)
        entry = next((x for x in self._pending if x.member_id == member_id), None)
        if entry is None or self.mode != BattleSchedulerMode.CONTINUOUS:
            return 0.0
        start = self._charge_from.get(member_id, 0.0)
        span = entry.ready_time - start
        if span <= 0:
            return 1.0
        return max(0.0, min(1.0, (self._time - start) / span))

    def gauges(self):
        """``member id -> gauge`` for everyone waiting to act (continuous mode)."""
        return {x.member_id: self.gauge(x.member_id) for x in self._pending}

    def preview_order(self, count):
        """The next ``count`` turns as ``(member id, ready time)`` without changing anything.

        In continuous mode this runs the timeline forward (each actor re-queues at its present
        speed), which is the turn-order bar of a charge-time battle; other modes list what is
        pending and then the following rounds in the same order.
        """
        count = max(0, int(count))
        if self.mode != BattleSchedulerMode.CONTINUOUS:
            order = [(x.member_id, x.ready_time) for x in self._pending]
            if not order:
                return ()
            full = order * (count // len(order) + 1)
            return tuple(full[:count])
        queue = [(x.ready_time, x.member_id, x.sequence, x.speed) for x in self._pending]
        sequence = self._sequence
        result = []
        while queue and len(result) < count:
            queue.sort()
            ready, member_id, _, _ = queue.pop(0)
            result.append((member_id, ready))
            member = self._members.get(member_id)
            if member is None:
                continue
            sequence += 1
            speed = self._speed(member)
            queue.append(
                (ready + self.definition.timeline_scale / speed, member_id, sequence, speed)
            )
        return tuple(result)

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
        if self._sitting_out and entry.member_id not in self._sitting_out:
            for waiting in sorted(self._sitting_out):  # the opening is over: they charge again
                if waiting in self._members:
                    self._schedule_continuous(self._members[waiting], from_time=self._time)
            self._sitting_out.clear()
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
                ScheduledTurn(
                    member.member_id, member.side, self._time, self._speed(member), self._sequence
                )
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

    def sit_out_round(self, member_id):
        """Give up the coming turn (a lost opening) without leaving the battle: in the round
        modes the member skips what is left of this round; on the timeline it is off until
        another member has acted once, then it starts charging again."""
        member_id = str(member_id)
        self._pending = [x for x in self._pending if x.member_id != member_id]
        if self.mode == BattleSchedulerMode.CONTINUOUS and member_id in self._members:
            self._charge_from.pop(member_id, None)
            self._sitting_out.add(member_id)

    def remove_pending(self, member_id):
        member_id = str(member_id)
        self._pending = [x for x in self._pending if x.member_id != member_id]
        self._charge_from.pop(member_id, None)
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
            **(
                {"charge_from": dict(sorted(self._charge_from.items()))}
                if self._charge_from
                else {}
            ),
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
        result._charge_from = {str(k): float(v) for k, v in data.get("charge_from", {}).items()}
        result._pending = [
            ScheduledTurn(
                x["member_id"],
                x["side"],
                float(x["ready_time"]),
                float(x["speed"]),
                int(x["sequence"]),
            )
            for x in data["pending"]
        ]
        return result


ATB_WAIT_MODES = {
    "active": frozenset(),  # the gauges never stop
    "semi": frozenset({"submenu"}),  # they stop while a skill / item list is open
    "wait": frozenset({"submenu", "target"}),  # ... and while a target is being chosen
}


class ATBClock:
    """Drives a continuous ``BattleScheduler`` from real time, like an Active Time Battle.

    ``tick(dt)`` moves the battle timeline forward by ``dt * rate`` and returns the turn that
    became ready (the first one, if several did), or ``None``. While a player is choosing, the
    wait mode decides whether time passes: ``choosing`` is ``""`` (nothing open), ``"command"``,
    ``"submenu"`` (skill / item list) or ``"target"``. Time stops at a ready turn, so a pending
    turn is never skipped; once the actor has acted (``BattleRuntime.advance_turn`` pops the
    entry) the next ``tick`` moves on.
    """

    def __init__(self, scheduler, *, wait_mode="active", rate=1.0):
        if scheduler.mode != BattleSchedulerMode.CONTINUOUS:
            raise ValueError("ATBClock needs a continuous scheduler")
        if wait_mode not in ATB_WAIT_MODES:
            raise ValueError(f"wait_mode must be one of {tuple(ATB_WAIT_MODES)}")
        rate = float(rate)
        if not rate > 0:
            raise ValueError("rate must be positive")
        self.scheduler = scheduler
        self.wait_mode = wait_mode
        self.rate = rate

    def paused(self, choosing=""):
        return choosing in ATB_WAIT_MODES[self.wait_mode]

    def tick(self, dt, *, choosing=""):
        dt = max(0.0, float(dt))
        entry = self.scheduler.peek()
        if entry is None or self.paused(choosing):
            return None
        target = self.scheduler.current_time + dt * self.rate
        if entry.ready_time <= self.scheduler.current_time:
            return entry  # already waiting for its actor
        if entry.ready_time <= target:
            self.scheduler.advance_time(entry.ready_time)
            return entry
        self.scheduler.advance_time(target)
        return None
