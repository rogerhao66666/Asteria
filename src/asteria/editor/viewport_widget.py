from asteria.core import Transform
from asteria.runtime import Camera2DComponent, SpriteRenderer2D

from .collision_overlay import build_collision_cells
from .commands import CommandTransaction
from .editing import build_set_component_field_command
from .entity_render import (
    build_camera_frames,
    build_entity_sprite_draws,
    camera_world_rect,
)
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
    build_grow_map_command,
    build_paint_command,
    flood_fill_cells,
    line_cells,
    rectangle_cells,
    world_to_tile,
)
from .tile_palette import TileToolState
from .viewport import ViewportCamera, pick_entity, scene_markers, selected_scene

try:
    from PySide6.QtCore import QEvent, QPointF, QRect, Qt, Signal
    from PySide6.QtGui import QBrush, QColor, QPainter, QPen
    from PySide6.QtWidgets import QWidget
except ImportError:
    QWidget = object
    Qt = None
    Signal = None

_ZOOM_STEP = 1.25

# Tiles are authored at 48px (the size RPG Maker MV uses), which is already a
# comfortable cell on a modern display — so the default view shows them 1:1
# rather than magnifying them the way the old 16px tiles needed.
DEFAULT_ZOOM = 1.0

# Cell size for the empty-cell field when no map is loaded to take it from.
_FALLBACK_TILE = 48.0


