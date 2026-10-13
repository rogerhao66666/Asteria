from asteria.assets import (
    AssetSource,
    CanonicalAsset,
    ProjectLoadIssue,
    ProjectLoadReport,
    RecordingRuntimeScene,
    ResolvedSceneAsset,
    ResourceAwareMaterializer,
    RuntimeBindingRegistry,
    SceneAssetBinding,
    SceneAssetRef,
    staged,
)


def P(n=3):
    rs = []
    for i in range(n):
        a = CanonicalAsset(f"a/{i}", "icon", AssetSource(f"{i}.png"))
        b = SceneAssetBinding(f"o{i}", "asset", SceneAssetRef(a.asset_id, a.kind))
        rs.append(ResolvedSceneAsset(b, a))
    return ProjectLoadReport((), tuple(x.binding for x in rs), tuple(rs), (), True)


def test_success_no_dispose():
    log = []
    r = RuntimeBindingRegistry()
    r.register(
        "*", lambda x, c: staged(x.binding.object_id, lambda: log.append(x.binding.object_id))
    )
    t = RecordingRuntimeScene()
    q = ResourceAwareMaterializer(r, t).materialize(P())
    assert q.ok and len(t.objects) == 3 and log == []


def test_failure_disposes_previous_reverse():
    log = []
    r = RuntimeBindingRegistry()

    def b(x, c):
        if x.binding.object_id == "o2":
            raise RuntimeError("bad")
        oid = x.binding.object_id
        return staged(oid, lambda oid=oid: log.append(oid))

    r.register("*", b)
    t = RecordingRuntimeScene()
    q = ResourceAwareMaterializer(r, t).materialize(P(4))
    assert not q.ok and not t.objects and log == ["o1", "o0"]


def test_commit_failure_disposes_all_reverse():
    log = []
    r = RuntimeBindingRegistry()
    r.register(
        "*",
        lambda x, c: staged(x.binding.object_id, lambda oid=x.binding.object_id: log.append(oid)),
    )
    t = RecordingRuntimeScene(True)
    q = ResourceAwareMaterializer(r, t).materialize(P())
    assert not q.ok and log == ["o2", "o1", "o0"]


def test_plain_value_supported():
    r = RuntimeBindingRegistry()
    r.register("*", lambda x, c: x.binding.object_id)
    t = RecordingRuntimeScene()
    assert ResourceAwareMaterializer(r, t).materialize(P()).ok


def test_release_idempotent():
    log = []
    x = staged(1, lambda: log.append(1))
    x.release()
    x.release()
    assert log == [1]


def test_cleanup_error_reported():
    r = RuntimeBindingRegistry()

    def b(x, c):
        if x.binding.object_id == "o1":
            raise RuntimeError("bind")

        def bad():
            raise RuntimeError("dispose")

        return staged("x", bad)

    r.register("*", b)
    q = ResourceAwareMaterializer(r, RecordingRuntimeScene()).materialize(P())
    assert q.cleanup_issues[0].code == "runtime.cleanup.failed"


def test_invalid_project_no_bind():
    p = ProjectLoadReport((), (), (), (ProjectLoadIssue("", "x", "bad"),), False)
    r = RuntimeBindingRegistry()
    t = RecordingRuntimeScene()
    q = ResourceAwareMaterializer(r, t).materialize(p)
    assert not q.ok and not t.objects


def test_context():
    r = RuntimeBindingRegistry()
    r.register("*", lambda x, c: staged(c))
    t = RecordingRuntimeScene()
    q = ResourceAwareMaterializer(r, t).materialize(P(1), {"gpu": "ctx"})
    assert q.objects == ({"gpu": "ctx"},)


def test_custom_component():
    p = P(1)
    old = p.resolved[0]
    b = SceneAssetBinding("o0", "vfx.custom", old.binding.asset_ref)
    p = ProjectLoadReport((), (b,), (ResolvedSceneAsset(b, old.canonical),), (), True)
    r = RuntimeBindingRegistry()
    r.register("vfx.custom", lambda x, c: staged("fx"))
    assert ResourceAwareMaterializer(r, RecordingRuntimeScene()).materialize(p).objects == ("fx",)


def test_10000_resources_success():
    r = RuntimeBindingRegistry()
    r.register("*", lambda x, c: staged(x.binding.object_id))
    t = RecordingRuntimeScene()
    q = ResourceAwareMaterializer(r, t).materialize(P(10000))
    assert q.ok and len(t.objects) == 10000


def test_10000_failure_cleanup():
    count = [0]
    r = RuntimeBindingRegistry()

    def b(x, c):
        i = int(x.binding.object_id[1:])
        if i == 9999:
            raise RuntimeError("last")
        return staged(i, lambda: count.__setitem__(0, count[0] + 1))

    r.register("*", b)
    t = RecordingRuntimeScene()
    q = ResourceAwareMaterializer(r, t).materialize(P(10000))
    assert not q.ok and count[0] == 9999 and not t.objects
