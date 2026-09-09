from asteria.core import Transform

from .camera import Camera2D, CameraFollow2D
from .components2d import Camera2DComponent


def build_runtime_camera(entity):
    transform = entity.get(Transform)
    spec = entity.get(Camera2DComponent)
    camera = Camera2D(
        x=transform.x,
        y=transform.y,
        width=spec.width,
        height=spec.height,
        zoom=spec.zoom,
    )
    follow = None
    if spec.follow_entity_id:
        follow = CameraFollow2D(
            camera,
            deadzone_x=spec.deadzone_x,
            deadzone_y=spec.deadzone_y,
            smoothing=spec.smoothing,
        )
    return camera, follow