class SceneViewportWidget(QWidget):
    if Signal is not None:
        zoomChanged = Signal(float)

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
        # Cell under the pointer, and the character waiting to be dropped on
        # it: both drive the placement preview drawn in paintEvent.
        self._hover_cell = None
        self._pending_actor_id = None
        self._reported_zoom = self.camera.zoom
        self._framed_once = False
        self.camera.zoom = DEFAULT_ZOOM
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # The constructor frames the scene before layout has given this
        # widget its real size, which leaves the map parked off-centre.
        # Re-frame once, as soon as there is a real size to centre in.
        if not self._framed_once and self.width() > 1 and self.height() > 1:
            self._framed_once = True
            self.reset_view()

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

    def markers(self):
        scene = self.current_scene()
        markers = scene_markers(scene, self.camera, self._selected_entities())
        if scene is None:
            return markers
        result = []
        for marker in markers:
            rect = camera_world_rect(marker.entity, scene)
            if rect is None:
                result.append(marker)
                continue
            world_x, world_y, _width, _height = rect
            screen_x, screen_y = self.camera.world_to_screen(world_x, world_y)
            result.append(
                type(marker)(
                    marker.entity,
                    world_x,
                    world_y,
                    screen_x,
                    screen_y,
                    marker.radius,
                    marker.selected,
                )
            )
        return tuple(result)

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

    # ---- placement / paint preview -------------------------------------

    def begin_actor_placement(self, actor_id):
        """Arm the pointer with a character; the next map click drops it."""
        self._pending_actor_id = None if actor_id is None else str(actor_id)
        self.setCursor(Qt.CrossCursor if actor_id is not None else Qt.ArrowCursor)
        self.setFocus()
        self.update()
        return True

    def cancel_placement(self):
        if self._pending_actor_id is None:
            return False
        self._pending_actor_id = None
        self.unsetCursor()
        self.update()
        return True

    def _cell_screen_rect(self, cell):
        map_rect = self.map_screen_rect()
        if cell is None or map_rect is None:
            return None
        step_x, step_y = self._cell_size()
        return QRect(
            int(map_rect.left() + cell[0] * step_x),
            int(map_rect.top() + cell[1] * step_y),
            int(step_x),
            int(step_y),
        )

    def _cell_world_position(self, cell):
        """Centre of a tile cell in world units, or None to use the default."""
        source = self.render_source
        if cell is None or source is None:
            return None
        return (
            source.origin_x + (cell[0] + 0.5) * source.tilemap.tile_width,
            source.origin_y + (cell[1] + 0.5) * source.tilemap.tile_height,
        )

    def _frame_image(self, sheet_asset_id, frame_index):
        sheet = self.document.asset_views.sprite_sheet(sheet_asset_id)
        if sheet is None or not sheet.frames:
            return None
        frame = sheet.frames[min(max(0, int(frame_index)), len(sheet.frames) - 1)]
        path = resolve_texture_source(self.document, sheet.texture.asset_id)
        image = self.texture_cache.get(path) if path else None
        if image is None or image.isNull():
            return None
        return image.copy(
            QRect(int(frame.x), int(frame.y), int(frame.width), int(frame.height))
        )

    def _pending_actor_image(self):
        window = self.window()
        appearance = None
        if hasattr(window, "actor_appearance"):
            appearance = window.actor_appearance(self._pending_actor_id)
        if appearance is None:
            return None
        return self._frame_image(
            appearance.sprite_sheet_asset_id, appearance.frame_index
        )

    def _active_tile_image(self):
        """Pixels of the tile the palette is currently set to paint."""
        source = self.render_source
        if source is None or self.tile_tools.mode not in {"paint", "fill", "rectangle"}:
            return None
        tileset = self.document.asset_views.tileset(source.tilemap.tileset.asset_id)
        if tileset is None:
            return None
        tile = tileset.tiles.get(int(self.tile_tools.effective_tile_id))
        if tile is None:
            return None
        return self._frame_image(tileset.sprite_sheet.asset_id, tile.frame_index)

    def _paint_actor_cells(self, painter):
        """Shade the cell each character stands on, the way an event tile reads
        as occupied in RPG Maker — a sprite alone does not say which cell it is
        actually on once it is taller than one tile."""
        from asteria.runtime import ActorLinkComponent

        scene = self.current_scene()
        source = self.render_source
        if scene is None or source is None:
            return
        painter.save()
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(QBrush(QColor(0, 0, 0, 55)))
        for entity in scene.entities():
            if entity.try_get(ActorLinkComponent) is None:
                continue
            transform = entity.try_get(Transform)
            if transform is None:
                continue
            # Character sprites pivot on their feet, so a transform sitting
            # exactly on a cell's bottom edge belongs to the cell above it.
            cell = world_to_tile(
                source.tilemap, transform.x,
                transform.y - source.tilemap.tile_height * 0.25,
                source.origin_x, source.origin_y,
            )
            rect = self._cell_screen_rect(cell)
            if rect is not None:
                painter.drawRect(rect)
        painter.restore()

    def _paint_hover_preview(self, painter):
        rect = self._cell_screen_rect(self._hover_cell)
        if rect is None:
            return
        ghost = (
            self._pending_actor_image()
            if self._pending_actor_id is not None
            else self._active_tile_image()
        )
        # The shaded cell is what makes the drop target unambiguous; the ghost
        # on top says *what* lands there.
        painter.save()
        painter.setOpacity(0.55)
        if ghost is not None:
            if self._pending_actor_id is not None:
                # Characters are taller than one tile and stand on its floor.
                scale = rect.height() / max(1, ghost.height())
                width = max(1, int(ghost.width() * scale * 1.6))
                height = max(1, int(ghost.height() * scale * 1.6))
                target = QRect(
                    rect.left() + (rect.width() - width) // 2,
                    rect.bottom() - height,
                    width,
                    height,
                )
            else:
                target = rect
            painter.drawImage(target, ghost)
        painter.setOpacity(1.0)
        painter.setPen(QPen(QColor(255, 226, 138, 230), 2))
        painter.setBrush(QBrush(QColor(255, 226, 138, 60)))
        painter.drawRect(rect)
        painter.restore()

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

    def reset_view(self):
        if self.frame_game_camera():
            return
        if self.frame_all_entities():
            return
        self.camera.pan_x = 0.0
        self.camera.pan_y = 0.0
        self.camera.zoom = DEFAULT_ZOOM
        self.update()

    def frame_all_entities(self):
        """Center the view on the scene's content — every positioned entity
        plus the tile map's extent — at the default zoom.

        Used when there's no in-scene camera to frame instead — otherwise the
        view falls back to pinning world (0, 0) at the screen's top-left
        corner, which crowds entities placed near the origin into a corner.
        The map extent matters because a map's entity sits at its top-left
        origin, so framing entities alone leaves the map hanging off-centre.
        """
        scene = self.current_scene()
        if scene is None:
            return False
        positions = [
            (transform.x, transform.y)
            for entity in scene.entities()
            if (transform := entity.try_get(Transform)) is not None
        ]
        positions.extend(self._tilemap_corners())
        if not positions:
            return False
        xs = [x for x, _ in positions]
        ys = [y for _, y in positions]
        center_x = (min(xs) + max(xs)) / 2
        center_y = (min(ys) + max(ys)) / 2
        self.camera.zoom = DEFAULT_ZOOM
        self.camera.pan_x = self.width() / 2 - center_x * DEFAULT_ZOOM
        self.camera.pan_y = self.height() / 2 - center_y * DEFAULT_ZOOM
        self.update()
        return True

    def map_world_rect(self):
        """The tile map's own bounds in world units, or None without a map.

        The editable map is a finite sheet like RPG Maker's, not an endless
        plane: the viewport paints a grid only inside these bounds so it is
        obvious where the map you are painting on actually ends.
        """
        corners = self._tilemap_corners()
        if not corners:
            return None
        xs = [x for x, _ in corners]
        ys = [y for _, y in corners]
        return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    def _tilemap_corners(self):
        source = self.render_source
        if source is None:
            return []
        tilemap = source.tilemap
        corners = []
        for layer in tilemap.layers:
            for chunk in layer.chunks.values():
                left = (chunk.chunk_x * tilemap.chunk_width) * tilemap.tile_width
                top = (chunk.chunk_y * tilemap.chunk_height) * tilemap.tile_height
                right = left + chunk.width * tilemap.tile_width
                bottom = top + chunk.height * tilemap.tile_height
                corners.append((source.origin_x + left, source.origin_y + top))
                corners.append((source.origin_x + right, source.origin_y + bottom))
        return corners

    def frame_game_camera(self):
        scene = self.current_scene()
        if scene is None:
            return False
        selected = self._selected_entities()
        candidates = [
            entity
            for entity in selected
            if entity.try_get(Camera2DComponent) is not None
        ]
        if not candidates:
            candidates = [
                entity
                for entity in scene.entities()
                if (spec := entity.try_get(Camera2DComponent)) is not None
                and spec.active
            ]
        if not candidates:
            return False
        entity = candidates[0]
        rect = camera_world_rect(entity, scene)
        if rect is None:
            return False
        world_x, world_y, world_width, world_height = rect
        margin = 32.0
        fit_zoom = min(
            max(1.0, self.width() - margin * 2) / world_width,
            max(1.0, self.height() - margin * 2) / world_height,
        )
        self.camera.zoom = max(
            self.camera.min_zoom, min(self.camera.max_zoom, fit_zoom)
        )
        center_x = world_x + world_width / 2
        center_y = world_y + world_height / 2
        self.camera.pan_x = self.width() / 2 - center_x * self.camera.zoom
        self.camera.pan_y = self.height() / 2 - center_y * self.camera.zoom
        self.update()
        return True

    def zoom_in(self):
        self._zoom_about_center(_ZOOM_STEP)

    def zoom_out(self):
        self._zoom_about_center(1.0 / _ZOOM_STEP)

    def _zoom_about_center(self, factor):
        self.camera.zoom_by(factor, (self.width() / 2, self.height() / 2))
        self.update()

    def pan_view(self, dx, dy):
        self.camera.pan_by(float(dx), float(dy))
        self.update()

    def _build_keyboard_move_command(self, entities, dx, dy):
        transaction = CommandTransaction("Move Entities")
        scene = self.current_scene()
        for entity in entities:
            transform = entity.try_get(Transform)
            if transform is None:
                continue
            base_x = transform.x
            base_y = transform.y
            camera = entity.try_get(Camera2DComponent)
            if camera is not None and camera.follow_entity_id and scene is not None:
                rect = camera_world_rect(entity, scene)
                if rect is not None:
                    base_x, base_y = rect[0], rect[1]
                transaction.add(
                    build_set_component_field_command(camera, "follow_entity_id", "")
                )
            transaction.add(
                build_set_component_field_command(transform, "x", base_x + dx)
            )
            transaction.add(
                build_set_component_field_command(transform, "y", base_y + dy)
            )
        if not transaction.commands:
            raise ValueError("No movable Transform components")
        return transaction

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.cancel_placement():
            event.accept()
            return
        selected = self._selected_entities()
        if selected:
            step = 10.0 if event.modifiers() & Qt.ShiftModifier else 1.0
            movement = {
                Qt.Key_Left: (-step, 0.0),
                Qt.Key_Right: (step, 0.0),
                Qt.Key_Up: (0.0, -step),
                Qt.Key_Down: (0.0, step),
            }.get(event.key())
            if movement is not None:
                try:
                    self.document.execute(
                        self._build_keyboard_move_command(selected, *movement)
                    )
                except ValueError:
                    pass
                window = self.window()
                if hasattr(window, "refresh_all"):
                    window.refresh_all()
                event.accept()
                return
        step = 64.0 if event.modifiers() & Qt.ShiftModifier else 24.0
        movement = {
            Qt.Key_Left: (step, 0.0),
            Qt.Key_Right: (-step, 0.0),
            Qt.Key_Up: (0.0, step),
            Qt.Key_Down: (0.0, -step),
        }.get(event.key())
        if movement is not None:
            self.pan_view(*movement)
            event.accept()
            return
        super().keyPressEvent(event)

    def event(self, event):
        if (
            event.type() == QEvent.NativeGesture
            and event.gestureType() == Qt.ZoomNativeGesture
        ):
            factor = max(0.01, 1.0 + float(event.value()))
            self.camera.zoom_by(factor, (self.width() / 2, self.height() / 2))
            self.update()
            event.accept()
            return True
        return super().event(event)

    def map_screen_rect(self):
        rect = self.map_world_rect()
        if rect is None:
            return None
        world_x, world_y, world_w, world_h = rect
        left, top = self.camera.world_to_screen(world_x, world_y)
        return QRect(
            int(left), int(top),
            int(world_w * self.camera.zoom), int(world_h * self.camera.zoom),
        )

    def _paint_cells(self, cells, tile_id):
        """Paint cells, growing the map first if any fall outside it.

        Painting at or past the edge is how the map grows — by exactly the
        cells painted, not a fixed jump — so the grow and the paint land on
        the undo stack as one step.
        """
        source = self.render_source
        layer = self.tile_tools.active_layer
        if source is None or layer is None:
            return False
        cells = list(cells)
        grow = None
        offset = (0, 0)
        if source.binding is not None:
            try:
                grow, offset = build_grow_map_command(
                    source.tilemap, source.binding, cells
                )
            except TileEditError:
                return False
        try:
            if grow is not None:
                grow.redo()
                cells = [(x + offset[0], y + offset[1]) for x, y in cells]
            paint = build_paint_command(source.tilemap, layer, cells, tile_id)
            paint.redo()
        except (TileEditError, ValueError, IndexError):
            if grow is not None:
                grow.undo()
            return False
        commands = [grow, paint] if grow is not None else [paint]
        self.document.commands.record_applied(
            CommandTransaction(paint.label, commands)
        )
        if grow is not None:
            # The binding origin moved, so the resolved render source is stale.
            window = self.window()
            if hasattr(window, "scene_controller"):
                window.scene_controller._sync_scene_authoring_context()
        return True

    def _cell_size(self):
        source = self.render_source
        tile_w = source.tilemap.tile_width if source is not None else _FALLBACK_TILE
        tile_h = source.tilemap.tile_height if source is not None else _FALLBACK_TILE
        return (
            max(4.0, tile_w * self.camera.zoom),
            max(4.0, tile_h * self.camera.zoom),
        )

    def grid_field_rect(self):
        """Screen rect of the empty-cell field, or None when it cannot fit.

        Trimmed to whole cells inside the pane so the field never spills past
        the visible viewport, and phase-aligned to the map's tile grid so the
        map's border lands on a cell boundary — empty cells read as "more map
        could go here", which is exactly what painting past the edge does.
        """
        step_x, step_y = self._cell_size()
        map_rect = self.map_screen_rect()
        phase_x = map_rect.left() if map_rect is not None else self.camera.pan_x
        phase_y = map_rect.top() if map_rect is not None else self.camera.pan_y
        start_x = phase_x % step_x
        start_y = phase_y % step_y
        width = int((self.width() - start_x) // step_x) * step_x
        height = int((self.height() - start_y) // step_y) * step_y
        if width <= 0 or height <= 0:
            return None
        return QRect(int(start_x), int(start_y), int(width), int(height))

    def _paint_backdrop(self, painter):
        field = self.grid_field_rect()
        map_rect = self.map_screen_rect()
        if field is not None:
            step_x, step_y = self._cell_size()
            painter.setPen(QPen(QColor(44, 47, 53), 1))
            x = float(field.left())
            while x <= field.left() + field.width():
                painter.drawLine(int(x), field.top(), int(x), field.top() + field.height())
                x += step_x
            y = float(field.top())
            while y <= field.top() + field.height():
                painter.drawLine(field.left(), int(y), field.left() + field.width(), int(y))
                y += step_y
        if map_rect is not None:
            painter.fillRect(map_rect, QColor(38, 41, 47))

    def _paint_map_grid(self, painter):
        """Tile grid drawn over the painted map, the way a map editor shows it.

        Under the tiles it would be invisible — a filled map covers it — so
        this runs after the tile draws rather than with the backdrop.
        """
        map_rect = self.map_screen_rect()
        source = self.render_source
        if map_rect is None or source is None:
            return
        step_x, step_y = self._cell_size()
        # Below a few pixels per cell the grid is solid noise, so zoomed-out
        # views get the outline only.
        if min(step_x, step_y) >= 4.0:
            painter.save()
            painter.setClipRect(map_rect)
            painter.setPen(QPen(QColor(255, 255, 255, 28), 1))
            offset = float(map_rect.left())
            while offset <= map_rect.right():
                painter.drawLine(int(offset), map_rect.top(), int(offset), map_rect.bottom())
                offset += step_x
            offset = float(map_rect.top())
            while offset <= map_rect.bottom():
                painter.drawLine(map_rect.left(), int(offset), map_rect.right(), int(offset))
                offset += step_y
            painter.restore()
        painter.setPen(QPen(QColor(120, 128, 142), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(map_rect)

    def paintEvent(self, event):
        # Zoom changes from many paths (wheel, pinch, buttons, reset, framing)
        # and every one of them repaints, so report it here once instead of
        # at each call site.
        if self.camera.zoom != self._reported_zoom:
            self._reported_zoom = self.camera.zoom
            self.zoomChanged.emit(self.camera.zoom)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(24, 26, 30))
        self._paint_backdrop(painter)

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
            self._paint_map_grid(painter)
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

        self._paint_actor_cells(painter)

        sprite_draws = build_entity_sprite_draws(
            self.current_scene(), self.camera, self.document.asset_views.sprite_sheet
        )
        paint_texture_draws(
            painter,
            sprite_draws,
            lambda aid: resolve_texture_source(self.document, aid),
            self.texture_cache,
        )

        self._paint_hover_preview(painter)

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

        if self.map_screen_rect() is None:
            # World-origin crosshair: the only spatial reference a scene
            # without a map has. A map's own border supersedes it.
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
        if self._pending_actor_id is not None and event.button() == Qt.LeftButton:
            actor_id = self._pending_actor_id
            cell = self._screen_to_tile(event.position().x(), event.position().y())
            self.cancel_placement()
            window = self.window()
            controller = getattr(window, "scene_controller", None)
            if controller is not None:
                controller.place_actor(actor_id, self._cell_world_position(cell))
            event.accept()
            return
        if event.button() == Qt.RightButton and self.cancel_placement():
            event.accept()
            return
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
                # Flood fill spreads within what is already there, so it never
                # needs the map to grow — only in-bounds clicks do anything.
                cells = flood_fill_cells(
                    self.render_source.tilemap, self.tile_tools.active_layer, *cell
                )
                self._paint_cells(cells, self.tile_tools.effective_tile_id)
            except (TileEditError, ValueError, IndexError):
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
        # Tracked for every move, so the hovered cell and its ghost follow the
        # pointer whether a character is armed or a tile brush is selected.
        cell = self._screen_to_tile(event.position().x(), event.position().y())
        if cell != self._hover_cell:
            self._hover_cell = cell
            self.update()
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
                self._paint_cells(cells, self.tile_tools.effective_tile_id)
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
                self._paint_cells(
                    self._tile_stroke_cells, self.tile_tools.effective_tile_id
                )
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
        # Trackpad two-finger scroll reports continuous pixelDelta and keeps
        # panning the view (matches the pinch-to-zoom gesture already bound
        # to zoom). A physical mouse wheel only reports discrete angleDelta
        # steps, and scrolling that zooms toward the cursor instead.
        pixel_delta = event.pixelDelta()
        if pixel_delta.x() != 0 or pixel_delta.y() != 0:
            self.camera.pan_by(float(pixel_delta.x()), float(pixel_delta.y()))
            self.update()
            event.accept()
            return
        angle = event.angleDelta()
        if angle.x() == 0 and angle.y() == 0:
            event.accept()
            return
        steps = angle.y() / 120.0
        factor = 1.15 ** steps
        pos = event.position()
        self.camera.zoom_by(factor, (pos.x(), pos.y()))
        self.update()
        event.accept()
