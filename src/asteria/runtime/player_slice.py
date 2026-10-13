from dataclasses import dataclass

from asteria.core import Transform

from .camera import CameraFollow2D
from .character import CharacterController2D
from .character_animation import CharacterAnimationController
from .components2d import SpriteRenderer2D


@dataclass(slots=True)
class PlayerCameraSlice:
    entity: object
    controller: CharacterController2D
    animation: CharacterAnimationController
    camera_follow: CameraFollow2D | None
    sprite: SpriteRenderer2D
    camera_target: object | None = None

    def step(self, input_snapshot, dt, tile_query):
        dx, dy = input_snapshot.movement_vector()
        actual_dx, actual_dy = self.controller.move(dx, dy, dt, tile_query)
        transform = self.entity.get(Transform)
        transform.x = self.controller.x
        transform.y = self.controller.y
        moving = self.animation.update_motion(actual_dx, actual_dy)
        self.animation.animator.update(dt)
        self.sprite.frame_index = self.animation.animator.frame_index
        if self.camera_follow is not None:
            target = self.camera_target or self.entity
            target_transform = target.get(Transform)
            velocity = (
                (actual_dx / dt, actual_dy / dt) if target is self.entity and dt > 0 else None
            )
            self.camera_follow.update(
                target_transform.x, target_transform.y, dt, velocity=velocity
            )
        return actual_dx, actual_dy, moving
