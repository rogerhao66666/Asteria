"""Drawing the scene view: the map, objects, skeletons, markers, name pills, regions and the
ghost of a character being placed."""

from __future__ import annotations

from asteria.assets.scene_placement import character_cell_position
from asteria.editor.assets.qt_texture_renderer import paint_texture_draws
from asteria.editor.scene.collision_overlay import (
    build_collision_cells,
    build_combat_boxes,
    shown_combat_boxes,
)
from asteria.editor.scene.entity_kinds import kind_of
from asteria.editor.scene.entity_render import (
    build_camera_frames,
    build_entity_sprite_draws,
    camera_world_rect,
)
from asteria.editor.scene.render import build_scene_texture_draws, resolve_texture_source
from asteria.editor.scene.viewport import scene_markers
from asteria.runtime import SkeletonAnimation2DComponent, SkeletonSceneRuntime, SpriteRenderer2D

try:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
except ImportError:
    Qt = None


class ViewportPaintingMixin:
    """``SceneViewportWidget``'s drawing: ``paintEvent`` and what it draws."""

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

    def _paint_placement_ghost(self, painter):
        """The character waiting to be placed, standing on the cell under the mouse."""

        cell, ghost = self._placement_cell, self._placement_ghost
        if cell is None or ghost is None or ghost.isNull():
            return
        tile_w, tile_h = self._tile_size()
        zoom = self.camera.zoom
        world_x, world_y = character_cell_position(cell[0], cell[1], (tile_w, tile_h))
        sx, sy = self.camera.world_to_screen(world_x, world_y)
        width, height = ghost.width() * zoom, ghost.height() * zoom
        painter.save()
        painter.setOpacity(0.75)
        painter.drawPixmap(
            QRectF(sx - width / 2, sy - height, width, height), ghost, QRectF(ghost.rect())
        )
        painter.setOpacity(1.0)
        painter.setPen(QPen(QColor(70, 184, 150), 2))
        painter.setBrush(Qt.NoBrush)
        cx, cy = self.camera.world_to_screen(cell[0] * tile_w, cell[1] * tile_h)
        painter.drawRect(QRectF(cx, cy, tile_w * zoom, tile_h * zoom))
        painter.restore()

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

        if self.character_placement_active:
            self._paint_placement_ghost(painter)

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
        from asteria.editor.scene.tile_edit import region_layer

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
