from dataclasses import dataclass


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
