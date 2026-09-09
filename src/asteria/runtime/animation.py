from dataclasses import dataclass


@dataclass(slots=True)
class AnimatorState:
    clip: object
    time: float = 0.0
    frame_cursor: int = 0
    playing: bool = True

    @property
    def frame_index(self):
        return self.clip.keyframes[self.frame_cursor].frame_index

    def set_clip(self, clip, restart=False):
        if clip is self.clip and not restart:
            return
        self.clip = clip
        self.time = 0.0
        self.frame_cursor = 0
        self.playing = True

    def update(self, dt):
        if not self.playing or dt <= 0:
            return
        if not self.clip.keyframes:
            raise ValueError("empty clip")
        self.time += dt
        while self.playing:
            k = self.clip.keyframes[self.frame_cursor]
            if self.time < k.duration:
                break
            self.time -= k.duration
            self.frame_cursor += 1
            if self.frame_cursor >= len(self.clip.keyframes):
                if self.clip.loop:
                    self.frame_cursor = 0
                else:
                    self.frame_cursor = len(self.clip.keyframes) - 1
                    self.time = 0.0
                    self.playing = False
