from asteria.assets import (
    AssetSource,
    AudioAsset,
    CanonicalAsset,
    ProjectLoadReport,
    RecordingRuntimeScene,
    ResolvedSceneAsset,
    ResourceAwareMaterializer,
    RuntimeAdapterRegistry,
    RuntimeBindingRegistry,
    RuntimeResource,
    SceneAssetBinding,
    SceneAssetRef,
    install_builtin_runtime_adapters,
    make_resource_aware_binder,
    staged,
)


def C(a, k):
    return CanonicalAsset(a, k, AssetSource("src"))


def resolved(asset, ctype="asset"):
    b = SceneAssetBinding("o", ctype, SceneAssetRef(asset.canonical.asset_id, asset.canonical.kind))
    return ResolvedSceneAsset(b, asset)


def audio():
    return AudioAsset(C("a", "audio"), "a.flac", 1000.0, 2, 96000, (10.0, 900.0), ())


def test_install():
    r = install_builtin_runtime_adapters(RuntimeAdapterRegistry())
    assert {"audio", "font", "material", "icon", "portrait", "vfx", "monster"} <= set(r.kinds())


def test_audio_adapt():
    q = install_builtin_runtime_adapters(RuntimeAdapterRegistry()).adapt(audio())
    assert q.sample_rate == 96000


def test_duplicate():
    import pytest

    r = RuntimeAdapterRegistry()
    r.register("x", lambda a: a)
    pytest.raises(ValueError, r.register, "x", lambda a: a)


def test_replace():
    r = RuntimeAdapterRegistry()
    r.register("x", lambda a: 1)
    r.register("x", lambda a: 2, replace_existing=True)
    assert r.adapt(C("a", "x")) == 2


def test_unregister():
    import pytest

    r = RuntimeAdapterRegistry()
    r.register("x", lambda a: 1)
    r.unregister("x")
    pytest.raises(KeyError, r.adapt, C("a", "x"))


def test_wildcard():
    r = RuntimeAdapterRegistry()
    r.register("*", lambda a: ("custom", a.kind))
    assert r.adapt(C("a", "project.magic")) == ("custom", "project.magic")


def test_specific_beats_wildcard():
    r = RuntimeAdapterRegistry()
    r.register("*", lambda a: 0)
    r.register("audio", lambda a: 1)
    assert r.adapt(audio()) == 1


def test_factory_receives_request_context():
    ar = install_builtin_runtime_adapters(RuntimeAdapterRegistry())
    seen = []
    b = make_resource_aware_binder(ar, lambda req, ctx: seen.append((req, ctx)) or "handle")
    x = b(resolved(audio()), {"device": "audio"})
    assert x.value == "handle" and seen[0][0].sample_rate == 96000


def test_resource_dispose():
    log = []
    ar = install_builtin_runtime_adapters(RuntimeAdapterRegistry())
    b = make_resource_aware_binder(ar, lambda q, c: RuntimeResource("h", lambda: log.append("free")))
    x = b(resolved(audio()))
    x.release()
    assert log == ["free"]


def test_factory_can_return_staged():
    ar = install_builtin_runtime_adapters(RuntimeAdapterRegistry())
    s = staged("native")
    b = make_resource_aware_binder(ar, lambda q, c: s)
    assert b(resolved(audio())) is s


def test_custom_kind_full_path():
    class X:
        def __init__(self):
            self.canonical = C("m", "project.magic")
            self.power = 9

    ar = RuntimeAdapterRegistry()
    ar.register("project.magic", lambda a: {"power": a.power})
    b = make_resource_aware_binder(ar, lambda q, c: RuntimeResource(("magic", q["power"])))
    assert b(resolved(X())).value == ("magic", 9)


def test_transaction_cleanup_through_bridge():
    log = []
    ar = install_builtin_runtime_adapters(RuntimeAdapterRegistry())
    assets = [audio(), AudioAsset(C("b", "audio"), "b.wav", None, 2, 48000, None, ())]
    rs = []
    for i, a in enumerate(assets):
        bb = SceneAssetBinding(f"o{i}", "asset", SceneAssetRef(a.canonical.asset_id, "audio"))
        rs.append(ResolvedSceneAsset(bb, a))
    p = ProjectLoadReport((), tuple(x.binding for x in rs), tuple(rs), (), True)

    def factory(q, c):
        if q.asset_id == "b":
            raise RuntimeError("backend fail")
        return RuntimeResource("h", lambda: log.append("free"))

    rr = RuntimeBindingRegistry()
    rr.register("*", make_resource_aware_binder(ar, factory))
    t = RecordingRuntimeScene()
    out = ResourceAwareMaterializer(rr, t).materialize(p)
    assert not out.ok and log == ["free"] and not t.objects


def test_10000_bridge():
    ar = install_builtin_runtime_adapters(RuntimeAdapterRegistry())
    b = make_resource_aware_binder(ar, lambda q, c: q.asset_id)
    for i in range(10000):
        a = AudioAsset(C(f"a/{i}", "audio"), "a.wav", None, 2, 48000, None, ())
        assert b(resolved(a)).value == f"a/{i}"
