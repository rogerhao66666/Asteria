from dataclasses import dataclass

LIGHT_POINT="point"
LIGHT_DIRECTIONAL="directional"
VALID_LIGHT_KINDS={LIGHT_POINT,LIGHT_DIRECTIONAL}

@dataclass(frozen=True,slots=True)
class Light2D:
    light_id:str
    kind:str=LIGHT_POINT
    x:float=0.0
    y:float=0.0
    radius:float=128.0
    intensity:float=1.0
    color:tuple[float,float,float]=(1.0,1.0,1.0)
    casts_shadow:bool=False
    layer_mask:int=-1

    def validate(self):
        if not self.light_id:
            raise ValueError("light_id required")
        if self.kind not in VALID_LIGHT_KINDS:
            raise ValueError("unsupported light kind")
        if self.kind==LIGHT_POINT and self.radius<=0:
            raise ValueError("point light radius must be positive")
        if self.intensity<0:
            raise ValueError("light intensity must be non-negative")
        if len(self.color)!=3 or any(c<0 for c in self.color):
            raise ValueError("invalid light color")
