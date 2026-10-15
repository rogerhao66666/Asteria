"""Terrain, region and doodad brushes in the Tiles panel and viewport."""

from __future__ import annotations

import pytest

from asteria.assets.types import AssetRef
from asteria.core import Scene
from asteria.editor.commands import CommandStack
from asteria.editor.tile_edit import TileEditError, build_region_command, tile_at
from asteria.editor.tile_palette import TileToolState, terrain_ids
from asteria.graphics import EMPTY_TILE, TileChunk, TileLayer, TileMap
from asteria.graphics.tiles import TileDef, Tileset

SHEET = "11111111-1111-4111-8111-111111111111"
SET = "22222222-2222-4222-8222-222222222222"


def _tileset():
    tiles = {100 + m: TileDef(0, terrain="water", tags=(f"mask:{m}",)) for m in range(16)}
    tiles[7] = TileDef(0, terrain="grass")  # no mask tags: not an autotile terrain
    return Tileset(AssetRef(SHEET, "sprite_sheet"), 16, 16, tiles)


def _map():
    ground = TileLayer("ground")
    ground.chunks[(0, 0)] = TileChunk.empty(0, 0, 32, 32)
    return TileMap(AssetRef(SET, "tileset"), 16, 16, layers=[ground]), ground


def test_terrain_ids_lists_only_masked_terrains():
    assert terrain_ids(_tileset()) == ("water",)


def test_terrain_mode_paints_through_the_tool_state_and_undoes():
    tilemap, ground = _map()
    tools = TileToolState(active_layer=ground, tileset=_tileset(), terrain_id="water")
    tools.set_mode("terrain")
    stack = CommandStack()
    stack.execute(tools.build_command(tilemap, [(1, 1), (2, 1)]))
    assert tile_at(tilemap, ground, 1, 1) == 100 + 2  # east neighbour only
    assert tile_at(tilemap, ground, 2, 1) == 100 + 8
    stack.undo()
    assert tile_at(tilemap, ground, 1, 1) == EMPTY_TILE
    tools.terrain_id = None
    with pytest.raises(ValueError):
        tools.build_command(tilemap, [(0, 0)])


def test_region_mode_creates_a_hidden_layer_once_and_one_undo_removes_all():
    tilemap, ground = _map()
    tools = TileToolState(active_layer=ground, region_id=3)
    tools.set_mode("region")
    stack = CommandStack()
    stack.execute(tools.build_command(tilemap, [(0, 0), (1, 0), (1, 0)]))
    layer = next(item for item in tilemap.layers if item.name == "regions")
    assert not layer.visible and layer.order > ground.order
    assert tile_at(tilemap, layer, 1, 0) == 3
    tools.region_id = 5
    stack.execute(tools.build_command(tilemap, [(1, 0)]))
    assert sum(1 for item in tilemap.layers if item.name == "regions") == 1
    assert tile_at(tilemap, layer, 1, 0) == 5
    stack.undo()
    assert tile_at(tilemap, layer, 1, 0) == 3
    stack.undo()
    assert all(item.name != "regions" for item in tilemap.layers)


def test_region_erase_and_noop():
    tilemap, ground = _map()
    stack = CommandStack()
    stack.execute(build_region_command(tilemap, "regions", [(2, 2)], 4))
    layer = next(item for item in tilemap.layers if item.name == "regions")
    stack.execute(build_region_command(tilemap, "regions", [(2, 2)], 0, erase=True))
    assert tile_at(tilemap, layer, 2, 2) == EMPTY_TILE
    with pytest.raises(TileEditError):
        build_region_command(tilemap, "regions", [(2, 2)], 0, erase=True)


