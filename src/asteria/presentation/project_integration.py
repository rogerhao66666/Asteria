"""Project-facing integration seam for existing Scene and AssetStore implementations.

Protocols intentionally avoid defining replacement Scene/AssetStore models.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Protocol
from .attachment_runtime import AttachmentRuntime
from .e2e_pipeline import SceneActorBinding, PresentationE2EPipeline
from .property_animation import PropertyAnimator
from .render_integration import RenderTransform

class AssetResolver(Protocol):
    def exists(self, asset_id:str)->bool: ...
    def resolve(self, asset_id:str)->Any: ...

@dataclass(frozen=True,slots=True)
class ProjectActorRecord:
    actor_id:str
    actor_asset_id:str
    presentation_id:str|None=None
    transform:RenderTransform=RenderTransform()
    metadata:Mapping[str,Any]=None
    def __post_init__(self):
        if not self.actor_id or not self.actor_asset_id: raise ValueError("actor identifiers required")
        if self.metadata is None: object.__setattr__(self,"metadata",{})

@dataclass(frozen=True,slots=True)
class ProjectPresentationRecord:
    actors:tuple[ProjectActorRecord,...]
    properties:PropertyAnimator=PropertyAnimator()
    def __post_init__(self):
        ids=[a.actor_id for a in self.actors]
        if len(ids)!=len(set(ids)): raise ValueError("duplicate actor id")

class ProjectPresentationIntegrator:
    """Materializes the canonical presentation path from project-facing records."""
    def __init__(self,assets:AssetResolver,
                 animator_factory:Callable[[ProjectActorRecord,Any],Any],
                 attachment_factory:Callable[[ProjectActorRecord,AssetResolver],AttachmentRuntime]):
        self.assets=assets; self.animator_factory=animator_factory; self.attachment_factory=attachment_factory

    def _asset(self,asset_id):
        if not self.assets.exists(asset_id): raise ValueError(f"unknown asset: {asset_id}")
        return self.assets.resolve(asset_id)

    def materialize(self,record:ProjectPresentationRecord)->PresentationE2EPipeline:
        # Full preflight first: actor refs and all attachment refs must be valid
        # before the returned runtime is exposed.
        staged=[]
        for a in record.actors:
            actor_asset=self._asset(a.actor_asset_id)
            runtime=self.attachment_factory(a,self.assets)
            for inst in runtime.instances.values():
                if inst.state.value!="detached": self._asset(inst.spec.asset_id)
            animator=self.animator_factory(a,actor_asset)
            staged.append(SceneActorBinding(a.actor_id,a.actor_asset_id,animator,runtime,
                                            a.transform,dict(a.metadata)))
        return PresentationE2EPipeline(tuple(staged),record.properties,self.assets.exists)
