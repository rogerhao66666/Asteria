from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _nonnegative(value, label):
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and >= 0")
    return value


def _positive(value, label):
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite and > 0")
    return value


def easing_value(name, t):
    """Small backend-neutral easing library for presentation interpolation."""
    t = min(1.0, max(0.0, float(t)))
    name = str(name).strip().lower() or "linear"
    if name == "linear":
        return t
    if name == "ease_in":
        return t * t
    if name == "ease_out":
        return 1.0 - (1.0 - t) * (1.0 - t)
    if name == "ease_in_out":
        if t < 0.5:
            return 2.0 * t * t
        return 1.0 - ((-2.0 * t + 2.0) ** 2) / 2.0
    if name == "smoothstep":
        return t * t * (3.0 - 2.0 * t)
    raise ValueError(f"unsupported presentation easing: {name}")


@dataclass(frozen=True, slots=True)
class BattleAnimationTimingRule:
    role: str
    playback_rate: float = 1.0
    transition_duration: float = 0.0
    transition_easing: str = "linear"
    recovery_hold: float = 0.0

    def __post_init__(self):
        role = str(self.role).strip()
        if not role:
            raise ValueError("animation timing role is required")
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "playback_rate", _positive(self.playback_rate, "playback_rate"))
        object.__setattr__(self, "transition_duration", _nonnegative(self.transition_duration, "transition_duration"))
        easing_value(self.transition_easing, 0.5)
        object.__setattr__(self, "transition_easing", str(self.transition_easing).strip().lower())
        object.__setattr__(self, "recovery_hold", _nonnegative(self.recovery_hold, "recovery_hold"))

    def to_data(self):
        return {
            "role": self.role,
            "playback_rate": self.playback_rate,
            "transition_duration": self.transition_duration,
            "transition_easing": self.transition_easing,
            "recovery_hold": self.recovery_hold,
        }

    @classmethod
    def from_data(cls, data):
        return cls(**data)


@dataclass(frozen=True, slots=True)
class BattleAnimationTimingProfile:
    rules: tuple[BattleAnimationTimingRule, ...] = ()
    default_playback_rate: float = 1.0
    default_transition_duration: float = 0.0
    default_transition_easing: str = "linear"
    default_recovery_hold: float = 0.0

    SCHEMA = "asteria.battle_animation_timing_profile"
    VERSION = 1

    def __init__(
        self,
        rules=(),
        *,
        default_playback_rate=1.0,
        default_transition_duration=0.0,
        default_transition_easing="linear",
        default_recovery_hold=0.0,
    ):
        rules = tuple(
            x if isinstance(x, BattleAnimationTimingRule)
            else BattleAnimationTimingRule.from_data(x)
            for x in rules
        )
        if len({x.role for x in rules}) != len(rules):
            raise ValueError("duplicate animation timing role")
        _positive(default_playback_rate, "default_playback_rate")
        _nonnegative(default_transition_duration, "default_transition_duration")
        easing_value(default_transition_easing, 0.5)
        _nonnegative(default_recovery_hold, "default_recovery_hold")
        object.__setattr__(self, "rules", rules)
        object.__setattr__(self, "default_playback_rate", float(default_playback_rate))
        object.__setattr__(self, "default_transition_duration", float(default_transition_duration))
        object.__setattr__(self, "default_transition_easing", str(default_transition_easing).strip().lower())
        object.__setattr__(self, "default_recovery_hold", float(default_recovery_hold))

    def rule_for(self, role):
        role = str(role)
        found = next((x for x in self.rules if x.role == role), None)
        if found is not None:
            return found
        return BattleAnimationTimingRule(
            role,
            playback_rate=self.default_playback_rate,
            transition_duration=self.default_transition_duration,
            transition_easing=self.default_transition_easing,
            recovery_hold=self.default_recovery_hold,
        )

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "rules": [x.to_data() for x in self.rules],
            "default_playback_rate": self.default_playback_rate,
            "default_transition_duration": self.default_transition_duration,
            "default_transition_easing": self.default_transition_easing,
            "default_recovery_hold": self.default_recovery_hold,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported battle animation timing profile")
        return cls(
            data.get("rules", ()),
            default_playback_rate=data.get("default_playback_rate", 1.0),
            default_transition_duration=data.get("default_transition_duration", 0.0),
            default_transition_easing=data.get("default_transition_easing", "linear"),
            default_recovery_hold=data.get("default_recovery_hold", 0.0),
        )


@dataclass(frozen=True, slots=True)
class BattleHitRhythm:
    """Presentation-only helper for authored multi-hit cadence."""

    intervals: tuple[float, ...]
    accent_every: int = 0
    accent_delay: float = 0.0

    def __init__(self, intervals=(0.1,), *, accent_every=0, accent_delay=0.0):
        intervals = tuple(_nonnegative(x, "hit interval") for x in intervals)
        if not intervals:
            raise ValueError("hit rhythm requires at least one interval")
        accent_every = int(accent_every)
        if accent_every < 0:
            raise ValueError("accent_every must be >= 0")
        object.__setattr__(self, "intervals", intervals)
        object.__setattr__(self, "accent_every", accent_every)
        object.__setattr__(self, "accent_delay", _nonnegative(accent_delay, "accent_delay"))

    def offsets(self, hit_count):
        hit_count = int(hit_count)
        if hit_count < 0:
            raise ValueError("hit_count must be >= 0")
        if hit_count == 0:
            return ()
        values = [0.0]
        current = 0.0
        for index in range(1, hit_count):
            current += self.intervals[(index - 1) % len(self.intervals)]
            if self.accent_every and index % self.accent_every == 0:
                current += self.accent_delay
            values.append(current)
        return tuple(values)

    def to_data(self):
        return {
            "intervals": list(self.intervals),
            "accent_every": self.accent_every,
            "accent_delay": self.accent_delay,
        }

    @classmethod
    def from_data(cls, data):
        return cls(data.get("intervals", (0.1,)), accent_every=data.get("accent_every", 0), accent_delay=data.get("accent_delay", 0.0))
