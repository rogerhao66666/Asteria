from asteria.core import Scene,Entity,Transform
from asteria.editor.model import EditorDocument
from asteria.editor.structure import (
    build_rename_command,build_add_entity_command,build_remove_entity_command,
    build_add_component_command,build_remove_component_command
)

def test_rename_is_reversible():
    scene=Scene("Town"); doc=EditorDocument()
    doc.execute(build_rename_command(scene,"Village"))
    assert scene.name=="Village"
    assert doc.undo() and scene.name=="Town"
    assert doc.redo() and scene.name=="Village"

def test_add_remove_entity_preserves_identity_across_undo_redo():
    scene=Scene("Town"); doc=EditorDocument()
    add=build_add_entity_command(scene,"NPC")
    entity=add.entity
    doc.execute(add)
    assert scene.entities()==(entity,) and entity.scene is scene
    doc.undo()
    assert scene.entities()==() and entity.scene is None
    doc.redo()
    assert scene.entities()==(entity,) and entity.scene is scene

    remove=build_remove_entity_command(entity)
    doc.execute(remove)
    assert entity.scene is None and scene.entities()==()
    doc.undo()
    assert entity.scene is scene and scene.entities()==(entity,)

def test_component_structural_edit_preserves_component_identity():
    entity=Entity("Hero"); doc=EditorDocument()
    add=build_add_component_command(entity,Transform)
    comp=add.component
    doc.execute(add)
    assert entity.get(Transform) is comp and comp.attached
    doc.undo()
    assert not entity.has(Transform) and not comp.attached
    doc.redo()
    assert entity.get(Transform) is comp and comp.attached

    remove=build_remove_component_command(comp)
    doc.execute(remove)
    assert not entity.has(Transform) and not comp.attached
    doc.undo()
    assert entity.get(Transform) is comp and comp.attached
