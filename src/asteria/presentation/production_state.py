"""Versioned persistence for production Presentation subsystem state."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Any
import json
from .camera_runtime import CameraState
from .material_runtime import MaterialState, LightState
from .audio_runtime import AudioCue

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ProductionState:
    playhead_ms: float = 0
    camera: CameraState = CameraState()
    material: MaterialState = MaterialState()
    lights: tuple[LightState, ...] = ()
    audio_cues: tuple[AudioCue, ...] = ()
    vfx_properties: Mapping[str, float] | None = None
    audio_properties: Mapping[str, float] | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self):
        if self.playhead_ms < 0:
            raise ValueError("negative playhead")
        if len({x.id for x in self.lights}) != len(self.lights):
            raise ValueError("duplicate light id")
        if len({x.id for x in self.audio_cues}) != len(self.audio_cues):
            raise ValueError("duplicate audio cue id")


class ProductionStateCodec:
    @staticmethod
    def encode(s):
        return {
            "schema_version": SCHEMA_VERSION,
            "playhead_ms": s.playhead_ms,
            "camera": {
                "x": s.camera.x,
                "y": s.camera.y,
                "zoom": s.camera.zoom,
                "rotation_deg": s.camera.rotation_deg,
                "viewport_x": s.camera.viewport_x,
                "viewport_y": s.camera.viewport_y,
                "parameters": dict(s.camera.parameters or {}),
            },
            "material": {
                "material_asset_id": s.material.material_asset_id,
                "shader_asset_id": s.material.shader_asset_id,
                "parameters": dict(s.material.parameters),
            },
            "lights": [
                {
                    "id": x.id,
                    "kind": x.kind,
                    "x": x.x,
                    "y": x.y,
                    "intensity": x.intensity,
                    "radius": x.radius,
                    "rotation_deg": x.rotation_deg,
                    "parameters": dict(x.parameters),
                }
                for x in s.lights
            ],
            "audio_cues": [
                {
                    "id": x.id,
                    "asset_id": x.asset_id,
                    "start_ms": x.start_ms,
                    "bus": x.bus,
                    "volume": x.volume,
                    "pitch": x.pitch,
                    "loop": x.loop,
                    "parameters": dict(x.parameters or {}),
                }
                for x in s.audio_cues
            ],
            "vfx_properties": dict(s.vfx_properties or {}),
            "audio_properties": dict(s.audio_properties or {}),
            "metadata": dict(s.metadata or {}),
        }

    @staticmethod
    def decode(r):
        if int(r.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("unsupported production state schema")
        c = r.get("camera", {})
        m = r.get("material", {})
        return ProductionState(
            float(r.get("playhead_ms", 0)),
            CameraState(**c),
            MaterialState(m.get("material_asset_id"), m.get("shader_asset_id"), dict(m.get("parameters", {}))),
            tuple(LightState(**{**x, "parameters": dict(x.get("parameters", {}))}) for x in r.get("lights", ())),
            tuple(AudioCue(**{**x, "parameters": dict(x.get("parameters", {}))}) for x in r.get("audio_cues", ())),
            dict(r.get("vfx_properties", {})),
            dict(r.get("audio_properties", {})),
            dict(r.get("metadata", {})),
        )

    @classmethod
    def dumps(cls, s):
        return json.dumps(cls.encode(s), sort_keys=True, separators=(",", ":"))

    @classmethod
    def loads(cls, t):
        return cls.decode(json.loads(t))
