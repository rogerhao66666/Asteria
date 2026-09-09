from asteria.core import Scene,Entity
from asteria.editor.model import EditorDocument
from asteria.editor.hierarchy import build_reorder_entity_command,build_move_entity_to_scene_command

def names(scene):
    return [e.name for e in scene.entities()]

def test_reorder_entity_is_reversible():
    s=Scene("Town")
    a=s.add_entity(Entity("A"))
    b=s.add_entity(Entity("B"))
    c=s.add_entity(Entity("C"))
    doc=EditorDocument()
    doc.execute(build_reorder_entity_command(c,0))
    assert names(s)==["C","A","B"]
    doc.undo()
    assert names(s)==["A","B","C"]
    doc.redo()
    assert names(s)==["C","A","B"]

def test_move_entity_between_scenes_preserves_identity_and_undo():
    a=Scene("A"); b=Scene("B")
    e=a.add_entity(Entity("Hero"))
    a.add_entity(Entity("NPC"))
    doc=EditorDocument()
    doc.execute(build_move_entity_to_scene_command(e,b))
    assert e.scene is b and names(a)==["NPC"] and names(b)==["Hero"]
    doc.undo()
    assert e.scene is a and names(a)==["Hero","NPC"] and names(b)==[]
    doc.redo()
    assert e.scene is b

def test_same_scene_move_uses_reorder():
    s=Scene()
    a=s.add_entity(Entity("A")); b=s.add_entity(Entity("B"))
    doc=EditorDocument()
    doc.execute(build_move_entity_to_scene_command(a,s,1))
    assert names(s)==["B","A"]
