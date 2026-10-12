from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from .abilities import AbilityRuntime, AbilityTarget


class ActionCueKind(str, Enum):
    GAMEPLAY_ABILITY = "gameplay_ability"
    ANIMATION = "animation"
    VFX = "vfx"
    AUDIO = "audio"
    CAMERA = "camera"
    LIGHT = "light"
    SCREEN_FX = "screen_fx"
    # ANI-05 (ASTERIA_SPEC §11): gameplay windows an entity action timeline drives
    MOVEMENT = "movement"  # payload: x, y (intent), duration
    HITBOX = "hitbox"  # payload: duration, hit_tag
    IFRAME = "iframe"  # payload: duration
    CANCEL_WINDOW = "cancel_window"  # payload: duration
    COMBO_WINDOW = "combo_window"  # payload: duration, next (optional follow-up timeline id)
    GAMEPLAY_EVENT = "gameplay_event"  # payload: name, ...
    ARMOR = "armor"  # payload: duration, level (default 1) — super armor while the action runs


@dataclass(frozen=True, slots=True)
class ActionCue:
    cue_id: str
    time: float
    kind: ActionCueKind
    payload: dict

    def __init__(self, cue_id, time, kind, payload=None):
        cue_id = str(cue_id).strip()
        if not cue_id:
            raise ValueError("cue_id is required")
        time = float(time)
        if not isfinite(time) or time < 0:
            raise ValueError("cue time must be finite and >= 0")
        payload = dict(payload or {})
        object.__setattr__(self, "cue_id", cue_id)
        object.__setattr__(self, "time", time)
        object.__setattr__(self, "kind", ActionCueKind(kind))
        object.__setattr__(self, "payload", payload)

    def to_data(self):
        return {
            "cue_id": self.cue_id,
            "time": self.time,
            "kind": self.kind.value,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"cue_id", "time", "kind", "payload"}:
            raise ValueError("invalid action cue")
        return cls(data["cue_id"], data["time"], data["kind"], data["payload"])


@dataclass(frozen=True, slots=True)
class ActionTimeline:
    timeline_id: str
    cues: tuple[ActionCue, ...]

    def __init__(self, timeline_id, cues=()):
        timeline_id = str(timeline_id).strip()
        if not timeline_id:
            raise ValueError("timeline_id is required")
        cues = tuple(cues)
        if any(not isinstance(x, ActionCue) for x in cues):
            raise TypeError("cues must be ActionCue")
        ids = [x.cue_id for x in cues]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate cue_id")
        object.__setattr__(self, "timeline_id", timeline_id)
        object.__setattr__(self, "cues", tuple(sorted(cues, key=lambda x: (x.time, x.cue_id))))

    @property
    def duration(self):
        return self.cues[-1].time if self.cues else 0.0

    def to_data(self):
        return {
            "schema": "asteria.action_timeline",
            "version": 1,
            "timeline_id": self.timeline_id,
            "cues": [x.to_data() for x in self.cues],
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"schema", "version", "timeline_id", "cues"}:
            raise ValueError("invalid timeline")
        if data["schema"] != "asteria.action_timeline" or data["version"] != 1:
            raise ValueError("unsupported timeline")
        return cls(data["timeline_id"], [ActionCue.from_data(x) for x in data["cues"]])


@dataclass(frozen=True, slots=True)
class PresentationCue:
    timeline_id: str
    cue: ActionCue


@dataclass(frozen=True, slots=True)
class TimelineAdvanceResult:
    gameplay_results: tuple
    presentation_cues: tuple[PresentationCue, ...]
    completed: bool


class ActionTimelinePlayer:
    """Deterministic backend-neutral timeline player.

    Gameplay cues invoke AbilityRuntime. Presentation cues are emitted as data
    for renderer/audio/editor adapters. No Qt, pygame, clock or animation backend
    belongs here.
    """

    def __init__(
        self,
        timeline: ActionTimeline,
        ability_runtime: AbilityRuntime,
        source: AbilityTarget,
        targets=(),
    ):
        if not isinstance(timeline, ActionTimeline):
            raise TypeError("timeline must be ActionTimeline")
        if not isinstance(ability_runtime, AbilityRuntime):
            raise TypeError("ability_runtime must be AbilityRuntime")
        self.timeline = timeline
        self.ability_runtime = ability_runtime
        self.source = source
        self.targets = tuple(targets)
        self.time = 0.0
        self._next = 0
        self.completed = False

    def advance(self, dt):
        dt = float(dt)
        if not isfinite(dt) or dt < 0:
            raise ValueError("dt must be finite and >= 0")
        if self.completed:
            return TimelineAdvanceResult((), (), True)
        end = self.time + dt
        gameplay = []
        presentation = []
        while self._next < len(self.timeline.cues):
            cue = self.timeline.cues[self._next]
            if cue.time > end:
                break
            self._next += 1
            if cue.kind == ActionCueKind.GAMEPLAY_ABILITY:
                ability_id = str(cue.payload.get("ability_id", "")).strip()
                if not ability_id:
                    raise ValueError("gameplay ability cue requires ability_id")
                gameplay.append(self.ability_runtime.execute(ability_id, self.source, self.targets))
            else:
                presentation.append(PresentationCue(self.timeline.timeline_id, cue))
        self.time = end
        self.completed = self._next >= len(self.timeline.cues) and self.time >= self.timeline.duration
        return TimelineAdvanceResult(tuple(gameplay), tuple(presentation), self.completed)

    def snapshot(self):
        return {
            "schema": "asteria.action_timeline_player",
            "version": 1,
            "timeline_id": self.timeline.timeline_id,
            "time": self.time,
            "next_index": self._next,
            "completed": self.completed,
        }

    def restore(self, data):
        expected = {
            "schema",
            "version",
            "timeline_id",
            "time",
            "next_index",
            "completed",
        }
        if set(data) != expected:
            raise ValueError("invalid timeline snapshot")
        if data["schema"] != "asteria.action_timeline_player" or data["version"] != 1:
            raise ValueError("unsupported timeline snapshot")
        if data["timeline_id"] != self.timeline.timeline_id:
            raise ValueError("timeline mismatch")
        time = float(data["time"])
        idx = int(data["next_index"])
        if not isfinite(time) or time < 0 or idx < 0 or idx > len(self.timeline.cues):
            raise ValueError("invalid timeline progress")
        self.time = time
        self._next = idx
        self.completed = bool(data["completed"])
