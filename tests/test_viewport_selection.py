from asteria.core import Entity, Scene
from asteria.editor.model import EditorDocument
from asteria.editor.viewport import selected_scene
from asteria.project import Project


def test_selected_scene_follows_entity_selection():
    p = Project("G")
    p.add_scene(Scene("A"))
    b = p.add_scene(Scene("B"))
    e = b.add_entity(Entity("Hero"))
    doc = EditorDocument(project=p)
    doc.select_entity(e)
    assert selected_scene(doc) is b


def test_selected_scene_falls_back_to_startup_scene():
    p = Project("G")
    a = p.add_scene(Scene("A"))
    p.add_scene(Scene("B"))
    doc = EditorDocument(project=p)
    assert selected_scene(doc) is a


def test_the_project_tree_marks_every_entity_of_a_box_selection(monkeypatch):
    """The tree marked items before they were in it, so a box selection showed only its first
    entity there (the Inspector said "3 selected")."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.widgets import ProjectTreeWidget

    QApplication.instance() or QApplication([])
    p = Project("G")
    scene = p.add_scene(Scene("A"))
    heroes = [scene.add_entity(Entity(name)) for name in ("Ann", "Bo", "Cy")]
    scene.add_entity(Entity("Dee"))
    doc = EditorDocument(project=p)
    doc.select_many("entity", heroes)
    tree = ProjectTreeWidget(doc)
    tree.refresh()
    marked = sorted(i.text(0) for i in tree.tree.selectedItems())
    assert marked == ["Ann", "Bo", "Cy"]
    tree.deleteLater()
