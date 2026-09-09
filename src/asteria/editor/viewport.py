from dataclasses import dataclass

from asteria.core import Transform


@dataclass(slots=True)
class ViewportCamera:
    pan_x: float = 0.0
    pan_y: float = 0.0
    zoom: float = 1.0
    min_zoom: float = 0.1
    max_zoom: float = 8.0

    def set_zoom(self, value, anchor_screen=None):
        new = max(self.min_zoom, min(self.max_zoom, float(value)))
        if anchor_screen is not None and self.zoom > 0:
            ax, ay = anchor_screen
            wx, wy = self.screen_to_world(ax, ay)
            self.zoom = new
            sx, sy = self.world_to_screen(wx, wy)
            self.pan_x += ax - sx
            self.pan_y += ay - sy
        else:
            self.zoom = new
        return self.zoom

    def zoom_by(self, factor, anchor_screen=None):
        return self.set_zoom(self.zoom * float(factor), anchor_screen)

    def pan_by(self, dx, dy):
        self.pan_x += float(dx)
        self.pan_y += float(dy)

    def world_to_screen(self, x, y, parallax_x=1.0, parallax_y=1.0, elevation=0.0):
        # Editor navigation is expressed as screen-space pan rather than a
        # gameplay camera world origin, but exposes the same transform protocol
        # so backend-neutral draw builders can be shared.
        return (
            x * self.zoom + self.pan_x * float(parallax_x),
            (y - float(elevation)) * self.zoom + self.pan_y * float(parallax_y),
        )

    def screen_to_world(self, x, y):
        return (x - self.pan_x) / self.zoom, (y - self.pan_y) / self.zoom


@dataclass(frozen=True, slots=True)
class EntityMarker:
    entity: object
    world_x: float
    world_y: float
    screen_x: float
    screen_y: float
    radius: float
    selected: bool


def scene_markers(scene, camera, selected_entities=(), base_radius=8.0):
    if scene is None:
        return ()
    selected = set(selected_entities)
    result = []
    for entity in scene.entities():
        transform = entity.try_get(Transform) if hasattr(entity, "try_get") else None
        if transform is None:
            continue
        sx, sy = camera.world_to_screen(transform.x, transform.y)
        result.append(
            EntityMarker(
                entity=entity,
                world_x=float(transform.x),
                world_y=float(transform.y),
                screen_x=sx,
                screen_y=sy,
                radius=max(4.0, base_radius * min(camera.zoom, 2.0)),
                selected=entity in selected,
            )
        )
    return tuple(result)


def pick_entity(markers, screen_x, screen_y, pick_radius=10.0):
    best = None
    best_d2 = None
    for marker in markers:
        dx = marker.screen_x - screen_x
        dy = marker.screen_y - screen_y
        limit = max(float(pick_radius), marker.radius)
        d2 = dx * dx + dy * dy
        if d2 <= limit * limit and (best_d2 is None or d2 < best_d2):
            best = marker.entity
            best_d2 = d2
    return best


def selected_scene(document):
    sel = document.selection
    if sel.kind == "scene" and not sel.multiple:
        return sel.value
    if sel.kind == "entity":
        values = sel.values or (() if sel.value is None else (sel.value,))
        scenes = {e.scene for e in values if getattr(e, "scene", None) is not None}
        return next(iter(scenes)) if len(scenes) == 1 else None
    if sel.kind == "component" and not sel.multiple and sel.value is not None:
        try:
            return sel.value.entity.scene
        except AttributeError:
            return None
    project = document.project
    if project is not None and project.startup_scene_id:
        return project.scene(project.startup_scene_id)
    return None
