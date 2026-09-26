"""Headless end-to-end seam for Asset -> Actor -> Presentation -> Renderer.

This composes existing canonical subsystems; it deliberately does not introduce
another scene, animator, AssetStore, or renderer model.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from .actor_attachment import ActorAttachmentBinding, ActorAnimatorSource
from .attachment_runtime import AttachmentRuntime
from .property_animation import PropertyAnimator, PresentationChannels, split_channels
from .render_integration import DrawPacket, PresentationRenderComposer, RenderTransform

@dataclass(frozen=True, slots=True)
class SceneActorBinding:
    actor_id: str
    actor_asset_id: str
    animator: ActorAnimatorSource
    attachments: AttachmentRuntime
    base_transform: RenderTransform = RenderTransform()
    metadata: Mapping[str,Any] = field(default_factory=dict)
    def __post_init__(self):
        if not self.actor_id or not self.actor_asset_id:
            raise ValueError("actor_id and actor_asset_id required")

@dataclass(frozen=True, slots=True)
class PresentationFrame:
    time_ms: float
    draw_packets: tuple[DrawPacket,...]
    channels: PresentationChannels

class PresentationE2EPipeline:
    """Samples actor animation, sockets, properties and renderer packets together."""
    def __init__(self, actors, properties:PropertyAnimator=PropertyAnimator(),
                 asset_exists:Callable[[str],bool]|None=None):
        actors=tuple(actors)
        ids=[a.actor_id for a in actors]
        if len(ids)!=len(set(ids)): raise ValueError("duplicate actor id")
        self.actors=actors; self.properties=properties; self.asset_exists=asset_exists
        self._composer=PresentationRenderComposer()

    def _check_asset(self, asset_id:str):
        if self.asset_exists is not None and not self.asset_exists(asset_id):
            raise ValueError(f"unknown asset: {asset_id}")

    @staticmethod
    def _actor_modifier(values, actor_id):
        def get(name, default):
            return values.get(f"actor.{actor_id}.{name}", values.get(f"actor.{name}", default))
        return RenderTransform(
            x=get("x",0.0), y=get("y",0.0), rotation_deg=get("rotation_deg",0.0),
            scale_x=get("scale_x",1.0), scale_y=get("scale_y",1.0),
            opacity=get("opacity",1.0), visible=bool(get("visible",1.0)),
            flip_x=bool(get("flip_x",0.0)), flip_y=bool(get("flip_y",0.0)),
        )

    def sample(self,time_ms:float)->PresentationFrame:
        if time_ms < 0: raise ValueError("negative time")
        values=self.properties.sample(time_ms)
        packets=[]
        for actor in self.actors:
            self._check_asset(actor.actor_asset_id)
            frame=ActorAttachmentBinding(actor.actor_id,actor.animator,actor.attachments).resolve()
            for resolved in frame.attachments: self._check_asset(resolved.asset_id)
            mod=self._actor_modifier(values,actor.actor_id)
            packets.extend(self._composer.actor_packets(frame,actor.actor_asset_id,actor.base_transform,
                                                        modifier=lambda _t,m=mod:m,render_time_ms=time_ms))
        packets.sort(key=lambda p:(p.z,p.owner_id or "",p.component_id or "",p.asset_id))
        return PresentationFrame(time_ms,tuple(packets),split_channels(values))
