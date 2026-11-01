"""Database > Game Data > New…: an empty record of the shown kind, from its name and id."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

DEMO = Path(__file__).resolve().parents[1] / "reference_projects/complex_reference_rpg"


def _document():
    from asteria.editor import EditorDocument
    from asteria.editor.storage import load_document

    document = EditorDocument()
    load_document(document, str(DEMO / "project.asteria.json"))
    return document


def _family(document):
    from asteria.editor.authoring_hub_widget import AdapterFamilyWidget
    from asteria.editor.integrated_authoring import IntegratedAuthoringControllers

    return AdapterFamilyWidget(
        "Game Data", IntegratedAuthoringControllers(document).rpg_categories(), document=document
    )


def test_suggested_ids_come_from_names():
    from asteria.editor.record_blank import suggest_id

    assert suggest_id("Fire Bolt!") == "fire_bolt"
    assert suggest_id("  Hero 13 ") == "hero_13"
    assert suggest_id("hero_01", taken=("hero_01",)) == "hero_01_2"
    assert suggest_id("") == "new"


def test_new_records_are_as_empty_as_their_kind_allows(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    document = _document()
    db = document.project.rpg_database
    family = _family(document)
    family.category.setCurrentIndex(family.category.findData("actors"))
    assert family.new_button.isEnabled()
    family.new_record_as("hero_13", "Hero 13")
    actor = db.actors["hero_13"]
    assert actor.display_name == "Hero 13"
    assert actor.class_assignments == () and actor.tags == () and actor.abilities == ()
    assert family.selected_id == "hero_13"  # shown and chosen in the list
    document.commands.undo()
    assert "hero_13" not in db.actors  # one undo takes it back
    family.category.setCurrentIndex(family.category.findData("items"))
    family.new_record_as("new_item", "New Item")
    item = db.items["new_item"]
    assert item.display_name == "New Item" and item.stack_limit >= 1  # a kind's minimum kept
    family.category.setCurrentIndex(family.category.findData("encounters"))
    family.new_record_as("new_fight", "New Fight")
    assert len(db.encounters["new_fight"].members) == 1  # a kind that needs one entry
    with pytest.raises(Exception, match="already exists"):
        family.new_record_as("new_fight", "Again")


def test_a_kind_with_no_record_yet_cannot_be_started_from(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.authoring_hub_widget import AuthoringHubError

    QApplication.instance() or QApplication([])
    family = _family(_document())
    family.category.setCurrentIndex(family.category.findData("evolutions"))
    assert not family.new_button.isEnabled()
    with pytest.raises(AuthoringHubError):
        family.new_record_as("x", "X")


def test_the_new_record_dialog_follows_the_name_until_the_id_is_typed(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QDialogButtonBox

    from asteria.editor.authoring_hub_widget import _NewRecordDialog

    QApplication.instance() or QApplication([])
    dialog = _NewRecordDialog("Actors", ("hero_01",))
    ok = dialog.buttons.button(QDialogButtonBox.Ok)
    assert not ok.isEnabled()  # no id yet
    dialog.name_edit.setText("Hero 13!")
    assert dialog.record_id() == "hero_13" and dialog.name() == "Hero 13!" and ok.isEnabled()
    dialog.id_edit.setText("hero_01")  # a taken id
    dialog.id_edit.textEdited.emit("hero_01")
    assert not ok.isEnabled()
    dialog.id_edit.setText("mine")
    dialog.name_edit.setText("Renamed")  # typed by hand: the id no longer follows
    assert dialog.record_id() == "mine" and ok.isEnabled()
