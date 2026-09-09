from asteria.assets import AssetRef
from asteria.editor.model import EditorDocument
from asteria.editor.tile_edit import (
    ReorderTileLayerCommand,
    SetTileLayerPropertyCommand,
    TileEditError,
    build_paint_command,
    flood_fill_cells,
    rectangle_cells,
)
from asteria.graphics import TileLayer, TileMap

A = "123e4567-e89b-12d3-a456-426614174002"


def make():
    layer = TileLayer("Ground")
    return TileMap(AssetRef(A, "tileset"), 16, 16, 4, 4, [layer]), layer


def test_rectangle_cells_are_inclusive_and_reverse_safe():
    assert rectangle_cells(2, 1, 0, 0) == (
        (0, 0),
        (1, 0),
        (2, 0),
        (0, 1),
        (1, 1),
        (2, 1),
    )


def test_flood_fill_respects_connected_value_region():
    tm, layer = make()
    doc = EditorDocument()
    doc.execute(
        build_paint_command(tm, layer, [(x, y) for y in range(3) for x in range(3)], 1)
    )
    doc.execute(build_paint_command(tm, layer, [(1, 1)], 2))
    got = set(flood_fill_cells(tm, layer, 0, 0))
    assert (1, 1) not in got
    assert len(got) == 8


def test_fill_rejects_unbounded_empty_sparse_world():
    tm, layer = make()
    try:
        flood_fill_cells(tm, layer, 0, 0)
    except TileEditError:
        pass
    else:
        raise AssertionError("expected finite-fill safety rejection")


def test_layer_reorder_and_collision_property_are_undoable():
    tm, a = make()
    b = TileLayer("Props", order=1)
    tm.layers.append(b)
    doc = EditorDocument()
    doc.execute(ReorderTileLayerCommand(tm, b, 0))
    assert tm.layers[0] is b
    assert [x.order for x in tm.layers] == [0, 1]
    doc.undo()
    assert tm.layers[0] is a
    doc.execute(SetTileLayerPropertyCommand(a, "collision_enabled", True))
    assert a.collision_enabled
    doc.undo()
    assert not a.collision_enabled
