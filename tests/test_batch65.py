import json
from pathlib import Path
from asteria.assets import *


def doc(a, kind="project.test", deps=(), source=None):
    return {
        "schema_version": 1,
        "asset_id": a,
        "kind": kind,
        "source": source or f"{a}.bin",
        "dependencies": list(deps),
        "payload": {"v": a},
    }


def write(root, name, data):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))
    return p


def factory():
    c = AssetCodecRegistry()
    c.register(passthrough_codec("project.test"))
    return AssetStore(c)


def test_valid_package_publishes(tmp_path):
    s = tmp_path / "pkg"
    s.mkdir()
    write(s, "a.asset.json", doc("a"))
    (s / "a.bin").write_text("raw")
    q = SemanticAssetImporter(tmp_path / "Assets", factory).import_tree(s)
    assert (
        q.ok
        and q.loaded_asset_ids == ("a",)
        and (tmp_path / "Assets/a.asset.json").exists()
        and (tmp_path / "Assets/a.bin").read_text() == "raw"
    )


def test_invalid_json_never_publishes(tmp_path):
    s = tmp_path / "pkg"
    s.mkdir()
    (s / "bad.asset.json").write_text("{")
    q = SemanticAssetImporter(tmp_path / "Assets", factory).import_tree(s)
    assert not q.ok and not (tmp_path / "Assets/bad.asset.json").exists()


def test_missing_dependency_never_publishes(tmp_path):
    s = tmp_path / "pkg"
    s.mkdir()
    write(s, "a.asset.json", doc("a", deps=("missing",)))
    q = SemanticAssetImporter(tmp_path / "Assets", factory).import_tree(s)
    assert not q.ok and q.issues[0].code == "asset.dependency.missing" and not (tmp_path / "Assets").exists()


def test_cycle_never_publishes(tmp_path):
    s = tmp_path / "pkg"
    s.mkdir()
    write(s, "a.asset.json", doc("a", deps=("b",)))
    write(s, "b.asset.json", doc("b", deps=("a",)))
    q = SemanticAssetImporter(tmp_path / "Assets", factory).import_tree(s)
    assert not q.ok and any(x.code == "asset.dependency.cycle" for x in q.issues)


def test_unknown_codec_never_publishes(tmp_path):
    s = tmp_path / "pkg"
    s.mkdir()
    write(s, "a.asset.json", doc("a", kind="unknown"))
    q = SemanticAssetImporter(tmp_path / "Assets", factory).import_tree(s)
    assert not q.ok and any(x.code == "asset.decode.failed" for x in q.issues)


def test_duplicate_asset_id_never_publishes(tmp_path):
    s = tmp_path / "pkg"
    s.mkdir()
    write(s, "x.asset.json", doc("a"))
    write(s, "y.asset.json", doc("a"))
    q = SemanticAssetImporter(tmp_path / "Assets", factory).import_tree(s)
    assert not q.ok and any(x.code == "asset.id.duplicate" for x in q.issues)


def test_collision_after_semantic_validation_preserves_live_assets(tmp_path):
    live = tmp_path / "Assets"
    live.mkdir()
    (live / "a.asset.json").write_text("OLD")
    s = tmp_path / "pkg"
    s.mkdir()
    write(s, "a.asset.json", doc("a"))
    q = SemanticAssetImporter(live, factory).import_tree(s)
    assert not q.ok and (live / "a.asset.json").read_text() == "OLD"


def test_explicit_replace(tmp_path):
    live = tmp_path / "Assets"
    live.mkdir()
    (live / "a.asset.json").write_text("OLD")
    s = tmp_path / "pkg"
    s.mkdir()
    write(s, "a.asset.json", doc("a"))
    q = SemanticAssetImporter(live, factory).import_tree(s, collision="replace")
    assert q.ok and "OLD" not in (live / "a.asset.json").read_text()


def test_destination(tmp_path):
    s = tmp_path / "pkg"
    s.mkdir()
    write(s, "a.asset.json", doc("a"))
    q = SemanticAssetImporter(tmp_path / "Assets", factory).import_tree(s, destination="Characters/Hero")
    assert q.ok and (tmp_path / "Assets/Characters/Hero/a.asset.json").exists()


def test_dependency_order_report(tmp_path):
    s = tmp_path / "pkg"
    s.mkdir()
    write(s, "b.asset.json", doc("b", deps=("a",)))
    write(s, "a.asset.json", doc("a"))
    q = SemanticAssetImporter(tmp_path / "Assets", factory).import_tree(s)
    assert q.ok and q.loaded_asset_ids == ("a", "b")


def test_10000_semantic_documents(tmp_path):
    s = tmp_path / "pkg"
    s.mkdir()
    for i in range(10000):
        write(s, f"{i}.asset.json", doc(str(i)))
    q = SemanticAssetImporter(tmp_path / "Assets", factory).import_tree(s)
    assert q.ok and len(q.loaded_asset_ids) == 10000
