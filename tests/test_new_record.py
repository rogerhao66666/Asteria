"""Database > Game Data > New: an empty record of the shown kind, named for its kind, its id
made from the name."""

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


def test_new_makes_a_named_record_at_once_without_asking(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.authoring_hub_widget import _new_name

    QApplication.instance() or QApplication([])
    document = _document()
    db = document.project.rpg_database
    family = _family(document)
    family.category.setCurrentIndex(family.category.findData("actors"))
    assert family.new_button.text() == "New" and family.duplicate_button.text() == "Duplicate"
    assert family.new_record() == "new_actor"  # no dialog: a name, an id made from it
    assert db.actors["new_actor"].display_name == "New Actor"
    assert family.new_record() == "new_actor_2"  # a second one stays apart
    family.category.setCurrentIndex(family.category.findData("enemies"))
    reward = db.enemies[family.new_record()].reward  # nothing of the first enemy's kept
    assert not reward.loot and not reward.drop_table_id
    assert _new_name("Enemies / Bosses") == "New Enemy"
    assert _new_name("Enemy AI / Boss Phases") == "New Enemy AI"
    assert _new_name("Loot Rarities") == "New Loot Rarity"


DEMOS = ("complex_reference_rpg", "full_verification_demo", "arpg_demo", "party_rpg_demo")


@pytest.mark.parametrize("demo", DEMOS)
def test_a_new_record_of_every_kind_leaves_the_project_valid(demo):
    from asteria.editor import EditorDocument
    from asteria.editor.integrated_authoring import IntegratedAuthoringControllers
    from asteria.editor.record_blank import blank_record
    from asteria.editor.storage import load_document

    document = EditorDocument()
    path = DEMO.parent / demo / "project.asteria.json"
    load_document(document, str(path))
    for adapter in IntegratedAuthoringControllers(document).rpg_categories():
        if adapter.create is None or not adapter.ids():
            continue
        template = adapter.encode(adapter.get(adapter.ids()[0]))
        adapter.create("zz_new", blank_record(adapter, template, "zz_new", "New"))
        document.project.to_data()  # validates: a growth's node keeps no socket it lacks
        document.commands.undo()


def test_new_then_delete_on_the_combat_page(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.combat_workspace import CombatWorkspace

    QApplication.instance() or QApplication([])
    document = _document()
    page = CombatWorkspace(document)
    page.resize(1600, 900)  # wide enough for the preview (a narrow page folds it)
    page.show()
    QApplication.processEvents()
    made = page.new_record()
    attack = document.project.gameplay_library.attacks[made]
    assert made == "new_attack" and attack.display_name == "New Attack"
    assert page.delete_button.isEnabled() and page.form_area.isVisible()
    page.delete_record(confirm=False)
    assert made not in document.project.gameplay_library.attacks
    if page.list.count():  # never "No attacks yet" beside a list that has some
        assert page.record_id is not None and not page.empty.isVisibleTo(page)
    assert not any(c.isdigit() for b in page.kind_buttons.values() for c in b.text())
    assert page.preview_toggle.text() == "Hide Preview"
    page.preview_toggle.click()
    assert page.preview_toggle.text() == "Show Preview" and not page.right_panel.isVisible()


def test_new_then_delete_on_behavior_trees_and_event_programs(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.behavior_tree_widget import BehaviorTreeEditorWidget
    from asteria.editor.event_flow_authoring import EventFlowError
    from asteria.editor.event_flow_widget import EventFlowWidget

    QApplication.instance() or QApplication([])
    document = _document()
    trees = BehaviorTreeEditorWidget(document)
    trees._new_clicked()
    made = trees.tree_id
    assert trees.delete_tree() and made not in trees.api.ids()  # no crash on the deleted tree
    events = EventFlowWidget(document)
    events._new_program_clicked()
    picked = events.program_pick.currentText()
    assert document.project.event_programs.get(picked) is not None
    assert events.delete_program() and document.project.event_programs.get(picked) is None
    document.commands.undo()  # one undo brings it back
    assert document.project.event_programs.get(picked) is not None
    used = next(iter(document.project.common_events), None)
    if used is not None:  # a program something runs stays
        with pytest.raises(EventFlowError, match="still in use"):
            events.api.delete_program(used.program_id)
