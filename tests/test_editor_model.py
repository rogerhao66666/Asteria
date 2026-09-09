from asteria.core import Entity, Scene, Transform
from asteria.editor.model import EditorDocument


def test_editor_document_uses_runtime_objects_directly():
    scene = Scene("Town")
    entity = scene.add_entity(Entity("Hero"))
    comp = entity.add_component(Transform(3.0, 4.0))
    doc = EditorDocument()
    doc.select_scene(scene)
    assert doc.selection.value is scene
    doc.select_entity(entity)
    assert doc.selection.value is entity
    doc.select_component(comp)
    assert doc.selection.value is comp
