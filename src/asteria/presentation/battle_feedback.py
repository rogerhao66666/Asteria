from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite

from asteria.gameplay.action_timeline import ActionCueKind
from asteria.rpg.gauge_composition import GaugeCompositionResult
from asteria.rpg.interactions import (
    InteractionDisposition,
    OutcomeResolutionResult,
    ValueResolutionResult,
)

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


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


class BattleValueKind(str, Enum):
    DAMAGE = "damage"
    HEAL = "heal"
    RESOURCE = "resource"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class BattleFeedbackProfile:
    """Project-authored mapping from resolved mechanics to presentation labels.

    Presentation never infers RPG semantics. A game may map any outcome tag or
    gauge threshold id to any label (WEAK, RESIST, BREAK, STAGGER, etc.).
    """

    outcome_tag_labels: tuple[tuple[str, str], ...] = ()
    disposition_labels: tuple[tuple[str, str], ...] = ()
    threshold_labels: tuple[tuple[str, str], ...] = ()
    value_duration: float = 0.9
    label_duration: float = 0.65
    vfx_default_duration: float = 0.5

    def __init__(
        self,
        *,
        outcome_tag_labels=None,
        disposition_labels=None,
        threshold_labels=None,
        value_duration=0.9,
        label_duration=0.65,
        vfx_default_duration=0.5,
    ):
        def pairs(values, label):
            result = []
            for key, value in dict(values or {}).items():
                result.append((_id(key, f"{label} key"), _id(value, f"{label} value")))
            return tuple(sorted(result))

        object.__setattr__(self, "outcome_tag_labels", pairs(outcome_tag_labels, "outcome label"))
        object.__setattr__(self, "disposition_labels", pairs(disposition_labels, "disposition label"))
        object.__setattr__(self, "threshold_labels", pairs(threshold_labels, "threshold label"))
        object.__setattr__(self, "value_duration", _positive(value_duration, "value_duration"))
        object.__setattr__(self, "label_duration", _positive(label_duration, "label_duration"))
        object.__setattr__(self, "vfx_default_duration", _positive(vfx_default_duration, "vfx_default_duration"))

    def labels_for(self, *, outcome_tags=(), disposition=None):
        tag_map = dict(self.outcome_tag_labels)
        disposition_map = dict(self.disposition_labels)
        labels = [tag_map[tag] for tag in sorted(set(map(str, outcome_tags))) if tag in tag_map]
        if disposition is not None:
            key = getattr(disposition, "value", str(disposition))
            if key in disposition_map:
                labels.append(disposition_map[key])
        return tuple(dict.fromkeys(labels))

    def threshold_label(self, threshold_id):
        return dict(self.threshold_labels).get(str(threshold_id))

    def to_data(self):
        return {
            "schema": "asteria.battle_feedback_profile",
            "version": 1,
            "outcome_tag_labels": dict(self.outcome_tag_labels),
            "disposition_labels": dict(self.disposition_labels),
            "threshold_labels": dict(self.threshold_labels),
            "value_duration": self.value_duration,
            "label_duration": self.label_duration,
            "vfx_default_duration": self.vfx_default_duration,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.battle_feedback_profile" or data.get("version") != 1:
            raise ValueError("unsupported battle feedback profile")
        return cls(
            outcome_tag_labels=data.get("outcome_tag_labels", {}),
            disposition_labels=data.get("disposition_labels", {}),
            threshold_labels=data.get("threshold_labels", {}),
            value_duration=data.get("value_duration", 0.9),
            label_duration=data.get("label_duration", 0.65),
            vfx_default_duration=data.get("vfx_default_duration", 0.5),
        )


@dataclass(frozen=True, slots=True)
class BattleFloatingValue:
    sequence: int
    target_id: str
    source_id: str
    value: float
    kind: BattleValueKind
    outcome_tags: tuple[str, ...]
    disposition: str
    age: float
    duration: float

    @property
    def expired(self):
        return self.age >= self.duration


@dataclass(frozen=True, slots=True)
class BattleFeedbackLabel:
    sequence: int
    target_id: str
    label: str
    reason_id: str
    age: float
    duration: float

    @property
    def expired(self):
        return self.age >= self.duration


@dataclass(frozen=True, slots=True)
class BattleVfxCue:
    sequence: int
    cue_id: str
    member_id: str
    payload: dict
    age: float
    duration: float

    @property
    def expired(self):
        return self.age >= self.duration


@dataclass(frozen=True, slots=True)
class BattleAudioCue:
    sequence: int
    cue_id: str
    member_id: str
    payload: dict


class BattleFeedbackRuntime:
    """Deterministic presentation-only state for resolved combat feedback."""

    def __init__(self, profile: BattleFeedbackProfile | None = None):
        self.profile = profile or BattleFeedbackProfile()
        self.time = 0.0
        self.last_sequence = 0
        self.values: list[BattleFloatingValue] = []
        self.labels: list[BattleFeedbackLabel] = []
        self.vfx: list[BattleVfxCue] = []
        self._audio_pending: list[BattleAudioCue] = []

    @staticmethod
    def _member_id(payload):
        for key in ("member_id", "target_id", "source_id", "combatant_id"):
            value = str(payload.get(key, "")).strip()
            if value:
                return value
        return ""

    def _apply_timeline(self, event):
        cue = dict(event.payload.get("cue", {}))
        kind = cue.get("kind")
        payload = dict(cue.get("payload", {}))
        member_id = self._member_id(payload)
        if kind == ActionCueKind.VFX.value:
            duration = _positive(payload.get("duration", self.profile.vfx_default_duration), "vfx duration")
            self.vfx.append(BattleVfxCue(event.sequence, str(cue.get("cue_id", "")), member_id, payload, 0.0, duration))
            return True
        if kind == ActionCueKind.AUDIO.value:
            self._audio_pending.append(BattleAudioCue(event.sequence, str(cue.get("cue_id", "")), member_id, payload))
            return True
        return False

    def _apply_resolved_value(self, event):
        payload = event.payload
        value = _finite(payload["value"], "resolved presentation value")
        kind = BattleValueKind(payload.get("value_kind", BattleValueKind.DAMAGE.value))
        tags = tuple(sorted(set(map(str, payload.get("outcome_tags", ())))))
        disposition = str(payload.get("disposition", InteractionDisposition.NORMAL.value))
        target_id = _id(payload["target_id"], "target_id")
        source_id = str(payload.get("source_id", ""))
        duration = _positive(payload.get("duration", self.profile.value_duration), "value duration")
        self.values.append(
            BattleFloatingValue(event.sequence, target_id, source_id, value, kind, tags, disposition, 0.0, duration)
        )
        for label in self.profile.labels_for(outcome_tags=tags, disposition=disposition):
            self.labels.append(
                BattleFeedbackLabel(
                    event.sequence, target_id, label, f"interaction:{disposition}", 0.0, self.profile.label_duration
                )
            )
        return True

    def _apply_gauge_threshold(self, event):
        payload = event.payload
        label = self.profile.threshold_label(payload.get("threshold_id", ""))
        if not label:
            return False
        self.labels.append(
            BattleFeedbackLabel(
                event.sequence,
                _id(payload["member_id"], "member_id"),
                label,
                f"threshold:{payload['threshold_id']}",
                0.0,
                self.profile.label_duration,
            )
        )
        return True

    def apply_event(self, event: BattlePresentationEvent):
        if not isinstance(event, BattlePresentationEvent):
            raise TypeError("event must be BattlePresentationEvent")
        if event.sequence <= self.last_sequence:
            raise ValueError("presentation feedback events must be applied in increasing sequence order")
        self.last_sequence = event.sequence
        if event.kind == BattlePresentationEventKind.TIMELINE_CUE:
            return self._apply_timeline(event)
        if event.kind == BattlePresentationEventKind.RESOLVED_VALUE:
            return self._apply_resolved_value(event)
        if event.kind == BattlePresentationEventKind.GAUGE_THRESHOLD:
            return self._apply_gauge_threshold(event)
        return False

    def apply_events(self, events):
        return tuple(self.apply_event(event) for event in events)

    def update(self, dt):
        dt = _finite(dt, "dt")
        if dt < 0:
            raise ValueError("dt must be >= 0")
        self.time += dt
        self.values = [replace(x, age=x.age + dt) for x in self.values if x.age + dt < x.duration]
        self.labels = [replace(x, age=x.age + dt) for x in self.labels if x.age + dt < x.duration]
        self.vfx = [replace(x, age=x.age + dt) for x in self.vfx if x.age + dt < x.duration]

    def drain_audio(self):
        def key(item):
            staging = dict(item.payload.get("staging", {}) or {})
            return (
                -int(staging.get("priority", 0)),
                int(staging.get("layer", 0)),
                item.sequence,
            )

        result = tuple(sorted(self._audio_pending, key=key))
        self._audio_pending.clear()
        return result

    def snapshot(self):
        return {
            "schema": "asteria.battle_feedback_runtime",
            "version": 1,
            "time": self.time,
            "last_sequence": self.last_sequence,
            "values": [
                {
                    "sequence": x.sequence,
                    "target_id": x.target_id,
                    "source_id": x.source_id,
                    "value": x.value,
                    "kind": x.kind.value,
                    "outcome_tags": list(x.outcome_tags),
                    "disposition": x.disposition,
                    "age": x.age,
                    "duration": x.duration,
                }
                for x in self.values
            ],
            "labels": [
                {
                    "sequence": x.sequence,
                    "target_id": x.target_id,
                    "label": x.label,
                    "reason_id": x.reason_id,
                    "age": x.age,
                    "duration": x.duration,
                }
                for x in self.labels
            ],
            "vfx": [
                {
                    "sequence": x.sequence,
                    "cue_id": x.cue_id,
                    "member_id": x.member_id,
                    "payload": dict(x.payload),
                    "age": x.age,
                    "duration": x.duration,
                }
                for x in self.vfx
            ],
            "audio_pending": [
                {
                    "sequence": x.sequence,
                    "cue_id": x.cue_id,
                    "member_id": x.member_id,
                    "payload": dict(x.payload),
                }
                for x in self._audio_pending
            ],
        }

    def restore(self, data):
        if data.get("schema") != "asteria.battle_feedback_runtime" or data.get("version") != 1:
            raise ValueError("unsupported battle feedback runtime snapshot")
        self.time = _finite(data["time"], "time")
        self.last_sequence = int(data["last_sequence"])
        self.values = [
            BattleFloatingValue(
                int(x["sequence"]),
                str(x["target_id"]),
                str(x.get("source_id", "")),
                _finite(x["value"], "value"),
                BattleValueKind(x["kind"]),
                tuple(x.get("outcome_tags", ())),
                str(x.get("disposition", "normal")),
                _finite(x["age"], "age"),
                _positive(x["duration"], "duration"),
            )
            for x in data.get("values", ())
        ]
        self.labels = [
            BattleFeedbackLabel(
                int(x["sequence"]),
                str(x["target_id"]),
                str(x["label"]),
                str(x["reason_id"]),
                _finite(x["age"], "age"),
                _positive(x["duration"], "duration"),
            )
            for x in data.get("labels", ())
        ]
        self.vfx = [
            BattleVfxCue(
                int(x["sequence"]),
                str(x["cue_id"]),
                str(x.get("member_id", "")),
                dict(x.get("payload", {})),
                _finite(x["age"], "age"),
                _positive(x["duration"], "duration"),
            )
            for x in data.get("vfx", ())
        ]
        self._audio_pending = [
            BattleAudioCue(
                int(x["sequence"]), str(x["cue_id"]), str(x.get("member_id", "")), dict(x.get("payload", {}))
            )
            for x in data.get("audio_pending", ())
        ]


def resolved_value_payload(result, *, target_id, source_id="", value_kind=BattleValueKind.DAMAGE, duration=None):
    """Convert an already-resolved interaction result into presentation primitives."""
    if isinstance(result, OutcomeResolutionResult):
        tags = result.outcome_tags
        value_result = result.value
    elif isinstance(result, ValueResolutionResult):
        tags = result.outcome_tags
        value_result = result
    else:
        raise TypeError("result must be ValueResolutionResult or OutcomeResolutionResult")
    payload = {
        "target_id": _id(target_id, "target_id"),
        "source_id": str(source_id),
        "value": value_result.resolved_value,
        "value_kind": BattleValueKind(value_kind).value,
        "outcome_tags": list(tags),
        "disposition": value_result.disposition.value,
        "matched_rules": list(value_result.matched_rules),
    }
    if duration is not None:
        payload["duration"] = _positive(duration, "duration")
    return payload


def gauge_threshold_payloads(result):
    """Flatten already-resolved gauge thresholds without evaluating any rule."""
    if not isinstance(result, GaugeCompositionResult):
        raise TypeError("result must be GaugeCompositionResult")
    return tuple(
        {
            "composition_id": result.composition_id,
            "threshold_id": item.threshold_id,
            "member_id": item.member_id,
            "resource_id": item.resource_id,
            "before": item.before,
            "after": item.after,
            "state_applied": item.state_applied,
            "timeline_shift": item.timeline_shift,
            "reset_to": item.reset_to,
            "emitted_trigger": item.emitted_trigger,
        }
        for item in result.thresholds
    )
