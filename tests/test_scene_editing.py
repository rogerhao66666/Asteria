from asteria.core import Scene
from asteria.project import Project
from asteria.editor.model import EditorDocument
from asteria.editor.scenes import build_add_scene_command,build_remove_scene_command,build_reorder_scene_command

def scene_names(p): return [s.name for s in p.scenes()]

def test_scene_add_remove_reorder_are_reversible():
    p=Project("Game")
    a=p.add_scene(Scene("A"))
    b=p.add_scene(Scene("B"))
    doc=EditorDocument(project=p)

    add=build_add_scene_command(p,"C")
    doc.execute(add)
    assert scene_names(p)==["A","B","C"]
    doc.undo(); assert scene_names(p)==["A","B"]
    doc.redo(); assert scene_names(p)==["A","B","C"]

    reorder=build_reorder_scene_command(p,add.scene,0)
    doc.execute(reorder)
    assert scene_names(p)==["C","A","B"]
    doc.undo(); assert scene_names(p)==["A","B","C"]

    remove=build_remove_scene_command(p,b)
    doc.execute(remove)
    assert scene_names(p)==["A","C"]
    doc.undo()
    assert scene_names(p)==["A","B","C"]

def test_remove_startup_scene_restores_startup_on_undo():
    p=Project("Game")
    a=p.add_scene(Scene("A"))
    b=p.add_scene(Scene("B"))
    p.startup_scene_id=b.id
    doc=EditorDocument(project=p)
    cmd=build_remove_scene_command(p,b)
    doc.execute(cmd)
    assert p.startup_scene_id==a.id
    doc.undo()
    assert p.startup_scene_id==b.id
