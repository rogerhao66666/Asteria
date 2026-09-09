from dataclasses import dataclass

@dataclass(frozen=True,slots=True)
class AmbientLight2D:
    color:tuple[float,float,float]=(1.0,1.0,1.0)
    intensity:float=0.25
    def validate(self):
        if self.intensity<0:
            raise ValueError("ambient intensity must be non-negative")
        if len(self.color)!=3 or any(c<0 for c in self.color):
            raise ValueError("invalid ambient color")

@dataclass(frozen=True,slots=True)
class Fog2D:
    density:float=0.0
    color:tuple[float,float,float]=(0.5,0.5,0.5)
    start_depth:float=0.0
    end_depth:float=1.0
    def validate(self):
        if not 0.0<=self.density<=1.0:
            raise ValueError("fog density must be 0..1")
        if self.end_depth<self.start_depth:
            raise ValueError("fog depth range invalid")

@dataclass(frozen=True,slots=True)
class ParticleEmitter2D:
    emitter_id:str
    max_particles:int=128
    spawn_rate:float=10.0
    lifetime:float=1.0
    speed_min:float=0.0
    speed_max:float=20.0
    layer:int=0
    depth:float=0.0
    def validate(self):
        if not self.emitter_id: raise ValueError("emitter_id required")
        if self.max_particles<0 or self.spawn_rate<0 or self.lifetime<=0:
            raise ValueError("invalid particle parameters")
        if self.speed_min<0 or self.speed_max<self.speed_min:
            raise ValueError("invalid particle speed range")
