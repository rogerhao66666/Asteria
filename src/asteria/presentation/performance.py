from dataclasses import dataclass
from bisect import bisect_right
@dataclass(frozen=True,slots=True)
class FrameBudget:
 target_ms:float=16.667;max_events:int=4096;max_layers:int=4096
 def __post_init__(self):
  if min(self.target_ms,self.max_events,self.max_layers)<=0:raise ValueError("invalid budget")
@dataclass(frozen=True,slots=True)
class FrameDiagnostics:event_count:int;layer_count:int;estimated_work:int;over_budget:bool;notes:tuple=()
class IndexedEvents:
 def __init__(self,events):
  self.events=tuple(sorted(events,key=lambda e:e.time_ms));self.times=tuple(e.time_ms for e in self.events)
 def between(self,a,b):
  if b<a:raise ValueError("range")
  return self.events[bisect_right(self.times,a):bisect_right(self.times,b)]
 def through(self,t,cursor=0,limit=None):
  b=bisect_right(self.times,t);end=b if limit is None else min(b,cursor+limit)
  return self.events[cursor:end],end,b>end
class BoundedDispatcher:
 def __init__(self,events,max_events_per_tick=4096):
  if max_events_per_tick<=0:raise ValueError("limit")
  self.index=IndexedEvents(events);self.cursor=0;self.limit=max_events_per_tick
 def dispatch_through(self,t):
  x,self.cursor,back=self.index.through(t,self.cursor,self.limit);return x,back
 def reset(self):self.cursor=0
class ReuseBuffer:
 def __init__(self):self.items=[]
 def begin(self):self.items.clear();return self.items
def diagnose(events,layers,budget=FrameBudget()):
 n=[]
 if events>budget.max_events:n.append("event_dispatch_pressure")
 if layers>budget.max_layers:n.append("layer_submission_pressure")
 return FrameDiagnostics(events,layers,events+layers,bool(n),tuple(n))
@dataclass(frozen=True,slots=True)
class DegradationPolicy:
 allow_skip_cosmetic_particles:bool=False
 allow_reduce_offscreen_updates:bool=True
 allow_batch_compatible_layers:bool=True
 preserve_character_frames:bool=True
 preserve_timing:bool=True
 preserve_alpha:bool=True
DEFAULT_DEGRADATION_POLICY=DegradationPolicy()
