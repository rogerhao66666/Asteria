"""CB10 / EDT-13, EDT-14: record list multi-select, filter, context menu, clipboard shortcuts,
batch edit (GUI)."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

REF = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"


@pytest.fixture
def window():
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project

    app = QApplication.instance() or QApplication([])
    value = AsteriaEditorWindow(None)
    project = Project.load_json(REF, value.document.component_registry)
    value.document.set_project(project, file_path=REF)
    value.refresh_all()
    value.rpg_authoring.rebuild()
    yield value
    value.document.mark_saved()
    value.close()
    app.processEvents()


def _items_family(window):
    family = window.rpg_authoring.child
    family.category.setCurrentIndex(family.category.findData("items"))
    return family


def test_filter_multi_select_copy_paste_and_undo_in_the_record_list(window):
    family = _items_family(window)
    everything = list(family._ids)
    family.search.setText("leaf")
    assert (
        family._ids
        and all("leaf" in key for key in family._ids)
        and len(family._ids) < len(everything)
    )
    family.search.clear()
    family.select_ids(everything[:2])
    assert family.selected_ids == everything[:2]
    labels = {label: enabled for label, _, enabled in family.context_actions() if label}
    assert (
        labels["Copy"]
        and labels["Cut"]
        and not labels["Paste"]
        and labels["Batch Edit 2 Records…"]
    )
    assert family.copy_selected()
    created = family.paste()
    assert created == [f"{x}_copy" for x in everything[:2]] and family.selected_ids == created
    project_items = window.document.project.rpg_database.items
    assert all(x in project_items for x in created)
    window.document.undo()  # one step for the whole paste
    assert not any(x in project_items for x in created)


def test_window_shortcuts_act_on_the_focused_record_list(window):
    from asteria.editor.workspace import WorkspaceMode

    family = _items_family(window)
    window.show()
    window.workspace.set_mode(WorkspaceMode.RPG)
    window.activateWindow()
    family.browser.setFocus()
    QApplication.processEvents()
    if window._focused_record_family() is not family:
        pytest.skip("no keyboard focus on this platform")
    family.select_ids([family._ids[0]])
    assert window.copy_action.isEnabled() and window.paste_action.isEnabled()
    window.copy_action.trigger()
    window.paste_action.trigger()
    copy_id = f"{family._ids[0]}_copy"
    assert copy_id in window.document.project.rpg_database.items
    family.select_ids([copy_id])
    window.cut_action.trigger()
    assert copy_id not in window.document.project.rpg_database.items
    assert window.document.clipboard.record_payload.records[0][0] == copy_id


def test_batch_edit_applies_to_every_selected_record(window):
    family = window.rpg_authoring.child
    family.category.setCurrentIndex(family.category.findData("enemies"))
    ids = family._ids[:3]
    family.select_ids(ids)
    fields = family.batch_fields()
    assert "stats.power" in fields and "enemy_id" not in fields
    assert family.batch_edit_selected("stats.power", "42")
    enemies = window.document.project.rpg_database.enemies
    assert all(enemies[k].stats["power"] == 42 for k in ids) and family.selected_ids == ids
    assert not family.batch_edit_selected("stats.power", "lots") and "not a" in family.last_error
    window.document.undo()
    assert not all(enemies[k].stats["power"] == 42 for k in ids)


def test_batch_edit_dialog_shows_mixed_and_shared_values(window):
    from asteria.editor.authoring_hub_widget import BatchEditDialog
    from asteria.editor.record_operations import MIXED

    dialog = BatchEditDialog({"stats.power": MIXED, "tags": ["boss"]}, 2)
    assert dialog.current.text() == "(differs between records)" and dialog.value == ""
    dialog.field.setCurrentText("tags")
    assert dialog.value == "boss" and dialog.path == "tags"
