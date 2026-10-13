from __future__ import annotations

from dataclasses import dataclass, replace
from math import floor, isfinite

from asteria.gameplay.action_timeline import ActionCueKind
from asteria.runtime import Camera2D

from .battle import BattlePresentationEvent, BattlePresentationEventKind, BattlePresentationScene


def _finite(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def _nonnegative(value, label):
    value = _finite(value, label)
    if value < 0:
        raise ValueError(f"{label} must be >= 0")
    return value


def _positive(value, label):
    value = _finite(value, label)
    if value <= 0:
        raise ValueError(f"{label} must be > 0")
    return value


@dataclass(frozen=True, slots=True)
class BattleCameraImpulse:
    sequence: int
    cue_id: str
    amplitude_x: float
    amplitude_y: float
    frequency: float
    age: float
    duration: float

    def offset(self):
        progress = min(1.0, self.age / self.duration)
        envelope = 1.0 - progress
        phase = int(floor(self.age * self.frequency * 2.0))
        sign = -1.0 if phase % 2 else 1.0
        return self.amplitude_x * envelope * sign, self.amplitude_y * envelope * sign


@dataclass(frozen=True, slots=True)
class BattleScreenFxCue:
    sequence: int
    cue_id: str
    effect: str
    payload: dict
    age: float
    duration: float


@dataclass(frozen=True, slots=True)
class BattleTargetIndicator:
    member_id: str
    primary: bool
    world_x: float
    world_y: float
    screen_x: float
    screen_y: float


@dataclass(frozen=True, slots=True)
class BattleCameraFeedbackFrame:
    offset_x: float
    offset_y: float
    screen_fx: tuple[BattleScreenFxCue, ...]
    targets: tuple[BattleTargetIndicator, ...]


class BattleCameraFeedbackRuntime:
    """Presentation-only camera/screen/target state.

    CAMERA and SCREEN_FX ActionTimeline cues are consumed as already-authored
    presentation instructions. Target IDs are mirrored from canonical selection
    state; no target legality, Battle Core rule, damage, or turn state is resolved
    here.
    """

    def __init__(self, scene: BattlePresentationScene):
        if not isinstance(scene, BattlePresentationScene):
            raise TypeError("scene must be BattlePresentationScene")
        self.scene = scene
        self.time = 0.0
        self.last_sequence = 0
        self.impulses: list[BattleCameraImpulse] = []
        self.screen_fx: list[BattleScreenFxCue] = []
        self.target_ids: tuple[str, ...] = ()
        self.primary_target_id: str | None = None

    def _apply_timeline(self, event):
        cue = dict(event.payload.get("cue", {}))
        kind = cue.get("kind")
        payload = dict(cue.get("payload", {}))
        cue_id = str(cue.get("cue_id", ""))
        if kind == ActionCueKind.CAMERA.value:
            effect = str(payload.get("effect", "shake"))
            if effect not in {"shake", "impulse", "hit_shake"}:
                return False
            duration = _positive(payload.get("duration", 0.16), "camera duration")
            amplitude = _finite(payload.get("amplitude", 0.0), "camera amplitude")
            ax = _finite(payload.get("amplitude_x", amplitude), "camera amplitude_x")
            ay = _finite(payload.get("amplitude_y", amplitude), "camera amplitude_y")
            frequency = _positive(payload.get("frequency", 18.0), "camera frequency")
            self.impulses.append(
                BattleCameraImpulse(event.sequence, cue_id, ax, ay, frequency, 0.0, duration)
            )
            return True
        if kind == ActionCueKind.SCREEN_FX.value:
            effect = str(payload.get("effect", "custom")).strip() or "custom"
            duration = _positive(payload.get("duration", 0.1), "screen effect duration")
            self.screen_fx.append(
                BattleScreenFxCue(event.sequence, cue_id, effect, payload, 0.0, duration)
            )
            return True
        return False

    def _apply_target_selection(self, event):
        raw = tuple(str(x) for x in event.payload.get("target_ids", ()))
        if len(raw) != len(set(raw)):
            raise ValueError("duplicate target_ids in presentation event")
        primary = event.payload.get("primary_target_id")
        primary = None if primary is None else str(primary)
        if primary is not None and primary not in raw:
            raise ValueError("primary target must be included in target_ids")
        self.target_ids = raw
        self.primary_target_id = primary
        return True

    def apply_event(self, event: BattlePresentationEvent):
        if not isinstance(event, BattlePresentationEvent):
            raise TypeError("event must be BattlePresentationEvent")
        if event.sequence <= self.last_sequence:
            raise ValueError("camera feedback events must be applied in increasing sequence order")
        self.last_sequence = event.sequence
        if event.kind == BattlePresentationEventKind.TIMELINE_CUE:
            return self._apply_timeline(event)
        if event.kind == BattlePresentationEventKind.TARGET_SELECTION:
            return self._apply_target_selection(event)
        return False

    def apply_events(self, events):
        return tuple(self.apply_event(x) for x in events)

    def update(self, dt):
        dt = _nonnegative(dt, "dt")
        self.time += dt
        self.impulses = [
            replace(x, age=x.age + dt) for x in self.impulses if x.age + dt < x.duration
        ]
        self.screen_fx = [
            replace(x, age=x.age + dt) for x in self.screen_fx if x.age + dt < x.duration
        ]

    def camera_offset(self):
        x = y = 0.0
        for impulse in self.impulses:
            dx, dy = impulse.offset()
            x += dx
            y += dy
        return x, y

    def camera_view(self, base_camera: Camera2D):
        if not isinstance(base_camera, Camera2D):
            raise TypeError("base_camera must be Camera2D")
        dx, dy = self.camera_offset()
        # World-space camera translation; the canonical/base camera remains untouched.
        return Camera2D(
            base_camera.x + dx,
            base_camera.y + dy,
            base_camera.width,
            base_camera.height,
            base_camera.zoom,
        )

    def build_frame(self, base_camera: Camera2D):
        view = self.camera_view(base_camera)
        indicators = []
        for member_id in self.target_ids:
            try:
                visual = self.scene.visual_for(member_id)
            except KeyError:
                # Selection may legitimately reference a combatant with no current visual.
                continue
            sx, sy = view.world_to_screen(visual.anchor.x, visual.anchor.y)
            indicators.append(
                BattleTargetIndicator(
                    member_id,
                    member_id == self.primary_target_id,
                    visual.anchor.x,
                    visual.anchor.y,
                    sx,
                    sy,
                )
            )
        dx, dy = self.camera_offset()
        ordered_fx = tuple(
            sorted(
                self.screen_fx,
                key=lambda item: (
                    int(dict(item.payload.get("staging", {}) or {}).get("layer", 0)),
                    -int(dict(item.payload.get("staging", {}) or {}).get("priority", 0)),
                    item.sequence,
                ),
            )
        )
        return BattleCameraFeedbackFrame(dx, dy, ordered_fx, tuple(indicators))

    def snapshot(self):
        return {
            "schema": "asteria.battle_camera_feedback_runtime",
            "version": 1,
            "scene_id": self.scene.scene_id,
            "time": self.time,
            "last_sequence": self.last_sequence,
            "target_ids": list(self.target_ids),
            "primary_target_id": self.primary_target_id,
            "impulses": [
                {
                    "sequence": x.sequence,
                    "cue_id": x.cue_id,
                    "amplitude_x": x.amplitude_x,
                    "amplitude_y": x.amplitude_y,
                    "frequency": x.frequency,
                    "age": x.age,
                    "duration": x.duration,
                }
                for x in self.impulses
            ],
            "screen_fx": [
                {
                    "sequence": x.sequence,
                    "cue_id": x.cue_id,
                    "effect": x.effect,
                    "payload": dict(x.payload),
                    "age": x.age,
                    "duration": x.duration,
                }
                for x in self.screen_fx
            ],
        }

    def restore(self, data):
        if (
            data.get("schema") != "asteria.battle_camera_feedback_runtime"
            or data.get("version") != 1
        ):
            raise ValueError("unsupported battle camera feedback snapshot")
        if data.get("scene_id") != self.scene.scene_id:
            raise ValueError("battle camera feedback scene mismatch")
        self.time = _nonnegative(data["time"], "time")
        self.last_sequence = int(data["last_sequence"])
        if self.last_sequence < 0:
            raise ValueError("last_sequence must be >= 0")
        self.target_ids = tuple(str(x) for x in data.get("target_ids", ()))
        primary = data.get("primary_target_id")
        self.primary_target_id = None if primary is None else str(primary)
        if self.primary_target_id is not None and self.primary_target_id not in self.target_ids:
            raise ValueError("primary target missing from restored target_ids")
        self.impulses = [
            BattleCameraImpulse(
                int(x["sequence"]),
                str(x["cue_id"]),
                _finite(x["amplitude_x"], "amplitude_x"),
                _finite(x["amplitude_y"], "amplitude_y"),
                _positive(x["frequency"], "frequency"),
                _nonnegative(x["age"], "age"),
                _positive(x["duration"], "duration"),
            )
            for x in data.get("impulses", ())
        ]
        self.screen_fx = [
            BattleScreenFxCue(
                int(x["sequence"]),
                str(x["cue_id"]),
                str(x["effect"]),
                dict(x.get("payload", {})),
                _nonnegative(x["age"], "age"),
                _positive(x["duration"], "duration"),
            )
            for x in data.get("screen_fx", ())
        ]
