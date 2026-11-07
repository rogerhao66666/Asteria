"""``SceneViewportWidget``: the editor's map canvas. This module builds it (its signals, state
and the skeleton timer); what it does lives in its mixins - ``viewport_tiles`` (tile tools and
placing characters), ``viewport_framing`` (where the view looks), ``viewport_painting``
(``paintEvent``) and ``viewport_input`` (keys, mouse, wheel)."""

from __future__ import annotations

from asteria.editor.assets.qt_texture_renderer import QtTextureCache
from asteria.editor.scene.gizmo import GridSnap
from asteria.editor.scene.tile_palette import TileToolState
from asteria.editor.scene.viewport import ViewportCamera, selected_scene
from asteria.editor.scene.viewport_framing import ViewportFramingMixin
from asteria.editor.scene.viewport_input import ViewportInputMixin
from asteria.editor.scene.viewport_painting import ViewportPaintingMixin
from asteria.editor.scene.viewport_tiles import ViewportTilesMixin
from asteria.runtime import SkeletonSceneRuntime

try:
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtWidgets import QWidget
except ImportError:
    QWidget = object
    Qt = None
    Signal = None


class SceneViewportWidget(
    ViewportTilesMixin, ViewportFramingMixin, ViewportPaintingMixin, ViewportInputMixin, QWidget
):
    # hit / hurt boxes (where a real-time attack reaches, where a body can be hit) are a debug
    # view: off unless View > Show Hit && Hurt Boxes turns them on
    show_combat_boxes = False

    if Signal is not None:
        characterCellClicked = Signal(tuple)
        # rows of tile ids picked off the map with the right mouse button (the eyedropper)
        tilesPicked = Signal(object)
        # a tool key (B / G / R / E / S, [ and ]) pressed over the map
        toolKeyPressed = Signal(str)
        # N over the map, or the tool strip's character button: place a character
        characterToolRequested = Signal()
        # Escape while a character waits to be placed
        placementCancelled = Signal()

    def __init__(self, document, parent=None):
        if Qt is None:
            raise RuntimeError("PySide6 is required for SceneViewportWidget")
        super().__init__(parent)
        self.document = document
        self.camera = ViewportCamera()
        self.snap = GridSnap(True, 16.0)
        self.render_source = None
        self.texture_cache = QtTextureCache()
        self.skeleton_runtime = SkeletonSceneRuntime()
        self._skeleton_scene_id = None
        self._skeleton_timer = QTimer(self)
        self._skeleton_timer.setInterval(33)
        self._skeleton_timer.timeout.connect(self._advance_skeletons)
        self.tile_tools = TileToolState()
        self._tile_stroke_cells = []
        self._tile_stroke_seen = set()  # the stroke's cells again, for O(1) membership
        self._last_tile_cell = None
        self._tile_rect_start = None
        self._panning = False
        self._last_pos = None
        self._box_start = None
        self._box_end = None
        self._drag_entity = None
        self._drag_start_world = None
        self.character_placement_active = False
        self._placement_ghost = None  # the character's picture, carried under the mouse
        self._placement_cell = None
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

    def current_scene(self):
        return selected_scene(self.document)

    def _selected_entities(self):
        sel = self.document.selection
        if sel.kind == "entity":
            return sel.values or (() if sel.value is None else (sel.value,))
        if sel.kind == "component" and sel.value is not None:
            entity = getattr(sel.value, "entity", None)
            return () if entity is None else (entity,)
        return ()

    def set_render_source(self, source):
        self.render_source = source
        if source is None:
            self.tile_tools.active_layer = None
            self.tile_tools.tileset = None
        elif self.tile_tools.active_layer not in source.tilemap.layers and source.tilemap.layers:
            self.tile_tools.active_layer = source.tilemap.ordered_layers()[0]
        if source is not None:
            self.tile_tools.tileset = getattr(source, "tileset", None)
        self.update()

    TOOL_KEYS = (
        {
            Qt.Key_B: "paint",
            Qt.Key_G: "fill",
            Qt.Key_R: "rectangle",
            Qt.Key_E: "erase",
            Qt.Key_S: "select",
            Qt.Key_BracketLeft: "smaller",
            Qt.Key_BracketRight: "bigger",
        }
        if Qt is not None
        else {}
    )

    WHEEL_ZOOM_STEP = 1.15  # zoom factor of one notch of a mouse wheel
