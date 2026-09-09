from .metadata import get_component_schema

class ComponentRegistry:
    def __init__(self):
        self._types = {}

    def register(self, component_type):
        type_id = get_component_schema(component_type).type_name
        existing = self._types.get(type_id)
        if existing is not None and existing is not component_type:
            raise ValueError(f"Component type ID collision: {type_id}")
        self._types[type_id] = component_type
        return component_type

    def resolve(self, type_id):
        try:
            return self._types[type_id]
        except KeyError as exc:
            raise KeyError(f"Unknown component type: {type_id}") from exc

    def contains_type(self, component_type):
        return component_type in self._types.values()

    def registrations(self):
        return tuple(sorted(self._types.items(), key=lambda item: item[0]))

    def component_types(self):
        return tuple(component_type for _,component_type in self.registrations())
