from dataclasses import dataclass
from asteria.core import Transform
from .character import CharacterController2D
from .character_animation import CharacterAnimationController
from .camera import CameraFollow2D
from .components2d import SpriteRenderer2D

@dataclass(slots=True)
class PlayerCameraSlice:
    entity:object
    controller:CharacterController2D
    animation:CharacterAnimationController
    camera_follow:CameraFollow2D
    sprite:SpriteRenderer2D

    def step(self,input_snapshot,dt,tile_query):
        dx,dy=input_snapshot.movement_vector()
        actual_dx,actual_dy=self.controller.move(dx,dy,dt,tile_query)
        transform=self.entity.get(Transform)
        transform.x=self.controller.x
        transform.y=self.controller.y
        moving=self.animation.update_motion(actual_dx,actual_dy)
        self.animation.animator.update(dt)
        self.sprite.frame_index=self.animation.animator.frame_index
        self.camera_follow.update(transform.x,transform.y,dt)
        return actual_dx,actual_dy,moving
