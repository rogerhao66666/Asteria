import pytest

from asteria.core import Scene
from asteria.project import Project


def test_visible_family_host_hides_old_placeholder_before_deferred_delete():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.workspace import WorkspaceMode

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    window.show()
    window.workspace.set_mode(WorkspaceMode.RPG)
    app.processEvents()
    old_placeholder = window.rpg_authoring.child
    assert old_placeholder.isVisible()

    project = Project("Visible Replacement")
    project.add_scene(Scene("Main"))
    window.document.set_project(project)
    window.refresh_all()
    app.processEvents()

    assert old_placeholder.isHidden()
    assert window.rpg_authoring.child is not old_placeholder
    window.close()
    app.processEvents()
