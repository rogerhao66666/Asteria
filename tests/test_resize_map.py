import pytest

from asteria.editor.tile_edit import (
    TileEditError,
    build_paint_command,
    build_resize_map_command,
    tile_at,
    tilemap_size,
)
from asteria.editor.storage import load_document
from asteria.editor.model import EditorDocument
from asteria.editor.storage import save_document
from asteria.editor.starter_project import build_untitled_project, seed_unsaved_views
from asteria.runtime import TileMap2DComponent


def _untitled_tilemap():
    document = EditorDocument()
    document.set_project(build_untitled_project())
    seed_unsaved_views(document)
    entity = document.project.scenes()[0].entities()[0]
    binding = entity.get(TileMap2DComponent)
    tilemap = document.asset_views.tilemap(binding.tilemap_asset_id)
    return document, tilemap


def test_painting_past_the_map_edge_no_longer_raises():
    document, tilemap = _untitled_tilemap()
    layer = tilemap.layers[0]
    assert tilemap_size(tilemap) == (20, 15)

    # A stroke straddling the edge keeps the in-bounds cells and drops the
    # rest, instead of raising IndexError and losing the whole gesture.
    command = build_paint_command(tilemap, layer, [(19, 5), (25, 5)], 3)
    document.execute(command)
    assert tile_at(tilemap, layer, 19, 5) == 3
    # (25, 5) sits inside the same 32x32 chunk as the map but past its real
    # edge — must stay untouched, not resize the chunk or crash.
    assert layer.chunks[(0, 0)].width == 20


def test_painting_a_cell_from_a_different_chunk_address_still_works():
    # A general, multi-chunk tilemap (e.g. the reference-world fixture) is
    # not something build_paint_command should assume away: only the
    # in-chunk IndexError case (an editor-authored map's origin chunk,
    # smaller than the tilemap's own chunk_width/height) is guarded against.
    document, tilemap = _untitled_tilemap()
    layer = tilemap.layers[0]
    command = build_paint_command(tilemap, layer, [(40, 40)], 3)
    document.execute(command)
    assert tile_at(tilemap, layer, 40, 40) == 3


def test_resize_grows_the_map_and_preserves_existing_tiles():
    document, tilemap = _untitled_tilemap()
    layer = tilemap.layers[0]
    document.execute(build_paint_command(tilemap, layer, [(5, 5)], 3))

    document.execute(build_resize_map_command(tilemap, 30, 20))

    assert tilemap_size(tilemap) == (30, 20)
    assert tile_at(tilemap, layer, 5, 5) == 3
    # Newly-added area starts empty.
    from asteria.graphics import EMPTY_TILE

    assert tile_at(tilemap, layer, 25, 18) == EMPTY_TILE


def test_resize_shrink_crops_and_undo_restores_cropped_tiles():
    document, tilemap = _untitled_tilemap()
    layer = tilemap.layers[0]
    document.execute(build_paint_command(tilemap, layer, [(18, 12)], 3))

    document.execute(build_resize_map_command(tilemap, 10, 10))
    assert tilemap_size(tilemap) == (10, 10)
    with pytest.raises(IndexError):
        tile_at(tilemap, layer, 18, 12)

    assert document.undo()
    assert tilemap_size(tilemap) == (20, 15)
    assert tile_at(tilemap, layer, 18, 12) == 3


def test_painting_past_the_right_edge_grows_the_map_by_exactly_one_column():
    import pytest

    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    viewport = window.viewport
    viewport.resize(900, 700)
    viewport.reset_view()
    source = viewport.render_source
    assert tilemap_size(source.tilemap) == (20, 15)

    assert viewport._paint_cells([(20, 3)], 5)

    # Exactly the painted cell, not a fixed jump.
    assert tilemap_size(source.tilemap) == (21, 15)
    assert tile_at(source.tilemap, source.tilemap.layers[0], 20, 3) == 5
    assert source.binding.origin_x == 0.0

    window.document.mark_saved()
    window.close(); app.processEvents()


def test_painting_left_of_the_map_grows_it_and_keeps_tiles_in_place():
    import pytest

    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    viewport = window.viewport
    viewport.resize(900, 700)
    viewport.reset_view()
    source = viewport.render_source
    tilemap = source.tilemap
    layer = tilemap.layers[0]
    window.document.execute(build_paint_command(tilemap, layer, [(0, 0)], 7))

    assert viewport._paint_cells([(-1, 2)], 5)

    # Growing leftwards shifts tile indices, so the map's world origin moves
    # by the same amount and the already-painted corner stays put on screen.
    assert tilemap_size(tilemap) == (21, 15)
    assert source.binding.origin_x == -tilemap.tile_width
    assert tile_at(tilemap, layer, 0, 2) == 5
    assert tile_at(tilemap, layer, 1, 0) == 7

    assert window.document.undo()
    assert tilemap_size(tilemap) == (20, 15)
    assert source.binding.origin_x == 0.0
    assert tile_at(tilemap, layer, 0, 0) == 7

    window.document.mark_saved()
    window.close(); app.processEvents()


def test_growth_stops_at_the_maximum_map_size():
    from asteria.editor.tile_edit import MAX_MAP_SIDE, build_grow_map_command

    document, tilemap = _untitled_tilemap()

    class _Binding:
        origin_x = 0.0
        origin_y = 0.0

    with pytest.raises(TileEditError):
        build_grow_map_command(tilemap, _Binding(), [(MAX_MAP_SIDE + 10, 0)])


def test_resize_to_the_same_size_is_rejected():
    document, tilemap = _untitled_tilemap()
    with pytest.raises(TileEditError):
        build_resize_map_command(tilemap, 20, 15)


def test_resize_to_nonpositive_dimensions_is_rejected():
    document, tilemap = _untitled_tilemap()
    with pytest.raises(TileEditError):
        build_resize_map_command(tilemap, 0, 10)
    with pytest.raises(TileEditError):
        build_resize_map_command(tilemap, 10, -1)


def test_resized_map_round_trips_through_save_and_load(tmp_path):
    document, tilemap = _untitled_tilemap()
    layer = tilemap.layers[0]
    document.execute(build_paint_command(tilemap, layer, [(5, 5)], 3))
    document.execute(build_resize_map_command(tilemap, 30, 20))

    path = save_document(document, tmp_path / "game.asteria.json")

    reloaded = EditorDocument()
    load_document(reloaded, path)
    from asteria.editor.resource_resolver import resolve_project_resources

    resolve_project_resources(reloaded)
    entity = reloaded.project.scenes()[0].entities()[0]
    binding = entity.get(TileMap2DComponent)
    reloaded_tilemap = reloaded.asset_views.tilemap(binding.tilemap_asset_id)
    assert tilemap_size(reloaded_tilemap) == (30, 20)
    assert tile_at(reloaded_tilemap, reloaded_tilemap.layers[0], 5, 5) == 3
