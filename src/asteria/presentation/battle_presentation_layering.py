from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .battle import BattlePresentationEvent, BattlePresentationEventKind


def _finite(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def _positive(value, label):
    value = _finite(value, label)
    if value <= 0:
        raise ValueError(f"{label} must be > 0")
    return value


@dataclass(frozen=True, slots=True)
class BattlePresentationChannelPolicy:
    channel: str
    layer: int = 0
    gain: float = 1.0
    bus: str = "default"

    def __post_init__(self):
        channel = str(self.channel).strip()
        if not channel:
            raise ValueError("channel is required")
        bus = str(self.bus).strip()
        if not bus:
            raise ValueError("bus is required")
        object.__setattr__(self, "channel", channel)
        object.__setattr__(self, "layer", int(self.layer))
        object.__setattr__(self, "gain", _positive(self.gain, "gain"))
        object.__setattr__(self, "bus", bus)

    def to_data(self):
        return {"channel": self.channel, "layer": self.layer, "gain": self.gain, "bus": self.bus}

    @classmethod
    def from_data(cls, data):
        return cls(**data)


@dataclass(frozen=True, slots=True)
class BattlePresentationLayeringProfile:
    channels: tuple[BattlePresentationChannelPolicy, ...] = ()

    SCHEMA = "asteria.battle_presentation_layering_profile"
    VERSION = 1

    def __init__(self, channels=()):
        channels = tuple(
            x
            if isinstance(x, BattlePresentationChannelPolicy)
            else BattlePresentationChannelPolicy.from_data(x)
            for x in channels
        )
        if len({x.channel for x in channels}) != len(channels):
            raise ValueError("duplicate presentation layering channel")
        object.__setattr__(self, "channels", channels)

    def policy_for(self, channel):
        channel = str(channel)
        return next(
            (x for x in self.channels if x.channel == channel),
            BattlePresentationChannelPolicy(channel),
        )

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "channels": [x.to_data() for x in self.channels],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported battle presentation layering profile")
        return cls(data.get("channels", ()))


@dataclass(frozen=True, slots=True)
class BattlePresentationLayerContext:
    group_id: str
    channel: str
    layer: int
    intensity: float
    gain: float
    bus: str
    priority: int


class BattlePresentationLayeringRuntime:
    """Decorates already-resolved presentation cues with shared staging context."""

    SCHEMA = "asteria.battle_presentation_layering_runtime"
    VERSION = 1

    def __init__(self, profile=None):
        self.profile = profile or BattlePresentationLayeringProfile()
        if not isinstance(self.profile, BattlePresentationLayeringProfile):
            raise TypeError("profile must be BattlePresentationLayeringProfile")
        self.last_sequence = 0

    @staticmethod
    def _channel(cue_kind):
        return {
            "vfx": "vfx",
            "audio": "audio",
            "camera": "camera",
            "screen_fx": "screen_fx",
            "light": "light",
            "animation": "animation",
        }.get(str(cue_kind), str(cue_kind) or "other")

    def process(self, events):
        result = []
        for event in tuple(events):
            if not isinstance(event, BattlePresentationEvent):
                raise TypeError("layering events must be BattlePresentationEvent")
            if event.sequence <= self.last_sequence:
                raise ValueError("layering events must be applied in increasing sequence order")
            self.last_sequence = event.sequence
            if event.kind != BattlePresentationEventKind.TIMELINE_CUE:
                result.append(event)
                continue

            outer = dict(event.payload)
            cue = dict(outer.get("cue", {}))
            payload = dict(cue.get("payload", {}) or {})
            staging = dict(payload.get("staging", {}) or {})
            channel = self._channel(cue.get("kind", ""))
            policy = self.profile.policy_for(channel)

            intensity = _positive(staging.get("intensity", 1.0), "staging intensity")
            gain = _positive(staging.get("gain", policy.gain), "staging gain")
            layer = int(staging.get("layer", policy.layer))
            priority = int(staging.get("priority", 0))
            group_id = (
                str(staging.get("group_id", outer.get("timeline_id", "default"))).strip()
                or "default"
            )
            bus = str(staging.get("bus", policy.bus)).strip() or policy.bus

            payload["staging"] = {
                "group_id": group_id,
                "channel": channel,
                "layer": layer,
                "intensity": intensity,
                "gain": gain,
                "bus": bus,
                "priority": priority,
            }

            # Channel-specific presentation scaling. Only copied cue payload changes.
            if channel == "camera":
                if "amplitude" in payload:
                    payload["amplitude"] = (
                        _finite(payload["amplitude"], "camera amplitude") * intensity * gain
                    )
                if "amplitude_x" in payload:
                    payload["amplitude_x"] = (
                        _finite(payload["amplitude_x"], "camera amplitude_x") * intensity * gain
                    )
                if "amplitude_y" in payload:
                    payload["amplitude_y"] = (
                        _finite(payload["amplitude_y"], "camera amplitude_y") * intensity * gain
                    )
            elif channel == "audio":
                payload["gain"] = gain * intensity
                payload["bus"] = bus
            else:
                payload["intensity"] = intensity * gain
                payload["layer"] = layer

            cue["payload"] = payload
            outer["cue"] = cue
            result.append(
                BattlePresentationEvent(event.sequence, event.kind, event.source_id, outer)
            )
        return tuple(result)

    def context_for_event(self, event):
        if event.kind != BattlePresentationEventKind.TIMELINE_CUE:
            return None
        cue = dict(event.payload.get("cue", {}))
        payload = dict(cue.get("payload", {}) or {})
        staging = dict(payload.get("staging", {}) or {})
        if not staging:
            return None
        return BattlePresentationLayerContext(
            str(staging["group_id"]),
            str(staging["channel"]),
            int(staging["layer"]),
            float(staging["intensity"]),
            float(staging["gain"]),
            str(staging["bus"]),
            int(staging["priority"]),
        )

    def snapshot(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "profile": self.profile.to_data(),
            "last_sequence": self.last_sequence,
        }

    def restore(self, data):
        if data.get("schema") != self.SCHEMA or data.get("version") != self.VERSION:
            raise ValueError("unsupported battle presentation layering snapshot")
        if BattlePresentationLayeringProfile.from_data(data["profile"]) != self.profile:
            raise ValueError("battle presentation layering profile mismatch")
        self.last_sequence = int(data["last_sequence"])
        if self.last_sequence < 0:
            raise ValueError("invalid layering sequence")
        return self
