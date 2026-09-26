from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Protocol
from .property_animation import PresentationChannels
class PropertySink(Protocol):
 def apply_properties(self, values:Mapping[str,float])->None: ...
@dataclass(frozen=True,slots=True)
class ChannelDispatchStats:
 camera:int=0; material:int=0; vfx:int=0; audio:int=0; custom:int=0
class PresentationChannelExecutor:
 def __init__(self,*,camera=None,material=None,vfx=None,audio=None,custom=None): self.sinks={"camera":camera,"material":material,"vfx":vfx,"audio":audio,"custom":custom}
 def execute(self,c:PresentationChannels)->ChannelDispatchStats:
  counts={}
  for name,values in (("camera",c.camera),("material",c.material),("vfx",c.vfx),("audio",c.audio),("custom",c.custom)):
   sink=self.sinks[name]
   if sink is not None and values: sink.apply_properties(dict(values))
   counts[name]=len(values) if sink is not None else 0
  return ChannelDispatchStats(**counts)
