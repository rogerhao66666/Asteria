"""Order-safe render batching and explicit backend resource lifetime."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Protocol,Sequence
from .render_integration import DrawPacket

@dataclass(frozen=True,slots=True)
class RenderBatch:
 key:tuple[str,str|None]
 packets:tuple[DrawPacket,...]

def compatible_batches(packets:Sequence[DrawPacket], material_for=lambda p:None)->tuple[RenderBatch,...]:
    """Batch only adjacent compatible packets after canonical z ordering.

    This never reorders across incompatible packets, preserving authored layer/z semantics.
    """
    ordered=sorted((p for p in packets if p.transform.visible and p.transform.opacity>0),
                   key=lambda p:(p.z,p.owner_id or "",p.component_id or "",p.asset_id))
    out=[]; key=None; buf=[]
    for p in ordered:
        k=(p.asset_id,material_for(p))
        if key is not None and k!=key:
            out.append(RenderBatch(key,tuple(buf)));buf=[]
        key=k;buf.append(p)
    if buf:out.append(RenderBatch(key,tuple(buf)))
    return tuple(out)

class ReleasableBackend(Protocol):
    def release_resource(self,resource:Any)->None: ...

class ResourceLifetimeCache:
    """Stable-id cache with explicit destruction on invalidate/clear."""
    def __init__(self,resolver,releaser):
        self.resolver=resolver;self.releaser=releaser;self._items={}
    def get(self,asset_id):
        if asset_id not in self._items:self._items[asset_id]=self.resolver(asset_id)
        return self._items[asset_id]
    def invalidate(self,asset_id):
        r=self._items.pop(asset_id,None)
        if r is not None:self.releaser(r)
    def clear(self):
        for k in sorted(self._items):self.releaser(self._items[k])
        self._items.clear()
    def __len__(self):return len(self._items)
