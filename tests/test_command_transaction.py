from dataclasses import dataclass

import pytest

from asteria.editor.commands import CommandTransaction
from asteria.editor.model import EditorDocument


@dataclass
class Box:
    value: int = 0


class Set:
    def __init__(self, b, v):
        self.b = b
        self.old = b.value
        self.new = v

    @property
    def label(self):
        return "Set"

    def redo(self):
        self.b.value = self.new

    def undo(self):
        self.b.value = self.old


class Fail:
    @property
    def label(self):
        return "Fail"

    def redo(self):
        raise RuntimeError("boom")

    def undo(self):
        pass


def test_transaction_one_history_entry():
    b = Box()
    doc = EditorDocument()
    doc.execute(CommandTransaction("Batch", [Set(b, 1), Set(b, 2)]))
    assert b.value == 2
    doc.undo()
    assert b.value == 0
    doc.redo()
    assert b.value == 2


def test_transaction_rolls_back_partial_failure():
    b = Box()
    with pytest.raises(RuntimeError):
        CommandTransaction("Fail", [Set(b, 1), Fail()]).redo()
    assert b.value == 0
