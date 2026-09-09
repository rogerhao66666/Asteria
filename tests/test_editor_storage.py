from asteria.core import Scene,Entity,Transform
from asteria.project import Project
from asteria.editor.model import EditorDocument
from asteria.editor.storage import save_document,load_document

def make_project():
    p=Project("Save Test")
    s=p.add_scene(Scene("Town"))
    e=s.add_entity(Entity("Hero"))
    e.add_component(Transform(12,34))
    return p

def test_save_and_load_document_roundtrip(tmp_path):
    doc=EditorDocument(make_project())
    path=tmp_path/"game.asteria.json"
    save_document(doc,path)
    assert path.exists()
    assert doc.file_path==path.resolve()
    assert not doc.dirty

    doc.project.name="Mutated outside command for setup"
    load_document(doc,path)
    assert doc.project.name=="Save Test"
    hero=doc.project.scenes()[0].entities()[0]
    assert hero.get(Transform).x==12
    assert not doc.dirty
    assert not doc.commands.can_undo

def test_save_marks_exact_current_history_state(tmp_path):
    doc=EditorDocument(make_project())
    old=doc.project.name
    from asteria.editor.commands import RenameCommand
    doc.execute(RenameCommand(doc.project,"Renamed",old))
    assert doc.dirty
    save_document(doc,tmp_path/"p.json")
    assert not doc.dirty
    doc.undo()
    assert doc.dirty
    doc.redo()
    assert not doc.dirty
