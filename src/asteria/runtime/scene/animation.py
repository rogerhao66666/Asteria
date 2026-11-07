"""Sprite animation at runtime: the animator playing a clip, clip sets, the binding of an animator
to a scene entity, and the controller that picks a walking character's clip from its motion."""

from dataclasses import dataclass, field

from asteria.runtime.scene.components import Animator2DComponent, SpriteRenderer2D


@dataclass(slots=True)
class AnimatorState:
    clip: object
    time: float = 0.0
    frame_cursor: int = 0
    playing: bool = True
    # (clip name, keyframe index, event name) in the order keyframes were entered.
    pending_events: list = field(default_factory=list)

    def __post_init__(self):
        self._enter_keyframe()

    def _enter_keyframe(self):
        keyframe = self.clip.keyframes[self.frame_cursor] if self.clip.keyframes else None
        for name in getattr(keyframe, "events", ()):
            self.pending_events.append((self.clip.name, self.frame_cursor, name))

    def drain_events(self):
        events, self.pending_events = self.pending_events, []
        return events

    @property
    def finished(self):
        return not self.playing and not self.clip.loop

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
        self._enter_keyframe()

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
                    break
            self._enter_keyframe()


@dataclass(frozen=True, slots=True)
class AnimationClipSet:
    clips: dict[str, object]
    # Optional AnimationStateMachineDefinition choosing clips from parameters.
    state_machine: object = None

    def validate(self, sprite_sheet):
        if not self.clips:
            raise ValueError("animation clip set requires clips")
        for name, clip in self.clips.items():
            if not name or clip.name != name:
                raise ValueError("clip key/name mismatch")
            clip.validate(sprite_sheet)

    def get(self, name):
        return self.clips.get(name)


@dataclass(slots=True)
class Animator2DBinding:
    entity: object
    animator: AnimatorState
    speed: float = 1.0

    @classmethod
    def create(cls, entity, resolve_clip_set):
        spec = entity.get(Animator2DComponent)
        clip_set = resolve_clip_set(spec.clip_set_id)
        if clip_set is None:
            raise ValueError("missing animation clip set")
        clip = clip_set.get(spec.default_clip)
        if clip is None:
            raise ValueError("missing default animation clip")
        state = AnimatorState(clip, playing=spec.playing)
        binding = cls(entity, state, spec.speed)
        binding.sync_sprite()
        return binding

    def set_clip(self, clip, restart=False):
        self.animator.set_clip(clip, restart)
        self.sync_sprite()

    def update(self, dt):
        self.animator.update(float(dt) * self.speed)
        self.sync_sprite()

    def sync_sprite(self):
        self.entity.get(SpriteRenderer2D).frame_index = self.animator.frame_index


@dataclass(slots=True)
class CharacterAnimationController:
    clips: object
    animator: object
    facing: str = "down"

    def _direction_from_motion(self, dx, dy):
        if abs(dx) > abs(dy):
            return "right" if dx > 0 else "left"
        if abs(dy) > 0:
            return "down" if dy > 0 else "up"
        return self.facing

    def update_motion(self, dx, dy):
        moving = abs(dx) > 1e-9 or abs(dy) > 1e-9
        if moving:
            self.facing = self._direction_from_motion(dx, dy)
            target = self.clips.walk[self.facing]
        else:
            target = self.clips.idle[self.facing]
        self.animator.set_clip(target)
        return moving
