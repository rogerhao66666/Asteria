"""Playable field camera (CAM-02): cutscene / boss focus, release and shake over the field map.

The playable field draws one map image that fills the screen. With no shot
active this camera is the identity view, so the field looks exactly as
before; event programs move it with presentation world commands:

* ``CAMERA_FOCUS``  ``entity`` (name or id) or ``x``/``y``, ``zoom`` (>= 1),
  ``blend`` seconds, ``ease`` (linear, smooth, ease_in, ease_out, cut)
* ``CAMERA_RELEASE`` ``blend``, ``ease`` — back to the normal view
* ``CAMERA_SHAKE``  ``intensity`` (world units), ``duration`` seconds

Views are clamped to the map image, so panning and zooming never show
past its edges; shake is applied after clamping.
"""

from __future__ import annotations

from asteria.core import Transform

from .camera import CameraDirector, CameraShot, clamp_center_to_bounds

CAMERA_COMMANDS = ("CAMERA_FOCUS", "CAMERA_RELEASE", "CAMERA_SHAKE")


class FieldCameraError(ValueError):
    pass


class FieldViewCamera:
    def __init__(self, width, height, scale, *, anchor_offset_y=65.0, max_zoom=3.0):
        self.width, self.height, self.scale = float(width), float(height), float(scale)
        self.anchor_offset_y = float(anchor_offset_y)
        self.max_zoom = float(max_zoom)
        self.director = CameraDirector()
        self.view = self.home

    @property
    def home(self):
        """The identity view: the map image exactly fills the screen."""
        return (0.0, -self.anchor_offset_y / self.scale, 1.0)

    @property
    def bounds(self):
        s, a = self.scale, self.anchor_offset_y
        return (-self.width / (2 * s), -(self.height / 2 + a) / s, self.width / (2 * s), (self.height / 2 - a) / s)

    def update(self, dt):
        x, y, zoom = self.director.update(dt, self.home)
        x, y = x - self.director.shake_offset[0], y - self.director.shake_offset[1]
        zoom = max(1.0, min(self.max_zoom, zoom))
        view_w, view_h = self.width / (self.scale * zoom), self.height / (self.scale * zoom)
        x, y = clamp_center_to_bounds(x, y, view_w, view_h, self.bounds)
        self.view = (x + self.director.shake_offset[0], y + self.director.shake_offset[1], zoom)
        return self.view

    def world_to_screen(self, wx, wy):
        x, y, zoom = self.view
        return (
            self.width / 2 + (float(wx) - x) * self.scale * zoom,
            self.height / 2 + (float(wy) - y) * self.scale * zoom,
        )

    @property
    def zoom(self):
        return self.view[2]

    def background_rect(self):
        """Screen rectangle ``(x, y, w, h)`` the map image is drawn into."""
        min_x, min_y, _, _ = self.bounds
        x, y = self.world_to_screen(min_x, min_y)
        return (x, y, self.width * self.zoom, self.height * self.zoom)

    # -- event commands ------------------------------------------------------------------
    def handle(self, command, scene):
        """Apply a CAMERA_* world command; ``scene`` resolves entity names/ids."""
        args = dict(command.args)
        name = command.name
        if name == "CAMERA_FOCUS":
            follow = None
            if args.get("entity"):
                entity = _find_entity(scene, str(args["entity"]))

                def follow():
                    t = entity.get(Transform)
                    return t.x, t.y

            elif "x" in args and "y" in args:
                pass
            else:
                raise FieldCameraError("CAMERA_FOCUS needs entity or x and y")
            zoom = args.get("zoom")
            shot = CameraShot(
                float(args.get("x", 0.0)), float(args.get("y", 0.0)), None if zoom is None else float(zoom), follow
            )
            self.director.focus(shot, blend=float(args.get("blend", 0.6)), ease=str(args.get("ease", "smooth")))
        elif name == "CAMERA_RELEASE":
            self.director.release(blend=float(args.get("blend", 0.6)), ease=str(args.get("ease", "smooth")))
        elif name == "CAMERA_SHAKE":
            self.director.shake(float(args.get("intensity", 3.0)), float(args.get("duration", 0.4)))
        else:
            raise FieldCameraError(f"not a camera command: {name}")


def _find_entity(scene, key):
    entity = scene.get_entity(key)
    if entity is None:
        entity = next((e for e in scene.entities() if e.name == key), None)
    if entity is None or not entity.has(Transform):
        raise FieldCameraError(f"camera focus: no entity {key} with a position in {scene.name}")
    return entity
