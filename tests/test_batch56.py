import json
from pathlib import Path
from asteria.assets import *


def C():
    r = install_common_passthrough_codecs(AssetCodecRegistry())
    return install_complex_typed_codecs(install_simple_typed_codecs(r))


def asset(root, aid="a", kind="audio"):
    p = Path(root) / f"{aid.replace('/', '_')}.asset.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "asset_id": aid,
                "kind": kind,
                "source": f"{aid}.dat",
                "payload": {"uri": f"{aid}.ogg"},
            }
        )
    )
    return p


def scene(path, bs):
    Path(path).write_text(json.dumps({"asset_bindings": [binding_to_dict(b) for b in bs]}))


def B(aid="a", kind="audio", oid="o"):
    return SceneAssetBinding(oid, "asset", SceneAssetRef(aid, kind))


def loader():
    return ProjectLoader(AssetStore(C()))


def test_empty(tmp_path):
    r = loader().load(tmp_path)
    assert r.ok and r.activated


def test_asset_only(tmp_path):
    asset(tmp_path)
    r = loader().load(tmp_path)
    assert r.ok and len(r.assets) == 1


def test_scene_resolution(tmp_path):
    asset(tmp_path)
    sp = tmp_path / "s.scene.json"
    scene(sp, [B()])
    r = loader().load(tmp_path, [sp])
    assert r.ok and len(r.resolved) == 1


def test_multiple_scenes(tmp_path):
    asset(tmp_path, "a")
    asset(tmp_path, "b")
    s1 = tmp_path / "1.json"
    s2 = tmp_path / "2.json"
    scene(s1, [B("a")])
    scene(s2, [B("b", oid="o2")])
    r = loader().load(tmp_path, [s2, s1])
    assert r.ok and len(r.resolved) == 2


def test_bad_asset_blocks(tmp_path):
    (tmp_path / "x.asset.json").write_text("{bad")
    r = loader().load(tmp_path)
    assert not r.ok and not r.activated


def test_bad_scene_json(tmp_path):
    asset(tmp_path)
    s = tmp_path / "s.json"
    s.write_text("{bad")
    r = loader().load(tmp_path, [s])
    assert not r.ok and not r.activated


def test_scene_not_object(tmp_path):
    asset(tmp_path)
    s = tmp_path / "s.json"
    s.write_text("[]")
    r = loader().load(tmp_path, [s])
    assert any(x.code == "scene.document.not_object" for x in r.issues)


def test_bindings_not_list(tmp_path):
    asset(tmp_path)
    s = tmp_path / "s.json"
    s.write_text('{"asset_bindings":{}}')
    r = loader().load(tmp_path, [s])
    assert any(x.code == "scene.bindings.not_list" for x in r.issues)


def test_invalid_binding(tmp_path):
    asset(tmp_path)
    s = tmp_path / "s.json"
    s.write_text('{"asset_bindings":[{"object_id":""}]}')
    r = loader().load(tmp_path, [s])
    assert not r.ok


def test_unresolved_ref(tmp_path):
    asset(tmp_path)
    s = tmp_path / "s.json"
    scene(s, [B("missing")])
    r = loader().load(tmp_path, [s])
    assert not r.ok and not r.resolved and any(x.code == "scene.asset.unresolved" for x in r.issues)


def test_kind_mismatch(tmp_path):
    asset(tmp_path)
    s = tmp_path / "s.json"
    scene(s, [B("a", "icon")])
    r = loader().load(tmp_path, [s])
    assert any(x.code == "scene.asset.kind_mismatch" for x in r.issues)


def test_no_partial_resolved_on_one_bad(tmp_path):
    asset(tmp_path, "a")
    s = tmp_path / "s.json"
    scene(s, [B("a"), B("missing", oid="bad")])
    r = loader().load(tmp_path, [s])
    assert not r.ok and r.resolved == ()


def test_deterministic_scene_path_order(tmp_path):
    asset(tmp_path, "a")
    asset(tmp_path, "b")
    a = tmp_path / "a.json"
    z = tmp_path / "z.json"
    scene(a, [B("a", oid="a")])
    scene(z, [B("b", oid="z")])
    r = loader().load(tmp_path, [z, a])
    assert [x.object_id for x in r.bindings] == ["a", "z"]


def test_custom_kind(tmp_path):
    c = C()
    c.register(passthrough_codec("project.custom"))
    p = tmp_path / "c.asset.json"
    p.write_text(
        json.dumps(
            {"schema_version": 1, "asset_id": "c", "kind": "project.custom", "source": "c.dat", "payload": {"x": 1}}
        )
    )
    s = tmp_path / "s.json"
    scene(s, [B("c", "project.custom")])
    r = ProjectLoader(AssetStore(c)).load(tmp_path, [s])
    assert r.ok


def test_warning_asset_can_activate(tmp_path):
    asset(tmp_path)
    v = lambda a: ValidationReport(a.canonical.asset_id, (ValidationIssue("review", "review", "warning"),))
    r = ProjectLoader(AssetStore(C(), validators={"audio": v})).load(tmp_path)
    assert r.ok and r.activated and r.issues[0].severity == "warning"


def test_5000_scene_bindings(tmp_path):
    for i in range(5000):
        asset(tmp_path, f"a/{i}")
    s = tmp_path / "scene.json"
    scene(s, [B(f"a/{i}", oid=f"o{i}") for i in range(5000)])
    r = loader().load(tmp_path, [s])
    assert r.ok and len(r.resolved) == 5000
