from .metadata import get_component_schema
from .entity import Entity
from .scene import Scene

def serialize_component(component):
    schema = get_component_schema(type(component))
    values = {}
    for name, field in schema.fields.items():
        if field.serialize:
            value = getattr(component, name)
            field.validate(value)
            values[name] = value
    return {
        "type": schema.type_name,
        "version": schema.version,
        "fields": values,
    }

def deserialize_component(data, registry):
    if set(data) != {"type", "version", "fields"}:
        raise ValueError("Invalid component record")
    component_type = registry.resolve(data["type"])
    schema = get_component_schema(component_type)
    if data["version"] != schema.version:
        raise ValueError(f"Unsupported component schema version: {data['version']}")
    incoming = data["fields"]
    if not isinstance(incoming, dict):
        raise TypeError("Component fields must be an object")
    unknown = set(incoming) - set(schema.fields)
    if unknown:
        raise ValueError(f"Unknown component fields: {sorted(unknown)}")
    c = component_type()
    for name, field in schema.fields.items():
        if not field.serialize:
            continue
        value = incoming.get(name, field.default)
        field.validate(value)
        setattr(c, name, value)
    return c

def serialize_entity(entity):
    return {
        "id": entity.id,
        "name": entity.name,
        "enabled": entity.enabled,
        "components": [serialize_component(c) for c in entity.components()],
    }

def deserialize_entity(data, registry):
    if set(data) != {"id", "name", "enabled", "components"}:
        raise ValueError("Invalid entity record")
    if not isinstance(data["components"], list):
        raise TypeError("Entity components must be a list")
    entity = Entity(data["name"], entity_id=data["id"], enabled=data["enabled"])
    for cdata in data["components"]:
        entity.add_component(deserialize_component(cdata, registry))
    return entity

def serialize_scene(scene):
    return {
        "schema": "asteria.scene",
        "version": 1,
        "id": scene.id,
        "name": scene.name,
        "entities": [serialize_entity(e) for e in scene.entities()],
    }

def deserialize_scene(data, registry):
    expected = {"schema", "version", "id", "name", "entities"}
    if set(data) != expected:
        raise ValueError("Invalid scene record")
    if data["schema"] != "asteria.scene" or data["version"] != 1:
        raise ValueError("Unsupported scene schema/version")
    if not isinstance(data["entities"], list):
        raise TypeError("Scene entities must be a list")
    scene = Scene(data["name"], scene_id=data["id"])
    for edata in data["entities"]:
        scene.add_entity(deserialize_entity(edata, registry))
    return scene
