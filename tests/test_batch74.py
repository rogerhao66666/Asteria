import pytest

from asteria.presentation.animated_text import AnimatedTextRuntime, AnimatedTextSpec, TextKey, TextTransform


def test_anchor():
    r = AnimatedTextRuntime()
    r.spawn("x", AnimatedTextSpec("42", anchor_id="actor.head"))
    assert r.resolve_all()[0].anchor_id == "actor.head"


def test_screen():
    r = AnimatedTextRuntime()
    r.spawn("x", AnimatedTextSpec("Quest", space="screen"))
    assert r.resolve_all()[0].space == "screen"


def test_interp():
    r = AnimatedTextRuntime()
    r.spawn(
        "x",
        AnimatedTextSpec(
            "x", duration_ms=1000, keys=(TextKey(0, TextTransform()), TextKey(1, TextTransform(10, -20, 2, 90, 0)))
        ),
    )
    t = r.update(500)[0].transform
    assert (t.x, t.y, t.scale, t.rotation_deg, t.opacity) == pytest.approx((5, -10, 1.5, 45, 0.5))


def test_resources():
    r = AnimatedTextRuntime()
    r.spawn(
        "x",
        AnimatedTextSpec("x", font_asset_id="f", material_asset_id="m", style_id="project.emphasis", metadata={"k": 1}),
    )
    x = r.resolve_all()[0]
    assert x.metadata["k"] == 1


def test_finish():
    r = AnimatedTextRuntime()
    r.spawn("x", AnimatedTextSpec("x", duration_ms=10))
    assert r.update(10)[0].finished and r.resolve_all() == ()


def test_order():
    r = AnimatedTextRuntime()
    r.spawn("b", AnimatedTextSpec("b"))
    r.spawn("a", AnimatedTextSpec("a"))
    assert [x.instance_id for x in r.resolve_all()] == ["a", "b"]


def test_duplicate():
    r = AnimatedTextRuntime()
    r.spawn("x", AnimatedTextSpec("x"))
    with pytest.raises(ValueError):
        r.spawn("x", AnimatedTextSpec("x"))


def test_invalid():
    with pytest.raises(ValueError):
        AnimatedTextSpec("x", duration_ms=0)
    with pytest.raises(ValueError):
        AnimatedTextSpec("x", space="bad")
    with pytest.raises(ValueError):
        AnimatedTextSpec("x", keys=())


def test_transform_invalid():
    with pytest.raises(ValueError):
        TextTransform(scale=-1)
    with pytest.raises(ValueError):
        TextTransform(opacity=2)


def test_remove_clear():
    r = AnimatedTextRuntime()
    r.spawn("a", AnimatedTextSpec("a"))
    r.spawn("b", AnimatedTextSpec("b"))
    r.remove("a")
    assert len(r.resolve_all()) == 1
    r.clear()
    assert r.resolve_all() == ()


def test_negative_dt():
    with pytest.raises(ValueError):
        AnimatedTextRuntime().update(-1)


def test_no_damage_api():
    r = AnimatedTextRuntime()
    r.spawn("x", AnimatedTextSpec("999", style_id="my_game.damage"))
    assert not hasattr(r, "spawn_damage")
