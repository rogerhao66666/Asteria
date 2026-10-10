from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _finite(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class BattleTurnEntry:
    member_id: str
    side: str
    ready_time: float
    speed: float
    sequence: int
    is_current: bool


@dataclass(frozen=True, slots=True)
class BattleCastEntry:
    token: str
    actor_id: str
    ability_id: str
    target_ids: tuple[str, ...]
    started_at: float
    resolve_at: float
    remaining: float
    progress: float
    priority: int
    interruptible: bool


@dataclass(frozen=True, slots=True)
class BattleTurnTimelineView:
    scheduler_mode: str
    round_index: int
    current_time: float
    turns: tuple[BattleTurnEntry, ...]
    casts: tuple[BattleCastEntry, ...]
    revision: int


class BattleTurnTimelineRuntime:
    """Read-only projection of canonical scheduler and action-timing state.

    It does not pop/shift scheduler entries, resolve actions, validate targets,
    interrupt casts, or derive gameplay timing policy. `current_member_id` is an
    optional canonical selection supplied by the battle controller.
    """

    SCHEMA = "asteria.battle_turn_timeline_runtime"
    VERSION = 1

    def __init__(self, *, max_turns=8):
        self.max_turns = max(1, int(max_turns))
        self._view = BattleTurnTimelineView("", 0, 0.0, (), (), 0)
        self.revision = 0

    @property
    def view(self):
        return self._view

    def sync(self, scheduler, timing=None, *, current_member_id=None):
        current_time = _finite(scheduler.current_time, "current_time")
        current_member_id = None if current_member_id is None else str(current_member_id)

        turns = []
        for item in scheduler.pending()[: self.max_turns]:
            turns.append(
                BattleTurnEntry(
                    str(item.member_id),
                    str(item.side),
                    _finite(item.ready_time, "ready_time"),
                    _finite(item.speed, "speed"),
                    int(item.sequence),
                    current_member_id is not None and str(item.member_id) == current_member_id,
                )
            )

        casts = []
        pending = () if timing is None else timing.pending()
        for item in pending:
            started = _finite(item.started_at, "started_at")
            resolve = _finite(item.resolve_at, "resolve_at")
            duration = max(0.0, resolve - started)
            remaining = max(0.0, resolve - current_time)
            if duration <= 0.0:
                progress = 1.0 if current_time >= resolve else 0.0
            else:
                progress = min(1.0, max(0.0, (current_time - started) / duration))
            casts.append(
                BattleCastEntry(
                    str(item.token),
                    str(item.actor_id),
                    str(item.ability_id),
                    tuple(str(x) for x in item.target_ids),
                    started,
                    resolve,
                    remaining,
                    progress,
                    int(item.priority),
                    bool(item.interruptible),
                )
            )
        casts.sort(key=lambda x: (x.resolve_at, -x.priority, x.actor_id, x.token))

        self.revision += 1
        self._view = BattleTurnTimelineView(
            scheduler.mode.value,
            int(scheduler.round_index),
            current_time,
            tuple(turns),
            tuple(casts),
            self.revision,
        )
        return self._view

    def snapshot(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "max_turns": self.max_turns,
            "revision": self.revision,
            "view": {
                "scheduler_mode": self._view.scheduler_mode,
                "round_index": self._view.round_index,
                "current_time": self._view.current_time,
                "turns": [
                    {
                        "member_id": x.member_id,
                        "side": x.side,
                        "ready_time": x.ready_time,
                        "speed": x.speed,
                        "sequence": x.sequence,
                        "is_current": x.is_current,
                    }
                    for x in self._view.turns
                ],
                "casts": [
                    {
                        "token": x.token,
                        "actor_id": x.actor_id,
                        "ability_id": x.ability_id,
                        "target_ids": list(x.target_ids),
                        "started_at": x.started_at,
                        "resolve_at": x.resolve_at,
                        "remaining": x.remaining,
                        "progress": x.progress,
                        "priority": x.priority,
                        "interruptible": x.interruptible,
                    }
                    for x in self._view.casts
                ],
            },
        }

    def restore(self, data):
        if data.get("schema") != self.SCHEMA or data.get("version") != self.VERSION:
            raise ValueError("unsupported battle turn timeline snapshot")
        self.max_turns = max(1, int(data["max_turns"]))
        self.revision = int(data["revision"])
        view = data["view"]
        turns = tuple(BattleTurnEntry(**x) for x in view.get("turns", ()))
        casts = tuple(
            BattleCastEntry(
                x["token"],
                x["actor_id"],
                x["ability_id"],
                tuple(x.get("target_ids", ())),
                float(x["started_at"]),
                float(x["resolve_at"]),
                float(x["remaining"]),
                float(x["progress"]),
                int(x["priority"]),
                bool(x["interruptible"]),
            )
            for x in view.get("casts", ())
        )
        self._view = BattleTurnTimelineView(
            str(view["scheduler_mode"]),
            int(view["round_index"]),
            float(view["current_time"]),
            turns,
            casts,
            self.revision,
        )
        return self._view
