from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class TextTransform:
    x: float = 0.0
    y: float = 0.0
    scale: float = 1.0
    rotation_deg: float = 0.0
    opacity: float = 1.0

    def __post_init__(self):
        if self.scale < 0:
            raise ValueError("scale must be >= 0")
        if not 0 <= self.opacity <= 1:
            raise ValueError("opacity must be in [0,1]")


@dataclass(frozen=True, slots=True)
class TextKey:
    t: float
    transform: TextTransform

    def __post_init__(self):
        if not 0 <= self.t <= 1:
            raise ValueError("key t must be in [0,1]")


@dataclass(frozen=True, slots=True)
class AnimatedTextSpec:
    text: str
    duration_ms: float = 600.0
    space: str = "world"
    anchor_id: str | None = None
    font_asset_id: str | None = None
    material_asset_id: str | None = None
    style_id: str | None = None
    z_order: int = 0
    keys: tuple[TextKey, ...] = (TextKey(0.0, TextTransform()), TextKey(1.0, TextTransform(y=-24.0, opacity=0.0)))
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.duration_ms <= 0:
            raise ValueError("duration_ms must be > 0")
        if self.space not in ("world", "screen"):
            raise ValueError("space must be world or screen")
        if not self.keys:
            raise ValueError("keys required")
        ts = [k.t for k in self.keys]
        if ts != sorted(ts) or len(set(ts)) != len(ts):
            raise ValueError("keys must be strictly increasing")


@dataclass(frozen=True, slots=True)
class ResolvedText:
    instance_id: str
    text: str
    space: str
    anchor_id: str | None
    font_asset_id: str | None
    material_asset_id: str | None
    style_id: str | None
    transform: TextTransform
    z_order: int
    finished: bool
    metadata: Mapping[str, Any]


def _lerp(a, b, t):
    return a + (b - a) * t


def _interp(a, b, t):
    return TextTransform(
        _lerp(a.x, b.x, t),
        _lerp(a.y, b.y, t),
        _lerp(a.scale, b.scale, t),
        _lerp(a.rotation_deg, b.rotation_deg, t),
        _lerp(a.opacity, b.opacity, t),
    )


class AnimatedTextRuntime:
    def __init__(self):
        self._items = {}

    def spawn(self, i, s):
        if not i:
            raise ValueError("instance_id required")
        if i in self._items:
            raise ValueError("duplicate animated text")
        self._items[i] = (s, 0.0)

    def remove(self, i):
        self._items.pop(i, None)

    def clear(self):
        self._items.clear()

    def resolve_all(self):
        return tuple(self._resolve(i, s, e) for i, (s, e) in sorted(self._items.items()))

    def update(self, dt):
        if dt < 0:
            raise ValueError("negative dt")
        for i, (s, e) in tuple(self._items.items()):
            self._items[i] = (s, e + dt)
        out = self.resolve_all()
        for x in out:
            if x.finished:
                self._items.pop(x.instance_id, None)
        return out

    def _resolve(self, i, s, e):
        p = min(1.0, e / s.duration_ms)
        ks = s.keys
        if p <= ks[0].t:
            tr = ks[0].transform
        elif p >= ks[-1].t:
            tr = ks[-1].transform
        else:
            tr = ks[-1].transform
            for a, b in zip(ks, ks[1:]):
                if a.t <= p <= b.t:
                    tr = _interp(a.transform, b.transform, (p - a.t) / (b.t - a.t))
                    break
        return ResolvedText(
            i,
            s.text,
            s.space,
            s.anchor_id,
            s.font_asset_id,
            s.material_asset_id,
            s.style_id,
            tr,
            s.z_order,
            e >= s.duration_ms,
            s.metadata,
        )
