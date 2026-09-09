from dataclasses import dataclass


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
