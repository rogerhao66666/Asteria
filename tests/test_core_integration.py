from asteria.core import (
    ComponentRegistry,
    Entity,
    Scene,
    Transform,
    deserialize_scene,
    serialize_scene,
)


def test_component_scene_serialization_roundtrip():
    r = ComponentRegistry()
    r.register(Transform)
    s = Scene("Town")
    e = s.add_entity(Entity("Hero"))
    e.add_component(Transform(4.0, 7.0))
    data = serialize_scene(s)
    s2 = deserialize_scene(data, r)
    t = s2.entities()[0].get(Transform)
    assert (t.x, t.y) == (4.0, 7.0)
    assert s2.events is not None
