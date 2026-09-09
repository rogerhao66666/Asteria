from asteria.core import Scene,Entity
from asteria.project import Project
from asteria.editor.model import EditorDocument
from asteria.editor.viewport import selected_scene

def test_selected_scene_follows_entity_selection():
    p=Project("G")
    a=p.add_scene(Scene("A"))
    b=p.add_scene(Scene("B"))
    e=b.add_entity(Entity("Hero"))
    doc=EditorDocument(project=p)
    doc.select_entity(e)
    assert selected_scene(doc) is b

def test_selected_scene_falls_back_to_startup_scene():
    p=Project("G")
    a=p.add_scene(Scene("A"))
    p.add_scene(Scene("B"))
    doc=EditorDocument(project=p)
    assert selected_scene(doc) is a
