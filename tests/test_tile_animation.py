"""Animated tiles and cover tiles in the tile scene view."""

import json
from types import SimpleNamespace

import pytest

from asteria.assets import AssetRef
from asteria.core.ids import new_id
from asteria.graphics import TileChunk, TileLayer, TileMap
from asteria.graphics.sprites import SpriteFrame
from asteria.graphics.tiles import TileDef, Tileset
from asteria.reference_data import load_tileset

pygame = pytest.importorskip("pygame")


def test_a_tileset_reads_and_checks_animation_frames(tmp_path):
    path = tmp_path / "tiles.json"
    path.write_text(
        json.dumps(
            {
                "sprite_sheet_asset_id": new_id(),
                "tile_width": 16,
                "tile_height": 16,
                "tiles": {
                    "0": {"frame_index": 0, "collision": "none", "terrain": None, "tags": []},
                    "1": {
                        "frame_index": 1,
                        "collision": "none",
                        "terrain": None,
                        "tags": ["cover"],
                        "animation": [1, 2],
                        "frame_ms": 120,
                    },
                },
            }
        )
    )
    tileset = load_tileset(path)
    assert tileset.tiles[0].animation == () and tileset.tiles[1].animation == (1, 2)
    assert tileset.tiles[1].frame_ms == 120.0 and tileset.tiles[1].tags == ("cover",)
    tileset.validate(3)
    with pytest.raises(ValueError):
        TileDef(0, animation=(0, 5), frame_ms=10).validate(3)
    with pytest.raises(ValueError):
        TileDef(0, animation=(0, 1)).validate(3)


def _view(layer_tiles):
    """A tile scene view over a 4 x 1 strip of 16 px frames 0..7 (frame n is red n x 30),
    with tile 1 animated through frames 1, 2, 3 (100 ms each) and tile 5 a cover tile that
    plays 6, 7 once."""
    from asteria.runtime.tile_scene_view import TileSceneView

    texture = pygame.Surface((8 * 16, 16), pygame.SRCALPHA)
    for n in range(8):
        texture.fill((n * 30, 0, 0, 255), (n * 16, 0, 16, 16))
    frames = [SpriteFrame(n * 16, 0, 16, 16) for n in range(8)]
    tiles = {n: TileDef(n) for n in range(8)}
    tiles[1] = TileDef(1, animation=(1, 2, 3), frame_ms=100)
    tiles[5] = TileDef(5, tags=("cover",), animation=(6, 7), frame_ms=50)
    layers = []
    for name, cells, visible in layer_tiles:
        layer = TileLayer(name, 0, visible)
        chunk = layer.chunks[(0, 0)] = TileChunk.empty(0, 0, 4, 4)
        for (x, y), tile in cells.items():
            chunk.set(x, y, tile)
        layers.append(layer)
    view = TileSceneView.__new__(TileSceneView)
    view.pg = pygame
    view.tilemap = TileMap(AssetRef(new_id()), 16, 16, 4, 4, layers)
    view.tileset = Tileset(AssetRef(new_id()), 16, 16, tiles)
    view.tile_sheet = SimpleNamespace(frames=frames)
    view._texture_surface = texture
    view._frame_rects, view._chunk_cache, view._frames = {}, {}, {}
    view._groups = {"below": [x for x in layers if x.visible], "above": []}
    view._tile_animations = {1: ((1, 2, 3), 100.0)}
    view._tile_clock, view._animated_chunks = 0.0, set()
    view._tile_phase = view._animation_phase()
    view._cover_ids = set()
    view._covers = view._cover_cells(skip="regions")
    view._cover_entered = {}
    view.camera = SimpleNamespace(zoom=1.0, world_to_screen=lambda x, y: (x, y))
    return view


def test_animated_tiles_change_frame_and_redraw_only_their_chunks():
    view = _view([("Below", {(0, 0): 1, (1, 0): 0}, True)])
    chunk = view._chunk_surface("below", 0, 0)
    assert chunk.get_at((0, 0))[0] == 30 and chunk.get_at((16, 0))[0] == 0
    assert ("below", 0, 0) in view._animated_chunks
    view._advance_tiles(0.05)  # still on its first frame: the picture is kept
    assert ("below", 0, 0) in view._chunk_cache
    view._advance_tiles(0.06)  # 110 ms: the next frame
    assert ("below", 0, 0) not in view._chunk_cache
    assert view._chunk_surface("below", 0, 0).get_at((0, 0))[0] == 60
    view._advance_tiles(0.2)  # 310 ms: round to the first again
    assert view._chunk_surface("below", 0, 0).get_at((0, 0))[0] == 30


def test_cover_tiles_are_left_out_of_layers_and_play_once_over_who_stands_there():
    view = _view(
        [
            ("Below", {(0, 0): 0, (1, 0): 0}, True),
            ("Grass", {(1, 0): 5}, True),  # shown, yet not drawn with the layer
            ("regions", {(2, 0): 5}, False),  # region numbers are not tiles
        ]
    )
    assert view._covers == {(1, 0): 5}
    assert view._chunk_surface("below", 0, 0).get_at((16, 0))[0] == 0  # only the ground
    screen = pygame.Surface((64, 16), pygame.SRCALPHA)
    person = SimpleNamespace(id="p")
    view._draw_cover(screen, person, SimpleNamespace(x=24.0, y=8.0))
    assert screen.get_at((16, 0))[0] == 180  # frame 6 as it steps in
    view._advance_tiles(0.06)
    view._draw_cover(screen, person, SimpleNamespace(x=24.0, y=8.0))
    assert screen.get_at((16, 0))[0] == 210  # then 7
    view._advance_tiles(1.0)
    view._draw_cover(screen, person, SimpleNamespace(x=24.0, y=8.0))
    assert screen.get_at((16, 0))[0] == 210  # and it stays on its last frame
    screen.fill((0, 0, 0, 0))
    view._draw_cover(screen, person, SimpleNamespace(x=8.0, y=8.0))  # off the grass
    assert screen.get_at((0, 0))[3] == 0 and "p" not in view._cover_entered
