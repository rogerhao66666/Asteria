import pytest
from asteria.core import Component
from asteria.core.metadata import Field,component_schema
from asteria.core import Transform
from asteria.editor.editing import build_set_component_field_command,EditError
from asteria.editor.model import EditorDocument

@component_schema(fields=(Field('mode',str,'a',choices=('a','b')),Field('level',int,1,minimum=1,maximum=5),Field('live',float,0.0,serialize=False)))
class Demo(Component):
    def __init__(self):
        super().__init__(); self.mode='a'; self.level=1; self.live=0.0

def test_edit_validate_execute_undo_redo():
    t=Transform(1.0,2.0); doc=EditorDocument()
    cmd=build_set_component_field_command(t,'x','8.5')
    assert t.x==1.0
    doc.execute(cmd); assert t.x==8.5 and doc.dirty
    doc.undo(); assert t.x==1.0 and not doc.dirty
    doc.redo(); assert t.x==8.5 and doc.dirty

def test_constraints_reject_without_modification():
    c=Demo()
    with pytest.raises(EditError): build_set_component_field_command(c,'level','9')
    with pytest.raises(EditError): build_set_component_field_command(c,'mode','c')
    with pytest.raises(EditError): build_set_component_field_command(c,'live','2.0')
    assert (c.level,c.mode,c.live)==(1,'a',0.0)
