from asteria.core import ComponentRegistry, Entity, Scene, Transform
from asteria.editor.clipboard import (
    EditorClipboard,
    build_duplicate_entity_command,
    build_paste_entity_command,
)
from asteria.editor.model import EditorDocument


def registry():
    r = ComponentRegistry()
    r.register(Transform)
    return r


def test_duplicate_is_deep_and_has_fresh_identity():
    r = registry()
    s = Scene("Town")
    e = s.add_entity(Entity("Hero"))
    e.add_component(Transform(2, 3))
    doc = EditorDocument(component_registry=r)
    cmd = build_duplicate_entity_command(e, r)
    dup = cmd.duplicate_entity
    assert dup.id != e.id and dup.name == "Hero Copy"
    assert dup.get(Transform) is not e.get(Transform)
    doc.execute(cmd)
    assert len(s.entities()) == 2
    doc.undo()
    assert s.entities() == (e,)
    doc.redo()
    assert len(s.entities()) == 2


def test_clipboard_is_serialized_snapshot():
    r = registry()
    src = Scene("Src")
    dst = Scene("Dst")
    e = src.add_entity(Entity("NPC"))
    e.add_component(Transform(5, 6))
    cb = EditorClipboard()
    cb.copy_entity(e)
    e.get(Transform).x = 99
    cmd = build_paste_entity_command(dst, cb, r)
    assert cmd.entity.get(Transform).x == 5
    assert cmd.entity.id != e.id
