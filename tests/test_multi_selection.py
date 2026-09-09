from asteria.core import Entity
from asteria.editor.model import EditorDocument


def test_multi_selection_is_homogeneous_data():
    doc = EditorDocument()
    a = Entity("A")
    b = Entity("B")
    doc.select_many("entity", [a, b])
    assert doc.selection.multiple
    assert doc.selection.kind == "entity"
    assert doc.selection.value is None
    assert doc.selection.values == (a, b)


def test_single_selection_uses_same_values_contract():
    doc = EditorDocument()
    a = Entity("A")
    doc.select_entity(a)
    assert not doc.selection.multiple
    assert doc.selection.value is a
    assert doc.selection.values == (a,)
