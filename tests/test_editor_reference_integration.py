from asteria.core import ComponentRegistry, Transform
from asteria.editor.model import EditorDocument
from asteria.editor.resource_resolver import resolve_project_resources
from asteria.editor.scene_render import render_source_for_scene
from asteria.editor.storage import load_document, save_document
from asteria.editor.tile_edit import build_paint_command, tile_at
from asteria.project import Project
from asteria.reference_ids import HERO_ANIMATION_ID, TILEMAP_ID
from asteria.reference_world import write_reference_world
from asteria.runtime import (
    Animator2DComponent,
    Camera2DComponent,
    SpriteRenderer2D,
    TileMap2DComponent,
)


def registry():
    reg = ComponentRegistry()
    for component_type in (
        Transform,
        SpriteRenderer2D,
        Camera2DComponent,
        Animator2DComponent,
        TileMap2DComponent,
    ):
        reg.register(component_type)
    return reg


def test_reference_project_resolves_editor_tile_and_animation_resources(tmp_path):
    write_reference_world(tmp_path)
    project_path = tmp_path / "AsteriaReferenceWorld.asteria.json"

    document = EditorDocument(component_registry=registry())
    load_document(document, project_path)
    resolve_project_resources(document)

    scene = document.project.scene(document.project.startup_scene_id)
    source = render_source_for_scene(document, scene)

    assert source is not None
    assert source.tilemap is document.asset_views.tilemap(TILEMAP_ID)
    assert source.tileset is document.asset_views.tileset(
        source.tilemap.tileset.asset_id
    )
    assert source.sprite_sheet is document.asset_views.sprite_sheet(
        source.tileset.sprite_sheet.asset_id
    )
    assert [layer.name for layer in source.tilemap.layers] == [
        "Ground",
        "Props",
        "Collision",
    ]
    assert len(source.tileset.tiles) == 16

    hero = next(e for e in scene.entities() if e.name == "Hero")
    animator = hero.get(Animator2DComponent)
    clips = document.asset_views.clip_set(animator.clip_set_id)

    assert animator.clip_set_id == HERO_ANIMATION_ID
    assert clips is not None
    assert set(clips.clips) == {
        "idle_down",
        "walk_down",
        "idle_left",
        "walk_left",
        "idle_right",
        "walk_right",
        "idle_up",
        "walk_up",
    }


def test_reference_tile_edits_persist_through_editor_save_and_reopen(tmp_path):
    write_reference_world(tmp_path)
    project_path = tmp_path / "AsteriaReferenceWorld.asteria.json"

    document = EditorDocument(component_registry=registry())
    load_document(document, project_path)
    resolve_project_resources(document)

    tilemap = document.asset_views.tilemap(TILEMAP_ID)
    ground = tilemap.layers[0]
    original = tile_at(tilemap, ground, 2, 2)
    replacement = 1 if original != 1 else 0
    document.execute(build_paint_command(tilemap, ground, ((2, 2),), replacement))

    save_document(document)

    reopened = EditorDocument(component_registry=registry())
    load_document(reopened, project_path)
    resolve_project_resources(reopened)

    reopened_tilemap = reopened.asset_views.tilemap(TILEMAP_ID)
    assert tile_at(reopened_tilemap, reopened_tilemap.layers[0], 2, 2) == replacement


def test_reference_project_roundtrip_preserves_tilemap_scene_binding(tmp_path):
    write_reference_world(tmp_path)
    project_path = tmp_path / "AsteriaReferenceWorld.asteria.json"

    loaded = Project.load_json(project_path, registry())
    scene = loaded.scene(loaded.startup_scene_id)

    world = next(e for e in scene.entities() if e.name == "World Map")
    binding = world.get(TileMap2DComponent)

    assert binding.tilemap_asset_id == TILEMAP_ID
    assert binding.visible is True
