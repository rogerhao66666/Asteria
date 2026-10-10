from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _nonnegative(value, name):
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return value


def _id(value, name):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


@dataclass(frozen=True, slots=True)
class BattleMotionBeat:
    beat_id: str
    at: float
    channel: str
    cue: str
    member_id: str | None = None
    target_id: str | None = None
    duration: float = 0.0
    easing: str = "linear"
    payload: tuple[tuple[str, object], ...] = ()

    def __init__(
        self, beat_id, at, channel, cue, *, member_id=None, target_id=None, duration=0.0, easing="linear", payload=None
    ):
        object.__setattr__(self, "beat_id", _id(beat_id, "beat_id"))
        object.__setattr__(self, "at", _nonnegative(at, "at"))
        object.__setattr__(self, "channel", _id(channel, "channel"))
        object.__setattr__(self, "cue", _id(cue, "cue"))
        object.__setattr__(self, "member_id", None if member_id is None else _id(member_id, "member_id"))
        object.__setattr__(self, "target_id", None if target_id is None else _id(target_id, "target_id"))
        object.__setattr__(self, "duration", _nonnegative(duration, "duration"))
        object.__setattr__(self, "easing", str(easing).strip() or "linear")
        object.__setattr__(self, "payload", tuple(sorted(dict(payload or {}).items())))

    def payload_dict(self):
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class BattleMotionSequence:
    sequence_id: str
    duration: float
    beats: tuple[BattleMotionBeat, ...]
    recovery_at: float | None = None

    def __init__(self, sequence_id, duration, beats=(), *, recovery_at=None):
        duration = _nonnegative(duration, "duration")
        beats = tuple(beats)
        if any(not isinstance(x, BattleMotionBeat) for x in beats):
            raise TypeError("beats must be BattleMotionBeat")
        ids = [x.beat_id for x in beats]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate motion beat")
        if any(x.at > duration + 1e-12 for x in beats):
            raise ValueError("motion beat exceeds sequence duration")
        recovery = None if recovery_at is None else _nonnegative(recovery_at, "recovery_at")
        if recovery is not None and recovery > duration:
            raise ValueError("recovery_at exceeds sequence duration")
        object.__setattr__(self, "sequence_id", _id(sequence_id, "sequence_id"))
        object.__setattr__(self, "duration", duration)
        object.__setattr__(self, "beats", tuple(sorted(beats, key=lambda x: (x.at, x.beat_id))))
        object.__setattr__(self, "recovery_at", recovery)


@dataclass(frozen=True, slots=True)
class BattleMotionFrame:
    sequence_id: str
    time: float
    released: tuple[BattleMotionBeat, ...]
    active: tuple[BattleMotionBeat, ...]
    hit_stop_remaining: float
    complete: bool


@dataclass(frozen=True, slots=True)
class BattleMotionMetrics:
    update_calls: int
    released_beats: int
    peak_active_beats: int
    current_active_beats: int


