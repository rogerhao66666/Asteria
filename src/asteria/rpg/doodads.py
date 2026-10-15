"""Doodads (YEP GridFreeDoodads): decorations placed anywhere, not on the tile grid.

A ``DoodadDefinition`` is the palette entry - which sprite-sheet cell to draw, how big its solid
footprint is (if any) and how it sorts. The editor turns one into a scene entity wherever the
author clicks (``editor.doodads``); nothing here knows about scenes.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _text(value):
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class DoodadDefinition:
    """``solid_width`` / ``solid_height`` > 0 gives the doodad a collider of that size at the foot
    (``solid_offset_y`` moves it); ``layer`` / ``depth`` feed the sprite's draw order;
    ``snap`` > 0 rounds placement to that grid (0 = free)."""

    doodad_id: str
    sprite_sheet_asset_id: str
    frame: int = 0
    solid_width: float = 0.0
    solid_height: float = 0.0
    solid_offset_y: float = 0.0
    layer: int = 0
    depth: float = 0.0
    snap: float = 0.0
    tags: tuple[str, ...] = ()

    def __init__(
        self,
        doodad_id,
        sprite_sheet_asset_id,
        *,
        frame=0,
        solid_width=0.0,
        solid_height=0.0,
        solid_offset_y=0.0,
        layer=0,
        depth=0.0,
        snap=0.0,
        tags=(),
    ):
        doodad_id, sheet = _text(doodad_id), _text(sprite_sheet_asset_id)
        if not doodad_id or not sheet:
            raise ValueError("a doodad needs an id and a sprite sheet")
        if int(frame) < 0:
            raise ValueError("frame must be >= 0")
        for name, value in (
            ("solid_width", solid_width),
            ("solid_height", solid_height),
            ("snap", snap),
        ):
            if not isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"{name} must be finite and >= 0")
        s = object.__setattr__
        s(self, "doodad_id", doodad_id)
        s(self, "sprite_sheet_asset_id", sheet)
        s(self, "frame", int(frame))
        s(self, "solid_width", float(solid_width))
        s(self, "solid_height", float(solid_height))
        s(self, "solid_offset_y", float(solid_offset_y))
        s(self, "layer", int(layer))
        s(self, "depth", float(depth))
        s(self, "snap", float(snap))
        s(self, "tags", tuple(sorted({_text(t) for t in tags if _text(t)})))

    @property
    def solid(self):
        return self.solid_width > 0 and self.solid_height > 0

    def to_data(self):
        data = {"doodad_id": self.doodad_id, "sprite_sheet_asset_id": self.sprite_sheet_asset_id}
        defaults = DoodadDefinition(self.doodad_id, self.sprite_sheet_asset_id)
        for name in (
            "frame",
            "solid_width",
            "solid_height",
            "solid_offset_y",
            "layer",
            "depth",
            "snap",
            "tags",
        ):
            value = getattr(self, name)
            if value != getattr(defaults, name):
                data[name] = list(value) if isinstance(value, tuple) else value
        return data

    @classmethod
    def from_data(cls, data):
        data = dict(data)
        return cls(data.pop("doodad_id"), data.pop("sprite_sheet_asset_id"), **data)


def snap_position(x, y, snap):
    """``(x, y)`` rounded to a grid of ``snap`` (unchanged when ``snap`` is 0)."""
    if snap <= 0:
        return float(x), float(y)
    return round(float(x) / snap) * snap, round(float(y) / snap) * snap


def scatter_positions(area, count, rng, *, min_distance=0.0, avoid=None, attempts=30):
    """Up to ``count`` random points in ``area`` = ``(x0, y0, x1, y1)``, no two closer than
    ``min_distance``; ``avoid(x, y)`` rejects a point. Deterministic for a seeded ``rng``."""
    x0, y0, x1, y1 = (float(v) for v in area)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("area must have a positive size")
    points = []
    for _ in range(int(count)):
        for _ in range(attempts):
            x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
            if avoid is not None and avoid(x, y):
                continue
            if any((x - px) ** 2 + (y - py) ** 2 < min_distance**2 for px, py in points):
                continue
            points.append((x, y))
            break
    return points
