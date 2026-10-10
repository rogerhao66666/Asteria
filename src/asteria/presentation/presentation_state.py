"""Versioned persistence for generic composable presentation state."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Mapping
import json
from .attachments import SocketRig, Attachment, GripTransform, Transform2D, validate_attachments
from .attachment_runtime import AttachmentRuntime, AttachmentState
from .property_animation import Ease, PropertyKey, PropertyCurve, Oscillator, Envelope, Modulation, PropertyAnimator

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class AttachmentRecord:
    spec: Attachment
    state: AttachmentState = AttachmentState.ACTIVE
    runtime_data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PresentationState:
    rig: SocketRig
    attachments: tuple[AttachmentRecord, ...] = ()
    curves: tuple[PropertyCurve, ...] = ()
    modulations: tuple[Modulation, ...] = ()
    playhead_ms: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.playhead_ms < 0:
            raise ValueError("negative playhead")
        ids = [r.spec.id for r in self.attachments]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate attachment id")
        validate_attachments(self.rig, (r.spec for r in self.attachments))


def _attachment_dict(a: Attachment):
    return {
        "id": a.id,
        "asset_id": a.asset_id,
        "socket_id": a.socket_id,
        "local": asdict(a.local),
        "inherit_position": a.inherit_position,
        "inherit_rotation": a.inherit_rotation,
        "inherit_scale": a.inherit_scale,
        "inherit_opacity": a.inherit_opacity,
        "metadata": dict(a.metadata),
        "grip": asdict(a.grip),
        "render_layer": a.render_layer,
    }


def _attachment(raw):
    return Attachment(
        str(raw["id"]),
        str(raw["asset_id"]),
        str(raw["socket_id"]),
        Transform2D(**raw.get("local", {})),
        bool(raw.get("inherit_position", True)),
        bool(raw.get("inherit_rotation", True)),
        bool(raw.get("inherit_scale", True)),
        bool(raw.get("inherit_opacity", True)),
        dict(raw.get("metadata", {})),
        GripTransform(**raw.get("grip", {})),
        str(raw.get("render_layer", "attachment")),
    )


def _curve_dict(c):
    return {
        "target": c.target,
        "keys": [{"time_ms": k.time_ms, "value": k.value, "ease": k.ease.value} for k in c.keys],
    }


def _curve(raw):
    return PropertyCurve(
        str(raw["target"]),
        tuple(PropertyKey(float(k["time_ms"]), float(k["value"]), Ease(k.get("ease", "linear"))) for k in raw["keys"]),
    )


def _mod_dict(m):
    return {
        "target": m.target,
        "mode": m.mode,
        "oscillator": {
            "amplitude": m.oscillator.amplitude,
            "frequency_hz": m.oscillator.frequency_hz,
            "phase": m.oscillator.phase,
            "waveform": m.oscillator.waveform,
        },
        "envelope": {
            "duration_ms": m.envelope.duration_ms,
            "attack_ms": m.envelope.attack_ms,
            "decay_power": m.envelope.decay_power,
        },
    }


def _mod(raw):
    o, e = raw["oscillator"], raw["envelope"]
    return Modulation(
        str(raw["target"]),
        Oscillator(
            float(o["amplitude"]), float(o["frequency_hz"]), float(o.get("phase", 0)), str(o.get("waveform", "sine"))
        ),
        Envelope(float(e["duration_ms"]), float(e.get("attack_ms", 0)), float(e.get("decay_power", 1))),
        str(raw.get("mode", "add")),
    )


class PresentationStateCodec:
    @staticmethod
    def encode(s: PresentationState):
        return {
            "schema_version": SCHEMA_VERSION,
            "rig": s.rig.to_dict(),
            "attachments": [
                {"spec": _attachment_dict(r.spec), "state": r.state.value, "runtime_data": dict(r.runtime_data)}
                for r in s.attachments
            ],
            "curves": [_curve_dict(c) for c in s.curves],
            "modulations": [_mod_dict(m) for m in s.modulations],
            "playhead_ms": s.playhead_ms,
            "metadata": dict(s.metadata),
        }

    @staticmethod
    def decode(raw):
        if int(raw.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("unsupported presentation state schema")
        return PresentationState(
            SocketRig.from_dict(raw["rig"]),
            tuple(
                AttachmentRecord(
                    _attachment(x["spec"]), AttachmentState(x.get("state", "active")), dict(x.get("runtime_data", {}))
                )
                for x in raw.get("attachments", ())
            ),
            tuple(_curve(x) for x in raw.get("curves", ())),
            tuple(_mod(x) for x in raw.get("modulations", ())),
            float(raw.get("playhead_ms", 0)),
            dict(raw.get("metadata", {})),
        )

    @classmethod
    def dumps(cls, s):
        return json.dumps(cls.encode(s), sort_keys=True, separators=(",", ":"))

    @classmethod
    def loads(cls, text):
        return cls.decode(json.loads(text))


def capture_state(runtime, animator=PropertyAnimator(), playhead_ms=0.0, metadata=None):
    records = tuple(
        AttachmentRecord(i.spec, i.state, dict(i.runtime_data)) for _, i in sorted(runtime.instances.items())
    )
    return PresentationState(
        runtime.rig, records, animator.curves, animator.modulations, float(playhead_ms), metadata or {}
    )


def restore_state(state):
    runtime = AttachmentRuntime(state.rig)
    for r in state.attachments:
        inst = runtime.attach(r.spec)
        inst.runtime_data = dict(r.runtime_data)
        if r.state is AttachmentState.HIDDEN:
            runtime.set_visible(r.spec.id, False)
        elif r.state is AttachmentState.DETACHED:
            runtime.detach(r.spec.id)
    return runtime, PropertyAnimator(state.curves, state.modulations)
