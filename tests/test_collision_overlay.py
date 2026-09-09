from asteria.assets import AssetRef
from asteria.editor.collision_overlay import build_collision_cells
from asteria.editor.model import EditorDocument
from asteria.editor.tile_edit import build_paint_command
from asteria.editor.viewport import ViewportCamera
from asteria.graphics import TileLayer, TileMap

A = "123e4567-e89b-12d3-a456-426614174002"


def test_collision_overlay_uses_only_collision_enabled_layers():
    collision = TileLayer("Collision", collision_enabled=True)
    visual = TileLayer("Ground", order=1)
    tm = TileMap(AssetRef(A, "tileset"), 16, 16, 4, 4, [collision, visual])
    doc = EditorDocument()
    doc.execute(build_paint_command(tm, collision, [(2, 3)], 1))
    doc.execute(build_paint_command(tm, visual, [(0, 0)], 1))
    cells = build_collision_cells(tm, ViewportCamera())
    assert len(cells) == 1
    assert (cells[0].tile_x, cells[0].tile_y) == (2, 3)
    assert (cells[0].screen_x, cells[0].screen_y) == (32, 48)
