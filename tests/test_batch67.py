import json
from asteria.assets import *
def w(r,a,v=1,deps=()):
 d={"schema_version":1,"asset_id":a,"kind":"project.test","source":f"{a}.bin","dependencies":list(deps),"payload":{"v":v},"tags":[str(v)]};(r/f"{a}.asset.json").write_text(json.dumps(d))
def cs():c=AssetCodecRegistry();c.register(passthrough_codec("project.test"));return c
def mk(t):
 live=AssetRegistry();i=SemanticAssetImporter(t/"Assets",lambda:AssetStore(cs()));r=LiveAssetReconciler(lambda reg:AssetStore(cs(),registry=reg),live);return EditorAssetImportService(i,r),live
def test_one(tmp_path):
 s=tmp_path/"p";s.mkdir();w(s,"hero");svc,l=mk(tmp_path);q=svc.import_package(s);assert q.ok and q.refresh_asset_ids==("hero",) and l.resolve("hero")
def test_invalid(tmp_path):
 s=tmp_path/"p";s.mkdir();(s/"bad.asset.json").write_text("{");svc,l=mk(tmp_path);q=svc.import_package(s);assert not q.ok and q.reconciliation_report is None and not l.snapshot()
def test_dependency(tmp_path):
 s=tmp_path/"p";s.mkdir();w(s,"a",deps=("missing",));svc,_=mk(tmp_path);assert any(x.code=="asset.dependency.missing" for x in svc.import_package(s).issues)
def test_replace(tmp_path):
 svc,l=mk(tmp_path);s=tmp_path/"p1";s.mkdir();w(s,"a",1);svc.import_package(s);s=tmp_path/"p2";s.mkdir();w(s,"a",2);q=svc.import_package(s,collision="replace");assert q.ok and q.changes[0].operation=="changed" and l.resolve("a").tags==frozenset({"2"})
def test_collision(tmp_path):
 svc,l=mk(tmp_path);s=tmp_path/"p1";s.mkdir();w(s,"a",1);svc.import_package(s);s=tmp_path/"p2";s.mkdir();w(s,"a",2);assert not svc.import_package(s).ok and l.resolve("a").tags==frozenset({"1"})
def test_many(tmp_path):
 s=tmp_path/"p";s.mkdir();[w(s,a) for a in ("c","a","b")];svc,_=mk(tmp_path);assert svc.import_package(s).refresh_asset_ids==("a","b","c")
def test_destination(tmp_path):
 s=tmp_path/"p";s.mkdir();w(s,"a");svc,_=mk(tmp_path);assert svc.import_package(s,destination="Characters/Hero").ok and (tmp_path/"Assets/Characters/Hero/a.asset.json").exists()
def test_event(tmp_path):
 s=tmp_path/"p";s.mkdir();w(s,"a");svc,l=mk(tmp_path);svc.import_package(s);assert l.events[-1].asset_id=="a"
def test_10000(tmp_path):
 s=tmp_path/"p";s.mkdir();[w(s,str(i)) for i in range(10000)];svc,l=mk(tmp_path);q=svc.import_package(s);assert q.ok and len(q.refresh_asset_ids)==10000 and len(l.snapshot())==10000
