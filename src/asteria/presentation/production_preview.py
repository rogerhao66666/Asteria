"""Editor production-preview bridge for generic presentation subsystems."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from .property_animation import PropertyAnimator, split_channels
from .channel_backend import PresentationChannelExecutor
from .camera_runtime import CameraRuntime, CameraState
from .material_runtime import MaterialRuntime, MaterialState
from .vfx_runtime import VFXRuntime, VFXFrame
from .audio_runtime import AudioRuntime, AudioCommand


@dataclass(frozen=True, slots=True)
class ProductionPreviewFrame:
    time_ms: float
    properties: Mapping[str, float]
    camera: CameraState
    material: MaterialState
    vfx: VFXFrame
    audio: tuple[AudioCommand, ...]


class ProductionPreviewSession:
    """Scrubbable preview using the same runtime channel implementations.

    GUI shells call this model; they do not own a second preview semantics.
    """

    def __init__(self, animator: PropertyAnimator, *, camera=None, material=None, vfx=None, audio=None):
        self.animator = animator
        self.camera = camera or CameraRuntime()
        self.material = material or MaterialRuntime()
        self.vfx = vfx or VFXRuntime()
        self.audio = audio or AudioRuntime()
        self.channels = PresentationChannelExecutor(
            camera=self.camera, material=self.material, vfx=self.vfx, audio=self.audio
        )
        self.time_ms = 0.0

    def sample(self, time_ms: float) -> ProductionPreviewFrame:
        if time_ms < 0:
            raise ValueError("negative preview time")
        # Rewind/seek audio deterministically; visual channels are absolute samples.
        if time_ms < self.time_ms:
            self.audio.seek(time_ms)
        values = self.animator.sample(time_ms)
        self.channels.execute(split_channels(values))
        commands = self.audio.advance(min(self.time_ms, time_ms), time_ms)
        self.time_ms = time_ms
        return ProductionPreviewFrame(
            time_ms, values, self.camera.sample(time_ms), self.material.snapshot(), self.vfx.frame(), commands
        )

    def reset(self) -> None:
        self.time_ms = 0.0
        self.audio.reset()
        self.camera.clear_modulations()
