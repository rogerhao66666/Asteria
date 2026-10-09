import json
from pathlib import Path

import pytest

from asteria.assets.local_reference import discover_mv_projects, resolve_rpg_maker_mv_root
from asteria.assets.rpg_maker_mv_catalog import RPGMakerMVCatalog
from asteria.assets.rpg_maker_mv_database import RPGMakerMVDatabase
from asteria.assets.rpg_maker_mv_map import (
    RPGMakerMVMap,
    discover_mv_maps,
    to_asteria_scene,
)
from asteria.core import Transform
from asteria.runtime import TileMap2DComponent


def _real():
    repo = Path(__file__).resolve().parents[1]
    layout = discover_mv_projects(resolve_rpg_maker_mv_root(repo))[0]
    database = RPGMakerMVDatabase.load(layout)
    return layout, RPGMakerMVCatalog.build(layout, database)


def _map(path: Path, *, data_length=24, tile=-1):
    raw = {
        "displayName": "Village", "width": 2, "height": 2, "tilesetId": 1,
        "parallaxName": "BlueSky", "scrollType": 0,
        "data": [tile] * data_length,
        "encounterList": [{"regionSet": [], "troopId": 1, "weight": 10}],
        "events": [None, {"id": 1, "name": "Guide", "x": 1, "y": 1,
            "pages": [{"image": {"characterName": "Actor1", "characterIndex": 0,
                                    "direction": 2, "pattern": 1, "tileId": 0}}]}],
    }
    path.write_text(json.dumps(raw), encoding="utf-8")


@pytest.mark.mv_reference
def test_real_map_infos_resolve_and_six_layers_validate():
    layout, _ = _real()
    entries = discover_mv_maps(layout)
    mv_map = RPGMakerMVMap.load(entries[0].path, map_id=entries[0].map_id,
                                name=entries[0].name)

    assert [(entry.map_id, entry.name) for entry in entries] == [(1, "MAP001")]
    assert (mv_map.width, mv_map.height, len(mv_map.layers)) == (17, 13, 6)
    assert all(len(layer) == 17 * 13 for layer in mv_map.layers)
    assert mv_map.tileset_id == 1


def test_map_retains_display_parallax_encounter_and_event_image(tmp_path):
    path = tmp_path / "Map001.json"
    _map(path, tile=0)
    mv_map = RPGMakerMVMap.load(path, map_id=1, name="Test")

    assert mv_map.display_name == "Village"
    assert mv_map.parallax_name == "BlueSky"
    assert mv_map.encounters[0].troop_id == 1
    assert (mv_map.events[0].x, mv_map.events[0].y) == (1, 1)
    assert mv_map.events[0].image.character_name == "Actor1"
    assert mv_map.events[0].image.pattern == 1


def test_map_rejects_wrong_layer_length_and_negative_tile_id(tmp_path):
    short = tmp_path / "Map001.json"
    _map(short, data_length=23, tile=0)
    with pytest.raises(ValueError, match="six layers"):
        RPGMakerMVMap.load(short, map_id=1)

    bad = tmp_path / "Map002.json"
    _map(bad, tile=-1)
    with pytest.raises(ValueError, match="tile id"):
        RPGMakerMVMap.load(bad, map_id=2)


@pytest.mark.mv_reference
def test_scene_conversion_uses_tilemap_host_and_event_standing_points(tmp_path):
    _, catalog = _real()
    path = tmp_path / "Map001.json"
    _map(path, tile=0)
    mv_map = RPGMakerMVMap.load(path, map_id=1, name="Test")

    scene = to_asteria_scene(mv_map, catalog)
    host, event = scene.entities()

    assert host.has(TileMap2DComponent)
    assert event.name == "Guide"
    assert (event.get(Transform).x, event.get(Transform).y) == (72.0, 96.0)
    assert event.rpg_maker_mv_event.image.character_name == "Actor1"
