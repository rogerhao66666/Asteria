"""Screen pictures (YEP PictureCommonEvents / PictureSpritesheets): images events put on screen.

A picture is an image asset at a screen position with scale, opacity, a layer and optionally a
sprite-sheet cell (``columns`` x ``rows``, ``frame`` picks the cell) and a ``click_event``: an
event program that starts when the player clicks it. State lives in the ``EventContext`` variables
(``picture.<id>.*``) so pictures are saved with the game; tweens (``move``) run in memory and the
target is stored at once, so a save during a tween loads at the end of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

PREFIX = "picture."
FIELDS = ("asset", "x", "y", "scale", "opacity", "frame", "columns", "rows", "layer", "click")
EASINGS = ("linear", "ease_in", "ease_out", "ease_in_out")


def _ease(kind, t):
    if kind == "ease_in":
        return t * t
    if kind == "ease_out":
        return 1 - (1 - t) * (1 - t)
    if kind == "ease_in_out":
        return 3 * t * t - 2 * t**3
    return t


@dataclass(frozen=True, slots=True)
class Picture:
    picture_id: str
    asset_id: str
    x: float
    y: float
    scale: float = 1.0
    opacity: float = 1.0
    frame: int = 0
    columns: int = 1
    rows: int = 1
    layer: int = 0
    click_event: str = ""

    def cell(self, width, height):
        """The ``(x, y, w, h)`` part of an image of the given size that this picture shows."""
        cell_w, cell_h = width // max(1, self.columns), height // max(1, self.rows)
        index = self.frame % max(1, self.columns * self.rows)
        return (index % self.columns) * cell_w, (index // self.columns) * cell_h, cell_w, cell_h

    def rect(self, width, height):
        """Screen rectangle ``(x, y, w, h)``: the picture's ``x, y`` is its top-left corner."""
        _, _, cell_w, cell_h = self.cell(width, height)
        return self.x, self.y, cell_w * self.scale, cell_h * self.scale


class PictureManager:
    def __init__(self, context):
        self.context = context
        self._tweens = {}  # picture id -> {field: (start, end)}, duration, easing, elapsed

    def _id(self, picture_id):
        picture_id = str(picture_id).strip()
        if not picture_id or "." in picture_id:
            raise ValueError("a picture id is a non-empty name without dots")
        return picture_id

    def _get(self, picture_id, field, default=None):
        return self.context.get_variable(f"{PREFIX}{picture_id}.{field}", default)

    def _set(self, picture_id, field, value):
        self.context.set_variable(f"{PREFIX}{picture_id}.{field}", value)

    # -- control -------------------------------------------------------------------------------
    def show(
        self,
        picture_id,
        asset_id,
        x=0.0,
        y=0.0,
        *,
        scale=1.0,
        opacity=1.0,
        frame=0,
        columns=1,
        rows=1,
        layer=0,
        click_event="",
    ):
        """Show (or replace) a picture."""
        picture_id = self._id(picture_id)
        if not str(asset_id).strip():
            raise ValueError("a picture needs an image")
        if not isfinite(float(scale)) or float(scale) <= 0:
            raise ValueError("scale must be positive")
        if int(columns) < 1 or int(rows) < 1:
            raise ValueError("columns and rows must be >= 1")
        self.erase(picture_id)
        values = {
            "asset": str(asset_id),
            "x": float(x),
            "y": float(y),
            "scale": float(scale),
            "opacity": max(0.0, min(1.0, float(opacity))),
            "frame": int(frame),
            "columns": int(columns),
            "rows": int(rows),
            "layer": int(layer),
            "click": str(click_event or ""),
        }
        for field, value in values.items():
            self._set(picture_id, field, value)

    def erase(self, picture_id):
        picture_id = self._id(picture_id)
        self._tweens.pop(picture_id, None)
        for field in FIELDS:
            self.context.variables.pop(f"{PREFIX}{picture_id}.{field}", None)

    def set_frame(self, picture_id, frame):
        if self.exists(picture_id):
            self._set(self._id(picture_id), "frame", int(frame))

    def move(
        self,
        picture_id,
        *,
        x=None,
        y=None,
        scale=None,
        opacity=None,
        duration=0.0,
        easing="linear",
    ):
        """Change position, scale or opacity, over ``duration`` seconds (0 = at once)."""
        picture_id = self._id(picture_id)
        if not self.exists(picture_id):
            raise KeyError(picture_id)
        if easing not in EASINGS:
            raise ValueError(f"easing must be one of {EASINGS}")
        targets = {"x": x, "y": y, "scale": scale, "opacity": opacity}
        spans = {}
        for field, target in targets.items():
            if target is None:
                continue
            target = float(target)
            if field == "scale" and target <= 0:
                raise ValueError("scale must be positive")
            if field == "opacity":
                target = max(0.0, min(1.0, target))
            spans[field] = (float(self._get(picture_id, field)), target)
            self._set(picture_id, field, target)  # saved at the end value
        if duration > 0 and spans:
            self._tweens[picture_id] = {
                "spans": spans,
                "duration": float(duration),
                "easing": easing,
                "elapsed": 0.0,
            }
        else:
            self._tweens.pop(picture_id, None)

    # -- reading -------------------------------------------------------------------------------
    def exists(self, picture_id):
        return self._get(str(picture_id), "asset") is not None

    def ids(self):
        return tuple(
            sorted(
                {
                    key[len(PREFIX) :].rsplit(".", 1)[0]
                    for key in self.context.variables
                    if key.startswith(PREFIX) and key.endswith(".asset")
                }
            )
        )

    def get(self, picture_id):
        """The picture as drawn now (a running tween shows its in-between values)."""
        picture_id = str(picture_id)
        if not self.exists(picture_id):
            return None
        values = {f: self._get(picture_id, f) for f in FIELDS}
        tween = self._tweens.get(picture_id)
        if tween is not None:
            t = min(1.0, tween["elapsed"] / tween["duration"])
            for field, (start, end) in tween["spans"].items():
                values[field] = start + (end - start) * _ease(tween["easing"], t)
        return Picture(
            picture_id,
            values["asset"],
            values["x"],
            values["y"],
            values["scale"],
            values["opacity"],
            values["frame"],
            values["columns"],
            values["rows"],
            values["layer"],
            values["click"],
        )

    def pictures(self):
        """Every picture, bottom layer first."""
        found = [self.get(i) for i in self.ids()]
        return sorted(found, key=lambda p: (p.layer, p.picture_id))

    def update(self, dt):
        dt = max(0.0, float(dt))
        for picture_id in tuple(self._tweens):
            tween = self._tweens[picture_id]
            tween["elapsed"] += dt
            if tween["elapsed"] >= tween["duration"]:
                del self._tweens[picture_id]

    def hit_test(self, x, y, size_of):
        """The topmost clickable picture under ``(x, y)``. ``size_of(picture)`` gives the image's
        ``(width, height)`` in pixels (``None`` skips the picture)."""
        for picture in reversed(self.pictures()):
            if not picture.click_event or picture.opacity <= 0:
                continue
            size = size_of(picture)
            if size is None:
                continue
            left, top, width, height = picture.rect(*size)
            if left <= x < left + width and top <= y < top + height:
                return picture
        return None
