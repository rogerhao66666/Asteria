from asteria.assets import (
    AssetDragPayload,
    PlaceAssetCommand,
    PlacementHandlerRegistry,
    PlacementRequest,
    PlacementResult,
    RecordingScene,
    SceneAssetRef,
    generic_asset_handler,
)


def P(k="icon", a="icon/a"):
    return AssetDragPayload(a, k, "Assets/a.png")


def R():
    r = PlacementHandlerRegistry()
    r.register("*", generic_asset_handler)
    return r


def test_place():
    s = RecordingScene()
    x = PlaceAssetCommand(PlacementRequest(P(), (1.25, 2.5)), s, R()).execute()
    assert s.objects[x.object_id]["position"] == (1.25, 2.5)


def test_ref():
    s = RecordingScene()
    x = PlaceAssetCommand(PlacementRequest(P()), s, R()).execute()
    assert x.asset_ref == SceneAssetRef("icon/a", "icon")


def test_parent_props():
    s = RecordingScene()
    x = PlaceAssetCommand(
        PlacementRequest(P(), parent_id="root", properties=(("x", 1),)), s, R()
    ).execute()
    assert s.objects[x.object_id]["parent_id"] == "root"


def test_undo_redo():
    s = RecordingScene()
    c = PlaceAssetCommand(PlacementRequest(P()), s, R())
    x = c.execute()
    c.undo()
    assert x.object_id not in s.objects
    c.redo()
    assert len(s.objects) == 1


def test_double():
    import pytest

    s = RecordingScene()
    c = PlaceAssetCommand(PlacementRequest(P()), s, R())
    c.execute()
    pytest.raises(RuntimeError, c.execute)


def test_undo_first():
    import pytest

    s = RecordingScene()
    c = PlaceAssetCommand(PlacementRequest(P()), s, R())
    pytest.raises(RuntimeError, c.undo)


def test_specific():
    def h(q, t):
        return PlacementResult(
            "custom", SceneAssetRef(q.payload.asset_id, q.payload.kind), "sprite"
        )

    r = R()
    r.register("icon", h)
    assert (
        PlaceAssetCommand(PlacementRequest(P()), RecordingScene(), r).execute().component_type
        == "sprite"
    )


def test_custom():
    assert (
        PlaceAssetCommand(PlacementRequest(P("project.magic", "m/a")), RecordingScene(), R())
        .execute()
        .asset_ref.kind
        == "project.magic"
    )


def test_no_handler():
    import pytest

    pytest.raises(
        KeyError,
        PlaceAssetCommand(
            PlacementRequest(P()), RecordingScene(), PlacementHandlerRegistry()
        ).execute,
    )


def test_duplicate():
    import pytest

    r = PlacementHandlerRegistry()
    r.register("icon", generic_asset_handler)
    pytest.raises(ValueError, r.register, "icon", generic_asset_handler)


def test_replace():
    r = PlacementHandlerRegistry()
    r.register("icon", generic_asset_handler)
    r.register("icon", generic_asset_handler, True)
    assert r.resolve("icon") is generic_asset_handler


def test_unregister():
    import pytest

    r = PlacementHandlerRegistry()
    r.register("icon", generic_asset_handler)
    r.unregister("icon")
    pytest.raises(KeyError, r.resolve, "icon")


def test_fractional():
    s = RecordingScene()
    q = PlacementRequest(P(), (0.125, -999.875))
    x = PlaceAssetCommand(q, s, R()).execute()
    assert s.objects[x.object_id]["position"] == q.position


def test_10000():
    s = RecordingScene()
    r = R()
    for i in range(10000):
        PlaceAssetCommand(PlacementRequest(P("project.custom", f"x/{i}")), s, r).execute()
    assert len(s.objects) == 10000
