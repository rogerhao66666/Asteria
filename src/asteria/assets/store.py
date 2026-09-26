from dataclasses import dataclass
from pathlib import Path
from typing import Any,Callable,Mapping
import json
from .package import AssetManifest,manifest_from_dict
from .codecs import AssetCodecRegistry
from .canonical import CanonicalAsset,ValidationIssue,ValidationReport
from .registry import AssetRegistry

@dataclass(frozen=True,slots=True)
class AssetStoreIssue:
 path:str;code:str;message:str;severity:str="error"
@dataclass(frozen=True,slots=True)
class LoadedAsset:
 path:str;manifest:AssetManifest;asset:Any
@dataclass(frozen=True,slots=True)
class AssetStoreReport:
 loaded:tuple[LoadedAsset,...];issues:tuple[AssetStoreIssue,...]
 @property
 def ok(self):return not any(x.severity=="error" for x in self.issues)

class AssetStore:
 def __init__(self,codecs:AssetCodecRegistry,registry=None,validators:Mapping[str,Callable]|None=None):
  self.codecs=codecs;self.registry=registry or AssetRegistry();self.validators=dict(validators or {})
 def discover(self,root):return tuple(sorted(p for p in Path(root).rglob("*.asset.json") if p.is_file()))
 def _read(self,path):
  try:
   data=json.loads(Path(path).read_text(encoding="utf-8"))
  except (OSError,json.JSONDecodeError) as e:return None,AssetStoreIssue(str(path),"asset.document.invalid_json",str(e))
  if not isinstance(data,dict):return None,AssetStoreIssue(str(path),"asset.document.not_object","asset document must be a JSON object")
  try:m=manifest_from_dict(data)
  except (KeyError,TypeError,ValueError) as e:return None,AssetStoreIssue(str(path),"asset.manifest.invalid",str(e))
  return (data,m),None
 def load(self,root):
  issues=[];docs={};paths={}
  for path in self.discover(root):
   item,err=self._read(path)
   if err:issues.append(err);continue
   data,m=item
   if m.asset_id in docs:issues.append(AssetStoreIssue(str(path),"asset.id.duplicate",m.asset_id));continue
   docs[m.asset_id]=(data,m);paths[m.asset_id]=str(path)
  existing={a.asset_id for a in self.registry.snapshot()}
  for aid,(_,m) in docs.items():
   for dep in m.dependencies:
    if dep not in docs and dep not in existing:issues.append(AssetStoreIssue(paths[aid],"asset.dependency.missing",f"{aid} -> {dep}"))
  indeg={a:0 for a in docs};out={a:[] for a in docs}
  for aid,(_,m) in docs.items():
   for dep in m.dependencies:
    if dep in docs:indeg[aid]+=1;out[dep].append(aid)
  ready=sorted(a for a,d in indeg.items() if d==0);order=[]
  while ready:
   a=ready.pop(0);order.append(a)
   for n in sorted(out[a]):
    indeg[n]-=1
    if indeg[n]==0:ready.append(n);ready.sort()
  cyc=sorted(a for a,d in indeg.items() if d)
  if cyc:issues.append(AssetStoreIssue(str(root),"asset.dependency.cycle",", ".join(cyc)))
  if any(x.severity=="error" for x in issues):return AssetStoreReport((),tuple(issues))
  staged=[]
  for aid in order:
   data,m=docs[aid]
   try:obj=self.codecs.decode_document(data)
   except (KeyError,TypeError,ValueError) as e:issues.append(AssetStoreIssue(paths[aid],"asset.decode.failed",str(e)));continue
   v=self.validators.get(m.kind)
   if v:
    try:rep=v(obj)
    except Exception as e:issues.append(AssetStoreIssue(paths[aid],"asset.validation.failed",str(e)));continue
    issues.extend(AssetStoreIssue(paths[aid],x.code,x.message,x.severity) for x in rep.issues)
   staged.append(LoadedAsset(paths[aid],m,obj))
  if any(x.severity=="error" for x in issues):return AssetStoreReport((),tuple(issues))
  current={a.asset_id for a in self.registry.snapshot()}
  conflicts=sorted(x.manifest.asset_id for x in staged if x.manifest.asset_id in current)
  if conflicts:return AssetStoreReport((),tuple(issues)+(AssetStoreIssue(str(root),"asset.registry.conflict",", ".join(conflicts)),))
  canon=[]
  for x in staged:
   c=getattr(x.asset,"canonical",None)
   if c is None and isinstance(x.asset,dict):c=x.asset.get("manifest").canonical()
   if not isinstance(c,CanonicalAsset):return AssetStoreReport((),tuple(issues)+(AssetStoreIssue(x.path,"asset.canonical.missing",x.manifest.asset_id),))
   canon.append(c)
  for c in canon:self.registry.register(c)
  return AssetStoreReport(tuple(staged),tuple(issues))
