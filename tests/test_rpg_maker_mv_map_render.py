import json
from pathlib import Path

from asteria.assets.local_reference import discover_mv_projects, resolve_rpg_maker_mv_root
from asteria.assets.rpg_maker_mv_catalog import RPGMakerMVCatalog
from asteria.assets.rpg_maker_mv_database import RPGMakerMVDatabase
from asteria.assets.rpg_maker_mv_map import RPGMakerMVMap
from asteria.assets.rpg_maker_mv_map_render import (
    MVTileResolver,
    compose_mv_map_draws,
)


def _context():
    repo = Path(__file__).resolve().parents[1]
    layout = discover_mv_projects(resolve_rpg_maker_mv_root(repo))[0]
    database = RPGMakerMVDatabase.load(layout)
    return layout, RPGMakerMVCatalog.build(layout, database)


def _write_map(path, tiles):
    data = [0] * (2 * 1 * 6)
    data[:2] = tiles
    path.write_text(json.dumps({
        "displayName": "Render", "width": 2, "height": 1, "tilesetId": 1,
        "parallaxName": "", "scrollType": 0, "data": data,
        "encounterList": [], "events": [None],
    }))
    return RPGMakerMVMap.load(path, map_id=1)


def test_resolver_maps_b_c_d_e_and_a_sheets():
    layout, catalog = _context()
    resolver = MVTileResolver(layout, catalog, tileset_id=1)

    assert resolver.resolve(1).source.name == "World_B.png"
    assert resolver.resolve(256).source.name == "World_C.png"
    assert resolver.resolve(512).source is None  # empty D slot in this tileset
    assert resolver.resolve(768).source is None  # empty E slot in this tileset
    assert resolver.resolve(1536).source is None  # empty A5 slot
    a2 = resolver.resolve(2816)
    assert a2.source.name == "World_A2.png"
    assert len(a2.quarters) == 4


def test_draw_order_empty_tiles_and_viewport_culling(tmp_path):
    layout, catalog = _context()
    mv_map = _write_map(tmp_path / "Map001.json", [2816, 1])
    resolver = MVTileResolver(layout, catalog, tileset_id=1)

    all_draws = compose_mv_map_draws(mv_map, resolver, (0, 0, 96, 48))
    first_cell = [draw for draw in all_draws if draw.screen_x < 48]
    second_cell = [draw for draw in all_draws if draw.screen_x >= 48]
    culled = compose_mv_map_draws(mv_map, resolver, (0, 0, 48, 48))

    assert len(first_cell) == 4
    assert len(second_cell) == 1
    assert [draw.layer for draw in all_draws] == sorted(draw.layer for draw in all_draws)
    assert all(draw.screen_x < 48 for draw in culled)


def test_zero_tile_emits_no_draw(tmp_path):
    layout, catalog = _context()
    mv_map = _write_map(tmp_path / "Map001.json", [0, 0])
    resolver = MVTileResolver(layout, catalog, tileset_id=1)

    assert compose_mv_map_draws(mv_map, resolver, (0, 0, 96, 48)) == ()
