"""Headless Asset Browser projection over canonical AssetRegistry."""
from dataclasses import dataclass
from typing import Any
from .registry import AssetRegistry
@dataclass(frozen=True,slots=True)
class AssetBrowserQuery:
 text:str="";kinds:frozenset[str]=frozenset();tags:frozenset[str]=frozenset()
 sort_by:str="id";descending:bool=False
@dataclass(frozen=True,slots=True)
class AssetBrowserItem:
 asset_id:str;kind:str;tags:tuple[str,...];metadata:tuple[tuple[str,Any],...]
@dataclass(frozen=True,slots=True)
class AssetInspector:
 asset_id:str;kind:str;source_uri:str;version:int;tags:tuple[str,...];metadata:tuple[tuple[str,Any],...]
class AssetBrowserModel:
 def __init__(self,registry:AssetRegistry):
  self.registry=registry;self._selected=None
 def items(self,q=AssetBrowserQuery()):
  text=q.text.casefold().strip();out=[]
  for a in self.registry.snapshot():
   if q.kinds and a.kind not in q.kinds:continue
   if q.tags and not q.tags.issubset(a.tags):continue
   hay=" ".join((a.asset_id,a.kind,*a.tags,*(str(v) for _,v in a.metadata))).casefold()
   if text and text not in hay:continue
   out.append(AssetBrowserItem(a.asset_id,a.kind,tuple(sorted(a.tags)),a.metadata))
  key={"id":lambda x:x.asset_id.casefold(),"kind":lambda x:(x.kind.casefold(),x.asset_id.casefold())}.get(q.sort_by)
  if key is None:raise ValueError("sort_by")
  return tuple(sorted(out,key=key,reverse=q.descending))
 def groups(self,q=AssetBrowserQuery()):
  d={}
  for x in self.items(q):d.setdefault(x.kind,[]).append(x)
  return tuple((k,tuple(d[k])) for k in sorted(d))
 def select(self,asset_id):
  self.registry.resolve(asset_id);self._selected=asset_id;return asset_id
 def clear_selection(self):self._selected=None
 @property
 def selected_id(self):return self._selected
 def inspector(self,asset_id=None):
  aid=asset_id or self._selected
  if aid is None:return None
  a=self.registry.resolve(aid)
  return AssetInspector(a.asset_id,a.kind,a.source.uri,a.version,tuple(sorted(a.tags)),a.metadata)
 def preview(self,asset_id=None):
  i=self.inspector(asset_id)
  if i is None:return None
  # UI/runtime adapters decide how a URI is rendered/played; browser never bakes a preview.
  return {"asset_id":i.asset_id,"kind":i.kind,"source_uri":i.source_uri}
