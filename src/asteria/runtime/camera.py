"""2D cameras (CAM-01, CAM-02): follow with dead zone, smoothing, look-ahead and bounds; target
groups;
a director that blends authored shots (cutscene / boss focus) with eased transitions; camera shake.

Positions on ``Camera2D`` are the top-left of the view; the group and director work with view
centres.
"""

from dataclasses import dataclass, field
from math import cos, exp, pi, sin


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
    world_bounds: tuple[float, float, float, float] | None = None
    look_ahead_x: float = 0.0  # world units shown ahead of the target in its direction of motion
    look_ahead_y: float = 0.0
    look_ahead_smoothing: float = 4.0
    _look_x: float = field(default=0.0, repr=False)
    _look_y: float = field(default=0.0, repr=False)

    def _update_look_ahead(self, velocity, dt):
        vx, vy = velocity if velocity is not None else (0.0, 0.0)
        want_x = self.look_ahead_x * ((vx > 1e-6) - (vx < -1e-6))
        want_y = self.look_ahead_y * ((vy > 1e-6) - (vy < -1e-6))
        if velocity is not None and abs(vx) <= 1e-6 and abs(vy) <= 1e-6:
            want_x, want_y = (
                self._look_x,
                self._look_y,
            )  # standing still keeps the last look direction
        if self.look_ahead_smoothing <= 0 or dt <= 0:
            self._look_x, self._look_y = want_x, want_y
        else:
            alpha = 1.0 - exp(-self.look_ahead_smoothing * dt)
            self._look_x += (want_x - self._look_x) * alpha
            self._look_y += (want_y - self._look_y) * alpha
        return self._look_x, self._look_y

    def update(self, target_x, target_y, dt, velocity=None):
        """Move toward ``target`` (plus look-ahead along ``velocity``), inside bounds, with
        smoothing."""
        if self.look_ahead_x or self.look_ahead_y:
            look_x, look_y = self._update_look_ahead(velocity, dt)
            target_x, target_y = target_x + look_x, target_y + look_y
        desired_x = target_x - (self.camera.width / self.camera.zoom) / 2
        desired_y = target_y - (self.camera.height / self.camera.zoom) / 2
        cx = self.camera.x + (self.camera.width / self.camera.zoom) / 2
        cy = self.camera.y + (self.camera.height / self.camera.zoom) / 2
        if abs(target_x - cx) <= self.deadzone_x:
            desired_x = self.camera.x
        if abs(target_y - cy) <= self.deadzone_y:
            desired_y = self.camera.y
        if self.world_bounds is not None:
            min_x, min_y, max_x, max_y = self.world_bounds
            visible_width = self.camera.width / self.camera.zoom
            visible_height = self.camera.height / self.camera.zoom
            desired_x = min(max(desired_x, min_x), max(min_x, max_x - visible_width))
            desired_y = min(max(desired_y, min_y), max(min_y, max_y - visible_height))
        if self.smoothing <= 0 or dt <= 0:
            self.camera.x = desired_x
            self.camera.y = desired_y
            return
        alpha = 1.0 - exp(-self.smoothing * dt)
        self.camera.x += (desired_x - self.camera.x) * alpha
        self.camera.y += (desired_y - self.camera.y) * alpha


def clamp_center_to_bounds(cx, cy, view_width, view_height, bounds):
    """Keep a ``view_width`` x ``view_height`` view centred at (cx, cy) inside ``bounds``.

    ``bounds`` is ``(min_x, min_y, max_x, max_y)``; a view larger than the bounds is centred on
    them.
    """
    if bounds is None:
        return cx, cy
    min_x, min_y, max_x, max_y = bounds
    half_w, half_h = view_width / 2, view_height / 2
    cx = (
        (min_x + max_x) / 2
        if max_x - min_x <= view_width
        else min(max(cx, min_x + half_w), max_x - half_w)
    )
    cy = (
        (min_y + max_y) / 2
        if max_y - min_y <= view_height
        else min(max(cy, min_y + half_h), max_y - half_h)
    )
    return cx, cy


