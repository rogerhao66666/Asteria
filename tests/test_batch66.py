import json

from asteria.assets import (
    AssetCodecRegistry,
    AssetRegistry,
    AssetSource,
    AssetStore,
    CanonicalAsset,
    LiveAssetReconciler,
    passthrough_codec,
)


def d(a, v=1):
    return {
        "schema_version": 1,
        "asset_id": a,
        "kind": "project.test",
        "source": f"{a}.bin",
        "dependencies": [],
        "payload": {"v": v},
        "tags": [str(v)],
    }


def w(root, a, v=1):
    p = root / f"{a}.asset.json"
    p.write_text(json.dumps(d(a, v)))
    return p


def sf(reg):
    c = AssetCodecRegistry()
    c.register(passthrough_codec("project.test"))
    return AssetStore(c, registry=reg)


def canon(a, v=0):
    return CanonicalAsset(a, "project.test", AssetSource(f"{a}.bin"), tags=(str(v),))


def test_initial_added(tmp_path):
    w(tmp_path, "a")
    r = AssetRegistry()
    q = LiveAssetReconciler(sf, r).reconcile(tmp_path)
    assert (
        q.ok and [(x.operation, x.asset_id) for x in q.changes] == [("added", "a")] and r.resolve("a").asset_id == "a"
    )


def test_no_change(tmp_path):
    w(tmp_path, "a")
    r = AssetRegistry()
    LiveAssetReconciler(sf, r).reconcile(tmp_path)
    q = LiveAssetReconciler(sf, r).reconcile(tmp_path)
    assert q.ok and q.changes == ()


def test_changed(tmp_path):
    w(tmp_path, "a", 1)
    r = AssetRegistry()
    LiveAssetReconciler(sf, r).reconcile(tmp_path)
    w(tmp_path, "a", 2)
    q = LiveAssetReconciler(sf, r).reconcile(tmp_path)
    assert q.changes[0].operation == "changed" and r.resolve("a").tags == frozenset({"2"})


def test_removed(tmp_path):
    w(tmp_path, "a")
    r = AssetRegistry()
    LiveAssetReconciler(sf, r).reconcile(tmp_path)
    (tmp_path / "a.asset.json").unlink()
    q = LiveAssetReconciler(sf, r).reconcile(tmp_path)
    assert q.changes[0].operation == "removed" and not r.snapshot()


def test_mixed_deterministic(tmp_path):
    for a in ("b", "a", "c"):
        w(tmp_path, a)
    r = AssetRegistry()
    LiveAssetReconciler(sf, r).reconcile(tmp_path)
    (tmp_path / "a.asset.json").unlink()
    w(tmp_path, "b", 2)
    w(tmp_path, "d")
    q = LiveAssetReconciler(sf, r).reconcile(tmp_path)
    assert [(x.operation, x.asset_id) for x in q.changes] == [("removed", "a"), ("added", "d"), ("changed", "b")]


def test_invalid_refresh_keeps_live_registry(tmp_path):
    w(tmp_path, "a")
    r = AssetRegistry()
    LiveAssetReconciler(sf, r).reconcile(tmp_path)
    (tmp_path / "a.asset.json").write_text("{")
    q = LiveAssetReconciler(sf, r).reconcile(tmp_path)
    assert not q.ok and q.changes == () and r.resolve("a").asset_id == "a"


def test_registry_events_are_emitted(tmp_path):
    w(tmp_path, "a")
    r = AssetRegistry()
    LiveAssetReconciler(sf, r).reconcile(tmp_path)
    w(tmp_path, "a", 2)
    LiveAssetReconciler(sf, r).reconcile(tmp_path)
    assert [e.operation for e in r.events] == ["register", "replace"]


def test_remove_event(tmp_path):
    w(tmp_path, "a")
    r = AssetRegistry()
    LiveAssetReconciler(sf, r).reconcile(tmp_path)
    (tmp_path / "a.asset.json").unlink()
    LiveAssetReconciler(sf, r).reconcile(tmp_path)
    assert r.events[-1].operation == "remove"


def test_10000_reconcile(tmp_path):
    for i in range(10000):
        w(tmp_path, str(i))
    r = AssetRegistry()
    q = LiveAssetReconciler(sf, r).reconcile(tmp_path)
    assert q.ok and len(q.changes) == 10000 and len(r.snapshot()) == 10000
