from asteria.editor.commands import CommandStack,SetAttributeCommand

class X:
    value=1

def test_command_stack_execute_undo_redo_and_branch():
    x=X(); stack=CommandStack()
    stack.execute(SetAttributeCommand(x,'value',2,1,'change value'))
    assert x.value==2 and stack.can_undo and not stack.can_redo
    assert stack.undo() and x.value==1 and stack.can_redo
    assert stack.redo() and x.value==2
    assert stack.undo()
    stack.execute(SetAttributeCommand(x,'value',3,1))
    assert x.value==3 and not stack.can_redo
