from asteria.assets import AssetRef
from asteria.core import Scene,Entity,Transform,serialize_entity,deserialize_entity,ComponentRegistry
from asteria.graphics import SpriteSheet,SpriteFrame
from asteria.runtime import SpriteRenderer2D,Camera2DComponent
from asteria.editor.viewport import ViewportCamera
from asteria.editor.entity_render import build_entity_sprite_draws,build_camera_frames

SHEET_ID="123e4567-e89b-12d3-a456-426614174001"
TEX_ID="123e4567-e89b-12d3-a456-426614174000"

def test_sprite_renderer_component_serializes_and_restores():
    e=Entity("Hero");e.add_component(Transform(10,20))
    sprite=e.add_component(SpriteRenderer2D())
    sprite.sprite_sheet_asset_id=SHEET_ID
    sprite.frame_index=1;sprite.layer=3;sprite.opacity=0.75
    registry=ComponentRegistry();registry.register(Transform);registry.register(SpriteRenderer2D)
    clone=deserialize_entity(serialize_entity(e),registry)
    restored=clone.get(SpriteRenderer2D)
    assert restored.sprite_sheet_asset_id==SHEET_ID
    assert (restored.frame_index,restored.layer,restored.opacity)==(1,3,0.75)

def test_entity_sprite_builds_texture_draw_from_canonical_components():
    scene=Scene("Town")
    e=scene.add_entity(Entity("Hero"));e.add_component(Transform(32,48))
    s=e.add_component(SpriteRenderer2D());s.sprite_sheet_asset_id=SHEET_ID
    sheet=SpriteSheet(AssetRef(TEX_ID,"texture"),[SpriteFrame(0,0,16,24,0.5,1.0)])
    draws=build_entity_sprite_draws(
        scene,ViewportCamera(),lambda aid: sheet if aid==SHEET_ID else None
    )
    assert len(draws)==1
    assert draws[0].texture_asset_id==TEX_ID
    assert (draws[0].screen_x,draws[0].screen_y)==(24,24)

def test_camera_authoring_frame_is_distinct_from_editor_camera():
    scene=Scene("S")
    e=scene.add_entity(Entity("Game Camera"));e.add_component(Transform(100,50))
    c=e.add_component(Camera2DComponent());c.width=320;c.height=180;c.zoom=2
    frames=build_camera_frames(scene,ViewportCamera(10,20,1.5))
    assert len(frames)==1
    f=frames[0]
    assert (f.screen_x,f.screen_y)==(160,95)
    assert (f.width,f.height)==(240,135)
