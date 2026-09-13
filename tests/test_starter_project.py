from asteria.editor.model import EditorDocument
from asteria.editor.resource_resolver import resolve_project_resources
from asteria.editor.scene_render import render_source_for_scene
from asteria.editor.starter_project import (
    GRASS,
    NEW_MAP_HEIGHT,
    NEW_MAP_WIDTH,
    TILE_INFO,
    create_new_project,
)
from asteria.editor.storage import load_document


def test_new_project_is_immediately_paintable(tmp_path):
    path = create_new_project("My Game", tmp_path / "my_game")

    document = EditorDocument()
    load_document(document, path)
    resolve_project_resources(document)

    project = document.project
    assert project.name == "My Game"
    scene = project.scene(project.startup_scene_id)
    source = render_source_for_scene(document, scene)
    assert source is not None
    assert len(source.tileset.tiles) == len(TILE_INFO)
    assert len(source.sprite_sheet.frames) == len(TILE_INFO)
    assert [layer.name for layer in source.tilemap.layers] == ["Ground", "Decor"]

    ground = source.tilemap.layers[0].chunks[(0, 0)]
    assert all(
        ground.get(x, y) == GRASS
        for y in range(NEW_MAP_HEIGHT)
        for x in range(NEW_MAP_WIDTH)
    )
    assert (tmp_path / "my_game" / "tiles" / "environment_atlas.png").is_file()


def test_new_projects_do_not_share_asset_files(tmp_path):
    first = create_new_project("A", tmp_path / "a")
    second = create_new_project("B", tmp_path / "b")
    assert (first.parent / "tiles" / "environment_atlas.png").is_file()
    assert (second.parent / "tiles" / "environment_atlas.png").is_file()


def test_project_folder_name_is_filesystem_safe():
    from asteria.editor.shell import project_folder_name

    assert project_folder_name("My Game") == "My Game"
    assert project_folder_name("a/b:c*?") == "a_b_c"
    assert project_folder_name("  ..  ") == "New Project"