@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PySide6")
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_palette_offers_the_terrains_and_doodads_and_drives_the_viewport(app):
    from asteria.editor.model import EditorDocument
    from asteria.editor.tile_palette_widget import TilePaletteWidget
    from asteria.editor.viewport_widget import SceneViewportWidget as ViewportWidget
    from asteria.rpg.doodads import DoodadDefinition

    document = EditorDocument()
    viewport = ViewportWidget(document)
    palette = TilePaletteWidget()
    palette.terrainChanged.connect(viewport.set_terrain)
    palette.regionChanged.connect(viewport.set_region)
    palette.doodadChanged.connect(viewport.set_doodad)
    palette.modeChanged.connect(viewport.set_tile_mode)

    palette.set_tileset(_tileset())
    assert viewport.tile_tools.terrain_id == "water"
    palette.region_spin.setValue(9)
    palette.region_erase.setChecked(True)
    assert (viewport.tile_tools.region_id, viewport.tile_tools.region_erase) == (9, True)
    tree = DoodadDefinition("tree", SHEET, frame=2)
    palette.set_doodads({"tree": tree})
    assert viewport.tile_tools.doodad is tree
    for button, mode in (
        (palette.terrain_button, "terrain"),
        (palette.region_button, "region"),
        (palette.doodad_button, "doodad"),
    ):
        button.click()
        assert viewport.tile_tools.mode == mode
        assert button.isChecked() and not palette.paint_button.isChecked()


def test_clicking_in_doodad_mode_places_one_undoable_entity(app):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from asteria.editor.model import EditorDocument
    from asteria.editor.viewport_widget import SceneViewportWidget as ViewportWidget
    from asteria.project import Project
    from asteria.rpg.doodads import DoodadDefinition

    project = Project("G")
    scene = project.add_scene(Scene("Town"))
    document = EditorDocument(project=project)
    viewport = ViewportWidget(document)
    viewport.resize(200, 200)
    viewport.set_doodad(DoodadDefinition("tree", SHEET, frame=2))
    viewport.set_tile_mode("doodad")
    press = QMouseEvent(
        QEvent.MouseButtonPress,
        QPointF(50, 60),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    viewport.mousePressEvent(press)
    assert [e.name for e in scene.entities()] == ["doodad:tree.1"]
    document.undo()
    assert not scene.entities()


def _rig_file(tmp_path):
    import json

    rig = {
        "bones": [{"name": "root"}, {"name": "arm", "parent": "root", "x": 10, "length": 20}],
        "slots": [{"name": "hand", "bone": "arm", "attachment": "fist"}],
        "animations": {
            "wave": {
                "bones": {"arm": {"rotate": [{"time": 0, "value": 0}, {"time": 1, "value": 90}]}}
            }
        },
    }
    path = tmp_path / "rig.json"
    path.write_text(json.dumps(rig), encoding="utf-8")
    return path


def test_bone_segments_follow_the_clip_time(tmp_path):
    from asteria.editor.skeleton_view import bone_segments, bounds, load_rig

    skeleton, notes = load_rig(_rig_file(tmp_path))
    assert notes == () or isinstance(notes, tuple)
    rest = {s.bone_id: s for s in bone_segments(skeleton)}
    assert (rest["arm"].x0, rest["arm"].x1) == (10.0, 30.0)
    turned = {s.bone_id: s for s in bone_segments(skeleton, "wave", 0.5)}
    assert turned["arm"].y1 != rest["arm"].y1
    left, top, right, bottom = bounds(tuple(rest.values()))
    assert left < 0 < right and bottom > top


def test_viewer_loads_a_rig_scrubs_and_reports_bad_files(app, tmp_path):
    from asteria.editor.skeleton_widget import SkeletonViewerWidget

    viewer = SkeletonViewerWidget()
    assert viewer.open_rig(_rig_file(tmp_path))
    assert viewer.clip_combo.currentText() == "wave"
    before = viewer.segments()
    viewer.slider.setValue(50)
    assert abs(viewer.time - 0.5) < 0.02 and viewer.segments() != before
    viewer.canvas.grab()  # paints without error
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert not viewer.open_rig(bad) and "Could not load" in viewer.status.text()
    assert not viewer.open_rig(tmp_path / "missing.json")
