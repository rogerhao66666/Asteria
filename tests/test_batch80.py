import pytest
from asteria.presentation.animated_text import *
from asteria.presentation.text_render_integration import *


def resolved(**kw):
    s = AnimatedTextSpec(text=kw.pop("text", "42"), **kw)
    rt = AnimatedTextRuntime()
    rt.spawn("t", s)
    return rt.resolve_all()[0]


def test_screen_text_packet():
    p = AnimatedTextRenderComposer().compose_one(resolved(space="screen"))
    assert p.text == "42" and p.space == "screen"


def test_world_anchor_offsets_position():
    p = AnimatedTextRenderComposer(lambda i: (100, 50)).compose_one(resolved(anchor_id="enemy"))
    assert (p.x, p.y) == (100, 50)


def test_world_anchor_preserves_animation_offset():
    r = ResolvedText("x", "hi", "world", "a", None, None, None, TextTransform(x=3, y=-7), 0, False, {})
    p = AnimatedTextRenderComposer(lambda i: (10, 20)).compose_one(r)
    assert (p.x, p.y) == (13, 13)


def test_missing_anchor_resolver_rejected():
    with pytest.raises(ValueError):
        AnimatedTextRenderComposer().compose_one(resolved(anchor_id="a"))


def test_unknown_anchor_rejected():
    with pytest.raises(ValueError):
        AnimatedTextRenderComposer(lambda i: None).compose_one(resolved(anchor_id="a"))


def test_font_material_refs_preserved_and_validated():
    r = resolved(space="screen", font_asset_id="font.main", material_asset_id="mat.glow", style_id="project.crit")
    p = AnimatedTextRenderComposer(
        font_exists=lambda x: x == "font.main", material_exists=lambda x: x == "mat.glow"
    ).compose_one(r)
    assert (p.font_asset_id, p.material_asset_id, p.style_id) == ("font.main", "mat.glow", "project.crit")


def test_unknown_font_rejected():
    with pytest.raises(ValueError):
        AnimatedTextRenderComposer(font_exists=lambda x: False).compose_one(resolved(space="screen", font_asset_id="x"))


def test_unknown_material_rejected():
    with pytest.raises(ValueError):
        AnimatedTextRenderComposer(material_exists=lambda x: False).compose_one(
            resolved(space="screen", material_asset_id="x")
        )


def test_z_order_deterministic():
    a = ResolvedText("b", "b", "screen", None, None, None, None, TextTransform(), 2, False, {})
    b = ResolvedText("a", "a", "screen", None, None, None, None, TextTransform(), 1, False, {})
    assert [p.instance_id for p in AnimatedTextRenderComposer().compose((a, b))] == ["a", "b"]


def test_zero_opacity_filtered():
    r = ResolvedText("a", "a", "screen", None, None, None, None, TextTransform(opacity=0), 0, False, {})
    assert AnimatedTextRenderComposer().compose((r,)) == ()


def test_generic_style_not_damage_semantics():
    p = AnimatedTextRenderComposer().compose_one(
        resolved(space="screen", style_id="my_game.quest_popup", text="Quest!")
    )
    assert p.style_id == "my_game.quest_popup"
