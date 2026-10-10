"""Editor timeline/live-preview integration for sockets and attachments.

Headless controller: Qt widgets bind to this model instead of owning a second
presentation data model.
"""

from __future__ import annotations

from dataclasses import dataclass

from asteria.editor.attachment_authoring import AttachmentAuthoringModel
from asteria.presentation.animation_attachment import AnimationClock, AnimationSample


@dataclass(frozen=True, slots=True)
class PreviewFrame:
    sample: AnimationSample
    attachments: tuple


class AttachmentPreviewController:
    def __init__(self, authoring: AttachmentAuthoringModel, clock: AnimationClock):
        self.authoring = authoring
        self.clock = clock
        self.time_ms = 0.0
        self.playing = False
        self.playback_rate = 1.0

    def _frame(self):
        s = self.clock.sample(self.time_ms)
        return PreviewFrame(s, self.authoring.preview(s.frame, s.subframe))

    def seek_time(self, time_ms: float):
        if time_ms < 0:
            raise ValueError("time must be >= 0")
        self.time_ms = float(time_ms)
        return self._frame()

    def seek_frame(self, frame: int, subframe: float = 0.0):
        if frame < 0 or frame >= len(self.clock.frames):
            raise IndexError("frame")
        if not 0 <= subframe <= 1:
            raise ValueError("subframe must be in [0,1]")
        self.time_ms = sum(x.duration_ms for x in self.clock.frames[:frame])
        if frame < len(self.clock.frames):
            self.time_ms += self.clock.frames[frame].duration_ms * subframe
        return self._frame()

    def play(self):
        self.playing = True

    def pause(self):
        self.playing = False

    def set_playback_rate(self, rate: float):
        if rate <= 0:
            raise ValueError("playback rate must be > 0")
        self.playback_rate = float(rate)

    def tick(self, dt_ms: float):
        if dt_ms < 0:
            raise ValueError("negative dt")
        if self.playing:
            self.time_ms += dt_ms * self.playback_rate
            if not self.clock.loop and self.time_ms >= self.clock.duration_ms:
                self.time_ms = self.clock.duration_ms
                self.playing = False
        return self._frame()

    def edit_socket_key_at_playhead(self, socket_id, transform):
        s = self.clock.sample(self.time_ms)
        self.authoring.set_socket_key(socket_id, s.frame, transform)
        return self._frame()

    def undo(self):
        changed = self.authoring.undo()
        return changed, self._frame()

    def redo(self):
        changed = self.authoring.redo()
        return changed, self._frame()
