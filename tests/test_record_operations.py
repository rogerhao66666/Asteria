"""CB10 / EDT-03, EDT-13, EDT-14: record cut/copy/paste, multi-delete and batch edit on the
canonical model."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.editor.integrated_authoring import IntegratedAuthoringControllers
from asteria.editor.record_operations import (
    MIXED,
    RecordOperationError,
    batch_set,
    common_fields,
    copy_records,
    cut_records,
    delete_records,
    get_path,
    paste_records,
)
from asteria.project import Project

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"


@pytest.fixture
def setup():
    document = EditorDocument()
    path = ROOT / "project.asteria.json"
    document.set_project(Project.load_json(path, document.component_registry), file_path=path)
    controllers = IntegratedAuthoringControllers(document)
    adapters = {a.category_id: a for a in controllers.rpg_categories()}
    adapters.update({a.category_id: a for a in controllers.battle_categories()})
    adapters.update({a.category_id: a for a in controllers.presentation_categories()})
    return document, adapters


def test_every_authoring_category_can_paste(setup):
    _, adapters = setup
    assert all(a.create is not None for a in adapters.values())


def test_copy_paste_creates_fresh_ids_as_one_undo_step(setup):
    document, adapters = setup
    items = adapters["items"]
    source = sorted(items.ids())[:2]
    copy_records(document.clipboard, items, source)
    before = set(items.ids())
    created = paste_records(document, document.clipboard, items)
    assert created == [f"{x}_copy" for x in source] and set(items.ids()) == before | set(created)
    assert items.get(created[0]).item_id == created[0]
    assert items.encode(items.get(created[0])) | {"item_id": source[0]} == items.encode(
        items.get(source[0])
    )
    assert paste_records(document, document.clipboard, items) == [f"{x}_copy2" for x in source]
    document.undo()
    document.undo()
    assert set(items.ids()) == before
    document.redo()
    assert set(created) <= set(items.ids())


def test_paste_into_the_wrong_category_is_refused(setup):
    document, adapters = setup
    copy_records(document.clipboard, adapters["items"], [next(iter(adapters["items"].ids()))])
    with pytest.raises(RecordOperationError, match="not enemies"):
        paste_records(document, document.clipboard, adapters["enemies"])


def test_cut_removes_unreferenced_records_and_refuses_referenced_ones(setup):
    document, adapters = setup
    items = adapters["items"]
    copy_records(document.clipboard, items, [sorted(items.ids())[0]])
    (spare,) = paste_records(document, document.clipboard, items)
    cut_records(document, document.clipboard, items, [spare])
    assert spare not in items.ids() and document.clipboard.record_payload.records[0][0] == spare
    assert paste_records(document, document.clipboard, items) == [
        spare
    ]  # cut + paste moves it back
    actors = adapters["actors"]
    used = sorted(actors.ids())[0]
    classes = adapters["classes"]
    referenced = actors.get(used).class_assignments[0].class_id
    before = set(classes.ids())
    with pytest.raises(Exception):  # noqa: B017 - the controller refuses deleting a referenced class
        delete_records(document, classes, [sorted(before - {referenced})[0], referenced])
    assert set(classes.ids()) == before  # the group rolled back the delete that had succeeded


def test_batch_edit_sets_one_field_on_many_records_with_validation(setup):
    document, adapters = setup
    enemies = adapters["enemies"]
    ids = sorted(enemies.ids())[:3]
    fields = common_fields(enemies, ids)
    assert "enemy_id" not in fields and "schema" not in fields and fields["stats.power"] is MIXED
    path = "stats.power"
    before = {k: enemies.encode(enemies.get(k)) for k in ids}
    batch_set(document, enemies, ids, path, "7")
    assert all(get_path(enemies.encode(enemies.get(k)), path) == 7 for k in ids)
    assert document.commands.undo_label.startswith("Batch Edit")
    document.undo()
    assert {k: enemies.encode(enemies.get(k)) for k in ids} == before
    with pytest.raises(RecordOperationError, match="cannot be batch edited"):
        batch_set(document, enemies, ids, "enemy_id", "x")
    with pytest.raises(RecordOperationError, match="no field"):
        batch_set(document, enemies, ids, "no.such.field", "1")
