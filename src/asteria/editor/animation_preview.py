from dataclasses import dataclass

from asteria.runtime import AnimatorState


@dataclass(slots=True)
class AnimationPreview:
    clip: object | None = None
    speed: float = 1.0
    playing: bool = True
    _animator: object | None = None

    def set_clip(self, clip, restart=True):
        self.clip = clip
        if clip is None:
            self._animator = None
            return
        if self._animator is None:
            self._animator = AnimatorState(clip)
        else:
            self._animator.set_clip(clip, restart=restart)
        self._animator.playing = self.playing

    @property
    def frame_index(self):
        return None if self._animator is None else self._animator.frame_index

    def update(self, dt):
        if self._animator is None or not self.playing:
            return
        self._animator.update(float(dt) * self.speed)

    def toggle(self):
        self.playing = not self.playing
        if self._animator is not None:
            self._animator.playing = self.playing

    def restart(self):
        if self.clip is not None:
            self.set_clip(self.clip, True)
