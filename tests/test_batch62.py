from dataclasses import replace

from asteria.assets import (
    AssetSource,
    BackendCapabilities,
    BackendPreflight,
    CanonicalAsset,
    CapabilityIssue,
    CapabilityValidatorRegistry,
    IconAsset,
    IconVariant,
    ResolvedSceneAsset,
    RuntimeAdapterRegistry,
    SceneAssetBinding,
    SceneAssetRef,
    install_builtin_capability_validators,
    install_builtin_runtime_adapters,
)


def C(i, k):
    return CanonicalAsset(i, k, AssetSource("src"))


def A(i, size):
    return IconAsset(C(i, "icon"), (IconVariant("d", image_uri=i + ".png", size=size),), "d")


def R(i, size, comp="sprite"):
    a = A(i, size)
    b = SceneAssetBinding("o/" + i, comp, SceneAssetRef(i, "icon"))
    return ResolvedSceneAsset(b, a)


def setup(maxsize=(4096, 4096)):
    a = install_builtin_runtime_adapters(RuntimeAdapterRegistry())
    v = install_builtin_capability_validators(CapabilityValidatorRegistry())
    return BackendPreflight(a, v, BackendCapabilities(max_texture_size=maxsize))


def test_all_valid():
    q = setup().run((R("a", (1024, 1024)), R("b", (2048, 2048))))
    assert q.ok and len(q.entries) == 2 and not q.issues


def test_collects_all_errors():
    q = setup().run(tuple(R(str(i), (8192, 8192)) for i in range(20)))
    assert not q.ok and q.error_count == 20 and len(q.entries) == 20


def test_context_preserved():
    q = setup().run((R("hero", (9000, 100), "actor.visual"),))
    x = q.issues[0]
    assert (x.object_id, x.asset_id, x.component_type) == ("o/hero", "hero", "actor.visual")


def test_no_backend_allocation():
    calls = []
    q = setup().run((R("x", (9999, 9999)),))
    assert not q.ok and calls == []


def test_missing_adapter_aggregates():
    a = RuntimeAdapterRegistry()
    v = install_builtin_capability_validators(CapabilityValidatorRegistry())
    p = BackendPreflight(a, v, BackendCapabilities())
    q = p.run((R("x", (10, 10)),))
    assert q.issues[0].code == "backend.adapter.failed"


def test_explicit_fallback():
    q = setup().run(
        (R("x", (8192, 8192)),), fallback_selector=lambda r, req, c, i: replace(req, size=c.max_texture_size)
    )
    assert q.ok and q.entries[0].fallback_applied and q.entries[0].request.size == (4096, 4096)


def test_no_fallback_no_mutation():
    r = R("x", (8192, 8192))
    q = setup().run((r,))
    assert not q.ok and q.entries[0].request.size == (8192, 8192) and not q.entries[0].fallback_applied


def test_bad_fallback_still_error():
    q = setup().run((R("x", (8192, 8192)),), fallback_selector=lambda r, req, c, i: req)
    assert not q.ok and q.entries[0].fallback_applied


def test_warning_does_not_block():
    class Q:
        pass

    a = RuntimeAdapterRegistry()
    a.register("icon", lambda x: Q())
    v = CapabilityValidatorRegistry()
    v.register(Q, lambda q, c: [CapabilityIssue("w", "warn", severity="warning")])
    q = BackendPreflight(a, v, BackendCapabilities()).run((R("x", (1, 1)),))
    assert q.ok and q.error_count == 0


def test_deterministic_order():
    xs = tuple(R(str(i), (5000, 5000)) for i in range(100))
    q = setup().run(xs)
    assert [x.asset_id for x in q.issues] == [str(i) for i in range(100)]


def test_custom_kind():
    class X:
        def __init__(self):
            self.canonical = C("magic", "project.magic")

    x = X()
    b = SceneAssetBinding("o", "custom", SceneAssetRef("magic", "project.magic"))
    rr = ResolvedSceneAsset(b, x)
    a = RuntimeAdapterRegistry()
    a.register("project.magic", lambda x: {"power": 9})
    v = CapabilityValidatorRegistry()
    q = BackendPreflight(a, v, BackendCapabilities()).run((rr,))
    assert q.ok and q.entries[0].request["power"] == 9


def test_10000_preflight():
    xs = tuple(R(str(i), (512, 512)) for i in range(10000))
    q = setup().run(xs)
    assert q.ok and len(q.entries) == 10000