class BattleMotionRuntime:
    """High-precision presentation choreography clock.

    Beat release is event-driven rather than fixed-substep scanning: host-frame
    dt may be coarse, but every authored beat boundary is still crossed exactly.
    Cost therefore scales primarily with beats actually released/active, not
    ``dt / quantum * total_beats``. Hit stop pauses presentation time only.
    ``quantum`` is retained as a compatibility/performance-policy hint for
    renderer adapters; choreography correctness does not depend on rendering at
    that frequency.
    """

    def __init__(self, *, quantum=1.0 / 240.0):
        self.quantum = float(quantum)
        if self.quantum <= 0:
            raise ValueError("quantum must be > 0")
        self.sequence = None
        self.time = 0.0
        self.hit_stop_remaining = 0.0
        self._next_index = 0
        self._active_beats = []
        self._update_calls = 0
        self._released_beats = 0
        self._peak_active_beats = 0

    def start(self, sequence):
        if not isinstance(sequence, BattleMotionSequence):
            raise TypeError("sequence must be BattleMotionSequence")
        self.sequence = sequence
        self.time = 0.0
        self.hit_stop_remaining = 0.0
        self._next_index = 0
        self._active_beats = []
        self._update_calls = 0
        self._released_beats = 0
        self._peak_active_beats = 0
        return self.frame(())

    def apply_hit_stop(self, duration):
        duration = _nonnegative(duration, "hit stop")
        self.hit_stop_remaining = max(self.hit_stop_remaining, duration)

    def _prune_active(self):
        if not self._active_beats:
            return
        now = self.time
        self._active_beats = [x for x in self._active_beats if now < x.at + x.duration - 1e-12]

    def _release_due(self, released):
        beats = self.sequence.beats
        while self._next_index < len(beats):
            beat = beats[self._next_index]
            if beat.at > self.time + 1e-12:
                break
            self._next_index += 1
            released.append(beat)
            self._released_beats += 1
            if beat.duration > 0:
                self._active_beats.append(beat)
                if len(self._active_beats) > self._peak_active_beats:
                    self._peak_active_beats = len(self._active_beats)
            if beat.channel == "timing" and beat.cue == "hit_stop":
                payload = beat.payload_dict()
                self.apply_hit_stop(payload.get("duration", beat.duration))

    def frame(self, released):
        seq = self.sequence
        self._prune_active()
        return BattleMotionFrame(
            "" if seq is None else seq.sequence_id,
            self.time,
            tuple(released),
            tuple(self._active_beats),
            self.hit_stop_remaining,
            seq is None or self.time >= seq.duration - 1e-12,
        )

    def metrics(self):
        return BattleMotionMetrics(
            self._update_calls,
            self._released_beats,
            self._peak_active_beats,
            len(self._active_beats),
        )

    def update(self, dt):
        dt = _nonnegative(dt, "dt")
        self._update_calls += 1
        if self.sequence is None:
            return self.frame(())
        released = []
        remaining = dt
        self._release_due(released)

        while remaining > 1e-12 and self.time < self.sequence.duration - 1e-12:
            if self.hit_stop_remaining > 0:
                held = min(remaining, self.hit_stop_remaining)
                remaining -= held
                self.hit_stop_remaining = max(0.0, self.hit_stop_remaining - held)
                if remaining <= 1e-12:
                    break

            beats = self.sequence.beats
            next_at = beats[self._next_index].at if self._next_index < len(beats) else self.sequence.duration
            advance = max(0.0, min(remaining, next_at - self.time, self.sequence.duration - self.time))
            if advance > 0:
                self.time += advance
                remaining -= advance

            # Exact event boundary: release every beat sharing this timestamp.
            before = self._next_index
            self._release_due(released)
            if self._next_index == before and advance <= 1e-12:
                # No more beat boundary is reachable; consume remaining time.
                advance = min(remaining, self.sequence.duration - self.time)
                self.time += advance
                remaining -= advance

        self._prune_active()
        return self.frame(released)


def make_reference_smooth_attack_sequence(*, multi_hits=3):
    """Reference choreography proving premium-JRPG temporal capability."""
    multi_hits = max(1, int(multi_hits))
    beats = [
        BattleMotionBeat("startup", 0.00, "animation", "startup", member_id="actor", duration=0.12, easing="ease_out"),
        BattleMotionBeat("cast", 0.08, "animation", "cast", member_id="actor", duration=0.18, easing="ease_in_out"),
        BattleMotionBeat(
            "projectile",
            0.18,
            "vfx",
            "projectile",
            member_id="actor",
            target_id="target",
            duration=0.22,
            easing="ease_in",
        ),
        BattleMotionBeat(
            "camera.pre_hit", 0.32, "camera", "push", target_id="target", duration=0.08, easing="ease_out"
        ),
    ]
    base = 0.36
    spacing = 0.055
    for i in range(multi_hits):
        t = base + i * spacing
        beats.extend(
            (
                BattleMotionBeat(f"impact.{i}", t, "vfx", "impact", target_id="target", duration=0.08),
                BattleMotionBeat(f"camera.hit.{i}", t, "camera", "impulse", target_id="target", duration=0.07),
                BattleMotionBeat(f"audio.hit.{i}", t, "audio", "hit", target_id="target"),
                BattleMotionBeat(f"value.{i}", t + 0.010, "ui", "floating_value", target_id="target", duration=0.45),
            )
        )
    last = base + (multi_hits - 1) * spacing
    beats.extend(
        (
            BattleMotionBeat("hit_stop", last, "timing", "hit_stop", duration=0.045, payload={"duration": 0.045}),
            BattleMotionBeat(
                "resource", last + 0.018, "ui", "resource_motion", target_id="target", duration=0.16, easing="ease_out"
            ),
            BattleMotionBeat("status", last + 0.035, "vfx", "status", target_id="target", duration=0.40),
            BattleMotionBeat(
                "recovery", last + 0.14, "animation", "recovery", member_id="actor", duration=0.18, easing="ease_in_out"
            ),
        )
    )
    duration = last + 0.34
    return BattleMotionSequence("reference.smooth_attack", duration, beats, recovery_at=last + 0.14)
