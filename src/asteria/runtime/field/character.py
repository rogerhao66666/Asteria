"""The simple field character: a controller that walks a box through a tile map, and the slice
that ties the player entity to its controller, animation, sprite and camera."""

from dataclasses import dataclass

from asteria.core import Transform
from asteria.runtime.scene.animation import CharacterAnimationController
from asteria.runtime.scene.camera import CameraFollow2D
from asteria.runtime.scene.components import SpriteRenderer2D


@dataclass(slots=True)
class CharacterController2D:
    x: float
    y: float
    speed: float = 80.0
    half_width: float = 6.0
    half_height: float = 8.0

    def _blocked(self, q, x, y):
        pts = (
            (x - self.half_width, y - self.half_height),
            (x + self.half_width, y - self.half_height),
            (x - self.half_width, y + self.half_height),
            (x + self.half_width, y + self.half_height),
        )
        return any(q.collides_world_point(px, py) for px, py in pts)

    def move(self, dx, dy, dt, q):
        if dt <= 0:
            return (0.0, 0.0)
        mag = (dx * dx + dy * dy) ** 0.5
        if mag > 1.0:
            dx /= mag
            dy /= mag
        mx = dx * self.speed * dt
        my = dy * self.speed * dt
        actual_x = actual_y = 0.0
        nx = self.x + mx
        if not self._blocked(q, nx, self.y):
            self.x = nx
            actual_x = mx
        ny = self.y + my
        if not self._blocked(q, self.x, ny):
            self.y = ny
            actual_y = my
        return actual_x, actual_y


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
