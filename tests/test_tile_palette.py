from asteria.assets import AssetRef
from asteria.editor.tile_palette import TileToolState, build_tile_palette
from asteria.graphics import TileDef, Tileset

A = "123e4567-e89b-12d3-a456-426614174001"


def test_palette_sorted_and_preserves_metadata():
    ts = Tileset(
        AssetRef(A, "sprite_sheet"),
        16,
        16,
        {7: TileDef(1, "solid", "stone", ("wall",)), 2: TileDef(0)},
    )
    items = build_tile_palette(ts)
    assert [i.tile_id for i in items] == [2, 7]
    assert items[1].collision == "solid"
    assert items[1].terrain == "stone"


def test_tool_state_effective_tile():
    s = TileToolState()
    s.set_mode("paint")
    s.selected_tile_id = 4
    assert s.effective_tile_id == 4
    s.set_mode("erase")
    assert s.effective_tile_id == -1
