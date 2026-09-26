from dataclasses import dataclass,field
from .canonical import Kind
@dataclass(frozen=True,slots=True)
class VisualNode:id:str;label:str;depth:int;lane:int;parent_id:str|None;branch:str="children"
@dataclass(frozen=True,slots=True)
class VisualEdge:source:str;target:str;relation:str
@dataclass(frozen=True,slots=True)
class TimelineBlock:id:str;lane:int;start_hint:float;duration_hint:float|None;label:str
@dataclass(slots=True)
class LayoutState:
 zoom:float=1.;pan_x:float=0.;pan_y:float=0.;collapsed:set[str]=field(default_factory=set);positions:dict=field(default_factory=dict)
class PresentationVisualProjection:
 def __init__(self,editor):self.editor=editor;self.layout=LayoutState()
 def _label(self,n):
  if n.command:return f"{n.command.channel}:{n.command.action}"
  if n.kind in (Kind.WAIT_EVENT,Kind.EMIT_EVENT):return f"{n.kind.value}: {n.event_name}"
  if n.kind==Kind.NESTED:return f"nested: {n.sequence_ref}"
  return n.kind.value
 def graph(self):
  ns=[];es=[]
  def walk(n,d,l,p=None,b="children"):
   ns.append(VisualNode(n.id,self._label(n),d,l,p,b))
   if p:es.append(VisualEdge(p,n.id,b))
   if n.id in self.layout.collapsed:return
   for i,c in enumerate(n.children):walk(c,d+1,l+i,n.id,"children")
   for i,c in enumerate(n.else_children):walk(c,d+1,l+len(n.children)+i,n.id,"else")
  walk(self.editor.sequence.root,0,0);return tuple(ns),tuple(es)
 def timeline(self):
  bs=[];cursor=0.
  def walk(n,l):
   nonlocal cursor
   bs.append(TimelineBlock(n.id,l,cursor,n.duration_ms if n.kind==Kind.WAIT else None,self._label(n)))
   if n.kind==Kind.SEQUENCE:
    for c in n.children:
     walk(c,l)
     if c.kind==Kind.WAIT:cursor+=c.duration_ms
   elif n.kind==Kind.PARALLEL:
    base=cursor
    for i,c in enumerate(n.children):cursor=base;walk(c,l+i)
    cursor=base
   else:
    for i,c in enumerate(n.children):walk(c,l+i)
  walk(self.editor.sequence.root,0);return tuple(bs)
 def collapse(self,i,v=True):self.layout.collapsed.add(i) if v else self.layout.collapsed.discard(i)
 def set_position(self,i,x,y):self.layout.positions[i]=(float(x),float(y))
 def set_view(self,z=None,x=None,y=None):
  if z is not None:
   if z<=0:raise ValueError("zoom")
   self.layout.zoom=float(z)
  if x is not None:self.layout.pan_x=float(x)
  if y is not None:self.layout.pan_y=float(y)
 def move(self,*a,**k):return self.editor.move(*a,**k)
 def delete(self,i):return self.editor.delete(i)
 def select(self,i):return self.editor.select(i)
