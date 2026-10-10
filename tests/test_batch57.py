from asteria.assets import *


def project(n=2, ok=True):
    r = AssetRegistry()
    resolved = []
    for i in range(n):
        a = CanonicalAsset(f"a/{i}", "icon", AssetSource(f"{i}.png"))
        r.register(a)
        b = SceneAssetBinding(f"o{i}", "asset", SceneAssetRef(a.asset_id, a.kind), (("i", i),))
        resolved.append(ResolvedSceneAsset(b, a))
    return ProjectLoadReport((), tuple(x.binding for x in resolved), tuple(resolved), (), ok)


def binders():
    r = RuntimeBindingRegistry()
    r.register("*", generic_runtime_binder)
    return r


def test_commit():
    t = RecordingRuntimeScene()
    x = RuntimeSceneMaterializer(binders(), t).materialize(project())
    assert x.ok and len(t.objects) == 2


def test_objects_returned():
    t = RecordingRuntimeScene()
    x = RuntimeSceneMaterializer(binders(), t).materialize(project(3))
    assert len(x.objects) == 3


def test_invalid_project_blocked():
    p = ProjectLoadReport((), (), (), (ProjectLoadIssue("", "x", "bad"),), False)
    t = RecordingRuntimeScene()
    x = RuntimeSceneMaterializer(binders(), t).materialize(p)
    assert not x.ok and not t.objects


def test_unactivated_blocked():
    p = ProjectLoadReport((), (), (), (), False)
    t = RecordingRuntimeScene()
    assert not RuntimeSceneMaterializer(binders(), t).materialize(p).ok


def test_binding_failure_no_commit():
    r = RuntimeBindingRegistry()
    r.register("*", lambda x, c: (_ for _ in ()).throw(RuntimeError("bad")))
    t = RecordingRuntimeScene()
    x = RuntimeSceneMaterializer(r, t).materialize(project())
    assert not x.ok and not t.objects


def test_second_binding_failure_no_partial():
    r = RuntimeBindingRegistry()
    r.register(
        "*",
        lambda x, c: (
            (_ for _ in ()).throw(RuntimeError("bad")) if x.binding.object_id == "o1" else {"id": x.binding.object_id}
        ),
    )
    t = RecordingRuntimeScene()
    x = RuntimeSceneMaterializer(r, t).materialize(project(3))
    assert not x.ok and not t.objects and not x.objects


def test_missing_binder_no_commit():
    t = RecordingRuntimeScene()
    x = RuntimeSceneMaterializer(RuntimeBindingRegistry(), t).materialize(project())
    assert not x.ok and not t.objects


def test_commit_failure():
    t = RecordingRuntimeScene(True)
    x = RuntimeSceneMaterializer(binders(), t).materialize(project())
    assert not x.ok and not t.objects and x.issues[0].code == "runtime.commit.failed"


def test_context_forwarded():
    r = RuntimeBindingRegistry()
    r.register("*", lambda x, c: c["token"])
    t = RecordingRuntimeScene()
    x = RuntimeSceneMaterializer(r, t).materialize(project(1), {"token": 7})
    assert x.objects == (7,)


def test_custom_component():
    p = project(1)
    b = p.resolved[0].binding
    b2 = SceneAssetBinding(b.object_id, "project.magic", b.asset_ref)
    p2 = ProjectLoadReport((), (b2,), (ResolvedSceneAsset(b2, p.resolved[0].canonical),), (), True)
    r = RuntimeBindingRegistry()
    r.register("project.magic", lambda x, c: "magic")
    t = RecordingRuntimeScene()
    assert RuntimeSceneMaterializer(r, t).materialize(p2).objects == ("magic",)


def test_order_preserved():
    t = RecordingRuntimeScene()
    x = RuntimeSceneMaterializer(binders(), t).materialize(project(100))
    assert [o["object_id"] for o in x.objects] == [f"o{i}" for i in range(100)]


def test_10000_materialize():
    t = RecordingRuntimeScene()
    x = RuntimeSceneMaterializer(binders(), t).materialize(project(10000))
    assert x.ok and len(t.objects) == 10000
