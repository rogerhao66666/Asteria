"""Generic continuous property animation and modulation.

Presentation targets are opaque project/runtime property paths. Engine Core does
not assign gameplay meaning to them. Curves and procedural modifiers can be
layered and sampled independently of sprite-frame rate.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from math import cos, pi, sin, tau
from typing import Callable, Mapping

class Ease(str, Enum):
    LINEAR="linear"; STEP="step"; EASE_IN="ease_in"; EASE_OUT="ease_out"; EASE_IN_OUT="ease_in_out"

@dataclass(frozen=True, slots=True)
class PropertyKey:
    time_ms: float
    value: float
    ease: Ease=Ease.LINEAR
    def __post_init__(self):
        if self.time_ms < 0: raise ValueError("negative key time")

def _ease(kind:Ease,t:float)->float:
    if kind is Ease.STEP: return 0.0
    if kind is Ease.EASE_IN: return t*t
    if kind is Ease.EASE_OUT: return 1-(1-t)*(1-t)
    if kind is Ease.EASE_IN_OUT: return 0.5-(cos(pi*t)/2)
    return t

@dataclass(frozen=True, slots=True)
class PropertyCurve:
    target: str
    keys: tuple[PropertyKey,...]
    def __post_init__(self):
        if not self.target: raise ValueError("target required")
        if not self.keys: raise ValueError("keys required")
        if any(b.time_ms <= a.time_ms for a,b in zip(self.keys,self.keys[1:])):
            raise ValueError("key times must strictly increase")
    def sample(self,time_ms:float)->float:
        if time_ms <= self.keys[0].time_ms: return self.keys[0].value
        if time_ms >= self.keys[-1].time_ms: return self.keys[-1].value
        for a,b in zip(self.keys,self.keys[1:]):
            if a.time_ms <= time_ms < b.time_ms:
                u=(time_ms-a.time_ms)/(b.time_ms-a.time_ms)
                return a.value+(b.value-a.value)*_ease(a.ease,u)
        return self.keys[-1].value

@dataclass(frozen=True, slots=True)
class Oscillator:
    amplitude: float
    frequency_hz: float
    phase: float=0.0
    waveform: str="sine"
    def __post_init__(self):
        if self.frequency_hz < 0: raise ValueError("negative frequency")
        if self.waveform not in ("sine","cosine"): raise ValueError("waveform")
    def sample(self,time_ms:float)->float:
        x=tau*(self.frequency_hz*time_ms/1000+self.phase)
        return self.amplitude*(sin(x) if self.waveform=="sine" else cos(x))

@dataclass(frozen=True, slots=True)
class Envelope:
    duration_ms: float
    attack_ms: float=0.0
    decay_power: float=1.0
    def __post_init__(self):
        if self.duration_ms <= 0 or self.attack_ms < 0 or self.attack_ms > self.duration_ms or self.decay_power < 0:
            raise ValueError("invalid envelope")
    def sample(self,time_ms:float)->float:
        if time_ms < 0 or time_ms >= self.duration_ms: return 0.0
        if self.attack_ms and time_ms < self.attack_ms: return time_ms/self.attack_ms
        span=max(self.duration_ms-self.attack_ms,1e-12)
        u=(time_ms-self.attack_ms)/span
        return max(0.0,1-u)**self.decay_power

@dataclass(frozen=True, slots=True)
class Modulation:
    target: str
    oscillator: Oscillator
    envelope: Envelope
    mode: str="add"
    def __post_init__(self):
        if not self.target: raise ValueError("target required")
        if self.mode not in ("add","multiply"): raise ValueError("mode")
    def sample(self,time_ms:float)->float:
        return self.oscillator.sample(time_ms)*self.envelope.sample(time_ms)

class PropertyAnimator:
    def __init__(self, curves=(), modulations=()):
        self.curves=tuple(curves); self.modulations=tuple(modulations)
    def sample(self,time_ms:float)->dict[str,float]:
        if time_ms < 0: raise ValueError("negative time")
        values={c.target:c.sample(time_ms) for c in self.curves}
        for m in self.modulations:
            v=m.sample(time_ms)
            if m.mode=="add": values[m.target]=values.get(m.target,0.0)+v
            else: values[m.target]=values.get(m.target,1.0)*(1.0+v)
        return values

@dataclass(frozen=True, slots=True)
class PresentationChannels:
    camera: Mapping[str,float]
    material: Mapping[str,float]
    vfx: Mapping[str,float]
    audio: Mapping[str,float]
    custom: Mapping[str,float]

def split_channels(values:Mapping[str,float])->PresentationChannels:
    buckets={"camera":{},"material":{},"vfx":{},"audio":{},"custom":{}}
    for k,v in values.items():
        head,sep,tail=k.partition(".")
        if sep and head in ("camera","material","vfx","audio"):
            buckets[head][tail]=v
        else: buckets["custom"][k]=v
    return PresentationChannels(**buckets)
