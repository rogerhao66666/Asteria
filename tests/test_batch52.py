from asteria.assets import (
    AssetBrowserModel,
    AssetBrowserQuery,
    AssetRegistry,
    AssetSource,
    CanonicalAsset,
)


def model(n=20):
    r = AssetRegistry()
    for i in range(n):
        r.register(
            CanonicalAsset(
                f"{'icon' if i % 2 == 0 else 'audio'}/{i}",
                "icon" if i % 2 == 0 else "audio",
                AssetSource(f"Assets/{i}.dat"),
                1,
                frozenset(("starter",) if i % 3 == 0 else ("dlc",)),
                (("index", i),),
            )
        )
    return AssetBrowserModel(r)


def test_all():
    assert len(model().items()) == 20


def test_text_id():
    assert [x.asset_id for x in model().items(AssetBrowserQuery(text="icon/2"))] == ["icon/2"]


def test_text_metadata():
    assert model().items(AssetBrowserQuery(text="19"))[0].asset_id == "audio/19"


def test_kind_filter():
    assert len(model().items(AssetBrowserQuery(kinds=frozenset(("icon",))))) == 10


def test_tag_filter():
    assert len(model().items(AssetBrowserQuery(tags=frozenset(("starter",))))) == 7


def test_combined():
    assert all(
        x.kind == "icon" and "starter" in x.tags
        for x in model().items(
            AssetBrowserQuery(kinds=frozenset(("icon",)), tags=frozenset(("starter",)))
        )
    )


def test_sort_kind():
    assert model().items(AssetBrowserQuery(sort_by="kind"))[0].kind == "audio"


def test_desc():
    assert model(3).items(AssetBrowserQuery(descending=True))[0].asset_id == "icon/2"


def test_bad_sort():
    import pytest

    pytest.raises(ValueError, model().items, AssetBrowserQuery(sort_by="x"))


def test_groups():
    assert [k for k, _ in model().groups()] == ["audio", "icon"]


def test_select():
    m = model()
    assert m.select("icon/2") == "icon/2" and m.selected_id == "icon/2"


def test_select_missing():
    import pytest

    m = model()
    pytest.raises(KeyError, m.select, "missing")


def test_clear():
    m = model()
    m.select("icon/2")
    m.clear_selection()
    assert m.selected_id is None


def test_inspector():
    m = model()
    m.select("icon/2")
    i = m.inspector()
    assert i.kind == "icon" and i.source_uri == "Assets/2.dat"


def test_inspector_explicit():
    assert model().inspector("audio/1").asset_id == "audio/1"


def test_preview():
    assert model().preview("icon/2") == {
        "asset_id": "icon/2",
        "kind": "icon",
        "source_uri": "Assets/2.dat",
    }


def test_no_preview_selection():
    assert model().preview() is None


def test_custom_kind():
    r = AssetRegistry()
    r.register(CanonicalAsset("custom/a", "project.magic", AssetSource("a")))
    m = AssetBrowserModel(r)
    assert m.items()[0].kind == "project.magic"


def test_10000_query():
    m = model(10000)
    assert len(m.items(AssetBrowserQuery(kinds=frozenset(("icon",))))) == 5000
