"""An edit rebuilds only the tab on screen; the other tabs are rebuilt when they are next opened,
and show the edit then."""

from pathlib import Path

import pytest

from asteria.rpg.localization import LocaleTable

DEMO = Path(__file__).resolve().parents[1] / "reference_projects/full_verification_demo"


def test_a_locale_table_finds_its_keys_and_only_its_keys():
    table = LocaleTable("zh-TW", {"data.b": "乙", "data.a": "甲", "data.ab": "甲乙"})
    assert table.get("data.a") == "甲"
    assert table.get("data.ab") == "甲乙"
    assert table.get("data.b") == "乙"
    for missing in ("data", "data.aa", "data.c", "zzz", "", None, 3):
        assert table.get(missing) is None
    assert LocaleTable("en").get("data.a") is None


@pytest.fixture
def window(monkeypatch):
    pytest.importorskip("PySide6")
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


@pytest.fixture
def rebuilt(window, monkeypatch):
    """The names of the pages rebuilt from here on."""
    names = []
    original = window._rebuild_page

    def spy(name):
        names.append(name)
        original(name)

    monkeypatch.setattr(window, "_rebuild_page", spy)
    return names


def _open(window, mode, tabs, page):
    window.workspace.set_mode(mode)
    tabs.setCurrentWidget(page)


def _listed_trees(page):
    from asteria.editor.ui_fit import named_id

    return [named_id(page.tree_list.item(i)) for i in range(page.tree_list.count())]


def _on_behavior_trees(window):
    from asteria.editor.workspace import WorkspaceMode

    _open(window, WorkspaceMode.RPG, window.rpg_workspace, window.behavior_tree_editor)
    return window.behavior_tree_editor


def _node_with_settings(page):
    return next(path for path, node in page.api.get(page.tree_id).root.walk() if node.params)


def test_apply_parameters_rebuilds_only_the_page_it_is_on(window, rebuilt):
    page = _on_behavior_trees(window)
    page.select_node(_node_with_settings(page))
    rebuilt.clear()
    assert page.apply_params()  # what the Apply Parameters button does
    assert page.last_error is None
    assert rebuilt == ["behavior_tree_editor"]


def test_a_tab_is_rebuilt_when_opened_and_shows_what_changed_while_hidden(window, rebuilt):
    from asteria.editor.workspace import WorkspaceMode

    trees = window.behavior_tree_editor
    _open(window, WorkspaceMode.RPG, window.rpg_workspace, window.enemy_ai_editor)
    trees.api.create("made_while_hidden")
    window.refresh_all()
    assert "made_while_hidden" not in _listed_trees(trees)  # it waits
    rebuilt.clear()
    window.rpg_workspace.setCurrentWidget(trees)
    assert rebuilt == ["behavior_tree_editor"]
    assert "made_while_hidden" in _listed_trees(trees)


def test_going_back_to_a_tab_with_nothing_changed_rebuilds_nothing(window, rebuilt):
    from asteria.editor.workspace import WorkspaceMode

    _open(window, WorkspaceMode.RPG, window.rpg_workspace, window.enemy_ai_editor)
    window.rpg_workspace.setCurrentWidget(window.behavior_tree_editor)
    rebuilt.clear()
    window.rpg_workspace.setCurrentWidget(window.enemy_ai_editor)
    window.rpg_workspace.setCurrentWidget(window.behavior_tree_editor)
    assert rebuilt == []
    window.workspace.set_mode(WorkspaceMode.SCENE)
    window.workspace.set_mode(WorkspaceMode.RPG)
    assert rebuilt == []


def test_an_undo_reaches_a_tab_hidden_at_the_time(window):
    from asteria.editor.workspace import WorkspaceMode

    trees = window.behavior_tree_editor
    _open(window, WorkspaceMode.RPG, window.rpg_workspace, trees)
    trees.api.create("undone_while_hidden")
    window.refresh_all()
    assert "undone_while_hidden" in _listed_trees(trees)
    window.rpg_workspace.setCurrentWidget(window.enemy_ai_editor)
    window.undo()
    window.rpg_workspace.setCurrentWidget(trees)
    assert "undone_while_hidden" not in _listed_trees(trees)


def test_a_tab_brought_forward_in_a_closed_workspace_waits_for_it(window, rebuilt):
    from asteria.editor.workspace import WorkspaceMode

    window.workspace.set_mode(WorkspaceMode.SCENE)
    window.refresh_all()  # everything in the other workspaces is out of date
    rebuilt.clear()
    window.rpg_workspace.setCurrentWidget(window.input_map_editor)
    assert rebuilt == []
    window.workspace.set_mode(WorkspaceMode.RPG)
    assert rebuilt == ["input_map_editor"]


@pytest.mark.parametrize(
    "mode, tabs, first, second",
    [
        ("UI", "ui_workspace", "vfx_editor", "animation_editor"),
        ("EVENT", "events_workspace", "event_flow_editor", "game_flow_overview"),
    ],
)
def test_the_other_workspaces_with_tabs_wait_too(window, rebuilt, mode, tabs, first, second):
    from asteria.editor.workspace import WorkspaceMode

    bar = getattr(window, tabs)
    _open(window, WorkspaceMode[mode], bar, getattr(window, first))
    window.refresh_all()
    rebuilt.clear()
    window.refresh_all()
    assert rebuilt == [first]
    rebuilt.clear()
    bar.setCurrentWidget(getattr(window, second))
    assert rebuilt == [second]


