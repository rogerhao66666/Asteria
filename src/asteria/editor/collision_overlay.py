from dataclasses import dataclass

from asteria.graphics import EMPTY_TILE


@dataclass(frozen=True, slots=True)
class CollisionCell:
    tile_x: int
    tile_y: int
    screen_x: float
    screen_y: float
    width: float
    height: float


def build_collision_cells(
    tilemap,
    camera,
    *,
    origin_x=0.0,
    origin_y=0.0,
    viewport_width=None,
    viewport_height=None,
):
    """Screen cells of every filled tile on a collision layer; with a viewport size, chunks and
    cells wholly outside it are left out."""
    from asteria.runtime.tile_draw import _visible_span

    cells = []
    width = tilemap.tile_width * camera.zoom
    height = tilemap.tile_height * camera.zoom
    for layer in tilemap.ordered_layers():
        if not layer.collision_enabled:
            continue
        for chunk in layer.chunks.values():
            base_x = chunk.chunk_x * tilemap.chunk_width
            base_y = chunk.chunk_y * tilemap.chunk_height
            if viewport_width is not None or viewport_height is not None:
                first = camera.world_to_screen(
                    origin_x + base_x * tilemap.tile_width,
                    origin_y + base_y * tilemap.tile_height,
                )
                last = camera.world_to_screen(
                    origin_x + (base_x + chunk.width - 1) * tilemap.tile_width,
                    origin_y + (base_y + chunk.height - 1) * tilemap.tile_height,
                )
                if not _visible_span(first[0], last[0], width, viewport_width):
                    continue
                if not _visible_span(first[1], last[1], height, viewport_height):
                    continue
            tiles = chunk.tiles
            for ly in range(chunk.height):
                row = ly * chunk.width
                for lx in range(chunk.width):
                    if tiles[row + lx] == EMPTY_TILE:
                        continue
                    tx = base_x + lx
                    ty = base_y + ly
                    sx, sy = camera.world_to_screen(
                        origin_x + tx * tilemap.tile_width,
                        origin_y + ty * tilemap.tile_height,
                    )
                    if viewport_width is not None and (sx + width < 0 or sx > viewport_width):
                        continue
                    if viewport_height is not None and (sy + height < 0 or sy > viewport_height):
                        continue
                    cells.append(CollisionCell(tx, ty, sx, sy, width, height))
    return tuple(cells)


@dataclass(frozen=True, slots=True)
class CombatBox:
    """One shape to outline in the scene view: ``kind`` is solid, one_way, slope_right,
    slope_left, ladder,
    trigger, hurtbox or hitbox; ``points`` are screen corners (a triangle for slopes)."""

    kind: str
    entity_id: str
    points: tuple


def build_combat_boxes(scene, camera):
    """Colliders, hurtboxes and hitboxes of a scene in screen space (D22 A9): what blocks, what
    can be hit,
    what hits (hitboxes are shown where they reach with the entity's facing)."""
    if scene is None:
        return ()
    from asteria.core import Transform, world_position
    from asteria.runtime.character_control import Hitbox2DComponent, Hurtbox2DComponent, facing_box
    from asteria.runtime.collision import Collider2DComponent

    boxes = []

    def corners(x0, y0, x1, y1):
        return tuple(
            camera.world_to_screen(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
        )

    for entity in scene.entities():
        if not entity.enabled or not entity.has(Transform):
            continue
        collider = entity.try_get(Collider2DComponent)
        if collider is not None and collider.enabled:
            x, y = world_position(entity)
            cx, cy = x + collider.offset_x, y + collider.offset_y
            if collider.shape == "circle":
                r = collider.radius
                x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r
            else:
                hw, hh = collider.width / 2, collider.height / 2
                x0, y0, x1, y1 = cx - hw, cy - hh, cx + hw, cy + hh
            if collider.shape == "slope_right":
                points = tuple(
                    camera.world_to_screen(px, py) for px, py in ((x0, y1), (x1, y1), (x1, y0))
                )
                kind = "slope_right"
            elif collider.shape == "slope_left":
                points = tuple(
                    camera.world_to_screen(px, py) for px, py in ((x0, y1), (x1, y1), (x0, y0))
                )
                kind = "slope_left"
            else:
                points = corners(x0, y0, x1, y1)
                kind = (
                    "ladder"
                    if collider.ladder
                    else "trigger"
                    if collider.is_trigger
                    else "one_way"
                    if collider.one_way
                    else "solid"
                )
            boxes.append(CombatBox(kind, entity.id, points))
        for component_type, kind in (
            (Hurtbox2DComponent, "hurtbox"),
            (Hitbox2DComponent, "hitbox"),
        ):
            component = entity.try_get(component_type)
            if component is not None and component.enabled:
                boxes.append(CombatBox(kind, entity.id, corners(*facing_box(entity, component))))
    return tuple(boxes)
