from asteria.core import Entity, Scene, Transform
from asteria.editor.inspector import (
    build_follow_entity_choices,
    build_inspector_fields,
)
from asteria.runtime import Camera2DComponent


def test_inspector_comes_from_component_metadata():
    fields = build_inspector_fields(Transform(5.0, 7.0))
    names = [f.name for f in fields]
    assert names == ["x", "y", "rotation", "scale_x", "scale_y", "parent_id"]
    values = {f.name: f.value for f in fields}
    assert values["x"] == 5.0 and values["y"] == 7.0


def test_camera_follow_choices_display_names_and_store_stable_ids():
    scene = Scene("Town")
    camera = scene.add_entity(Entity("Game Camera"))
    component = camera.add_component(Camera2DComponent())
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform())

    assert build_follow_entity_choices(component) == (
        ("Fixed", ""),
        ("Follow Hero", hero.id),
    )
