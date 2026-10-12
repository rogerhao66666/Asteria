from .ids import new_id, validate_id


class Entity:
    def __init__(self, name="Entity", *, entity_id=None, enabled=True):
        self.id = validate_id(entity_id) if entity_id is not None else new_id()
        self.name = str(name)
        self.enabled = bool(enabled)
        self._scene = None
        self._components = {}
        self._destroy_requested = False

    @property
    def scene(self):
        return self._scene

    @property
    def destroy_requested(self):
        return self._destroy_requested

    def add_component(self, component):
        ctype = type(component)
        if ctype in self._components:
            raise ValueError(f"{ctype.__name__} already exists on entity")
        self._components[ctype] = component
        component._attach(self)
        if self._scene is not None:
            self._scene._component_added(self, component)
        return component

    def get(self, component_type):
        return self._components[component_type]

    def try_get(self, component_type):
        return self._components.get(component_type)

    def has(self, component_type):
        return component_type in self._components

    def components(self):
        return tuple(self._components.values())

    def detach_component(self, component_type):
        if self._scene is not None and component_type in self._components:
            self._scene._component_removed(self, self._components[component_type])
        c = self._components.pop(component_type)
        c._detach()
        return c

    def remove_component(self, component_type):
        if self._scene is not None and component_type in self._components:
            self._scene._component_removed(self, self._components[component_type])
        c = self._components.pop(component_type)
        c._destroy()
        return c

    def destroy(self):
        if self._scene is not None:
            self._scene.remove_entity(self)
            return
        if self._destroy_requested:
            return
        self._destroy_requested = True
        for c in tuple(self._components.values()):
            c._destroy()
        self._components.clear()
