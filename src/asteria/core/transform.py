from math import cos, radians, sin

from .columns import column_storage
from .component import Component
from .metadata import Field, component_schema


@column_storage()
@component_schema(
    type_name="asteria.Transform",
    version=1,
    fields=(
        Field("x", float, 0.0),
        Field("y", float, 0.0),
        Field("rotation", float, 0.0),
        Field("scale_x", float, 1.0),
        Field("scale_y", float, 1.0),
        Field(
            "parent_id", str, "", label="Parent", tooltip="Entity whose transform this one is relative to (same scene)."
        ),
    ),
)
class Transform(Component):
    """Local position/rotation (degrees)/scale, relative to ``parent_id`` when set."""

    def __init__(self, x=0.0, y=0.0):
        super().__init__()
        self.x = float(x)
        self.y = float(y)
        self.rotation = 0.0
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.parent_id = ""


class TransformHierarchyError(ValueError):
    pass


def parent_entity(entity):
    """The entity this entity's Transform is parented to, or None."""
    transform = entity.try_get(Transform)
    if transform is None or not transform.parent_id or entity.scene is None:
        return None
    parent = entity.scene.get_entity(transform.parent_id)
    return parent if parent is not None and parent.has(Transform) else None


def children(entity):
    """Entities in the same scene whose Transform is parented to ``entity``."""
    if entity.scene is None:
        return ()
    return tuple(
        e
        for e in entity.scene.entities()
        if e is not entity and e.has(Transform) and e.get(Transform).parent_id == entity.id
    )


def ancestors(entity):
    """Parent chain from nearest to root; raises on cycles."""
    chain, seen = [], {entity.id}
    current = parent_entity(entity)
    while current is not None:
        if current.id in seen:
            raise TransformHierarchyError(f"transform parent cycle at {current.name}")
        seen.add(current.id)
        chain.append(current)
        current = parent_entity(current)
    return tuple(chain)


def world_transform(entity):
    """``(x, y, rotation, scale_x, scale_y)`` of ``entity`` in scene space."""
    t = entity.get(Transform)
    x, y, rotation, sx, sy = t.x, t.y, t.rotation, t.scale_x, t.scale_y
    for parent in ancestors(entity):
        p = parent.get(Transform)
        x, y = x * p.scale_x, y * p.scale_y
        angle = radians(p.rotation)
        x, y = x * cos(angle) - y * sin(angle), x * sin(angle) + y * cos(angle)
        x, y = x + p.x, y + p.y
        rotation += p.rotation
        sx, sy = sx * p.scale_x, sy * p.scale_y
    return x, y, rotation, sx, sy


def world_position(entity):
    x, y, *_ = world_transform(entity)
    return x, y


def world_delta_to_local(entity, dx, dy):
    """Convert a scene-space movement into ``entity``'s local (parent) space."""
    parent = parent_entity(entity)
    if parent is None:
        return dx, dy
    _, _, rotation, sx, sy = world_transform(parent)
    angle = radians(-rotation)
    dx, dy = dx * cos(angle) - dy * sin(angle), dx * sin(angle) + dy * cos(angle)
    return dx / sx if sx else dx, dy / sy if sy else dy


def can_parent(child, parent):
    """True when ``parent`` may become ``child``'s transform parent."""
    if parent is None:
        return True
    if parent is child or parent.scene is not child.scene or not parent.has(Transform):
        return False
    try:
        return child not in ancestors(parent)
    except TransformHierarchyError:
        return False


def set_parent(child, parent, *, keep_world=True):
    """Parent ``child`` to ``parent`` (or None), keeping its scene position by default."""
    if not can_parent(child, parent):
        raise TransformHierarchyError(f"cannot parent {child.name} to {getattr(parent, 'name', None)}")
    transform = child.get(Transform)
    wx, wy = world_position(child)
    transform.parent_id = "" if parent is None else parent.id
    if keep_world:
        if parent is None:
            transform.x, transform.y = wx, wy
        else:
            px, py = world_position(parent)
            transform.x, transform.y = world_delta_to_local(child, wx - px, wy - py)
    return transform
