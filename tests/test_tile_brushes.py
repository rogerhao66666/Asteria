"""Map painting like RPG Maker: a block of tiles as a stamp, a wider brush, the right-click
eyedropper, tool keys and painting that shows while the mouse is still down."""

import pytest

from asteria.editor.tile_palette import TileToolState
from asteria.graphics import EMPTY_TILE


def test_a_stamp_repeats_seamlessly_from_where_the_stroke_began():
    tools = TileToolState(mode="paint")
    tools.set_stamp(((1, 2), (3, 4)))
    assert tools.selected_tile_id == 1 and tools.stamp == ((1, 2), (3, 4))
    out = tools.assignments([(10, 10), (11, 10)])
    assert out[(10, 10)] == 1 and out[(11, 10)] == 2 and out[(12, 10)] == 1  # the pattern tiles
    assert out[(10, 11)] == 3 and out[(11, 11)] == 4
    tools.mode = "rectangle"  # a rectangle repeats the block from its corner
    rect = tools.assignments([(0, 0), (1, 0), (2, 0), (0, 1)], origin=(0, 0))
    assert rect == {(0, 0): 1, (1, 0): 2, (2, 0): 1, (0, 1): 3}


def test_a_single_tile_paints_and_erases_a_square_as_wide_as_the_brush():
    tools = TileToolState(mode="paint", selected_tile_id=7, brush_size=3)
    out = tools.assignments([(5, 5)])
    assert len(out) == 9 and set(out.values()) == {7} and (4, 4) in out and (6, 6) in out
    tools.mode = "erase"
    assert set(tools.assignments([(5, 5)]).values()) == {EMPTY_TILE}
    tools.set_stamp(((7,),))  # one tile picked: a plain tile, not a stamp
    assert tools.stamp is None


@pytest.fixture
def viewport():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.assets.types import AssetRef
    from asteria.core import Scene
    from asteria.editor import EditorDocument
    from asteria.editor.scene_render import TileMapRenderSource
    from asteria.editor.viewport_widget import SceneViewportWidget
    from asteria.graphics.tilemap import TileLayer, TileMap
    from asteria.project import Project

    QApplication.instance() or QApplication([])
    project = Project("Map")
    project.add_scene(Scene("Field"))
    layer = TileLayer("Ground")
    tilemap = TileMap(
        AssetRef("2a295d51-3682-588c-af08-4e8e7916f5f2", "tileset"), 16, 16, 16, 16, [layer]
    )
    widget = SceneViewportWidget(EditorDocument(project))
    widget.resize(640, 480)
    widget.set_render_source(TileMapRenderSource(tilemap, None, None))
    widget.tile_tools.active_layer = layer
    widget.camera.zoom, widget.camera.pan_x, widget.camera.pan_y = 1.0, 0.0, 0.0
    return widget, tilemap, layer


def _mouse(widget, kind, x, y, button):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    buttons = Qt.NoButton if kind == QEvent.MouseButtonRelease else button
    event = QMouseEvent(kind, QPointF(x, y), QPointF(x, y), button, buttons, Qt.NoModifier)
    {
        QEvent.MouseButtonPress: widget.mousePressEvent,
        QEvent.MouseMove: widget.mouseMoveEvent,
        QEvent.MouseButtonRelease: widget.mouseReleaseEvent,
    }[kind](event)


def test_a_stroke_shows_while_dragging_and_undoes_in_one_step(viewport):
    from PySide6.QtCore import QEvent, Qt

    from asteria.editor.tile_edit import tile_at

    widget, tilemap, layer = viewport
    widget.tile_tools.mode, widget.tile_tools.selected_tile_id = "paint", 5
    _mouse(widget, QEvent.MouseButtonPress, 8, 8, Qt.LeftButton)
    _mouse(widget, QEvent.MouseMove, 8 + 16 * 4, 8, Qt.LeftButton)
    assert [tile_at(tilemap, layer, x, 0) for x in range(5)] == [5] * 5  # already on the map
    _mouse(widget, QEvent.MouseButtonRelease, 8 + 16 * 4, 8, Qt.LeftButton)
    assert [tile_at(tilemap, layer, x, 0) for x in range(5)] == [5] * 5
    widget.document.undo()
    assert [tile_at(tilemap, layer, x, 0) for x in range(5)] == [EMPTY_TILE] * 5


def test_right_drag_picks_a_block_off_the_map(viewport):
    from PySide6.QtCore import QEvent, Qt

    from asteria.editor.tile_edit import build_assign_command

    widget, tilemap, layer = viewport
    build_assign_command(tilemap, layer, {(0, 0): 1, (1, 0): 2, (0, 1): 3, (1, 1): 4}).redo()
    widget.tile_tools.mode = "paint"
    picked = []
    widget.tilesPicked.connect(picked.append)
    _mouse(widget, QEvent.MouseButtonPress, 4, 4, Qt.RightButton)
    _mouse(widget, QEvent.MouseButtonRelease, 20, 20, Qt.RightButton)
    assert picked == [((1, 2), (3, 4))] and widget.tile_tools.stamp == ((1, 2), (3, 4))


def test_tool_keys_switch_the_tiles_panel(viewport):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    from asteria.editor.tile_palette_widget import TilePaletteWidget

    widget, _tilemap, _layer = viewport
    palette = TilePaletteWidget()
    widget.toolKeyPressed.connect(palette.handle_tool_key)
    modes = []
    palette.modeChanged.connect(modes.append)
    for key in (Qt.Key_G, Qt.Key_R, Qt.Key_E, Qt.Key_B):
        widget.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier))
    assert modes == ["fill", "rectangle", "erase", "paint"] and palette.paint_button.isChecked()
    widget.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_BracketRight, Qt.NoModifier))
    assert palette.brush_spin.value() == 2
