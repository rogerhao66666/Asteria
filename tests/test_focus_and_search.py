"""Focus Mode folds both sides away and brings them back; Search Everything (Ctrl+K) finds
pages, records, scenes and entities by name or id and opens them."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

DEMO = Path(__file__).resolve().parents[1] / "reference_projects/full_verification_demo"


@pytest.fixture
def window(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project
    from asteria.runtime.component_registry import default_component_registry

    app = QApplication.instance() or QApplication([])
    project = Project.load_json(DEMO / "project.asteria.json", default_component_registry())
    value = AsteriaEditorWindow(project)
    value.document.file_path = DEMO / "project.asteria.json"
    value._resolve_project_resources()
    value.refresh_all()
    value.resize(1400, 900)
    value.show()
    app.processEvents()
    yield value
    value.document.mark_saved()
    value.runtime_monitor.stop()
    value.close()
    value.deleteLater()


def test_focus_mode_folds_both_sides_and_brings_them_back(window):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QDockWidget

    from asteria.editor.project.workspace import WorkspaceMode

    sides = (Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea)

    def side_docks():
        return [
            d
            for d in window.findChildren(QDockWidget)
            if d.isVisible() and not d.isFloating() and window.dockWidgetArea(d) in sides
        ]

    before = side_docks()
    assert before  # the Scene workspace has its Project and Inspector panels
    assert window.focus_mode_action.shortcut().toString() == "Ctrl+\\"
    window.focus_mode_action.trigger()
    QApplication.processEvents()
    assert not side_docks() and window.focus_mode_action.isChecked()
    window.focus_mode_action.trigger()  # the same key again
    QApplication.processEvents()
    assert side_docks() == before and not window.focus_mode_action.isChecked()
    # a record page: its list and preview fold away too
    window.workspace.set_mode(WorkspaceMode.RPG)
    QApplication.processEvents()
    family = window.rpg_authoring.child
    panel = next(
        w
        for w in family.findChildren(object)
        if getattr(w, "property", None) and w.property("sidePanel")
    )
    assert panel.isVisible()
    window.set_focus_mode(True)
    assert not panel.isVisible()
    window.workspace.set_mode(WorkspaceMode.SCENE)  # another workspace: everything back
    window.workspace.set_mode(WorkspaceMode.RPG)
    QApplication.processEvents()
    assert panel.isVisible() and not window.focus_mode_action.isChecked()


def test_search_everything_finds_and_opens(window):
    from asteria.editor.project.global_search import matches, open_entry, search_entries
    from asteria.editor.project.workspace import WorkspaceMode

    assert window.search_action.shortcut().toString() == "Ctrl+K"
    entries = search_entries(window)
    roger = matches(entries, "roger")
    assert roger and roger[0].title == "Roger"
    assert roger[0].target[:3] == ("record", "rpg", "actors")
    assert matches(entries, "hero_01 actors")[0].title == "Roger"  # by id, words in any order
    assert any(e.detail.startswith("Game Systems ▸") for e in matches(entries, "shop"))
    assert any(e.detail.startswith("Entity") for e in matches(entries, "player"))
    page = matches(entries, "game start")[0]
    assert page.detail.startswith("Page") and open_entry(window, page)
    assert window.workspace.mode == WorkspaceMode.RPG
    assert window.rpg_workspace.currentWidget() is window.game_start_editor
    assert open_entry(window, roger[0])
    assert window.rpg_authoring.child.selected_ids == ["hero_01"]
    dialog = window.open_global_search(run=False)
    dialog.field.setText("roger")
    assert dialog.results.count() >= 1
    assert dialog.results.currentItem().data(0x0100).title == "Roger"
    dialog.close()


def test_scene_tabs_follow_the_scenes_opened(window):
    from PySide6.QtWidgets import QApplication

    tabs = window.scene_tabs
    project = window.document.project
    first, second = list(project.scenes())[:2]
    window.show_scene(first)
    window.show_scene(second)
    QApplication.processEvents()
    assert tabs.scene_ids()[-2:] == [first.id, second.id]
    assert tabs.bar.tabData(tabs.bar.currentIndex()) == second.id
    tabs.bar.tabBarClicked.emit(tabs.scene_ids().index(first.id))  # a click opens its scene
    QApplication.processEvents()
    assert window.viewport.current_scene().id == first.id
    tabs._fill_menu()  # ▾ lists every scene, the open ones ticked
    assert len(tabs.menu.actions()) == len(list(project.scenes()))
    while tabs.bar.count() > 1:
        tabs.close_tab(0)  # a tab closes; the scene stays in the project
    assert tabs.bar.count() == 1
    tabs.close_tab(0)  # the last tab stays: a scene is always shown
    assert tabs.bar.count() == 1
    assert len(list(project.scenes())) == len(tabs.menu.actions())
    assert window.viewport.current_scene().id == tabs.scene_ids()[0]
