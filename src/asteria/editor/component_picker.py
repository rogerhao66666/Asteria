from dataclasses import dataclass

from asteria.core.metadata import get_component_schema


@dataclass(frozen=True, slots=True)
class ComponentChoice:
    type_id: str
    display_name: str
    component_type: type
    addable: bool
    reason: str | None = None


def build_component_choices(registry, entity=None):
    choices = []
    for type_id, component_type in registry.registrations():
        schema = get_component_schema(component_type)
        display = getattr(schema, "display_name", None) or component_type.__name__
        addable = True
        reason = None
        if entity is not None and entity.has(component_type):
            addable = False
            reason = "Already added"
        else:
            try:
                component_type()
            except TypeError:
                addable = False
                reason = "Requires constructor arguments"
        choices.append(ComponentChoice(type_id, display, component_type, addable, reason))
    return tuple(choices)
