"""Headless Asset Browser workspace/controller and extension seams."""
from dataclasses import dataclass,replace
from typing import Any,Callable
from .browser import AssetBrowserModel,AssetBrowserQuery,AssetBrowserItem,AssetInspector

@dataclass(frozen=True,slots=True)
class AssetPreview:
 asset_id:str;kind:str;provider:str;content:Any
@dataclass(frozen=True,slots=True)
class AssetDragPayload:
 asset_id:str;kind:str;source_uri:str;metadata:tuple[tuple[str,Any],...]=()
@dataclass(frozen=True,slots=True)
class AssetBrowserState:
 query:AssetBrowserQuery=AssetBrowserQuery()
 selected_id:str|None=None
 group_by_kind:bool=False

class PreviewProviderRegistry:
 def __init__(self):self._providers={}
 def register(self,kind:str,provider:Callable,*,replace_existing=False):
  if not kind:raise ValueError("kind")
  if kind in self._providers and not replace_existing:raise ValueError(f"provider exists: {kind}")
  self._providers[kind]=provider
 def unregister(self,kind):self._providers.pop(kind,None)
 def has(self,kind):return kind in self._providers
 def preview(self,item:AssetInspector):
  fn=self._providers.get(item.kind) or self._providers.get("*")
  if fn is None:return AssetPreview(item.asset_id,item.kind,"none",{"source_uri":item.source_uri})
  out=fn(item)
  return out if isinstance(out,AssetPreview) else AssetPreview(item.asset_id,item.kind,getattr(fn,"__name__","provider"),out)

class AssetBrowserWorkspace:
 def __init__(self,model:AssetBrowserModel,previews:PreviewProviderRegistry|None=None):
  self.model=model;self.previews=previews or PreviewProviderRegistry();self.state=AssetBrowserState()
 def set_search(self,text):self.state=replace(self.state,query=replace(self.state.query,text=text));return self.refresh()
 def set_kinds(self,kinds):self.state=replace(self.state,query=replace(self.state.query,kinds=frozenset(kinds)));return self.refresh()
 def set_tags(self,tags):self.state=replace(self.state,query=replace(self.state.query,tags=frozenset(tags)));return self.refresh()
 def set_sort(self,sort_by,descending=False):self.state=replace(self.state,query=replace(self.state.query,sort_by=sort_by,descending=descending));return self.refresh()
 def set_grouped(self,enabled):self.state=replace(self.state,group_by_kind=bool(enabled));return self.refresh()
 def refresh(self):return self.model.groups(self.state.query) if self.state.group_by_kind else self.model.items(self.state.query)
 def select(self,asset_id):
  self.model.select(asset_id);self.state=replace(self.state,selected_id=asset_id);return self.inspector()
 def clear_selection(self):
  self.model.clear_selection();self.state=replace(self.state,selected_id=None)
 def inspector(self):
  return self.model.inspector(self.state.selected_id) if self.state.selected_id else None
 def preview(self):
  i=self.inspector();return None if i is None else self.previews.preview(i)
 def drag_payload(self,asset_id=None):
  aid=asset_id or self.state.selected_id
  if aid is None:raise ValueError("no asset selected")
  i=self.model.inspector(aid)
  # Stable canonical identity, not a raw OS path-only payload.
  return AssetDragPayload(i.asset_id,i.kind,i.source_uri,i.metadata)
