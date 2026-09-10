from asteria.runtime import SpriteRenderer2D

from .collision_overlay import build_collision_cells
from .entity_render import build_camera_frames, build_entity_sprite_draws
from .gizmo import (
    GridSnap,
    SelectionRect,
    build_move_entities_command,
    entities_in_screen_rect,
)
from .qt_texture_renderer import QtTextureCache, paint_texture_draws
from .scene_render import build_scene_texture_draws, resolve_texture_source
from .tile_edit import (
    TileEditError,
    build_paint_command,
    flood_fill_cells,
    line_cells,
    rectangle_cells,
    world_to_tile,
)
from .tile_palette import TileToolState
from .viewport import ViewportCamera, pick_entity, scene_markers, selected_scene

try:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QBrush, QColor, QPainter, QPen
    from PySide6.QtWidgets import QWidget
except ImportError:
    QWidget = object
    Qt = None


class SceneViewportWidget(QWidget):
    def __init__(self, document, parent=None):
        if Qt is None:
            raise RuntimeError("PySide6 is required for SceneViewportWidget")
        super().__init__(parent)
        self.document = document
        self.camera = ViewportCamera()
        self.snap = GridSnap(True, 16.0)
        self.render_source = None
        self.texture_cache = QtTextureCache()
        self.tile_tools = TileToolState()
        self._tile_stroke_cells = []
        self._last_tile_cell = None
        self._tile_rect_start = None
        self._panning = False
        self._last_pos = None
        self._box_start = None
        self._box_end = None
        self._drag_entity = None
        self._drag_start_world = None
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

    def current_scene(self):
        return selected_scene(self.document)

    def _selected_entities(self):
        sel = self.document.selection
        if sel.kind != "entity":
            return ()
        return sel.values or (() if sel.value is None else (sel.value,))

    def markers(self):
        return scene_markers(
            self.current_scene(), self.camera, self._selected_entities()
        )

    def set_render_source(self, source):
        self.render_source = source
        if source is None:
            self.tile_tools.active_layer = None
        elif (
            self.tile_tools.active_layer not in source.tilemap.layers
            and source.tilemap.layers
        ):
            self.tile_tools.active_layer = source.tilemap.ordered_layers()[0]
        self.update()

    def set_tile_mode(self, mode):
        self.tile_tools.set_mode(mode)
        self.update()

    def set_selected_tile(self, tile_id):
        self.tile_tools.selected_tile_id = int(tile_id)

    def set_active_tile_layer(self, layer):
        if (
            self.render_source is not None
            and layer not in self.render_source.tilemap.layers
        ):
            raise ValueError("Layer does not belong to current TileMap")
        self.tile_tools.active_layer = layer
        self.update()

    def _screen_to_tile(self, x, y):
        if self.render_source is None:
            return None
        wx, wy = self.camera.screen_to_world(x, y)
        return world_to_tile(
            self.render_source.tilemap,
            wx,
            wy,
            self.render_source.origin_x,
            self.render_source.origin_y,
        )

    def _append_tile_stroke(self, cell):
        if cell is None:
            return
        if self._last_tile_cell is None:
            new_cells = (cell,)
        else:
            new_cells = line_cells(*self._last_tile_cell, *cell)
        for c in new_cells:
            if c not in self._tile_stroke_cells:
                self._tile_stroke_cells.append(c)
        self._last_tile_cell = cell

    def refresh(self):
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(32, 34, 38))

        spacing = max(8.0, 32.0 * self.camera.zoom)
        ox = self.camera.pan_x % spacing
        oy = self.camera.pan_y % spacing
        painter.setPen(QPen(QColor(52, 55, 61), 1))
        x = ox
        while x < self.width():
            painter.drawLine(int(x), 0, int(x), self.height())
            x += spacing
        y = oy
        while y < self.height():
            painter.drawLine(0, int(y), self.width(), int(y))
            y += spacing

        if self.render_source is not None:
            draws = build_scene_texture_draws(
                self.render_source, self.camera, self.width(), self.height()
            )
            paint_texture_draws(
                painter,
                draws,
                lambda aid: resolve_texture_source(self.document, aid),
                self.texture_cache,
            )
            painter.setPen(QPen(QColor(222, 91, 91, 180), 1))
            painter.setBrush(QBrush(QColor(222, 91, 91, 38)))
            for cell in build_collision_cells(
                self.render_source.tilemap,
                self.camera,
                origin_x=self.render_source.origin_x,
                origin_y=self.render_source.origin_y,
            ):
                painter.drawRect(
                    int(cell.screen_x),
                    int(cell.screen_y),
                    int(cell.width),
                    int(cell.height),
                )

        sprite_draws = build_entity_sprite_draws(
            self.current_scene(), self.camera, self.document.asset_views.sprite_sheet
        )
        paint_texture_draws(
            painter,
            sprite_draws,
            lambda aid: resolve_texture_source(self.document, aid),
            self.texture_cache,
        )

        for frame in build_camera_frames(self.current_scene(), self.camera):
            color = (
                QColor(92, 181, 122, 210)
                if frame.active
                else QColor(120, 132, 160, 160)
            )
            painter.setPen(QPen(color, 2 if frame.active else 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(
                int(frame.screen_x),
                int(frame.screen_y),
                int(frame.width),
                int(frame.height),
            )
            if frame.deadzone is not None:
                x, y, w, h = frame.deadzone
                painter.setPen(QPen(QColor(92, 181, 122, 130), 1, Qt.DotLine))
                painter.drawRect(int(x), int(y), int(w), int(h))

        painter.setPen(QPen(QColor(70, 74, 82), 1))
        painter.drawLine(
            int(self.camera.pan_x), 0, int(self.camera.pan_x), self.height()
        )
        painter.drawLine(
            0, int(self.camera.pan_y), self.width(), int(self.camera.pan_y)
        )

        markers = self.markers()
        for m in markers:
            renderer = m.entity.try_get(SpriteRenderer2D)
            has_sprite = (
                renderer is not None
                and renderer.visible
                and self.document.asset_views.sprite_sheet(
                    renderer.sprite_sheet_asset_id
                )
                is not None
            )
            if has_sprite and not m.selected:
                continue
            if m.selected:
                painter.setPen(QPen(QColor(255, 196, 64), 2))
                painter.setBrush(QBrush(QColor(255, 196, 64, 80)))
            else:
                painter.setPen(QPen(QColor(190, 196, 210), 1))
                painter.setBrush(QBrush(QColor(120, 132, 160, 90)))
            painter.drawEllipse(QPointF(m.screen_x, m.screen_y), m.radius, m.radius)
            painter.drawText(
                int(m.screen_x + m.radius + 3), int(m.screen_y - 3), m.entity.name
            )

        if self._box_start is not None and self._box_end is not None:
            x1, y1 = self._box_start.x(), self._box_start.y()
            x2, y2 = self._box_end.x(), self._box_end.y()
            painter.setPen(QPen(QColor(100, 145, 195), 1))
            painter.setBrush(QBrush(QColor(100, 145, 195, 35)))
            painter.drawRect(
                int(min(x1, x2)), int(min(y1, y2)), int(abs(x2 - x1)), int(abs(y2 - y1))
            )

        selected = [m for m in markers if m.selected]
        if selected:
            m = selected[0]
            painter.setPen(QPen(QColor(215, 220, 228), 1))
            painter.drawEllipse(QPointF(m.screen_x, m.screen_y), 3, 3)
            painter.setPen(QPen(QColor(211, 91, 91), 2))
            painter.drawLine(
                int(m.screen_x), int(m.screen_y), int(m.screen_x + 34), int(m.screen_y)
            )
            painter.setPen(QPen(QColor(92, 181, 122), 2))
            painter.drawLine(
                int(m.screen_x), int(m.screen_y), int(m.screen_x), int(m.screen_y - 34)
            )
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton or (
            event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier
        ):
            self._panning = True
            self._last_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        if (
            event.button() == Qt.LeftButton
            and self.render_source is not None
            and self.tile_tools.mode == "fill"
        ):
            if self.tile_tools.active_layer is None:
                event.accept()
                return
            cell = self._screen_to_tile(event.position().x(), event.position().y())
            try:
                cells = flood_fill_cells(
                    self.render_source.tilemap, self.tile_tools.active_layer, *cell
                )
                self.document.execute(
                    build_paint_command(
                        self.render_source.tilemap,
                        self.tile_tools.active_layer,
                        cells,
                        self.tile_tools.effective_tile_id,
                    )
                )
            except (TileEditError, ValueError):
                pass
            window = self.window()
            if hasattr(window, "refresh_all"):
                window.refresh_all()
            event.accept()
            return

        if (
            event.button() == Qt.LeftButton
            and self.render_source is not None
            and self.tile_tools.mode == "rectangle"
        ):
            if self.tile_tools.active_layer is None:
                event.accept()
                return
            self._tile_rect_start = self._screen_to_tile(
                event.position().x(), event.position().y()
            )
            event.accept()
            return

        if (
            event.button() == Qt.LeftButton
            and self.render_source is not None
            and self.tile_tools.mode in {"paint", "erase"}
        ):
            if self.tile_tools.active_layer is None:
                event.accept()
                return
            self._tile_stroke_cells = []
            self._last_tile_cell = None
            self._append_tile_stroke(
                self._screen_to_tile(event.position().x(), event.position().y())
            )
            self.update()
            event.accept()
            return

        if event.button() == Qt.LeftButton:
            entity = pick_entity(
                self.markers(), event.position().x(), event.position().y()
            )
            if entity is not None:
                if event.modifiers() & Qt.ControlModifier:
                    current = list(self._selected_entities())
                    if entity in current:
                        current.remove(entity)
                    else:
                        current.append(entity)
                    self.document.select_many("entity", current)
                elif entity not in self._selected_entities():
                    self.document.selection.set_single("entity", entity)
                self._drag_entity = entity
                self._drag_start_world = self.camera.screen_to_world(
                    event.position().x(), event.position().y()
                )
                window = self.window()
                if hasattr(window, "refresh_all"):
                    window.refresh_all()
                event.accept()
                return
            self._box_start = event.position()
            self._box_end = event.position()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._last_pos is not None:
            pos = event.position()
            delta = pos - self._last_pos
            self.camera.pan_by(delta.x(), delta.y())
            self._last_pos = pos
            self.update()
            event.accept()
            return
        if self._tile_stroke_cells and self.tile_tools.mode in {"paint", "erase"}:
            self._append_tile_stroke(
                self._screen_to_tile(event.position().x(), event.position().y())
            )
            self.update()
            event.accept()
            return
        if self._drag_entity is not None:
            self.update()
            event.accept()
            return
        if self._box_start is not None:
            self._box_end = event.position()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning:
            self._panning = False
            self._last_pos = None
            self.unsetCursor()
            event.accept()
            return
        if (
            event.button() == Qt.LeftButton
            and self._tile_rect_start is not None
            and self.render_source is not None
        ):
            end = self._screen_to_tile(event.position().x(), event.position().y())
            try:
                cells = rectangle_cells(*self._tile_rect_start, *end)
                self.document.execute(
                    build_paint_command(
                        self.render_source.tilemap,
                        self.tile_tools.active_layer,
                        cells,
                        self.tile_tools.effective_tile_id,
                    )
                )
            except (TileEditError, ValueError):
                pass
            self._tile_rect_start = None
            window = self.window()
            if hasattr(window, "refresh_all"):
                window.refresh_all()
            event.accept()
            return

        if (
            event.button() == Qt.LeftButton
            and self._tile_stroke_cells
            and self.render_source is not None
        ):
            try:
                command = build_paint_command(
                    self.render_source.tilemap,
                    self.tile_tools.active_layer,
                    self._tile_stroke_cells,
                    self.tile_tools.effective_tile_id,
                )
                self.document.execute(command)
            except (TileEditError, ValueError):
                pass
            self._tile_stroke_cells = []
            self._last_tile_cell = None
            window = self.window()
            if hasattr(window, "refresh_all"):
                window.refresh_all()
            event.accept()
            return

        if (
            event.button() == Qt.LeftButton
            and self._drag_entity is not None
            and self._drag_start_world is not None
        ):
            end = self.camera.screen_to_world(
                event.position().x(), event.position().y()
            )
            dx = end[0] - self._drag_start_world[0]
            dy = end[1] - self._drag_start_world[1]
            entities = self._selected_entities() or (self._drag_entity,)
            try:
                self.document.execute(
                    build_move_entities_command(entities, dx, dy, self.snap)
                )
            except ValueError:
                pass
            self._drag_entity = None
            self._drag_start_world = None
            window = self.window()
            if hasattr(window, "refresh_all"):
                window.refresh_all()
            event.accept()
            return
        if event.button() == Qt.LeftButton and self._box_start is not None:
            end = self._box_end or event.position()
            rect = SelectionRect(
                self._box_start.x(), self._box_start.y(), end.x(), end.y()
            )
            self.document.select_many(
                "entity", entities_in_screen_rect(self.markers(), rect)
            )
            self._box_start = None
            self._box_end = None
            window = self.window()
            if hasattr(window, "refresh_all"):
                window.refresh_all()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        pos = event.position()
        self.camera.zoom_by(factor, (pos.x(), pos.y()))
        self.update()
        event.accept()
