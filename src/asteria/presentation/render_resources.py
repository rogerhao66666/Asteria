from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .render_bridge import RenderBackend, RenderBatch


@dataclass(frozen=True, slots=True)
class TextureSpec:
    asset_id: str
    width: int
    height: int
    channels: int = 4

    def __post_init__(self):
        if min(self.width, self.height, self.channels) <= 0:
            raise ValueError("invalid texture dimensions")

    @property
    def bytes_estimate(self):
        return self.width * self.height * self.channels


@dataclass(slots=True)
class TextureRecord:
    spec: TextureSpec
    handle: Any
    refs: int = 0
    last_used_frame: int = 0


class TextureStore:
    def __init__(self, loader: Callable, releaser: Callable, budget_bytes=268435456):
        self.loader, self.releaser, self.budget_bytes = loader, releaser, budget_bytes
        self.records = {}
        self.frame = 0

    def begin_frame(self):
        self.frame += 1

    @property
    def resident_bytes(self):
        return sum(r.spec.bytes_estimate for r in self.records.values())

    def acquire(self, spec):
        r = self.records.get(spec.asset_id)
        if r and r.spec != spec:
            raise ValueError("asset id/spec mismatch")
        if not r:
            r = TextureRecord(spec, self.loader(spec))
            self.records[spec.asset_id] = r
        r.refs += 1
        r.last_used_frame = self.frame
        return r.handle

    def release(self, aid):
        r = self.records[aid]
        r.refs = max(0, r.refs - 1)

    def evict_to_budget(self):
        v = sorted((r for r in self.records.values() if r.refs == 0), key=lambda r: r.last_used_frame)
        out = []
        while self.resident_bytes > self.budget_bytes and v:
            r = v.pop(0)
            self.releaser(r.handle)
            del self.records[r.spec.asset_id]
            out.append(r.spec.asset_id)
        return tuple(out)

    def close(self):
        for r in tuple(self.records.values()):
            self.releaser(r.handle)
        self.records.clear()


class ResourceRenderAdapter:
    def __init__(self, backend: RenderBackend, textures: TextureStore, spec_resolver: Callable):
        self.backend, self.textures, self.spec_resolver = backend, textures, spec_resolver
        self.held = []

    def begin_frame(self, camera=None):
        self.textures.begin_frame()
        self.held = []
        self.backend.begin_frame(camera)

    def submit(self, batch: RenderBatch):
        for i in batch.items:
            self.textures.acquire(self.spec_resolver(i.asset_id))
            self.held.append(i.asset_id)
        self.backend.submit(batch)

    def end_frame(self):
        self.backend.end_frame()
        for a in self.held:
            self.textures.release(a)
        self.held = []
        self.textures.evict_to_budget()
