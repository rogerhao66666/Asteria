"""PySide6 6.12 segfaults when its garbage collector frees a cycle between a widget and a
child widget that keeps it in an attribute (CI crashed in test_picture_fields). A child holds
its owner weakly, so the owner is freed by reference counting alone."""

import gc
import weakref

import pytest


@pytest.fixture
def app():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _freed_without_the_collector(make):
    gc.collect()
    gc.disable()
    try:
        gone = weakref.ref(make())
        return gone() is None
    finally:
        gc.enable()


def test_an_icon_picker_is_freed_without_the_cycle_collector(app):
    from asteria.editor.game_systems_widget import _IconPicker

    def make():
        picker = _IconPicker(None)
        assert picker.combo._owner() is picker
        return picker

    assert _freed_without_the_collector(make)


def test_the_project_tree_is_freed_without_the_cycle_collector(app):
    from asteria.editor import EditorDocument
    from asteria.editor.widgets import ProjectTreeWidget

    document = EditorDocument()

    def make():
        panel = ProjectTreeWidget(document)
        assert panel.tree._owner() is panel
        return panel

    assert _freed_without_the_collector(make)
