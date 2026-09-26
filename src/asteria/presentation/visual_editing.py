from __future__ import annotations
from dataclasses import dataclass,field,replace
from copy import deepcopy
from .canonical import Node,Kind
from .editor_model import PresentationEditorModel,_find

def _clone(node:Node,suffix:str)->Node:
 def c(n):
  return replace(n,id=n.id+suffix,children=tuple(c(x) for x in n.children),else_children=tuple(c(x) for x in n.else_children))
 return c(node)

@dataclass(slots=True)
class VisualEditState:
 selected:list[str]=field(default_factory=list)
 clipboard:Node|None=None
 clipboard_cut:bool=False
 snap_ms:float=10.0
 playhead_ms:float=0.0
 active_nodes:tuple[str,...]=()

class PresentationVisualEditor:
 def __init__(self,editor:PresentationEditorModel):
  self.editor=editor;self.state=VisualEditState()
 def select(self,node_id,add=False):
  self.editor.select(node_id)
  if add:
   if node_id not in self.state.selected:self.state.selected.append(node_id)
  else:self.state.selected=[node_id]
 def clear_selection(self):self.state.selected.clear()
 def copy(self,node_id=None):
  n=_find(self.editor.sequence.root,node_id or self.editor.selected_id)
  if not n:raise KeyError(node_id)
  self.state.clipboard=deepcopy(n);self.state.clipboard_cut=False
 def cut(self,node_id=None):
  nid=node_id or self.editor.selected_id;self.copy(nid);self.state.clipboard_cut=True;self.editor.delete(nid)
 def paste(self,parent_id,new_suffix="_copy",index=None,branch="children"):
  if self.state.clipboard is None:raise ValueError("clipboard empty")
  n=_clone(self.state.clipboard,new_suffix)
  self.editor.insert(parent_id,n,index,branch)
  if self.state.clipboard_cut:self.state.clipboard_cut=False;self.state.clipboard=None
  return n.id
 def duplicate(self,node_id,parent_id,index=None,branch="children",suffix="_copy"):
  n=_find(self.editor.sequence.root,node_id)
  if not n:raise KeyError(node_id)
  c=_clone(n,suffix);self.editor.insert(parent_id,c,index,branch);return c.id
 def reorder(self,node_id,parent_id,index,branch="children"):
  self.editor.move(node_id,parent_id,index,branch)
 def set_snap(self,ms):
  if ms<=0:raise ValueError("snap must be positive")
  self.state.snap_ms=float(ms)
 def snap(self,time_ms):
  q=self.state.snap_ms;return round(float(time_ms)/q)*q
 def set_playhead(self,time_ms):
  if time_ms<0:raise ValueError("negative playhead")
  self.state.playhead_ms=float(time_ms)
 def sync_preview(self,preview):
  self.state.playhead_ms=float(preview.time_ms);self.state.active_nodes=tuple(preview.active_nodes())
 def ruler_ticks(self,start_ms,end_ms):
  if end_ms<start_ms:raise ValueError("range")
  q=self.state.snap_ms;first=self.snap(start_ms)
  if first<start_ms:first+=q
  out=[];x=first
  while x<=end_ms+1e-9:out.append(x);x+=q
  return tuple(out)
