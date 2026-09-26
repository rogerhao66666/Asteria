from asteria.assets import *
def ws(n=20):
 r=AssetRegistry()
 for i in range(n):r.register(CanonicalAsset(f"{'icon' if i%2==0 else 'audio'}/{i}",'icon' if i%2==0 else 'audio',AssetSource(f"Assets/{i}.dat"),1,frozenset(("starter",) if i%3==0 else ("dlc",)),(("index",i),)))
 return AssetBrowserWorkspace(AssetBrowserModel(r))
def test_initial():assert len(ws().refresh())==20
def test_search():assert len(ws().set_search("icon/2"))==1
def test_kind():assert len(ws().set_kinds(["audio"]))==10
def test_tags():assert len(ws().set_tags(["starter"]))==7
def test_sort():assert ws(3).set_sort("id",True)[0].asset_id=="icon/2"
def test_group():assert [k for k,_ in ws().set_grouped(True)]==["audio","icon"]
def test_select_inspector():w=ws();assert w.select("icon/2").kind=="icon" and w.inspector().asset_id=="icon/2"
def test_clear():w=ws();w.select("icon/2");w.clear_selection();assert w.inspector() is None and w.preview() is None
def test_fallback_preview():w=ws();w.select("icon/2");p=w.preview();assert p.provider=="none" and p.content["source_uri"]=="Assets/2.dat"
def test_kind_preview():
 w=ws();w.previews.register("icon",lambda i:{"thumb":i.source_uri});w.select("icon/2");assert w.preview().content["thumb"]=="Assets/2.dat"
def test_wildcard_preview():
 w=ws();w.previews.register("*",lambda i:{"generic":i.kind});w.select("audio/1");assert w.preview().content["generic"]=="audio"
def test_kind_beats_wildcard():
 w=ws();w.previews.register("*",lambda i:"all");w.previews.register("icon",lambda i:"icon");w.select("icon/2");assert w.preview().content=="icon"
def test_provider_duplicate():
 import pytest;r=PreviewProviderRegistry();r.register("icon",lambda i:1);pytest.raises(ValueError,r.register,"icon",lambda i:2)
def test_provider_replace():
 r=PreviewProviderRegistry();r.register("icon",lambda i:1);r.register("icon",lambda i:2,replace_existing=True);assert r.has("icon")
def test_provider_unregister():
 r=PreviewProviderRegistry();r.register("icon",lambda i:1);r.unregister("icon");assert not r.has("icon")
def test_drag_selected():
 w=ws();w.select("icon/2");d=w.drag_payload();assert (d.asset_id,d.kind,d.source_uri)==("icon/2","icon","Assets/2.dat")
def test_drag_explicit_without_selection():assert ws().drag_payload("audio/1").asset_id=="audio/1"
def test_drag_no_selection():
 import pytest;pytest.raises(ValueError,ws().drag_payload)
def test_custom_kind():
 r=AssetRegistry();r.register(CanonicalAsset("magic/a","project.magic",AssetSource("Assets/a.magic")));w=AssetBrowserWorkspace(AssetBrowserModel(r));w.select("magic/a");assert w.drag_payload().kind=="project.magic"
def test_state_independent_of_asset():w=ws();w.set_search("icon");w.set_grouped(True);assert w.state.query.text=="icon" and w.state.group_by_kind
def test_10000_refresh():
 w=ws(10000);assert len(w.set_kinds(["icon"]))==5000
