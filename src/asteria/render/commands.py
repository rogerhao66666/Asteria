from dataclasses import dataclass

@dataclass(frozen=True,slots=True)
class LitSpriteDraw:
    material_id:str
    source:tuple[int,int,int,int]
    screen_x:float
    screen_y:float
    width:float
    height:float
    layer:int=0
    depth:float=0.0
    opacity:float=1.0
    flip_x:bool=False

@dataclass(frozen=True,slots=True)
class LightCommand:
    light_id:str;kind:str;screen_x:float;screen_y:float;radius:float;intensity:float
    color:tuple[float,float,float];casts_shadow:bool;layer_mask:int

@dataclass(frozen=True,slots=True)
class ShadowCasterCommand:
    caster_id:str;polygon:tuple[tuple[float,float],...];layer:int=0;depth:float=0.0
