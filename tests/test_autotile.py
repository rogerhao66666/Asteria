"""Terrain autotiling: neighbour masks, tile choice with fallback, and the editor paint command."""

import pytest

from asteria.assets.types import AssetRef
from asteria.editor.commands import CommandStack
from asteria.editor.tile_edit import TileEditError, build_terrain_command, tile_at
from asteria.graphics import EMPTY_TILE, TileChunk, TileLayer, TileMap
from asteria.graphics.autotile import (
    NE,
    AutotileSet,
    E,
    N,
    S,
    W,
    build_autotile_set,
    neighbour_mask,
    terrain_updates,
)
from asteria.graphics.tiles import TileDef, Tileset

SHEET = "11111111-1111-4111-8111-111111111111"
SET = "22222222-2222-4222-8222-222222222222"
# a 16-tile "water" terrain: tile id = 100 + mask
WATER = {mask: 100 + mask for mask in range(16)}


def _tileset(extra=None):
    tiles = {100 + mask: TileDef(0, terrain="water", tags=(f"mask:{mask}",)) for mask in WATER}
    tiles[7] = TileDef(0, terrain="grass")
    tiles.update(extra or {})
    return Tileset(AssetRef(SHEET, "sprite_sheet"), 16, 16, tiles)


def _map():
    layer = TileLayer("ground")
    layer.chunks[(0, 0)] = TileChunk.empty(0, 0, 32, 32)
    return TileMap(AssetRef(SET, "tileset"), 16, 16, layers=[layer]), layer


def test_masks_count_the_four_sides_and_only_supported_corners():
    cells = {(1, 1), (1, 0), (2, 1), (2, 0)}
    filled = lambda x, y: (x, y) in cells  # noqa: E731
    assert neighbour_mask(filled, 1, 1) == N | E
    assert neighbour_mask(filled, 1, 1, "blob8") == N | E | NE  # N and E are there: NE counts
    lonely_corner = {(1, 1), (2, 0)}
    assert neighbour_mask(lambda x, y: (x, y) in lonely_corner, 1, 1, "blob8") == 0


def test_tile_for_uses_the_exact_mask_else_the_best_subset():
    auto = AutotileSet("w", {0: 10, N: 11, N | E: 12})
    assert auto.tile_for(N | E) == 12
    assert auto.tile_for(N | E | S) == 12  # no tile with S: the one asking for most of the rest
    assert auto.tile_for(E) == 10  # nothing for E alone: the bare tile
    assert AutotileSet("w", {N: 11}).tile_for(S | W) == 11  # nothing fits: the first tile


def test_set_is_built_from_the_tilesets_terrain_tags():
    auto = build_autotile_set(_tileset(), "water")
    assert dict(auto.masks) == WATER and auto.tile_for(N | S) == 100 + (N | S)
    with pytest.raises(ValueError):
        build_autotile_set(_tileset(), "lava")  # no tiles


def test_painting_a_row_picks_end_and_middle_tiles_and_fixes_neighbours():
    tilemap, layer = _map()
    tileset = _tileset()
    auto = build_autotile_set(tileset, "water")
    cells = [(2, 3), (3, 3), (4, 3)]
    updates = terrain_updates(tilemap, layer, tileset, {"water": auto}, cells)
    assert updates == {(2, 3): 100 + E, (3, 3): 100 + (E | W), (4, 3): 100 + W}
    command = build_terrain_command(tilemap, layer, tileset, auto, cells)
    command.redo()
    assert [tile_at(tilemap, layer, x, 3) for x in (2, 3, 4)] == [100 + E, 100 + 10, 100 + W]
    extend = build_terrain_command(tilemap, layer, tileset, auto, [(5, 3)])
    extend.redo()
    assert tile_at(tilemap, layer, 4, 3) == 100 + (E | W)  # the old end joined up
    assert tile_at(tilemap, layer, 5, 3) == 100 + W


def test_other_terrains_and_empty_cells_do_not_join():
    tilemap, layer = _map()
    tileset = _tileset()
    auto = build_autotile_set(tileset, "water")
    from asteria.editor.tile_edit import SetTileCommand

    SetTileCommand(tilemap, layer, 1, 1, 7).redo()  # grass next to the water
    updates = terrain_updates(tilemap, layer, tileset, {"water": auto}, [(2, 1)])
    assert updates == {(2, 1): 100}  # grass is not water, so the cell stands alone


def test_erasing_empties_the_cells_and_reshapes_neighbours():
    tilemap, layer = _map()
    tileset = _tileset()
    auto = build_autotile_set(tileset, "water")
    build_terrain_command(tilemap, layer, tileset, auto, [(2, 3), (3, 3), (4, 3)]).redo()
    erase = build_terrain_command(tilemap, layer, tileset, auto, [(3, 3)], erase=True)
    erase.redo()
    assert tile_at(tilemap, layer, 3, 3) == EMPTY_TILE
    assert tile_at(tilemap, layer, 2, 3) == 100 and tile_at(tilemap, layer, 4, 3) == 100


def test_a_paint_is_one_undo_step():
    tilemap, layer = _map()
    tileset = _tileset()
    auto = build_autotile_set(tileset, "water")
    stack = CommandStack()
    stack.execute(build_terrain_command(tilemap, layer, tileset, auto, [(2, 3), (3, 3)]))
    stack.undo()
    assert all(tile_at(tilemap, layer, x, 3) == EMPTY_TILE for x in (1, 2, 3, 4))
    stack.redo()
    assert tile_at(tilemap, layer, 2, 3) == 100 + E
    with pytest.raises(TileEditError):
        build_terrain_command(tilemap, layer, tileset, auto, [(2, 3), (3, 3)])  # no change


def test_validation():
    with pytest.raises(ValueError):
        AutotileSet("w", {})
    with pytest.raises(ValueError):
        AutotileSet("w", {16: 1})  # edge4 has 16 masks
    with pytest.raises(ValueError):
        AutotileSet("w", {1: 1}, mode="odd")
    auto = AutotileSet("w", {0: 1})
    with pytest.raises(ValueError):
        terrain_updates(*_map(), _tileset(), {"a": auto, "b": auto}, [(0, 0)])
