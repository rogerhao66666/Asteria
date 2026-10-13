"""CB4c: Transform parent/child hierarchy (ASTERIA_SPEC §8 Transform)."""

import pytest

from asteria.core import (
    Entity,
    Scene,
    Transform,
    TransformHierarchyError,
    can_parent,
    children,
    set_parent,
    world_position,
    world_transform,
)
from asteria.core.serialization import deserialize_scene, serialize_scene


def _entity(scene, name, x=0.0, y=0.0):
    entity = scene.add_entity(Entity(name))
    entity.add_component(Transform(x, y))
    return entity


def test_world_transform_composes_translation_rotation_and_scale():
    scene = Scene("S")
    ship = _entity(scene, "Ship", 100, 50)
    ship.get(Transform).rotation = 90
    ship.get(Transform).scale_x = ship.get(Transform).scale_y = 2
    turret = _entity(scene, "Turret", 10, 0)
    turret.get(Transform).parent_id = ship.id
    x, y, rotation, sx, sy = world_transform(turret)
    assert (round(x, 6), round(y, 6)) == (100.0, 70.0)  # (10*2) rotated 90 deg -> (0, 20)
    assert (rotation, sx, sy) == (90, 2, 2)
    assert children(ship) == (turret,)


def test_reparenting_keeps_scene_position_and_refuses_cycles():
    scene = Scene("S")
    a = _entity(scene, "A", 10, 10)
    b = _entity(scene, "B", 30, 40)
    set_parent(b, a)
    assert (b.get(Transform).x, b.get(Transform).y) == (20, 30)
    assert world_position(b) == (30, 40)
    assert not can_parent(a, b)
    with pytest.raises(TransformHierarchyError):
        set_parent(a, b)
    set_parent(b, None)
    assert (b.get(Transform).x, b.get(Transform).parent_id) == (30, "")


def test_parent_id_round_trips_and_old_scenes_without_it_still_load():
    from asteria.editor import EditorDocument

    scene = Scene("S")
    a = _entity(scene, "A")
    b = _entity(scene, "B", 5, 5)
    set_parent(b, a, keep_world=False)
    registry = EditorDocument().component_registry
    data = serialize_scene(scene)
    restored = deserialize_scene(data, registry)
    assert restored.get_entity(b.id).get(Transform).parent_id == a.id
    for entity in data["entities"]:
        for component in entity["components"]:
            component["fields"].pop("parent_id", None)
    assert deserialize_scene(data, registry).get_entity(b.id).get(Transform).parent_id == ""


def test_inspector_reparent_keeps_position_and_undoes_in_one_step():
    from asteria.editor.editing import EditError, build_set_component_field_command

    scene = Scene("S")
    parent = _entity(scene, "Parent", 100, 0)
    child = _entity(scene, "Child", 120, 10)
    command = build_set_component_field_command(child.get(Transform), "parent_id", parent.id)
    command.redo()
    assert world_position(child) == (120, 10) and child.get(Transform).x == 20
    command.undo()
    assert (child.get(Transform).x, child.get(Transform).parent_id) == (120, "")
    command.redo()
    with pytest.raises(EditError):
        build_set_component_field_command(parent.get(Transform), "parent_id", child.id)


def test_interaction_distance_uses_world_position():
    from asteria.runtime import Interaction2DComponent
    from asteria.runtime.interaction import InteractionQuery

    scene = Scene("S")
    hero = _entity(scene, "Hero", 0, 0)
    cart = _entity(scene, "Cart", 500, 0)
    sign = _entity(scene, "Sign", -490, 0)  # world x = 10 once parented to the cart
    sign.get(Transform).parent_id = cart.id
    talk = sign.add_component(Interaction2DComponent())
    talk.event_program_id, talk.range, talk.require_facing = "read_sign", 16.0, False
    assert [c.entity for c in InteractionQuery().candidates(scene, hero, "right")] == [sign]


def test_editor_tree_nests_children_under_their_parent():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project

    app = QApplication.instance() or QApplication([])
    project = Project("Game")
    scene = project.add_scene(Scene("Map"))
    parent = _entity(scene, "Wagon")
    child = _entity(scene, "Wheel")
    child.get(Transform).parent_id = parent.id
    window = AsteriaEditorWindow(project)
    try:
        window.refresh_all()
        tree = window.project_tree.tree
        root = tree.topLevelItem(0)
        scenes = next(
            root.child(i) for i in range(root.childCount()) if root.child(i).text(0) == "Scenes"
        )
        map_item = scenes.child(0)
        top_names = [map_item.child(i).text(0) for i in range(map_item.childCount())]
        assert "Wagon" in top_names and "Wheel" not in top_names
        wagon = next(
            map_item.child(i)
            for i in range(map_item.childCount())
            if map_item.child(i).text(0) == "Wagon"
        )
        assert "Wheel" in [wagon.child(i).text(0) for i in range(wagon.childCount())]
    finally:
        window.document.mark_saved()
        window.close()
        app.processEvents()
