from asteria.editor.commands import SetAttributeCommand
from asteria.editor.model import EditorDocument


class X:
    value = 1


def test_dirty_state_uses_history_identity_not_revision_depth():
    x = X()
    doc = EditorDocument()
    doc.execute(SetAttributeCommand(x, "value", 2, 1, "A"))
    doc.mark_saved()
    saved = doc.saved_state_id
    assert not doc.dirty

    assert doc.undo()
    assert doc.dirty
    doc.execute(SetAttributeCommand(x, "value", 3, 1, "B"))
    assert doc.commands.current_state_id != saved
    assert doc.dirty


def test_undo_back_to_exact_saved_state_becomes_clean():
    x = X()
    doc = EditorDocument()
    doc.execute(SetAttributeCommand(x, "value", 2, 1))
    doc.mark_saved()
    doc.execute(SetAttributeCommand(x, "value", 3, 2))
    assert doc.dirty
    doc.undo()
    assert not doc.dirty
