"""Prefabs, variants, instance overrides and change propagation (ASTERIA_SPEC §10).

A prefab is a named set of serialized components. A variant names a base
prefab and lists only what it changes or adds. Scene entities created from a
prefab carry ``PrefabInstanceComponent``. Instance overrides are not stored:
when a prefab changes, each instance's differences from the *previous*
resolution are its overrides and are kept on top of the *new* resolution.
Placement (Transform x/y/parent_id) always belongs to the instance.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .component import Component
from .entity import Entity
from .metadata import Field, component_schema, get_component_schema
from .serialization import deserialize_component, serialize_component

TRANSFORM_TYPE = "asteria.Transform"
INSTANCE_TYPE = "asteria.PrefabInstance"
PLACEMENT_FIELDS = {TRANSFORM_TYPE: ("x", "y", "parent_id")}


@component_schema(
    type_name=INSTANCE_TYPE,
    version=1,
    fields=(Field("prefab_id", str, "", label="Prefab"),),
)
class PrefabInstanceComponent(Component):
    def __init__(self):
        super().__init__()
        self.prefab_id = ""


class PrefabError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PrefabDefinition:
    prefab_id: str
    name: str
    components: tuple = ()  # serialized component records
    base_prefab_id: str = ""  # set for variants
    removed_components: tuple = ()  # variant: base component types it drops

    def __post_init__(self):
        if not str(self.prefab_id).strip():
            raise PrefabError("prefab_id is required")
        object.__setattr__(self, "components", tuple(copy.deepcopy(dict(c)) for c in self.components))
        object.__setattr__(self, "removed_components", tuple(self.removed_components))
        if any(c.get("type") == INSTANCE_TYPE for c in self.components):
            raise PrefabError("a prefab cannot contain PrefabInstance")

    def to_data(self):
        return {
            "schema": "asteria.prefab",
            "version": 1,
            "prefab_id": self.prefab_id,
            "name": self.name,
            "components": [copy.deepcopy(c) for c in self.components],
            "base_prefab_id": self.base_prefab_id,
            "removed_components": list(self.removed_components),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.prefab" or data.get("version") != 1:
            raise PrefabError("unsupported prefab")
        return cls(
            data["prefab_id"],
            data["name"],
            tuple(data["components"]),
            data.get("base_prefab_id", ""),
            tuple(data.get("removed_components", ())),
        )


@dataclass(slots=True)
class PrefabLibrary:
    _prefabs: dict = field(default_factory=dict)

    def ids(self):
        return tuple(sorted(self._prefabs))

    def get(self, prefab_id):
        return self._prefabs.get(str(prefab_id))

    def require(self, prefab_id):
        value = self.get(prefab_id)
        if value is None:
            raise PrefabError(f"unknown prefab: {prefab_id}")
        return value

    def add(self, definition):
        if definition.prefab_id in self._prefabs:
            raise PrefabError(f"duplicate prefab: {definition.prefab_id}")
        self.set(definition)
        return definition

    def set(self, definition):
        if not isinstance(definition, PrefabDefinition):
            raise TypeError("definition must be PrefabDefinition")
        previous = self._prefabs.get(definition.prefab_id)
        self._prefabs[definition.prefab_id] = definition
        try:
            self.resolve(definition.prefab_id)
        except PrefabError:
            if previous is None:
                del self._prefabs[definition.prefab_id]
            else:
                self._prefabs[definition.prefab_id] = previous
            raise
        return definition

    def remove(self, prefab_id):
        dependants = [p.prefab_id for p in self._prefabs.values() if p.base_prefab_id == prefab_id]
        if dependants:
            raise PrefabError(f"{prefab_id} is the base of {', '.join(sorted(dependants))}")
        return self._prefabs.pop(str(prefab_id))

    def resolve(self, prefab_id, _seen=()):
        """``{component type: {field: value}}`` after applying the variant chain."""
        definition = self.require(prefab_id)
        if definition.prefab_id in _seen:
            raise PrefabError(f"prefab variant cycle at {prefab_id}")
        resolved = {}
        if definition.base_prefab_id:
            resolved = self.resolve(definition.base_prefab_id, (*_seen, definition.prefab_id))
            for type_name in definition.removed_components:
                resolved.pop(type_name, None)
        for record in definition.components:
            resolved.setdefault(record["type"], {}).update(copy.deepcopy(record["fields"]))
        return resolved

    def to_data(self):
        return {
            "schema": "asteria.prefab_library",
            "version": 1,
            "prefabs": [self._prefabs[k].to_data() for k in sorted(self._prefabs)],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.prefab_library" or data.get("version") != 1:
            raise PrefabError("unsupported prefab library")
        library = cls()
        for raw in data["prefabs"]:  # bases may follow variants; validate after loading all
            definition = PrefabDefinition.from_data(raw)
            library._prefabs[definition.prefab_id] = definition
        for prefab_id in library.ids():
            library.resolve(prefab_id)
        return library


def _component_record(type_name, fields, registry):
    component_type = registry.resolve(type_name)
    return {"type": type_name, "version": get_component_schema(component_type).version, "fields": fields}


def instantiate(library, prefab_id, registry, *, name=None, entity_id=None):
    """A new entity built from the prefab's resolved components plus PrefabInstanceComponent."""
    definition = library.require(prefab_id)
    entity = Entity(name or definition.name, entity_id=entity_id)
    for type_name, fields in library.resolve(prefab_id).items():
        entity.add_component(deserialize_component(_component_record(type_name, fields, registry), registry))
    marker = entity.add_component(PrefabInstanceComponent())
    marker.prefab_id = definition.prefab_id
    return entity


