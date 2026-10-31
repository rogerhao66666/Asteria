import os
from math import floor

from asteria.core import Transform, world_position
from asteria.runtime import (
    Camera2DComponent,
    SkeletonAnimation2DComponent,
    SkeletonSceneRuntime,
    SpriteRenderer2D,
)

from .collision_overlay import build_collision_cells, build_combat_boxes
from .commands import CommandTransaction
from .editing import build_set_component_field_command
from .entity_kinds import kind_of
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
    build_assign_command,
    flood_fill_cells,
    line_cells,
    rectangle_cells,
    world_to_tile,
)
from .tile_palette import STROKE_MODES, TileToolState
from .viewport import ViewportCamera, pick_entity, scene_markers, selected_scene

try:
    from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
    from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
    from PySide6.QtWidgets import QWidget
except ImportError:
    QWidget = object
    Qt = None
    Signal = None


def shown_combat_boxes(boxes, *, hit_and_hurt=False):
    """The boxes the scene view draws: what blocks always, hit / hurt boxes only when asked."""
    return tuple(b for b in boxes if hit_and_hurt or b.kind not in ("hurtbox", "hitbox"))


class SceneViewportWidget(QWidget):
    # hit / hurt boxes (where a real-time attack reaches, where a body can be hit) are a debug
    # view: off unless View > Show Hit && Hurt Boxes turns them on
    show_combat_boxes = False

    if Signal is not None:
        characterCellClicked = Signal(tuple)
        # rows of tile ids picked off the map with the right mouse button (the eyedropper)
        tilesPicked = Signal(object)
        # a tool key (B / G / R / E / S, [ and ]) pressed over the map
        toolKeyPressed = Signal(str)

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

    def _paint_skeletons(self, painter):
        scene = self.current_scene()
        has_rigs = scene is not None and any(
            entity.try_get(SkeletonAnimation2DComponent) is not None for entity in scene.entities()
        )
        if not has_rigs:
            self._skeleton_timer.stop()
            return
        if scene.id != self._skeleton_scene_id:
            self.skeleton_runtime = SkeletonSceneRuntime()
            self._skeleton_scene_id = scene.id
        if not self._skeleton_timer.isActive():
            self._skeleton_timer.start()
        draws = self.skeleton_runtime.draw_commands(
            scene, self.camera, self.document.asset_views.sprite_sheet
        )
        paint_texture_draws(
            painter,
            draws,
            lambda asset_id: resolve_texture_source(self.document, asset_id),
            self.texture_cache,
        )

    def _advance_skeletons(self):
        scene = self.current_scene()
        if scene is None:
            self._skeleton_timer.stop()
            return
        self.skeleton_runtime.update(scene, self._skeleton_timer.interval() / 1000.0)
        self.update()

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
            self.tile_tools.tileset = None
        elif self.tile_tools.active_layer not in source.tilemap.layers and source.tilemap.layers:
            self.tile_tools.active_layer = source.tilemap.ordered_layers()[0]
        if source is not None:
            self.tile_tools.tileset = getattr(source, "tileset", None)
        self.update()

    def set_tile_mode(self, mode):
        self.tile_tools.set_mode(mode)
        self.update()

    def set_terrain(self, terrain_id):
        self.tile_tools.terrain_id = terrain_id or None

    def set_region(self, region_id, erase=False):
        self.tile_tools.region_id = int(region_id)
        self.tile_tools.region_erase = bool(erase)
        self.update()

    def set_region_layer_name(self, layer_name):
        self.tile_tools.region_layer_name = str(layer_name or "regions")
        self.update()

    def set_doodad(self, definition):
        self.tile_tools.doodad = definition

    def set_selected_tile(self, tile_id):
        self.tile_tools.selected_tile_id = int(tile_id)

    def set_active_tile_layer(self, layer):
        if self.render_source is not None and layer not in self.render_source.tilemap.layers:
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

    def cell_at_screen(self, x, y):
        """Resolve a clicked scene position into the canonical 48px RPG cell."""
        if self.render_source is not None:
            return self._screen_to_tile(x, y)
        world_x, world_y = self.camera.screen_to_world(x, y)
        return (floor(world_x / 48), floor(world_y / 48))

    def begin_character_placement(self):
        self.character_placement_active = True
        self.setCursor(Qt.CrossCursor)

    def end_character_placement(self):
        self.character_placement_active = False
        self.unsetCursor()

    def _append_tile_stroke(self, cell):
        if cell is None:
            return
        if self._last_tile_cell is None:
            new_cells = (cell,)
        else:
            new_cells = line_cells(*self._last_tile_cell, *cell)
        added = []
        for c in new_cells:
            if c not in self._tile_stroke_seen:
                self._tile_stroke_seen.add(c)
                self._tile_stroke_cells.append(c)
                added.append(c)
        self._last_tile_cell = cell
        self._paint_live(added)

    def _paint_live(self, cells):
        """Paint / Erase show on the map while the mouse is still down; the stroke becomes one
        undo step when it is let go (``_undo_live`` first puts the cells back)."""
        tools, source = self.tile_tools, self.render_source
        if not cells or source is None or tools.active_layer is None:
            return
        if tools.mode not in {"paint", "erase"}:
            return
        from .tile_edit import SetTileCommand, tile_at

        try:
            wanted = tools.assignments(cells, origin=self._tile_stroke_cells[0])
        except ValueError:
            return
        live = self.__dict__.setdefault("_live_tiles", {})
        for (x, y), tile_id in wanted.items():
            if x < 0 or y < 0:
                continue
            if (x, y) not in live:
                live[(x, y)] = tile_at(source.tilemap, tools.active_layer, x, y)
            SetTileCommand(source.tilemap, tools.active_layer, x, y, int(tile_id)).redo()

    def _undo_live(self):
        from .tile_edit import SetTileCommand

        live = self.__dict__.pop("_live_tiles", {})
        source, layer = self.render_source, self.tile_tools.active_layer
        if source is None or layer is None:
            return
        for (x, y), old in live.items():
            if layer in source.tilemap.layers:
                SetTileCommand(source.tilemap, layer, x, y, int(old)).redo()

    def _pick_tiles(self, start, end):
        """The eyedropper: the tiles of the active layer (else the topmost one that has a tile)
        between two cells become the brush."""
        from asteria.graphics import EMPTY_TILE

        from .tile_edit import tile_at

        source = self.render_source
        if source is None or start is None or end is None:
            return None
        layers = list(source.tilemap.ordered_layers())[::-1]
        active = self.tile_tools.active_layer
        x0, x1 = sorted((start[0], end[0]))
        y0, y1 = sorted((start[1], end[1]))

        def pick(x, y):
            if active is not None and tile_at(source.tilemap, active, x, y) != EMPTY_TILE:
                return tile_at(source.tilemap, active, x, y)
            for layer in layers:
                tile = tile_at(source.tilemap, layer, x, y)
                if tile != EMPTY_TILE:
                    return tile
            return EMPTY_TILE

        rows = tuple(tuple(pick(x, y) for x in range(x0, x1 + 1)) for y in range(y0, y1 + 1))
        if all(t == EMPTY_TILE for row in rows for t in row):
            return None
        self.tile_tools.set_stamp(rows)
        if Signal is not None:
            self.tilesPicked.emit(rows)
        return rows

    def refresh(self):
        self.update()

    def reset_view(self):
        if self.frame_initial():
            return
        self.camera.pan_x = 0.0
        self.camera.pan_y = 0.0
        self.camera.zoom = 1.0
        self.update()

    def frame_initial(self):
        """The view a scene opens with: the active game camera's frame, else every entity."""
        if self.frame_game_camera(context=0.4):
            self._keep_map_in_view()
            return True
        return self.frame_entities()

    def _map_rect(self):
        """World rectangle the scene's tile map covers, or None without one."""
        source = getattr(self, "render_source", None)
        tilemap = getattr(source, "tilemap", None)
        if tilemap is None:
            return None
        cells = [
            (cx, cy)
            for layer in tilemap.layers
            for (cx, cy), chunk in layer.chunks.items()
            if any(t >= 0 for t in chunk.tiles)
        ]
        if not cells:
            return None
        width, height = (
            tilemap.chunk_width * tilemap.tile_width,
            tilemap.chunk_height * (tilemap.tile_height),
        )
        left = source.origin_x + min(c[0] for c in cells) * width
        top = source.origin_y + min(c[1] for c in cells) * height
        right = source.origin_x + (max(c[0] for c in cells) + 1) * width
        bottom = source.origin_y + (max(c[1] for c in cells) + 1) * height
        return left, top, right, bottom

    def _keep_map_in_view(self):
        """Slide the opening view so it shows map, not the empty void beside it (where the map
        is large enough to fill the view)."""
        rect = self._map_rect()
        if rect is None:
            return
        zoom = self.camera.zoom
        for axis, size in (("pan_x", self.width()), ("pan_y", self.height())):
            low, high = (rect[0], rect[2]) if axis == "pan_x" else (rect[1], rect[3])
            if (high - low) * zoom < size:
                continue
            pan = getattr(self.camera, axis)
            pan = min(-low * zoom, max(size - high * zoom, pan))
            setattr(self.camera, axis, pan)
        self.update()

    def frame_entities(self):
        """Centre the view on all the scene's entities (zoomed out to fit when they spread wider
        than the view, never zoomed in past 1.5x). False when the scene has none."""
        scene = self.current_scene()
        if scene is None:
            return False
        points = [world_position(e) for e in scene.entities() if e.try_get(Transform) is not None]
        if not points:
            return False
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
        margin = 64.0
        fit = min(
            max(1.0, self.width() - margin * 2) / max(span_x, 1.0),
            max(1.0, self.height() - margin * 2) / max(span_y, 1.0),
        )
        zoom = 1.0 if len(points) == 1 else min(1.5, fit)
        self.camera.zoom = max(self.camera.min_zoom, min(self.camera.max_zoom, zoom))
        self.camera.pan_x = self.width() / 2 - (min(xs) + max(xs)) / 2 * self.camera.zoom
        self.camera.pan_y = self.height() / 2 - (min(ys) + max(ys)) / 2 * self.camera.zoom
        self._framed = (self.camera.pan_x, self.camera.pan_y, self.camera.zoom, self.width())
        self.update()
        return True

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        framed = getattr(self, "_framed", None)
        if framed is not None and (
            (self.camera.pan_x, self.camera.pan_y, self.camera.zoom) == framed[:3]
        ):  # the view still shows what framing chose (nobody panned or zoomed): keep it centred
            self.frame_entities()

    def frame_game_camera(self, context=1.0):
        """Fit the active game camera's frame; ``context`` < 1 leaves room around it (a scene
        opens showing the frame at about that share of the view, the map around it visible)."""
        scene = self.current_scene()
        if scene is None:
            return False
        selected = self._selected_entities()
        candidates = [
            entity for entity in selected if entity.try_get(Camera2DComponent) is not None
        ]
        if not candidates:
            candidates = [
                entity
                for entity in scene.entities()
                if (spec := entity.try_get(Camera2DComponent)) is not None and spec.active
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
        fit_zoom *= max(0.1, float(context))
        self.camera.zoom = max(self.camera.min_zoom, min(self.camera.max_zoom, fit_zoom))
        center_x = world_x + world_width / 2
        center_y = world_y + world_height / 2
        self.camera.pan_x = self.width() / 2 - center_x * self.camera.zoom
        self.camera.pan_y = self.height() / 2 - center_y * self.camera.zoom
        self.update()
        return True

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
                transaction.add(build_set_component_field_command(camera, "follow_entity_id", ""))
            transaction.add(build_set_component_field_command(transform, "x", base_x + dx))
            transaction.add(build_set_component_field_command(transform, "y", base_y + dy))
        if not transaction.commands:
            raise ValueError("No movable Transform components")
        return transaction

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

    def keyPressEvent(self, event):
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

    def _paint_name_pill(self, painter, marker, tint):
        """The entity's name in a pill of its kind's colour beside its marker: the same colour
        the project tree and the Inspector give it, so what it is reads at a glance."""
        metrics = painter.fontMetrics()
        text = marker.entity.name
        width = metrics.horizontalAdvance(text) + 14
        height = metrics.height() + 4
        x = marker.screen_x + marker.radius + 5
        y = marker.screen_y - height / 2
        # names of entities standing together step down instead of writing over each other
        pill = QRectF(x, y, width, height)
        for _ in range(8):
            if not any(pill.intersects(other) for other in self._pill_rects):
                break
            pill.translate(0, height + 2)
        self._pill_rects.append(pill)
        x, y = pill.x(), pill.y()
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(QColor(255, 255, 255), 1.5) if marker.selected else Qt.NoPen)
        painter.setBrush(QBrush(QColor(tint.red(), tint.green(), tint.blue(), 235)))
        painter.drawRoundedRect(QRectF(x, y, width, height), height / 2, height / 2)
        painter.setPen(QPen(QColor(20, 21, 26), 1))
        painter.drawText(
            QRectF(x + 7, y, width - 14, height), Qt.AlignVCenter | Qt.AlignLeft, text
        )
        painter.restore()

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
                viewport_width=self.width(),
                viewport_height=self.height(),
            ):
                painter.drawRect(
                    int(cell.screen_x),
                    int(cell.screen_y),
                    int(cell.width),
                    int(cell.height),
                )

        if self.render_source is not None and self.tile_tools.mode == "region":
            self._paint_region_overlay(painter)

        sprite_draws = build_entity_sprite_draws(
            self.current_scene(), self.camera, self.document.asset_views.sprite_sheet
        )
        paint_texture_draws(
            painter,
            sprite_draws,
            lambda aid: resolve_texture_source(self.document, aid),
            self.texture_cache,
        )
        self._paint_skeletons(painter)

        # D22 A9: what blocks (colliders, slopes, ladders), what can be hit and what hits
        styles = {
            "solid": (QColor(150, 162, 196, 200), QColor(150, 162, 196, 40), Qt.SolidLine),
            "one_way": (QColor(212, 176, 110, 220), QColor(212, 176, 110, 40), Qt.DashLine),
            "slope_right": (QColor(150, 162, 196, 200), QColor(150, 162, 196, 60), Qt.SolidLine),
            "slope_left": (QColor(150, 162, 196, 200), QColor(150, 162, 196, 60), Qt.SolidLine),
            "ladder": (QColor(200, 150, 90, 220), QColor(200, 150, 90, 30), Qt.DotLine),
            "trigger": (QColor(120, 200, 220, 160), QColor(120, 200, 220, 20), Qt.DotLine),
            "hurtbox": (QColor(92, 181, 122, 210), QColor(92, 181, 122, 30), Qt.SolidLine),
            "hitbox": (QColor(222, 91, 91, 230), QColor(222, 91, 91, 45), Qt.DashLine),
        }
        boxes = build_combat_boxes(self.current_scene(), self.camera)
        for box in shown_combat_boxes(boxes, hit_and_hurt=self.show_combat_boxes):
            line, fill, style = styles[box.kind]
            painter.setPen(QPen(line, 1.5, style))
            painter.setBrush(QBrush(fill))
            painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in box.points]))

        for frame in build_camera_frames(self.current_scene(), self.camera):
            color = QColor(92, 181, 122, 210) if frame.active else QColor(120, 132, 160, 160)
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
        painter.drawLine(int(self.camera.pan_x), 0, int(self.camera.pan_x), self.height())
        painter.drawLine(0, int(self.camera.pan_y), self.width(), int(self.camera.pan_y))

        markers = self.markers()
        self._pill_rects = []
        for m in markers:
            renderer = m.entity.try_get(SpriteRenderer2D)
            has_sprite = (
                renderer is not None
                and renderer.visible
                and self.document.asset_views.sprite_sheet(renderer.sprite_sheet_asset_id)
                is not None
            )
            if has_sprite and not m.selected:
                continue
            tint = QColor(kind_of(m.entity).colour)
            if m.selected:
                painter.setPen(QPen(QColor(255, 255, 255), 2))
                painter.setBrush(QBrush(QColor(tint.red(), tint.green(), tint.blue(), 150)))
            else:
                painter.setPen(QPen(tint, 1.5))
                painter.setBrush(QBrush(QColor(tint.red(), tint.green(), tint.blue(), 90)))
            painter.drawEllipse(QPointF(m.screen_x, m.screen_y), m.radius, m.radius)
            self._paint_name_pill(painter, m, tint)

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

    def _paint_region_overlay(self, painter):
        """Tint every painted region cell and print its number (region mode only)."""
        from .tile_edit import region_layer

        tilemap = self.render_source.tilemap
        layer = region_layer(tilemap, self.tile_tools.region_layer_name)
        if layer is None:
            return
        width = tilemap.tile_width * self.camera.zoom
        height = tilemap.tile_height * self.camera.zoom
        # a cell's number is printed from its corner and may run past a small cell: cells (and
        # chunks) are skipped only when even the number cannot reach the view
        reach_x = max(width, 3 + 8 * 12)
        reach_y = max(height, 14 + 8)
        view_w, view_h = self.width(), self.height()
        origin_x, origin_y = self.render_source.origin_x, self.render_source.origin_y
        for (chunk_x, chunk_y), chunk in layer.chunks.items():
            rows = -(-len(chunk.tiles) // tilemap.chunk_width)
            left, top = self.camera.world_to_screen(
                origin_x + chunk_x * tilemap.chunk_width * tilemap.tile_width,
                origin_y + chunk_y * tilemap.chunk_height * tilemap.tile_height,
            )
            right, bottom = self.camera.world_to_screen(
                origin_x + (chunk_x + 1) * tilemap.chunk_width * tilemap.tile_width,
                origin_y + (chunk_y * tilemap.chunk_height + rows) * tilemap.tile_height,
            )
            if right + reach_x < 0 or left > view_w or bottom + reach_y < 0 or top > view_h:
                continue
            for index, value in enumerate(chunk.tiles):
                if value < 0:
                    continue
                tile_x = chunk_x * tilemap.chunk_width + index % tilemap.chunk_width
                tile_y = chunk_y * tilemap.chunk_height + index // tilemap.chunk_width
                sx, sy = self.camera.world_to_screen(
                    origin_x + tile_x * tilemap.tile_width,
                    origin_y + tile_y * tilemap.tile_height,
                )
                if sx + reach_x < 0 or sx > view_w or sy + reach_y < 0 or sy > view_h:
                    continue
                hue = (value * 47) % 360
                painter.setPen(QPen(QColor.fromHsv(hue, 200, 255, 220), 1))
                painter.setBrush(QBrush(QColor.fromHsv(hue, 200, 255, 70)))
                painter.drawRect(int(sx), int(sy), int(width), int(height))
                painter.setPen(QColor(255, 255, 255, 230))
                painter.drawText(int(sx) + 3, int(sy) + 14, str(value))

    def _place_doodad(self, x, y):
        from .doodads import build_place_doodads_command

        scene = self.current_scene()
        definition = self.tile_tools.doodad
        if scene is None or definition is None:
            return
        world_x, world_y = self.camera.screen_to_world(x, y)
        try:
            self.document.execute(
                build_place_doodads_command(scene, definition, [(world_x, world_y)])
            )
        except ValueError:
            return
        window = self.window()
        if hasattr(window, "refresh_all"):
            window.refresh_all()

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
        if event.button() == Qt.RightButton and getattr(self, "_pick_start", None) is not None:
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

    WHEEL_ZOOM_STEP = 1.15  # zoom factor of one notch of a mouse wheel

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
