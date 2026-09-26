"""Frame-aware visual layers for layered character composition.

These layers carry presentation-only pixels such as a foreground hand/coat flap.
They intentionally have no weapon, equipment, JRPG, or ARPG semantics.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from .attachments import Transform2D

@dataclass(frozen=True, slots=True)
class FrameVisualLayer:
    asset_id: str
    component_id: str = "foreground"
    z: float = 0.0
    transform: Transform2D = Transform2D()
    frames: tuple[int, ...] = ()
    clips: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.asset_id or not self.component_id:
            raise ValueError("asset_id and component_id required")
        if any(f < 0 for f in self.frames):
            raise ValueError("frames must be >= 0")
        self.transform.validate()

    def matches(self, clip_id: str, frame: int) -> bool:
        return (not self.clips or clip_id in self.clips) and (not self.frames or frame in self.frames)

@dataclass(frozen=True, slots=True)
class ResolvedVisualLayer:
    asset_id: str
    component_id: str
    z: float
    transform: Transform2D

class ActorVisualLayerTrack:
    def __init__(self, layers: Iterable[FrameVisualLayer] = ()):
        self.layers = tuple(layers)
        for layer in self.layers: layer.validate()

    def resolve(self, clip_id: str, frame: int) -> tuple[ResolvedVisualLayer, ...]:
        if frame < 0: raise ValueError("frame must be >= 0")
        return tuple(ResolvedVisualLayer(x.asset_id,x.component_id,x.z,x.transform)
                     for x in self.layers if x.matches(clip_id,frame))

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return {"version":1,"layers":[asdict(x) for x in self.layers]}

    @classmethod
    def from_dict(cls, data: dict) -> "ActorVisualLayerTrack":
        out=[]
        for raw in data.get("layers",[]):
            t=raw.get("transform",{})
            out.append(FrameVisualLayer(
                raw["asset_id"], raw.get("component_id","foreground"), float(raw.get("z",0)),
                Transform2D(**t), tuple(int(x) for x in raw.get("frames",())), tuple(str(x) for x in raw.get("clips",()))))
        return cls(out)
