from dataclasses import dataclass
from .animation import AnimatorState
from .components2d import Animator2DComponent,SpriteRenderer2D

@dataclass(slots=True)
class Animator2DBinding:
    entity:object
    animator:AnimatorState
    speed:float=1.0

    @classmethod
    def create(cls,entity,resolve_clip_set):
        spec=entity.get(Animator2DComponent)
        clip_set=resolve_clip_set(spec.clip_set_id)
        if clip_set is None:
            raise ValueError("missing animation clip set")
        clip=clip_set.get(spec.default_clip)
        if clip is None:
            raise ValueError("missing default animation clip")
        state=AnimatorState(clip,playing=spec.playing)
        binding=cls(entity,state,spec.speed)
        binding.sync_sprite()
        return binding

    def set_clip(self,clip,restart=False):
        self.animator.set_clip(clip,restart)
        self.sync_sprite()

    def update(self,dt):
        self.animator.update(float(dt)*self.speed)
        self.sync_sprite()

    def sync_sprite(self):
        self.entity.get(SpriteRenderer2D).frame_index=self.animator.frame_index
