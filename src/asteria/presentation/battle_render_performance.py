from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _positive(value, name):
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and > 0")
    return value


@dataclass(frozen=True, slots=True)
class BattleRenderDraw:
    draw_id: str
    asset_id: str
    layer: int
    depth: float
    x: float
    y: float
    width: float
    height: float
    visible: bool = True
    material_id: str = "sprite.default"
    atlas_id: str | None = None


@dataclass(frozen=True, slots=True)
class BattleRenderBatch:
    batch_key: tuple[str, str, int]
    draws: tuple[BattleRenderDraw, ...]


@dataclass(frozen=True, slots=True)
class BattleRenderCullResult:
    visible: tuple[BattleRenderDraw, ...]
    culled_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BattleFrameBudgetMetrics:
    frame_count: int
    dropped_frames: int
    last_frame_ms: float
    max_frame_ms: float
    average_frame_ms: float
    target_frame_ms: float


class BattleFrameBudgetTracker:
    def __init__(self, target_fps=60.0):
        self.target_frame_ms = 1000.0 / _positive(target_fps, "target_fps")
        self.frame_count = 0
        self.dropped_frames = 0
        self.total_frame_ms = 0.0
        self.max_frame_ms = 0.0
        self.last_frame_ms = 0.0

    def record(self, frame_ms):
        frame_ms = float(frame_ms)
        if not isfinite(frame_ms) or frame_ms < 0:
            raise ValueError("frame_ms must be finite and >= 0")
        self.frame_count += 1
        self.last_frame_ms = frame_ms
        self.total_frame_ms += frame_ms
        self.max_frame_ms = max(self.max_frame_ms, frame_ms)
        if frame_ms > self.target_frame_ms:
            self.dropped_frames += 1
        return self.metrics()

    def metrics(self):
        avg = 0.0 if not self.frame_count else self.total_frame_ms / self.frame_count
        return BattleFrameBudgetMetrics(
            self.frame_count,
            self.dropped_frames,
            self.last_frame_ms,
            self.max_frame_ms,
            avg,
            self.target_frame_ms,
        )


class BattleRenderVisibilityCuller:
    def __init__(self, *, min_x=0.0, min_y=0.0, max_x=320.0, max_y=180.0, padding=16.0):
        self.min_x = float(min_x) - float(padding)
        self.min_y = float(min_y) - float(padding)
        self.max_x = float(max_x) + float(padding)
        self.max_y = float(max_y) + float(padding)

    def resolve(self, draws):
        visible = []
        culled = []
        for draw in draws:
            if not draw.visible:
                culled.append(draw.draw_id)
                continue
            right = draw.x + draw.width
            bottom = draw.y + draw.height
            if (
                right < self.min_x
                or draw.x > self.max_x
                or bottom < self.min_y
                or draw.y > self.max_y
            ):
                culled.append(draw.draw_id)
            else:
                visible.append(draw)
        return BattleRenderCullResult(tuple(visible), tuple(culled))


class BattleRenderBatcher:
    """Groups visible sprite draws by atlas/material/layer.

    This is backend-neutral batch planning. A concrete renderer may map each
    group to one or more real GPU draw calls.
    """

    def build(self, draws):
        groups = {}
        for draw in draws:
            atlas = draw.atlas_id or draw.asset_id
            key = (atlas, draw.material_id, int(draw.layer))
            groups.setdefault(key, []).append(draw)
        return tuple(
            BattleRenderBatch(key, tuple(sorted(values, key=lambda x: (x.depth, x.draw_id))))
            for key, values in sorted(groups.items())
        )


@dataclass(slots=True)
class BattleTransientObject:
    object_id: int
    active: bool = False
    kind: str = ""
    payload: object = None


class BattleTransientPool:
    """Reusable pool for VFX/popups/transient presentation objects."""

    def __init__(self, capacity):
        capacity = int(capacity)
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._objects = [BattleTransientObject(i) for i in range(capacity)]
        self._free = list(reversed(range(capacity)))
        self.peak_active = 0

    def acquire(self, kind, payload=None):
        if not self._free:
            return None
        index = self._free.pop()
        obj = self._objects[index]
        obj.active = True
        obj.kind = str(kind)
        obj.payload = payload
        active = len(self._objects) - len(self._free)
        self.peak_active = max(self.peak_active, active)
        return obj

    def release(self, obj):
        if not isinstance(obj, BattleTransientObject) or not obj.active:
            return False
        obj.active = False
        obj.kind = ""
        obj.payload = None
        self._free.append(obj.object_id)
        return True

    @property
    def active_count(self):
        return len(self._objects) - len(self._free)

    @property
    def capacity(self):
        return len(self._objects)


class BattleAssetPreloadRegistry:
    """Tracks presentation assets expected before a battle scene becomes hot."""

    def __init__(self):
        self._required = []
        self._loaded = set()

    def require(self, *asset_ids):
        for asset_id in asset_ids:
            asset_id = str(asset_id).strip()
            if asset_id and asset_id not in self._required:
                self._required.append(asset_id)

    def mark_loaded(self, *asset_ids):
        for asset_id in asset_ids:
            asset_id = str(asset_id).strip()
            if asset_id:
                self._loaded.add(asset_id)

    @property
    def missing(self):
        return tuple(x for x in self._required if x not in self._loaded)

    @property
    def ready(self):
        return not self.missing
