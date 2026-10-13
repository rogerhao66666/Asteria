from asteria.assets import AssetRef
from asteria.core import (
    ComponentRegistry,
    Entity,
    Scene,
    Transform,
    deserialize_entity,
    serialize_entity,
)
from asteria.editor.entity_render import build_camera_frames, build_entity_sprite_draws
from asteria.editor.viewport import ViewportCamera
from asteria.graphics import SpriteFrame, SpriteSheet
from asteria.runtime import Camera2DComponent, SpriteRenderer2D

SHEET_ID = "123e4567-e89b-12d3-a456-426614174001"
TEX_ID = "123e4567-e89b-12d3-a456-426614174000"


def test_sprite_renderer_component_serializes_and_restores():
    e = Entity("Hero")
    e.add_component(Transform(10, 20))
    sprite = e.add_component(SpriteRenderer2D())
    sprite.sprite_sheet_asset_id = SHEET_ID
    sprite.frame_index = 1
    sprite.layer = 3
    sprite.opacity = 0.75
    registry = ComponentRegistry()
    registry.register(Transform)
    registry.register(SpriteRenderer2D)
    clone = deserialize_entity(serialize_entity(e), registry)
    restored = clone.get(SpriteRenderer2D)
    assert restored.sprite_sheet_asset_id == SHEET_ID
    assert (restored.frame_index, restored.layer, restored.opacity) == (1, 3, 0.75)


def test_entity_sprite_builds_texture_draw_from_canonical_components():
    scene = Scene("Town")
    e = scene.add_entity(Entity("Hero"))
    e.add_component(Transform(32, 48))
    s = e.add_component(SpriteRenderer2D())
    s.sprite_sheet_asset_id = SHEET_ID
    sheet = SpriteSheet(AssetRef(TEX_ID, "texture"), [SpriteFrame(0, 0, 16, 24, 0.5, 1.0)])
    draws = build_entity_sprite_draws(
        scene, ViewportCamera(), lambda aid: sheet if aid == SHEET_ID else None
    )
    assert len(draws) == 1
    assert draws[0].texture_asset_id == TEX_ID
    assert (draws[0].screen_x, draws[0].screen_y) == (24, 24)


def test_camera_authoring_frame_is_distinct_from_editor_camera():
    scene = Scene("S")
    e = scene.add_entity(Entity("Game Camera"))
    e.add_component(Transform(100, 50))
    c = e.add_component(Camera2DComponent())
    c.width = 320
    c.height = 180
    c.zoom = 2
    frames = build_camera_frames(scene, ViewportCamera(10, 20, 1.5))
    assert len(frames) == 1
    f = frames[0]
    assert (f.screen_x, f.screen_y) == (160, 95)
    assert (f.width, f.height) == (240, 135)


def test_follow_camera_authoring_frame_is_centered_on_target():
    scene = Scene("S")
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform(300, 200))
    camera = scene.add_entity(Entity("Game Camera"))
    camera.add_component(Transform(0, 0))
    spec = camera.add_component(Camera2DComponent())
    spec.width = 480
    spec.height = 270
    spec.zoom = 1
    spec.follow_entity_id = hero.id

    frame = build_camera_frames(scene, ViewportCamera())[0]

    assert (frame.screen_x, frame.screen_y) == (60, 65)
    assert (frame.width, frame.height) == (480, 270)
