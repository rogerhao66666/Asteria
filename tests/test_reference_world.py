from asteria.reference_ids import PROJECT_ID, SCENE_ID
from asteria.reference_world import build_reference_world, write_reference_world
from asteria.runtime import (
    Animator2DComponent,
    Camera2DComponent,
    SpriteRenderer2D,
    TileMapQuery,
)


def test_reference_world_has_real_assets_map_player_camera():
    b = build_reference_world()
    assert b.project.id == PROJECT_ID
    assert b.scene.id == SCENE_ID
    assert b.project.startup_scene_id == SCENE_ID
    assert len(b.tilemap.layers) == 3
    assert len(b.environment_sheet.frames) == 16
    assert len(b.hero_sheet.frames) == 16
    assert len(b.hero_clips.clips) == 8
    assert b.hero.get(SpriteRenderer2D).sprite_sheet_asset_id
    assert b.hero.get(Animator2DComponent).clip_set_id
    assert b.camera.get(Camera2DComponent).follow_entity_id == b.hero.id


def test_reference_world_collision_boundary_and_bridge():
    b = build_reference_world()
    q = TileMapQuery(b.tilemap)
    assert q.collides_world_point(0, 0)
    assert q.collides_world_point(33 * 16 + 8, 5 * 16 + 8)
    assert not q.collides_world_point(33 * 16 + 8, 12 * 16 + 8)


def test_reference_world_export_writes_canonical_project_and_sidecars(tmp_path):
    write_reference_world(tmp_path)
    assert (tmp_path / "AsteriaReferenceWorld.asteria.json").exists()
    assert (tmp_path / "reference_data/tilemap.json").exists()
    assert (tmp_path / "reference_data/hero_animation.json").exists()
