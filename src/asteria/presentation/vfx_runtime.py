"""Generic VFX/particle production runtime.

VFX is presentation data: emitters, particles and their continuously sampled
properties carry no gameplay semantics.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import cos, sin, radians
from typing import Mapping

@dataclass(frozen=True,slots=True)
class Particle:
    id:str; x:float; y:float; vx:float=0; vy:float=0
    age_ms:float=0; lifetime_ms:float=1000
    scale:float=1; rotation_deg:float=0; opacity:float=1
    asset_id:str|None=None
    def sample(self,dt_ms:float)->"Particle":
        age=self.age_ms+dt_ms
        return Particle(self.id,self.x+self.vx*dt_ms/1000,self.y+self.vy*dt_ms/1000,
                        self.vx,self.vy,age,self.lifetime_ms,self.scale,self.rotation_deg,
                        self.opacity,self.asset_id)
    @property
    def alive(self): return self.age_ms < self.lifetime_ms and self.opacity>0

@dataclass(frozen=True,slots=True)
class VFXFrame:
    particles:tuple[Particle,...]
    properties:Mapping[str,float]

class VFXRuntime:
    def __init__(self,particles=()):
        self._particles={p.id:p for p in particles}; self.properties={}

    def apply_properties(self,values:Mapping[str,float])->None:
        self.properties.update(values)

    def spawn(self,p:Particle)->None:
        if p.id in self._particles: raise ValueError("duplicate particle id")
        if p.lifetime_ms<=0: raise ValueError("particle lifetime must be positive")
        self._particles[p.id]=p

    def update(self,dt_ms:float)->None:
        if dt_ms<0: raise ValueError("negative dt")
        updated=(p.sample(dt_ms) for p in self._particles.values())
        self._particles={p.id:p for p in updated if p.alive}

    def frame(self)->VFXFrame:
        return VFXFrame(tuple(sorted(self._particles.values(),key=lambda p:p.id)),dict(self.properties))

    def clear(self)->None:
        self._particles.clear(); self.properties.clear()
