"""Where the scene view looks: resetting and fitting the view, keeping the map in sight,
framing the chosen objects or the game's camera, and panning."""

from __future__ import annotations

from asteria.core import Transform, world_position
from asteria.editor.scene.entity_render import camera_world_rect
from asteria.runtime import Camera2DComponent


class ViewportFramingMixin:
    """``SceneViewportWidget``'s view: reset, fit, frame objects or the game camera, pan."""

    # defaults until something sets them (code may read them first)
    _framed = None
    render_source = None

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
        source = self.render_source
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
        framed = self._framed
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
