from asteria.assets import AssetRef
from asteria.editor.viewport import ViewportCamera
from asteria.graphics import (
    SpriteFrame,
    SpriteSheet,
    TileChunk,
    TileDef,
    TileLayer,
    TileMap,
    Tileset,
)
from asteria.runtime import build_tile_draws

TEX = "123e4567-e89b-12d3-a456-426614174000"
SHEET = "123e4567-e89b-12d3-a456-426614174001"
SET = "123e4567-e89b-12d3-a456-426614174002"


def make():
    sheet = SpriteSheet(
        AssetRef(TEX, "texture"),
        [SpriteFrame(0, 0, 16, 16, 0, 0), SpriteFrame(16, 0, 16, 16, 0, 0)],
    )
    ts = Tileset(
        AssetRef(SHEET, "sprite_sheet"), 16, 16, {0: TileDef(0), 1: TileDef(1)}
    )
    ch = TileChunk.empty(0, 0, 2, 2)
    ch.set(0, 0, 0)
    ch.set(1, 1, 1)
    tm = TileMap(
        AssetRef(SET, "tileset"),
        16,
        16,
        2,
        2,
        [TileLayer("Ground", 2, True, 0.5, False, {(0, 0): ch})],
    )
    return tm, ts, sheet


def test_tilemap_builds_backend_neutral_texture_draws():
    tm, ts, sheet = make()
    cam = ViewportCamera(0, 0, 2)
    draws = build_tile_draws(tm, ts, sheet, cam)
    assert len(draws) == 2
    assert draws[0].source == (0, 0, 16, 16)
    assert draws[0].width == 32 and draws[0].height == 32
    assert draws[1].screen_x == 32 and draws[1].screen_y == 32
    assert all(d.opacity == 0.5 and d.layer == 2 for d in draws)


def test_tile_draw_culls_outside_viewport():
    tm, ts, sheet = make()
    cam = ViewportCamera(1000, 1000, 1)
    draws = build_tile_draws(
        tm, ts, sheet, cam, viewport_width=100, viewport_height=100
    )
    assert draws == ()
