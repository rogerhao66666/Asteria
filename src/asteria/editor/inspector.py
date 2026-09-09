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