def prefab_from_entity(entity, prefab_id, name=None, *, base_prefab_id=""):
    """Capture an entity's components (placement reset to the origin) as a prefab."""
    records = []
    for component in entity.components():
        record = serialize_component(component)
        if record["type"] == INSTANCE_TYPE:
            continue
        for placement in PLACEMENT_FIELDS.get(record["type"], ()):
            schema = get_component_schema(type(component))
            record["fields"][placement] = schema.fields[placement].default
        records.append(record)
    return PrefabDefinition(prefab_id, name or entity.name, tuple(records), base_prefab_id)


def _entity_values(entity):
    return {serialize_component(c)["type"]: serialize_component(c)["fields"] for c in entity.components()}


def instance_overrides(entity, resolution):
    """Fields where the instance differs from ``resolution`` (placement excluded)."""
    values = _entity_values(entity)
    overrides = {}
    for type_name, fields in values.items():
        if type_name == INSTANCE_TYPE:
            continue
        base = resolution.get(type_name)
        if base is None:
            overrides[type_name] = dict(fields)  # component added on the instance only
            continue
        changed = {k: v for k, v in fields.items() if k not in PLACEMENT_FIELDS.get(type_name, ()) and base.get(k) != v}
        if changed:
            overrides[type_name] = changed
    return overrides


def sync_instance(entity, old_resolution, new_resolution, registry):
    """Rebuild an instance from ``new_resolution`` keeping its overrides against ``old_resolution``."""
    overrides = instance_overrides(entity, old_resolution)
    by_type = {serialize_component(c)["type"]: c for c in entity.components()}
    for type_name in set(old_resolution) - set(new_resolution):
        component = by_type.get(type_name)
        if component is not None and type_name not in overrides:
            entity.remove_component(type(component))
    for type_name, fields in new_resolution.items():
        merged = dict(fields)
        merged.update(overrides.get(type_name, {}))
        component = by_type.get(type_name)
        if component is None:
            entity.add_component(deserialize_component(_component_record(type_name, merged, registry), registry))
            continue
        schema = get_component_schema(type(component))
        for name, value in merged.items():
            if name in PLACEMENT_FIELDS.get(type_name, ()):
                continue
            schema.fields[name].validate(value)
            setattr(component, name, copy.deepcopy(value))
    return overrides


def instances(scenes, prefab_id=None):
    """``(scene, entity)`` for every prefab instance (optionally of one prefab)."""
    for scene in scenes:
        for entity in scene.entities():
            marker = entity.try_get(PrefabInstanceComponent)
            if marker is not None and (prefab_id is None or marker.prefab_id == prefab_id):
                yield scene, entity