def test_another_project_reaches_every_tab_without_opening_them(window):
    from asteria.project import Project

    trees = window.behavior_tree_editor
    assert _listed_trees(trees)
    window.set_project(Project("Empty"))
    assert _listed_trees(trees) == []
    assert window.rpg_authoring.project_id[0] == id(window.document.project)


@pytest.fixture
def forms_built(window, monkeypatch):
    """The records whose form is built from here on (a form cleared is not counted)."""
    from asteria.editor.record_form import RecordForm

    names = []
    original = RecordForm._rebuild

    def spy(form):
        if form._data is not None:
            names.append(form._title)
        original(form)

    monkeypatch.setattr(RecordForm, "_rebuild", spy)
    return names


def _on_enemy_ai(window, ai_id=None):
    from asteria.editor.workspace import WorkspaceMode

    page = window.enemy_ai_editor
    _open(window, WorkspaceMode.RPG, window.rpg_workspace, page)
    ids = sorted(page.api.ai_ids())
    assert len(ids) > 1
    chosen = ai_id or ids[-1]  # not the first: nothing lands on it by chance
    assert page.select_ai(chosen)
    return page, chosen


def test_choosing_an_enemy_ai_builds_its_form_once(window, forms_built):
    page, chosen = _on_enemy_ai(window)
    other = sorted(page.api.ai_ids())[0]
    forms_built.clear()
    assert page.select_ai(other)
    assert forms_built == [other]
    assert page.family.editor._data is not None


def test_a_refresh_with_nothing_changed_keeps_the_enemy_ai_form(window, forms_built):
    page, chosen = _on_enemy_ai(window)
    form_page = page.family.editor.widget()
    forms_built.clear()
    page.refresh()
    window.refresh_all()
    assert forms_built == []
    assert page.ai_id == chosen and page.family.browser.currentRow() >= 0
    assert page.family.editor.widget() is form_page


def test_an_edit_elsewhere_builds_the_enemy_ai_form_once_with_the_new_data(window, forms_built):
    page, chosen = _on_enemy_ai(window)
    stored = page.api.get(chosen)
    assert stored.rules
    window.behavior_tree_editor.api.create("an_edit_elsewhere")  # the names it picks from
    forms_built.clear()
    window.refresh_all()
    assert forms_built == [chosen]
    assert page.ai_id == chosen
    assert len(page.family.editor._data["rules"]) == len(stored.rules)


def test_binding_an_enemy_shows_at_once_and_stays_chosen(window):
    page, chosen = _on_enemy_ai(window)
    enemy = page.enemy.itemData(0)
    assert page.bind_enemy(enemy)
    assert page.ai_id == chosen
    assert page._names().get(enemy, enemy) in page.used_by.text()


def test_a_new_language_builds_the_form_again(window, forms_built, monkeypatch):
    from asteria.editor.i18n import CURRENT

    page, chosen = _on_enemy_ai(window)
    forms_built.clear()
    monkeypatch.setitem(CURRENT, "language", "zh_TW")
    page.refresh()
    assert forms_built == [chosen]


def test_a_list_with_nothing_left_empties_the_form(window):
    page, _chosen = _on_enemy_ai(window)
    family = page.family
    family.search.setText("no record is called this")
    family.refresh()
    assert family.selected_id is None and family.editor._data is None
    family.search.clear()
    family.refresh()
    assert family.selected_id is not None and family.editor._data is not None


def _on_game_data(window, rows=(3,)):
    from asteria.editor.workspace import WorkspaceMode

    _open(window, WorkspaceMode.RPG, window.rpg_workspace, window.rpg_authoring)
    family = window.rpg_authoring.child
    assert len(family._ids) > max(rows)
    family.select_ids([family._ids[row] for row in rows])
    return family, family.selected_ids


def test_game_data_stays_on_its_record_through_a_refresh(window):
    family, chosen = _on_game_data(window)
    window.refresh_all()
    assert family.selected_ids == chosen and family.browser.currentRow() == 3
    assert family.editor._title == chosen[0]


def test_game_data_is_still_on_its_record_when_opened_after_an_edit(window):
    family, chosen = _on_game_data(window)
    window.rpg_workspace.setCurrentWidget(window.behavior_tree_editor)
    window.behavior_tree_editor.api.create("an_edit_elsewhere")
    window.refresh_all()
    window.rpg_workspace.setCurrentWidget(window.rpg_authoring)
    assert family.selected_ids == chosen and family.editor._title == chosen[0]


def test_game_data_keeps_several_records_selected(window):
    family, chosen = _on_game_data(window, rows=(1, 2, 4))
    assert len(chosen) == 3
    window.refresh_all()
    assert family.selected_ids == chosen


def test_game_data_opens_on_the_first_record_when_its_record_is_gone(window):
    family, chosen = _on_game_data(window)
    family.delete_selected()
    window.refresh_all()
    assert chosen[0] not in family._ids
    assert family.selected_ids == [family._ids[0]]