@dataclass(slots=True)
class CameraTargetGroup:
    """Frames several targets: weighted centre, zoom that fits them all with padding (clamped)."""

    padding: float = 32.0
    min_zoom: float = 0.5
    max_zoom: float = 2.0

    def frame(self, targets, view_width, view_height):
        """Return ``(cx, cy, zoom)`` for ``targets`` given as ``(x, y[, weight[, radius]])``."""
        points = []
        for target in targets:
            x, y = float(target[0]), float(target[1])
            weight = float(target[2]) if len(target) > 2 else 1.0
            radius = float(target[3]) if len(target) > 3 else 0.0
            if weight > 0:
                points.append((x, y, weight, radius))
        if not points:
            raise ValueError("a camera target group needs at least one weighted target")
        total = sum(p[2] for p in points)
        cx = sum(p[0] * p[2] for p in points) / total
        cy = sum(p[1] * p[2] for p in points) / total
        span_x = max(max(abs(p[0] - cx) + p[3] for p in points) * 2 + self.padding * 2, 1e-6)
        span_y = max(max(abs(p[1] - cy) + p[3] for p in points) * 2 + self.padding * 2, 1e-6)
        zoom = min(view_width / span_x, view_height / span_y)
        return cx, cy, max(self.min_zoom, min(self.max_zoom, zoom))


EASINGS = {
    "linear": lambda t: t,
    "smooth": lambda t: t * t * (3 - 2 * t),
    "ease_in": lambda t: t * t,
    "ease_out": lambda t: 1 - (1 - t) * (1 - t),
    "cut": lambda t: 1.0,
}


@dataclass(slots=True)
class CameraShot:
    """An authored view: a fixed centre, or ``follow`` (callable returning the live centre), and a
    zoom."""

    x: float = 0.0
    y: float = 0.0
    zoom: float | None = None  # None keeps the follow camera's zoom
    follow: object = None


class CameraDirector:
    """Blends the follow camera (base view) with authored shots — cutscene and boss focus — and
    shake.

    ``update(dt, base)`` takes the follow view ``(cx, cy, zoom)`` and returns the view to render.
    ``focus`` starts a blend from the current view to a shot; ``release`` blends back to the live
    follow
    view. Shake is a deterministic decaying wobble (reproducible in tests and replays).
    """

    def __init__(self):
        self.shot = None
        self.releasing = False
        self._from = None
        self._elapsed = 0.0
        self._blend = 0.0
        self._ease = EASINGS["smooth"]
        self._last = None
        self._shake = None  # (intensity, duration, frequency, elapsed)
        self.shake_offset = (
            0.0,
            0.0,
        )  # part of the last view that came from shake (hosts may apply it separately)

    @property
    def active(self):
        return self.shot is not None

    @property
    def transitioning(self):
        return self._from is not None and self._elapsed < self._blend

    def focus(self, shot, *, blend=0.6, ease="smooth"):
        if ease not in EASINGS:
            raise ValueError(f"unknown camera easing {ease}; use one of {sorted(EASINGS)}")
        self._from = self._last
        self.shot, self.releasing = shot, False
        self._elapsed, self._blend, self._ease = 0.0, max(0.0, float(blend)), EASINGS[ease]

    def release(self, *, blend=0.6, ease="smooth"):
        if self.shot is None:
            return
        if ease not in EASINGS:
            raise ValueError(f"unknown camera easing {ease}; use one of {sorted(EASINGS)}")
        self._from = self._last
        self.releasing = True
        self._elapsed, self._blend, self._ease = 0.0, max(0.0, float(blend)), EASINGS[ease]

    def shake(self, intensity, duration, frequency=24.0):
        self._shake = [float(intensity), max(1e-6, float(duration)), float(frequency), 0.0]

    def _shot_view(self, base):
        if self.shot.follow is not None:
            x, y = self.shot.follow()
        else:
            x, y = self.shot.x, self.shot.y
        return (float(x), float(y), base[2] if self.shot.zoom is None else float(self.shot.zoom))

    def update(self, dt, base):
        base = tuple(float(v) for v in base)
        self._elapsed += max(0.0, float(dt))
        if self.shot is None:
            view = base
        else:
            goal = base if self.releasing else self._shot_view(base)
            if self._from is None or self._blend <= 0 or self._elapsed >= self._blend:
                view = goal
                if self.releasing:
                    self.shot, self.releasing = None, False
            else:
                k = self._ease(self._elapsed / self._blend)
                view = tuple(a + (b - a) * k for a, b in zip(self._from, goal))
        self._last = view
        self.shake_offset = (0.0, 0.0)
        if self._shake is not None:
            intensity, duration, frequency, elapsed = self._shake
            elapsed += max(0.0, float(dt))
            if elapsed >= duration:
                self._shake = None
            else:
                self._shake[3] = elapsed
                decay = 1.0 - elapsed / duration
                phase = 2 * pi * frequency * elapsed
                self.shake_offset = (
                    intensity * decay * sin(phase),
                    intensity * decay * cos(phase * 1.3),
                )
                view = (view[0] + self.shake_offset[0], view[1] + self.shake_offset[1], view[2])
        return view
