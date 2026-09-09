from asteria.assets import AssetRef
from asteria.core import ComponentRegistry, Entity, deserialize_entity, serialize_entity
from asteria.editor.animation_preview import AnimationPreview
from asteria.graphics import SpriteClip, SpriteFrame, SpriteKeyframe, SpriteSheet
from asteria.runtime import (
    AnimationClipSet,
    Animator2DBinding,
    Animator2DComponent,
    SpriteRenderer2D,
)

TEX = "123e4567-e89b-12d3-a456-426614174000"


def clips():
    return AnimationClipSet(
        {
            "idle_down": SpriteClip("idle_down", [SpriteKeyframe(0, 0.1)], True),
            "walk_down": SpriteClip(
                "walk_down", [SpriteKeyframe(0, 0.1), SpriteKeyframe(1, 0.1)], True
            ),
        }
    )


def test_animator_component_serializes():
    e = Entity("Hero")
    a = e.add_component(Animator2DComponent())
    a.clip_set_id = "hero"
    a.speed = 1.5
    reg = ComponentRegistry()
    reg.register(Animator2DComponent)
    clone = deserialize_entity(serialize_entity(e), reg)
    got = clone.get(Animator2DComponent)
    assert got.clip_set_id == "hero" and got.speed == 1.5


def test_clip_set_validation_and_editor_preview():
    sheet = SpriteSheet(
        AssetRef(TEX, "texture"),
        [SpriteFrame(0, 0, 16, 16), SpriteFrame(16, 0, 16, 16)],
    )
    cs = clips()
    cs.validate(sheet)
    p = AnimationPreview()
    p.set_clip(cs.get("walk_down"))
    assert p.frame_index == 0
    p.update(0.11)
    assert p.frame_index == 1
    p.restart()
    assert p.frame_index == 0


def test_runtime_binding_drives_persistent_sprite_frame():
    e = Entity("Hero")
    s = e.add_component(SpriteRenderer2D())
    a = e.add_component(Animator2DComponent())
    a.clip_set_id = "hero"
    a.default_clip = "walk_down"
    b = Animator2DBinding.create(e, lambda key: clips() if key == "hero" else None)
    b.update(0.11)
    assert s.frame_index == 1
