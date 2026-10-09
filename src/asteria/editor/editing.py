from __future__ import annotations

from asteria.core.metadata import get_component_schema

from .commands import SetAttributeCommand


class EditError(ValueError):
    pass


class ReparentTransformCommand:
    """Set Transform.parent_id while keeping the entity where it is in the scene."""

    def __init__(self, transform, new_parent_id):
        from asteria.core.transform import set_parent

        self.transform = transform
        self.attribute = "parent_id"
        self.old_value = transform.parent_id
        self.new_value = str(new_parent_id)
        entity = transform.entity
        self._old = (transform.x, transform.y, transform.parent_id)
        parent = entity.scene.get_entity(self.new_value) if self.new_value else None
        if self.new_value and parent is None:
            raise EditError(f"parent_id: no entity {self.new_value} in this scene")
        # Compute the new local position once, then restore; redo/undo just swap values.
        try:
            set_parent(entity, parent)
        except ValueError as exc:
            raise EditError(f"parent_id: {exc}") from exc
        self._new = (transform.x, transform.y, transform.parent_id)
        transform.x, transform.y, transform.parent_id = self._old

    @property
    def label(self):
        return "Set Transform.parent_id"

    def redo(self):
        self.transform.x, self.transform.y, self.transform.parent_id = self._new

    def undo(self):
        self.transform.x, self.transform.y, self.transform.parent_id = self._old


def _field_for(component, field_name):
    schema = get_component_schema(type(component))
    try:
        return schema.fields[field_name]
    except KeyError as exc:
        raise EditError(f"unknown component field: {field_name}") from exc


def coerce_field_value(field, value):
    typ = field.value_type
    if isinstance(value, typ) and not (typ is int and isinstance(value, bool)):
        return value
    try:
        if typ is bool:
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"true", "1", "yes", "on"}:
                    return True
                if normalized in {"false", "0", "no", "off"}:
                    return False
                raise ValueError
            return bool(value)
        if typ is int:
            if isinstance(value, bool):
                raise ValueError
            return int(value)
        if typ is float:
            return float(value)
        if typ is str:
            return str(value)
    except (TypeError, ValueError) as exc:
        raise EditError(f"{field.name}: cannot convert to {typ.__name__}") from exc
    raise EditError(f"{field.name}: unsupported editor field type {typ.__name__}")


def build_set_component_field_command(component, field_name, raw_value):
    field = _field_for(component, field_name)
    if not field.serialize:
        raise EditError(f"{field_name}: runtime-only field is not editable")
    value = coerce_field_value(field, raw_value)
    try:
        field.validate(value)
    except (TypeError, ValueError) as exc:
        raise EditError(str(exc)) from exc
    old = getattr(component, field_name)
    from asteria.core import Transform

    if isinstance(component, Transform) and field_name == "parent_id" and value != old:
        return ReparentTransformCommand(component, value)
    return SetAttributeCommand(
        component,
        field_name,
        value,
        old,
        f"Set {type(component).__name__}.{field_name}",
    )
