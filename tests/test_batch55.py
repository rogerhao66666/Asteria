import json
from asteria.assets import *
def registry():
 r=AssetRegistry();r.register(CanonicalAsset("icon/a","icon",AssetSource("Assets/a.png")));r.register(CanonicalAsset("audio/b","audio",AssetSource("Assets/b.ogg")));return r
def B(aid="icon/a",kind="icon",ctype="asset"):return SceneAssetBinding("obj-1",ctype,SceneAssetRef(aid,kind),(("opacity",.5),))
def test_ref_roundtrip():r=SceneAssetRef("icon/a","icon");assert asset_ref_from_dict(asset_ref_to_dict(r))==r
def test_ref_json_roundtrip():r=SceneAssetRef("icon/a","icon");assert asset_ref_from_dict(json.loads(json.dumps(asset_ref_to_dict(r))))==r
def test_binding_roundtrip():b=B();assert binding_from_dict(binding_to_dict(b))==b
def test_binding_json_roundtrip():b=B();assert binding_from_dict(json.loads(json.dumps(binding_to_dict(b))))==b
def test_bad_ref_id():
 import pytest;pytest.raises(ValueError,asset_ref_from_dict,{"asset_id":"","kind":"icon"})
def test_bad_ref_kind():
 import pytest;pytest.raises(ValueError,asset_ref_from_dict,{"asset_id":"a","kind":""})
def test_bad_props():
 import pytest;pytest.raises(ValueError,binding_from_dict,{"object_id":"x","asset_ref":{"asset_id":"a","kind":"icon"},"properties":[]})
def test_resolve():x=SceneAssetResolver(registry()).resolve(B());assert x.canonical.asset_id=="icon/a"
def test_missing():
 import pytest;pytest.raises(KeyError,SceneAssetResolver(registry()).resolve,B("missing","icon"))
def test_kind_mismatch():
 import pytest;pytest.raises(ValueError,SceneAssetResolver(registry()).resolve,B("icon/a","audio"))
def test_resolve_many():r=SceneAssetResolver(registry());assert len(r.resolve_many((B(),SceneAssetBinding("o2","asset",SceneAssetRef("audio/b","audio")))))==2
def test_generic_runtime():
 x=SceneAssetResolver(registry()).resolve(B());y=generic_runtime_binder(x);assert y["asset_id"]=="icon/a" and y["properties"]["opacity"]==.5
def test_runtime_registry_specific():
 rr=RuntimeBindingRegistry();rr.register("sprite",lambda x,c:("sprite",x.canonical.asset_id));x=SceneAssetResolver(registry()).resolve(B(ctype="sprite"));assert rr.bind(x)==("sprite","icon/a")
def test_runtime_wildcard():
 rr=RuntimeBindingRegistry();rr.register("*",generic_runtime_binder);x=SceneAssetResolver(registry()).resolve(B());assert rr.bind(x)["kind"]=="icon"
def test_specific_beats_wildcard():
 rr=RuntimeBindingRegistry();rr.register("*",lambda x,c:"all");rr.register("sprite",lambda x,c:"sprite");x=SceneAssetResolver(registry()).resolve(B(ctype="sprite"));assert rr.bind(x)=="sprite"
def test_no_binder():
 import pytest;x=SceneAssetResolver(registry()).resolve(B());pytest.raises(KeyError,RuntimeBindingRegistry().bind,x)
def test_duplicate_binder():
 import pytest;rr=RuntimeBindingRegistry();rr.register("asset",generic_runtime_binder);pytest.raises(ValueError,rr.register,"asset",generic_runtime_binder)
def test_replace_binder():
 rr=RuntimeBindingRegistry();rr.register("asset",lambda x,c:1);rr.register("asset",lambda x,c:2,replace_existing=True);assert rr.bind(SceneAssetResolver(registry()).resolve(B()))==2
def test_custom_kind_same_path():
 r=registry();r.register(CanonicalAsset("magic/a","project.magic",AssetSource("Assets/a.magic")));x=SceneAssetResolver(r).resolve(B("magic/a","project.magic"));assert x.canonical.kind=="project.magic"
def test_10000_resolution():
 r=AssetRegistry();bs=[]
 for i in range(10000):
  aid=f"icon/{i}";r.register(CanonicalAsset(aid,"icon",AssetSource(f"Assets/{i}.png")));bs.append(SceneAssetBinding(f"o{i}","asset",SceneAssetRef(aid,"icon")))
 assert len(SceneAssetResolver(r).resolve_many(bs))==10000
