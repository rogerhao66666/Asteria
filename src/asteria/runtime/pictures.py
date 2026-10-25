"""Screen pictures (YEP PictureCommonEvents / PictureSpritesheets): images events put on screen.

A picture is an image asset at a screen position with scale, opacity, a layer and optionally a
sprite-sheet cell (``columns`` x ``rows``, ``frame`` picks the cell) and a ``click_event``: an
event program that starts when the player clicks it. State lives in the ``EventContext`` variables
(``picture.<id>.*``) so pictures are saved with the game; tweens (``move``) run in memory and the
target is stored at once, so a save during a tween loads at the end of it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from math import isfinite

PREFIX = "picture."
FIELDS = (
    "asset", "x", "y", "scale", "opacity", "frame", "columns", "rows", "layer", "click", "tint",
    "tint_color", "frame_rate", "frame_loop", "scroll_x", "scroll_y", "wave_amplitude",
    "wave_length", "wave_speed", "blend", "text", "font", "text_color", "shadow_color",
    "text_align",
)  # fmt: skip
MOTION = {  # the moving looks a picture can have, and their defaults
    "frame_loop": True, "scroll_x": 0.0, "scroll_y": 0.0, "wave_amplitude": 0.0,
    "wave_length": 64.0, "wave_speed": 0.0, "blend": "normal",
}  # fmt: skip
BLENDS = ("normal", "add")
EASINGS = ("linear", "ease_in", "ease_out", "ease_in_out")


def _rgb(value):
    """``(r, g, b)`` from ``"r,g,b"`` or a list (white when there is none)."""
    if not value:
        return (255, 255, 255)
    parts = value.split(",") if isinstance(value, str) else value
    found = tuple(max(0, min(255, int(float(c)))) for c in parts)
    if len(found) != 3:
        raise ValueError("a colour is three numbers: r, g, b")
    return found


def _rgb_text(value):
    return ",".join(str(c) for c in _rgb(value))


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
    tint: float = 0.0  # 0 = its own colours, 1 = all ``tint_color`` (a creature out of a ball)
    tint_color: tuple = (255, 255, 255)
    frame_rate: float = 0.0  # sheet cells a second, from ``frame`` on (0 = it stays)
    frame_loop: bool = True  # False: the cells play once and the last one stays
    scroll_x: float = 0.0  # the image's own pixels a second, its content wrapping round
    scroll_y: float = 0.0
    wave_amplitude: float = 0.0  # each row shifted sideways by amplitude x sin(...)
    wave_length: float = 64.0  # rows to a whole wave
    wave_speed: float = 0.0  # rows a second the wave travels up
    blend: str = "normal"  # "add": its colours x opacity added to what is under it (a glow)
    age: float = 0.0  # seconds since it was shown
    text: str = ""  # words drawn as the picture (no image): \V[...] filled in as drawn
    font: str = ""  # a bitmap font's id ("" = the message window's)
    text_color: tuple = (255, 255, 255)
    shadow_color: tuple | None = None  # the letters' shadow (None: none)
    text_align: str = "left"  # the words' x is their left, "right" end or "center"

    def scroll_offset(self):
        """``(x, y)`` image pixels its content has scrolled by now."""
        return self.scroll_x * self.age, self.scroll_y * self.age

    def wave_offset(self, row):
        """The sideways shift (image pixels) of image row ``row`` now."""
        if not self.wave_amplitude:
            return 0.0
        phase = (row + self.wave_speed * self.age) / max(1e-6, self.wave_length)
        return self.wave_amplitude * math.sin(2 * math.pi * phase)

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
        self._clock = 0.0  # seconds of update(): a cycling sheet counts from its showing
        self._shown_at = {}

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
        tint=0.0,
        tint_color=None,
        frame_rate=0.0,
        text="",
        font="",
        text_color=None,
        shadow_color=None,
        text_align="left",
        **motion,
    ):
        """Show (or replace) a picture (``tint``: how far it is mixed with ``tint_color``,
        0..1; white unless given; ``frame_rate``: sheet cells a second, cycling; ``motion``:
        ``frame_loop``, ``scroll_x`` / ``scroll_y`` and ``wave_amplitude`` / ``wave_length`` /
        ``wave_speed``, see ``Picture``; ``text``: words drawn instead of an image, in
        ``font`` with ``text_color`` and ``shadow_color``)."""
        unknown = set(motion) - set(MOTION)
        if unknown:
            raise ValueError(f"unknown picture setting: {sorted(unknown)[0]}")
        picture_id = self._id(picture_id)
        if not str(asset_id or "").strip() and not str(text or ""):
            raise ValueError("a picture needs an image or words")
        if not isfinite(float(scale)) or float(scale) <= 0:
            raise ValueError("scale must be positive")
        if int(columns) < 1 or int(rows) < 1:
            raise ValueError("columns and rows must be >= 1")
        self.erase(picture_id)
        values = {
            "asset": str(asset_id or ""),
            "x": float(x),
            "y": float(y),
            "scale": float(scale),
            "opacity": max(0.0, min(1.0, float(opacity))),
            "frame": int(frame),
            "columns": int(columns),
            "rows": int(rows),
            "layer": int(layer),
            "click": str(click_event or ""),
            "tint": max(0.0, min(1.0, float(tint))),
            "tint_color": _rgb_text(tint_color),
            "frame_rate": max(0.0, float(frame_rate or 0.0)),
        }
        values.update(
            text=str(text or ""),
            font=str(font or ""),
            text_color=_rgb_text(text_color),
            shadow_color=_rgb_text(shadow_color) if shadow_color else "",
            text_align=str(text_align or "left"),
        )
        if values["text_align"] not in ("left", "right", "center"):
            raise ValueError("text_align is left, right or center")
        for field, default in MOTION.items():
            value = motion.get(field, default)
            if field == "frame_loop":
                values[field] = bool(value)
            elif field == "blend":
                values[field] = str(value or "normal")
            else:
                values[field] = float(value or 0.0)
        if values["blend"] not in BLENDS:
            raise ValueError(f"blend is one of {BLENDS}")
        if values["wave_length"] <= 0:
            raise ValueError("wave_length must be positive")
        for field, value in values.items():
            self._set(picture_id, field, value)
        self._shown_at[picture_id] = self._clock

    def erase(self, picture_id):
        picture_id = self._id(picture_id)
        self._tweens.pop(picture_id, None)
        self._shown_at.pop(picture_id, None)
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
        tint=None,
        tint_color=None,
        duration=0.0,
        easing="linear",
        delay=0.0,
    ):
        """Change position, scale, opacity or tint, over ``duration`` seconds (0 = at once;
        ``tint_color`` changes at once), starting ``delay`` seconds from now (until then the
        picture keeps its values: an instant MOVE then a delayed one plays one after the
        other)."""
        picture_id = self._id(picture_id)
        if not self.exists(picture_id):
            raise KeyError(picture_id)
        if easing not in EASINGS:
            raise ValueError(f"easing must be one of {EASINGS}")
        targets = {"x": x, "y": y, "scale": scale, "opacity": opacity, "tint": tint}
        spans = {}
        for field, target in targets.items():
            if target is None:
                continue
            target = float(target)
            if field == "scale" and target <= 0:
                raise ValueError("scale must be positive")
            if field in ("opacity", "tint"):
                target = max(0.0, min(1.0, target))
            spans[field] = (float(self._get(picture_id, field, 0.0) or 0.0), target)
            self._set(picture_id, field, target)  # saved at the end value
        if tint_color is not None:
            self._set(picture_id, "tint_color", _rgb_text(tint_color))
        delay = max(0.0, float(delay or 0.0))
        if (duration > 0 or delay > 0) and spans:
            self._tweens[picture_id] = {
                "spans": spans,
                "duration": max(float(duration), 1e-9),
                "easing": easing,
                "elapsed": -delay,
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
            t = min(1.0, max(0.0, tween["elapsed"]) / tween["duration"])
            for field, (start, end) in tween["spans"].items():
                values[field] = start + (end - start) * _ease(tween["easing"], t)
        for field, default in MOTION.items():  # a picture saved before it had one
            if values[field] is None:
                values[field] = default
        age = self._clock - self._shown_at.setdefault(picture_id, self._clock)
        rate = float(values["frame_rate"] or 0.0)
        if rate > 0:  # a cycling sheet: on from its frame, a cell every 1 / rate seconds
            cells = max(1, int(values["columns"]) * int(values["rows"]))
            step = int(values["frame"]) + int(age * rate + 1e-9)
            values["frame"] = step % cells if values["frame_loop"] else min(step, cells - 1)
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
            float(values["tint"] or 0.0),  # a picture saved before it had one: none
            _rgb(values["tint_color"]),
            float(values["frame_rate"] or 0.0),
            bool(values["frame_loop"]),
            float(values["scroll_x"]),
            float(values["scroll_y"]),
            float(values["wave_amplitude"]),
            float(values["wave_length"]),
            float(values["wave_speed"]),
            str(values["blend"] or "normal"),
            age,
            str(values["text"] or ""),
            str(values["font"] or ""),
            _rgb(values["text_color"]),
            _rgb(values["shadow_color"]) if values["shadow_color"] else None,
            str(values["text_align"] or "left"),
        )

    def pictures(self):
        """Every picture, bottom layer first."""
        found = [self.get(i) for i in self.ids()]
        return sorted(found, key=lambda p: (p.layer, p.picture_id))

    def update(self, dt):
        dt = max(0.0, float(dt))
        self._clock += dt
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
