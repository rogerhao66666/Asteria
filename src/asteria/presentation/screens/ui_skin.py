"""UI skin pieces: a nine-patch picture for panels and buttons.

A nine-patch is one picture cut into nine parts by four insets: the corners keep their size, the
edges stretch along one axis and the middle stretches both ways, so one small frame fits a panel of
any size. It is project data (an asset id and four numbers), drawn by a backend.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass
from fnmatch import fnmatchcase


@dataclass(frozen=True, slots=True)
class NinePatch:
    """``asset_id``: a project asset (or a .png path); ``left/top/right/bottom``: the corner
    sizes in picture pixels; ``scale``: how large a picture pixel is drawn (pixel art is
    usually drawn 2x or 3x)."""

    asset_id: str
    left: int = 4
    top: int = 4
    right: int = 4
    bottom: int = 4
    scale: float = 1.0

    def __post_init__(self):
        if not str(self.asset_id).strip():
            raise ValueError("a nine-patch needs an asset_id")
        for name in ("left", "top", "right", "bottom"):
            if int(getattr(self, name)) < 0:
                raise ValueError(f"{name} must be >= 0")
            object.__setattr__(self, name, int(getattr(self, name)))
        if not float(self.scale) > 0:
            raise ValueError("scale must be > 0")
        object.__setattr__(self, "scale", float(self.scale))
        object.__setattr__(self, "asset_id", str(self.asset_id).strip())

    def to_data(self):
        data = {
            "asset_id": self.asset_id,
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
        }
        if self.scale != 1.0:
            data["scale"] = self.scale
        return data

    @classmethod
    def from_data(cls, data):
        return cls(
            data["asset_id"],
            data.get("left", 4),
            data.get("top", 4),
            data.get("right", 4),
            data.get("bottom", 4),
            data.get("scale", 1.0),
        )


def skin_for(skins, role):
    """The nine-patch of the first ``(role pattern, NinePatch)`` pair whose pattern matches
    ``role`` (shell patterns: ``hud:*``, ``button:selected``, ``*``), or ``None``."""
    for pattern, patch in skins:
        if fnmatchcase(str(role), pattern):
            return patch
    return None


# picture -> {(width, height, patch, unit): the whole panel}: a HUD draws the same few panels
# every frame, and nine scaled pieces each were most of drawing one
_PANELS = weakref.WeakKeyDictionary()
_PANELS_PER_PICTURE = 64


def draw_nine_patch(pg, target, image, rect, patch, *, scale=1.0):
    """Draw ``image`` into ``rect`` of the ``target`` surface as ``patch`` describes."""
    x, y, w, h = rect
    if image.get_flags() & pg.SRCALPHA:  # composed once per size, then one blit a frame
        panels = _PANELS.get(image)
        if panels is None:
            panels = _PANELS[image] = {}
        key = (w, h, patch, float(scale))
        panel = panels.get(key)
        if panel is None:
            panel = pg.Surface((max(1, w), max(1, h)), pg.SRCALPHA)
            # the pieces never overlap: MAX onto a clear surface copies them exactly
            _nine_patch(pg, panel, image, (0, 0, w, h), patch, scale, pg.BLEND_RGBA_MAX)
            if len(panels) >= _PANELS_PER_PICTURE:
                panels.clear()
            panels[key] = panel
        target.blit(panel, (x, y))
        return
    _nine_patch(pg, target, image, rect, patch, scale, 0)


def _nine_patch(pg, target, image, rect, patch, scale, flags):
    unit = float(patch.scale) * float(scale)
    iw, ih = image.get_size()
    left, top = min(patch.left, iw // 2), min(patch.top, ih // 2)
    right, bottom = min(patch.right, iw - left), min(patch.bottom, ih - top)
    dl, dt = max(1, round(left * unit)), max(1, round(top * unit))
    dr, db = max(1, round(right * unit)), max(1, round(bottom * unit))
    x, y, w, h = rect
    if w < dl + dr or h < dt + db:  # smaller than its corners: squeeze the whole picture
        target.blit(pg.transform.scale(image, (max(1, w), max(1, h))), (x, y), special_flags=flags)
        return
    sx = (0, left, iw - right, iw)
    sy = (0, top, ih - bottom, ih)
    dx = (x, x + dl, x + w - dr, x + w)
    dy = (y, y + dt, y + h - db, y + h)
    for row in range(3):
        for col in range(3):
            source = pg.Rect(sx[col], sy[row], sx[col + 1] - sx[col], sy[row + 1] - sy[row])
            size = (dx[col + 1] - dx[col], dy[row + 1] - dy[row])
            if source.width <= 0 or source.height <= 0 or size[0] <= 0 or size[1] <= 0:
                continue
            piece = image.subsurface(source)
            if piece.get_size() != size:
                piece = pg.transform.scale(piece, size)
            target.blit(piece, (dx[col], dy[row]), special_flags=flags)
