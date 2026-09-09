from dataclasses import dataclass


@dataclass(slots=True)
class Camera2D:
    x: float = 0.0
    y: float = 0.0
    width: int = 320
    height: int = 180
    zoom: float = 1.0

    def world_to_screen(self, wx, wy, parallax_x=1.0, parallax_y=1.0, elevation=0.0):
        return (
            (wx - self.x * parallax_x) * self.zoom,
            ((wy - elevation) - self.y * parallax_y) * self.zoom,
        )

    def visible_rect(self):
        inv = 1.0 / self.zoom
        return (self.x, self.y, self.x + self.width * inv, self.y + self.height * inv)


@dataclass(slots=True)
class CameraFollow2D:
    camera: Camera2D
    deadzone_x: float = 0.0
    deadzone_y: float = 0.0
    smoothing: float = 0.0

    def update(self, target_x, target_y, dt):
        desired_x = target_x - (self.camera.width / self.camera.zoom) / 2
        desired_y = target_y - (self.camera.height / self.camera.zoom) / 2
        cx = self.camera.x + (self.camera.width / self.camera.zoom) / 2
        cy = self.camera.y + (self.camera.height / self.camera.zoom) / 2
        if abs(target_x - cx) <= self.deadzone_x:
            desired_x = self.camera.x
        if abs(target_y - cy) <= self.deadzone_y:
            desired_y = self.camera.y
        if self.smoothing <= 0 or dt <= 0:
            self.camera.x = desired_x
            self.camera.y = desired_y
            return
        alpha = min(1.0, self.smoothing * dt)
        self.camera.x += (desired_x - self.camera.x) * alpha
        self.camera.y += (desired_y - self.camera.y) * alpha
