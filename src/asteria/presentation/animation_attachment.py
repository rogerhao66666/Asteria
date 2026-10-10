"""Animation-clock binding for generic socket/attachment presentation.

This module bridges an animation player's time/frame state to AttachmentRuntime.
It deliberately has no gameplay vocabulary: clips, sockets and attachments are
project-defined presentation data.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

from .attachment_runtime import AttachmentRuntime, ResolvedAttachment


@dataclass(frozen=True, slots=True)
class FrameTiming:
    """One animation frame's duration in milliseconds."""

    duration_ms: float

    def __post_init__(self) -> None:
        if self.duration_ms <= 0:
            raise ValueError("frame duration must be > 0")


@dataclass(frozen=True, slots=True)
class AnimationClock:
    """Canonical timing description for a presentation animation clip."""

    frames: tuple[FrameTiming, ...]
    loop: bool = True

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("animation clock requires at least one frame")

    @classmethod
    def uniform(cls, frame_count: int, fps: float, *, loop: bool = True) -> "AnimationClock":
        if frame_count <= 0:
            raise ValueError("frame_count must be > 0")
        if fps <= 0:
            raise ValueError("fps must be > 0")
        duration = 1000.0 / float(fps)
        return cls(tuple(FrameTiming(duration) for _ in range(frame_count)), loop)

    @property
    def duration_ms(self) -> float:
        return sum(f.duration_ms for f in self.frames)

    def sample(self, time_ms: float) -> "AnimationSample":
        if time_ms < 0:
            raise ValueError("animation time must be >= 0")
        total = self.duration_ms
        if self.loop:
            local = time_ms % total
            finished = False
        else:
            finished = time_ms >= total
            local = min(time_ms, total)

        if finished:
            return AnimationSample(len(self.frames) - 1, 1.0, total, True)

        elapsed = 0.0
        for index, timing in enumerate(self.frames):
            end = elapsed + timing.duration_ms
            if local < end:
                subframe = (local - elapsed) / timing.duration_ms
                return AnimationSample(index, subframe, local, False)
            elapsed = end
        return AnimationSample(len(self.frames) - 1, 1.0, local, not self.loop)


@dataclass(frozen=True, slots=True)
class AnimationSample:
    frame: int
    subframe: float
    local_time_ms: float
    finished: bool = False


@dataclass(frozen=True, slots=True)
class AttachmentPoseFrame:
    """Resolved attachment pose snapshot for one animation-clock sample."""

    sample: AnimationSample
    attachments: tuple[ResolvedAttachment, ...]


class AnimatedAttachmentBinding:
    """Resolve all active attachments from an animation clip's clock.

    The binding is intentionally thin: animation playback remains authoritative
    for time, while AttachmentRuntime remains authoritative for socket hierarchy,
    attachment lifecycle and world-space composition.
    """

    def __init__(self, runtime: AttachmentRuntime, clock: AnimationClock):
        self.runtime = runtime
        self.clock = clock

    def resolve_at(self, time_ms: float) -> AttachmentPoseFrame:
        sample = self.clock.sample(time_ms)
        resolved = self.runtime.resolve_all(sample.frame, sample.subframe)
        return AttachmentPoseFrame(sample, resolved)

    def resolve_one_at(self, attachment_id: str, time_ms: float) -> ResolvedAttachment:
        sample = self.clock.sample(time_ms)
        return self.runtime.resolve(attachment_id, sample.frame, sample.subframe)


@dataclass(slots=True)
class AnimationAttachmentPlayer:
    """Small deterministic reference player used by runtime/editor preview.

    Real renderer integration may drive the same binding from an existing actor
    animator; this class proves the timing contract without replacing that actor
    animation system.
    """

    binding: AnimatedAttachmentBinding
    time_ms: float = 0.0
    playing: bool = True

    def seek(self, time_ms: float) -> AttachmentPoseFrame:
        if time_ms < 0:
            raise ValueError("seek time must be >= 0")
        self.time_ms = float(time_ms)
        return self.binding.resolve_at(self.time_ms)

    def update(self, dt_ms: float) -> AttachmentPoseFrame:
        if dt_ms < 0:
            raise ValueError("negative dt")
        if self.playing:
            self.time_ms += float(dt_ms)
        pose = self.binding.resolve_at(self.time_ms)
        if pose.sample.finished and not self.binding.clock.loop:
            self.playing = False
        return pose

    def play(self) -> None:
        self.playing = True

    def pause(self) -> None:
        self.playing = False
