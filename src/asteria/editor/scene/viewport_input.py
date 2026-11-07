"""The scene view's keys, mouse and wheel: moving the chosen objects with the arrows, selecting,
dragging, painting with the mouse, and zooming."""

from __future__ import annotations

import os

from asteria.core import Transform
from asteria.editor.project.commands import CommandTransaction
from asteria.editor.project.editing import build_set_component_field_command
from asteria.editor.scene.entity_render import camera_world_rect
from asteria.editor.scene.gizmo import (
    SelectionRect,
    build_move_entities_command,
    entities_in_screen_rect,
)
from asteria.editor.scene.tile_edit import (
    TileEditError,
    build_assign_command,
    flood_fill_cells,
    rectangle_cells,
)
from asteria.editor.scene.tile_palette import STROKE_MODES
from asteria.editor.scene.viewport import pick_entity
from asteria.runtime import Camera2DComponent

try:
    from PySide6.QtCore import QEvent, Qt, Signal
except ImportError:
    Qt = None
    Signal = None


class ViewportInputMixin:
    """``SceneViewportWidget``'s key, mouse and wheel events."""

    # defaults until something sets them (code may read them first)
    _pick_start = None

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
                transaction.add(build_set_component_field_command(camera, "follow_entity_id", ""))
            transaction.add(build_set_component_field_command(transform, "x", base_x + dx))
            transaction.add(build_set_component_field_command(transform, "y", base_y + dy))
        if not transaction.commands:
            raise ValueError("No movable Transform components")
        return transaction

    def keyPressEvent(self, event):
        if self.character_placement_active and event.key() == Qt.Key_Escape:
            self.placementCancelled.emit()
            event.accept()
            return
        if event.key() == Qt.Key_N and not event.modifiers() & ~Qt.KeypadModifier:
            self.characterToolRequested.emit()
            event.accept()
            return
        tool = self.TOOL_KEYS.get(event.key())
        if tool and not event.modifiers() & ~Qt.KeypadModifier and self.render_source is not None:
            self.toolKeyPressed.emit(tool)  # the Tiles panel switches tool / brush size
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
                    self.document.execute(self._build_keyboard_move_command(selected, *movement))
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
        if event.type() == QEvent.NativeGesture and event.gestureType() == Qt.ZoomNativeGesture:
            factor = max(0.01, 1.0 + float(event.value()))
            self.camera.zoom_by(factor, (self.width() / 2, self.height() / 2))
            self.update()
            event.accept()
            return True
        return super().event(event)

    def mousePressEvent(self, event):
        if (
            event.button() == Qt.RightButton
            and self.render_source is not None
            and self.tile_tools.mode in {"paint", "erase", "fill", "rectangle"}
        ):
            # right button: the eyedropper (drag for a block of tiles)
            self._pick_start = self._screen_to_tile(event.position().x(), event.position().y())
            event.accept()
            return
        if (
            event.button() == Qt.LeftButton
            and self.tile_tools.mode == "doodad"
            and not event.modifiers() & Qt.AltModifier
        ):
            self._place_doodad(event.position().x(), event.position().y())
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
        if event.button() == Qt.LeftButton and self.character_placement_active:
            self.characterCellClicked.emit(
                self.cell_at_screen(event.position().x(), event.position().y())
            )
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
                self.document.execute(  # a stamp repeats from the clicked cell
                    build_assign_command(
                        self.render_source.tilemap,
                        self.tile_tools.active_layer,
                        self.tile_tools.assignments(cells, origin=cell),
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
            and self.tile_tools.mode in STROKE_MODES
        ):
            if self.tile_tools.active_layer is None and self.tile_tools.mode != "region":
                event.accept()
                return
            self._tile_stroke_cells = []
            self._tile_stroke_seen = set()
            self._last_tile_cell = None
            self._append_tile_stroke(
                self._screen_to_tile(event.position().x(), event.position().y())
            )
            self.update()
            event.accept()
            return

        if event.button() == Qt.LeftButton:
            entity = pick_entity(self.markers(), event.position().x(), event.position().y())
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
        if self.character_placement_active:
            self._placement_cell = self.cell_at_screen(event.position().x(), event.position().y())
            self.update()
        if self._tile_stroke_cells and self.tile_tools.mode in STROKE_MODES:
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
        if event.button() == Qt.RightButton and self._pick_start is not None:
            end = self._screen_to_tile(event.position().x(), event.position().y())
            self._pick_tiles(self._pick_start, end)
            self._pick_start = None
            if self.tile_tools.mode == "erase" and Signal is not None:
                self.toolKeyPressed.emit("paint")  # a picked tile is for painting
            self.update()
            event.accept()
            return
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
                corner = (min(c[0] for c in cells), min(c[1] for c in cells))
                self.document.execute(  # a stamp repeats from the rectangle's corner
                    build_assign_command(
                        self.render_source.tilemap,
                        self.tile_tools.active_layer,
                        self.tile_tools.assignments(cells, origin=corner),
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
            self._undo_live()  # the live preview goes; the stroke comes back as one undo step
            try:
                command = self.tile_tools.build_command(
                    self.render_source.tilemap, self._tile_stroke_cells
                )
                self.document.execute(command)
            except (TileEditError, ValueError):
                pass
            self._tile_stroke_cells = []
            self._tile_stroke_seen = set()
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
            end = self.camera.screen_to_world(event.position().x(), event.position().y())
            dx = end[0] - self._drag_start_world[0]
            dy = end[1] - self._drag_start_world[1]
            entities = self._selected_entities() or (self._drag_entity,)
            try:
                self.document.execute(build_move_entities_command(entities, dx, dy, self.snap))
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
            rect = SelectionRect(self._box_start.x(), self._box_start.y(), end.x(), end.y())
            self.document.select_many("entity", entities_in_screen_rect(self.markers(), rect))
            self._box_start = None
            self._box_end = None
            window = self.window()
            if hasattr(window, "refresh_all"):
                window.refresh_all()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    @staticmethod
    def is_mouse_wheel(event):
        """True for a mouse wheel, false for a trackpad. A trackpad (and a Magic Mouse) always
        reports a scroll phase - begin, update, end, momentum; a wheel reports none, even when it
        is a smooth-scrolling mouse that also sends pixel deltas."""
        return event.phase() == Qt.NoScrollPhase

    def wheelEvent(self, event):
        angle = event.angleDelta()
        if os.environ.get("ASTERIA_DEBUG_WHEEL"):  # what a device really sends
            print(
                "wheel",
                f"pixel={event.pixelDelta().x()},{event.pixelDelta().y()}",
                f"angle={angle.x()},{angle.y()}",
                f"phase={event.phase()}",
                f"source={event.source()}",
                f"inverted={event.inverted()}",
                f"-> {'zoom' if self.is_mouse_wheel(event) else 'pan'}",
                flush=True,
            )
        if self.is_mouse_wheel(event):
            # a mouse wheel zooms around the cursor (forward = zoom in, whatever the system's
            # natural-scrolling setting); the arrow keys pan, the trackpad scrolls
            notches = float(angle.y()) / 120.0
            if event.inverted():
                notches = -notches
            if notches == 0:
                event.accept()
                return
            position = event.position()
            self.camera.zoom_by(
                self.WHEEL_ZOOM_STEP**notches, (float(position.x()), float(position.y()))
            )
            self.update()
            event.accept()
            return
        delta = event.pixelDelta()
        dx = float(delta.x())
        dy = float(delta.y())
        if dx == 0 and dy == 0:
            dx = float(angle.x()) / 120.0 * 48.0
            dy = float(angle.y()) / 120.0 * 48.0
        if dx == 0 and dy == 0:
            event.accept()
            return
        self.camera.pan_by(dx, dy)
        self.update()
        event.accept()
