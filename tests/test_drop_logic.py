from asteria.core import Entity, Scene
from asteria.editor.drop_logic import build_hierarchy_drop_intent
from asteria.editor.model import EditorDocument
from asteria.project import Project


def names(scene):
    return [e.name for e in scene.entities()]


def test_entity_drop_to_other_scene_builds_real_command():
    p = Project("G")
    a = p.add_scene(Scene("A"))
    b = p.add_scene(Scene("B"))
    e = a.add_entity(Entity("Hero"))
    doc = EditorDocument(project=p)
    intent = build_hierarchy_drop_intent(p, "entity", e, "scene", b)
    doc.execute(intent.command)
    assert e.scene is b
    doc.undo()
    assert e.scene is a


def test_entity_drop_on_entity_reorders_canonical_scene():
    p = Project("G")
    s = p.add_scene(Scene("S"))
    a = s.add_entity(Entity("A"))
    s.add_entity(Entity("B"))
    c = s.add_entity(Entity("C"))
    doc = EditorDocument(project=p)
    intent = build_hierarchy_drop_intent(p, "entity", c, "entity", a)
    doc.execute(intent.command)
    assert names(s) == ["C", "A", "B"]
