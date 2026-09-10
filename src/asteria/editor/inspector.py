from dataclasses import dataclass

from asteria.core.metadata import get_component_schema


@dataclass(frozen=True, slots=True)
class InspectorFieldModel:
    name: str
    label: str
    value: object
    value_type: type
    type_name: str
    editable: bool
    minimum: float | int | None = None
    maximum: float | int | None = None
    choices: tuple | None = None
    tooltip: str = ""


def build_inspector_fields(component):
    schema = get_component_schema(type(component))
    fields = schema.fields.values()
    return tuple(
        InspectorFieldModel(
            name=f.name,
            label=f.label or f.name.replace("_", " ").title(),
            value=getattr(component, f.name),
            value_type=f.value_type,
            type_name=f.value_type.__name__,
            editable=bool(f.serialize),
            minimum=f.minimum,
            maximum=f.maximum,
            choices=tuple(f.choices) if f.choices is not None else None,
            tooltip=f.tooltip,
        )
        for f in fields
    )


def build_follow_entity_choices(component):
    """Return display labels mapped to canonical entity IDs for Camera2D."""
    from asteria.core import Transform

    try:
        owner = component.entity
    except RuntimeError:
        return (("Fixed", ""),)
    scene = owner.scene
    if scene is None:
        return (("Fixed", ""),)
    choices = [("Fixed", "")]
    for entity in scene.entities():
        if entity is owner or entity.try_get(Transform) is None:
            continue
        choices.append((f"Follow {entity.name}", entity.id))
    current = str(getattr(component, "follow_entity_id", ""))
    if current and all(value != current for _, value in choices):
        choices.append((f"Missing entity ({current})", current))
    return tuple(choices)
