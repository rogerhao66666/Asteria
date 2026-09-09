from asteria.core import Scene,Entity,Transform
from asteria.editor.gizmo import GridSnap,SelectionRect,entities_in_screen_rect,build_move_entities_command
from asteria.editor.viewport import ViewportCamera,scene_markers
from asteria.editor.model import EditorDocument

def test_grid_snap():
    s=GridSnap(True,16)
    assert s.point(17,31)==(16,32)
    assert GridSnap(False,16).point(17,31)==(17,31)

def test_rectangle_selection_uses_screen_markers():
    scene=Scene()
    a=scene.add_entity(Entity("A"));a.add_component(Transform(10,10))
    b=scene.add_entity(Entity("B"));b.add_component(Transform(100,100))
    markers=scene_markers(scene,ViewportCamera())
    got=entities_in_screen_rect(markers,SelectionRect(0,0,30,30))
    assert got==(a,)

def test_move_entities_is_one_undoable_transaction():
    scene=Scene()
    a=scene.add_entity(Entity("A"));a.add_component(Transform(10,10))
    b=scene.add_entity(Entity("B"));b.add_component(Transform(20,20))
    doc=EditorDocument()
    cmd=build_move_entities_command((a,b),9,9,GridSnap(True,16))
    doc.execute(cmd)
    assert (a.get(Transform).x,a.get(Transform).y)==(16,16)
    assert (b.get(Transform).x,b.get(Transform).y)==(32,32)
    doc.undo()
    assert (a.get(Transform).x,a.get(Transform).y)==(10,10)
    assert (b.get(Transform).x,b.get(Transform).y)==(20,20)
