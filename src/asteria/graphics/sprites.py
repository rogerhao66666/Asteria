from dataclasses import dataclass,field
from asteria.assets import AssetRef
@dataclass(frozen=True,slots=True)
class SpriteFrame:
    x:int;y:int;width:int;height:int;pivot_x:float=0.5;pivot_y:float=1.0
    def validate(self):
        if self.width<=0 or self.height<=0: raise ValueError("positive frame size required")
        if self.x<0 or self.y<0: raise ValueError("non-negative coords required")
        if not(0<=self.pivot_x<=1 and 0<=self.pivot_y<=1): raise ValueError("pivot 0..1")
@dataclass(slots=True)
class SpriteSheet:
    texture:AssetRef;frames:list[SpriteFrame]=field(default_factory=list)
    def validate(self):
        if self.texture.expected_kind not in (None,"texture"): raise TypeError("texture ref required")
        if not self.frames: raise ValueError("frames required")
        for f in self.frames:f.validate()
@dataclass(frozen=True,slots=True)
class SpriteKeyframe:
    frame_index:int;duration:float
    def validate(self):
        if self.frame_index<0 or self.duration<=0: raise ValueError("invalid keyframe")
@dataclass(slots=True)
class SpriteClip:
    name:str;keyframes:list[SpriteKeyframe];loop:bool=True
    def validate(self,sheet):
        if not self.name or not self.keyframes: raise ValueError("clip data required")
        for k in self.keyframes:
            k.validate()
            if k.frame_index>=len(sheet.frames): raise ValueError("missing frame")
