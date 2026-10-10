from dataclasses import dataclass
from typing import Any, Protocol

from asteria.graphics.character_placement import standing_point_for_cell

from .browser_workspace import AssetDragPayload


def character_cell_position(column, row, tile_size=(48, 48)):
    return standing_point_for_cell(column, row, tile_size)


@dataclass(frozen=True, slots=True)
class SceneAssetRef:
    asset_id: str
    kind: str


@dataclass(frozen=True, slots=True)
class PlacementRequest:
    payload: AssetDragPayload
    position: tuple[float, float] = (0.0, 0.0)
    parent_id: str | None = None
    properties: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class PlacementResult:
    object_id: str
    asset_ref: SceneAssetRef
    component_type: str = "asset"


class ScenePlacementTarget(Protocol):
    def create_object(self, **kwargs) -> str: ...
    def remove_object(self, object_id: str) -> None: ...


class PlacementHandlerRegistry:
    def __init__(self):
        self._h = {}

    def register(self, kind, handler, replace_existing=False):
        if not kind:
            raise ValueError("kind")
        if kind in self._h and not replace_existing:
            raise ValueError("handler exists")
        self._h[kind] = handler

    def unregister(self, kind):
        self._h.pop(kind, None)

    def resolve(self, kind):
        h = self._h.get(kind) or self._h.get("*")
        if h is None:
            raise KeyError(kind)
        return h


def generic_asset_handler(q, t):
    ref = SceneAssetRef(q.payload.asset_id, q.payload.kind)
    oid = t.create_object(
        parent_id=q.parent_id, position=q.position, component_type="asset", asset_ref=ref, properties=q.properties
    )
    return PlacementResult(oid, ref)


@dataclass
class PlaceAssetCommand:
    request: PlacementRequest
    target: ScenePlacementTarget
    handlers: PlacementHandlerRegistry
    result: PlacementResult | None = None
    _done: bool = False

    def execute(self):
        if self._done:
            raise RuntimeError("already executed")
        self.result = self.handlers.resolve(self.request.payload.kind)(self.request, self.target)
        self._done = True
        return self.result

    def undo(self):
        if not self._done or self.result is None:
            raise RuntimeError("not executed")
        self.target.remove_object(self.result.object_id)
        self._done = False

    def redo(self):
        if self._done:
            raise RuntimeError("already executed")
        return self.execute()


class RecordingScene:
    def __init__(self):
        self.objects = {}
        self._next = 1

    def create_object(self, **kw):
        oid = f"obj-{self._next}"
        self._next += 1
        self.objects[oid] = kw
        return oid

    def remove_object(self, oid):
        if oid not in self.objects:
            raise KeyError(oid)
        del self.objects[oid]
