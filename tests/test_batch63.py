from asteria.assets import *


def C(i, k):
    return CanonicalAsset(i, k, AssetSource("src"))


def RR(i, size=(64, 64)):
    a = IconAsset(C(i, "icon"), (IconVariant("d", image_uri=i + ".png", size=size),), "d")
    b = SceneAssetBinding("o" + i, "sprite", SceneAssetRef(i, "icon"))
    return ResolvedSceneAsset(b, a)


def pre(xs, caps=(4096, 4096)):
    ar = install_builtin_runtime_adapters(RuntimeAdapterRegistry())
    vr = install_builtin_capability_validators(CapabilityValidatorRegistry())
    return BackendPreflight(ar, vr, BackendCapabilities(max_texture_size=caps)).run(xs)


def test_success():
    t = RecordingRuntimeScene()
    q = PreflightMaterializer(t, lambda req, c: req.asset_id).materialize(pre((RR("a"), RR("b"))))
    assert q.ok and t.objects == ["a", "b"]


def test_failed_preflight_allocates_nothing():
    calls = []
    pf = pre((RR("a", (9999, 9999)),))
    t = RecordingRuntimeScene()
    q = PreflightMaterializer(t, lambda r, c: calls.append(r)).materialize(pf)
    assert not q.ok and calls == [] and not t.objects


def test_uses_preflight_request_not_readapt():
    pf = pre((RR("a"),))
    req = pf.entries[0].request
    seen = []
    PreflightMaterializer(RecordingRuntimeScene(), lambda r, c: seen.append(r) or "h").materialize(pf)
    assert seen[0] is req


def test_context():
    pf = pre((RR("a"),))
    q = PreflightMaterializer(RecordingRuntimeScene(), lambda r, c: c["h"]).materialize(pf, {"h": 7})
    assert q.objects == (7,)


def test_resource_cleanup_on_late_failure():
    log = []
    pf = pre((RR("a"), RR("b")))

    def f(r, c):
        if r.asset_id == "b":
            raise RuntimeError("fail")
        return RuntimeResource("h", lambda: log.append("free"))

    t = RecordingRuntimeScene()
    q = PreflightMaterializer(t, f).materialize(pf)
    assert not q.ok and log == ["free"] and not t.objects


def test_commit_failure_cleanup():
    log = []
    pf = pre((RR("a"), RR("b")))
    t = RecordingRuntimeScene(True)
    q = PreflightMaterializer(t, lambda r, c: RuntimeResource(r.asset_id, lambda: log.append("f"))).materialize(pf)
    assert not q.ok and log == ["f", "f"] and not t.objects


def test_staged_passthrough():
    x = staged("native")
    pf = pre((RR("a"),))
    q = PreflightMaterializer(RecordingRuntimeScene(), lambda r, c: x).materialize(pf)
    assert q.objects == ("native",)


def test_order():
    xs = tuple(RR(str(i)) for i in range(100))
    q = PreflightMaterializer(RecordingRuntimeScene(), lambda r, c: r.asset_id).materialize(pre(xs))
    assert q.objects == tuple(str(i) for i in range(100))


def test_fallback_request_is_materialized():
    from dataclasses import replace

    ar = install_builtin_runtime_adapters(RuntimeAdapterRegistry())
    vr = install_builtin_capability_validators(CapabilityValidatorRegistry())
    pf = BackendPreflight(ar, vr, BackendCapabilities(max_texture_size=(1024, 1024))).run(
        (RR("a", (2048, 2048)),), fallback_selector=lambda rr, r, c, i: replace(r, size=(1024, 1024))
    )
    seen = []
    q = PreflightMaterializer(RecordingRuntimeScene(), lambda r, c: seen.append(r.size) or "h").materialize(pf)
    assert q.ok and seen == [(1024, 1024)]


def test_10000():
    xs = tuple(RR(str(i)) for i in range(10000))
    t = RecordingRuntimeScene()
    q = PreflightMaterializer(t, lambda r, c: r.asset_id).materialize(pre(xs))
    assert q.ok and len(t.objects) == 10000
