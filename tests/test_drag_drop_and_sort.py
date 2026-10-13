"""CB10 / EDT-14: hierarchy drag-and-drop (reparent, reorder, move scene) and record sorting."""

import pytest

from asteria.core import Entity, Scene, Transform, world_position
from asteria.editor import EditorDocument
from asteria.editor.hierarchy import HierarchyEditError, drop_entities
from asteria.project import Project


def _project():
    project = Project("P")
    town = project.add_scene(Scene("Town"))
    cave = project.add_scene(Scene("Cave"))
    for name, x in (("Hero", 10.0), ("Cart", 50.0), ("Lamp", 90.0)):
        town.add_entity(Entity(name)).add_component(Transform(x, 0.0))
    document = EditorDocument()
    document.set_project(project)
    return document, town, cave


def _e(scene, name):
    return next(e for e in scene.entities() if e.name == name)


def test_drop_on_an_entity_parents_it_and_keeps_its_world_position():
    document, town, _ = _project()
    hero, cart = _e(town, "Hero"), _e(town, "Cart")
    drop_entities(document, [hero], "entity", cart, "on")
    assert hero.get(Transform).parent_id == cart.id and world_position(hero) == (10.0, 0.0)
    document.undo()
    assert hero.get(Transform).parent_id == "" and hero.get(Transform).x == 10.0


def test_drop_above_or_below_reorders_and_matches_the_siblings_parent():
    document, town, _ = _project()
    hero, cart, lamp = (_e(town, n) for n in ("Hero", "Cart", "Lamp"))
    drop_entities(document, [hero], "entity", cart, "on")
    drop_entities(document, [lamp], "entity", hero, "below")
    assert [e.name for e in town.entities()] == ["Hero", "Lamp", "Cart"]
    assert lamp.get(Transform).parent_id == cart.id  # dropped next to a child → same parent
    drop_entities(document, [lamp], "entity", hero, "above")
    assert [e.name for e in town.entities()] == ["Lamp", "Hero", "Cart"] and lamp.get(
        Transform
    ).parent_id == cart.id
    with pytest.raises(HierarchyEditError):  # next to its own child would make it its own parent
        drop_entities(document, [cart], "entity", hero, "above")


def test_drop_on_a_scene_moves_and_unparents_as_one_undo_step():
    document, town, cave = _project()
    hero, cart = _e(town, "Hero"), _e(town, "Cart")
    drop_entities(document, [hero], "entity", cart, "on")
    drop_entities(document, [hero, cart], "scene", cave)
    assert {e.name for e in cave.entities()} == {"Hero", "Cart"} and hero.get(
        Transform
    ).parent_id == ""
    document.undo()
    assert {e.name for e in town.entities()} == {"Hero", "Cart", "Lamp"} and hero.get(
        Transform
    ).parent_id == cart.id


def test_a_cycle_is_refused_and_nothing_changes():
    document, town, _ = _project()
    hero, cart = _e(town, "Hero"), _e(town, "Cart")
    drop_entities(document, [hero], "entity", cart, "on")
    before = [(e.name, e.get(Transform).parent_id) for e in town.entities()]
    with pytest.raises(HierarchyEditError):
        drop_entities(document, [cart], "entity", hero, "on")
    assert [(e.name, e.get(Transform).parent_id) for e in town.entities()] == before


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    document, town, cave = _project()
    value = AsteriaEditorWindow(document.project)
    yield value
    value.document.mark_saved()
    value.close()
    app.processEvents()


def _tree_item(tree, kind, name):
    from PySide6.QtCore import Qt

    def walk(item):
        payload = item.data(0, Qt.UserRole)
        if payload and payload[0] == kind and getattr(payload[1], "name", None) == name:
            return item
        for i in range(item.childCount()):
            found = walk(item.child(i))
            if found is not None:
                return found
        return None

    return next(
        x for x in (walk(tree.topLevelItem(i)) for i in range(tree.topLevelItemCount())) if x
    )


def test_the_project_tree_applies_a_real_drop_event_to_the_model(window):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QDropEvent

    tree = window.project_tree.tree
    town = window.document.project.scenes()[0]
    tree.clearSelection()
    _tree_item(tree, "entity", "Hero").setSelected(True)
    window.show()
    tree.expandAll()
    target = _tree_item(tree, "entity", "Cart")
    point = tree.visualItemRect(target).center()
    mime = tree.mimeData(tree.selectedItems())
    event = QDropEvent(QPointF(point), Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
    tree.dropEvent(event)
    hero, cart = _e(town, "Hero"), _e(town, "Cart")
    assert (
        hero.get(Transform).parent_id == cart.id
    )  # the drop changed the scene, not only the tree items
    hero_item = _tree_item(window.project_tree.tree, "entity", "Hero")
    assert hero_item.parent().text(0) == "Cart"  # tree rebuilt from the model
    window.document.undo()
    assert hero.get(Transform).parent_id == ""


def test_record_lists_sort_by_id_or_name(window):
    from pathlib import Path

    ref = (
        Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"
    )
    window.document.set_project(
        Project.load_json(ref, window.document.component_registry), file_path=ref
    )
    window.refresh_all()
    window.rpg_authoring.rebuild()
    family = window.rpg_authoring.child
    family.category.setCurrentIndex(family.category.findData("enemies"))
    by_id = list(family._ids)
    assert by_id == sorted(by_id)
    family.sort.setCurrentText("ID Z→A")
    assert family._ids == by_id[::-1]
    family.sort.setCurrentText("Name A→Z")
    names = [family._display_name(k) for k in family._ids]
    assert names == sorted(names, key=str.lower)
