"""D109: properties read by their own names, a gear page says who can wear it, the Demon Ring
is Roger's alone (his own trait), the Knight job covers, a list cell is a button to pick."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _project():
    from asteria.project import Project
    from asteria.runtime.component_registry import default_component_registry

    return Project.load_json(DEMO / "project.asteria.json", default_component_registry())


def _family(category, key):
    from asteria.editor import EditorDocument
    from asteria.editor.records.hub import AdapterFamilyWidget
    from asteria.editor.rpg.integrated_authoring import IntegratedAuthoringControllers

    document = EditorDocument(_project())
    controllers = IntegratedAuthoringControllers(document)
    family = AdapterFamilyWidget("Game Data", controllers.rpg_categories(), document=document)
    family.category.setCurrentIndex(family.category.findData(category))
    family.select_ids([key])
    return family


def test_a_property_reads_by_the_name_its_definition_gives():
    from asteria.editor import EditorDocument
    from asteria.editor.records.vocabulary import tag_label, vocabulary_for

    names = vocabulary_for(EditorDocument(_project())).names()
    assert tag_label("trait.cover", names) == "Trait: Cover"
    assert tag_label("capability.weapon.ring", names) == "Can Wield: Ring"
    assert tag_label("consumable", names) == "Consumable"
    assert tag_label("roster.01") == "Party Slot: 01"  # no project: the editor's own words


def test_the_demon_ring_is_rogers_alone_and_the_knight_covers():
    from asteria.editor.rpg.wearers import actor_capabilities, who_can_wear

    project = _project()
    db = project.rpg_database
    assert who_can_wear(project, db.equipment["w_demon_ring"].to_data()) == (("hero_01", "Roger"),)
    archmage = db.actors["hero_02"]  # Mira as an Archmage: the job's ring is not enough
    ring = db.equipment["w_demon_ring"]
    mira = actor_capabilities(db, archmage) | set(db.classes["archmage"].granted_tags)
    assert not ring.eligibility(mira).allowed
    assert "trait.cover" not in db.actors["hero_01"].tags
    assert "trait.cover" in actor_capabilities(db, db.actors["hero_03"])  # Vesper, a Knight


def test_the_gear_page_says_who_can_wear_it_and_follows_edits(app):
    from asteria.editor.records.wearers_line import WearersLine

    family = _family("equipment", "w_demon_ring")
    (line,) = family.editor.findChildren(WearersLine)
    assert line.names() == ["Roger"]
    opened = []
    line.window().navigate_to_problem = lambda problem: opened.append(problem.target)
    line.open("hero_01")
    assert opened == [("record", "rpg", "actors", "hero_01")]
    form = family.editor
    form._data["required_capabilities"] = []
    form._data["any_capabilities"] = ["capability.weapon.sword"]
    form.changed.emit()  # an edit on the page: the line again
    (line,) = form.findChildren(WearersLine)
    assert line.names() == ["Roger", "Vesper", "Cael"]  # Brave, Knight, Duelist wield swords
    form._data["any_capabilities"] = []
    form.changed.emit()
    assert line.names() == ["Everyone (it needs nothing)"]


def test_a_list_cell_is_a_button_with_a_property_icon(app):
    from asteria.editor.records.form_parts import ListCell

    family = _family("equipment", "w_demon_ring")
    cells = family.editor.findChildren(ListCell)
    assert cells and all(not c.icon().isNull() for c in cells)
    assert cells[0].toolTip() == "Click to pick: Accepted Properties"


def _game_start():
    from asteria.editor import EditorDocument
    from asteria.editor.rpg.game_start_authoring import GameStartAuthoringController

    document = EditorDocument(_project())
    document.file_path = DEMO / "project.asteria.json"  # pictures are read beside it
    return GameStartAuthoringController(document)


def test_roger_starts_wearing_the_ring_and_the_chest_holds_charms_only():
    controller = _game_start()
    roger = controller.project.rpg_database.actors["hero_01"]
    assert ("sub_weapon", "w_demon_ring") in roger.starting_equipment  # his own (D110)
    chest = controller.project.event_programs.require("home.chest").to_data()
    assert "w_demon_ring" not in str(chest)


def test_the_starting_equipment_card_and_its_words_in_chinese(app):
    from asteria.editor.rpg.game_start_authoring import GAME_START_CARDS
    from asteria.editor.ui.i18n import set_language, translate

    assert ("Starting Equipment", "weapon", ()) in GAME_START_CARDS  # shown, not edited (D110)
    set_language("zh_TW")
    try:
        assert translate("Starting Equipment") == "初始裝備"
        assert translate("Oak Staff does not go in the Head slot").endswith("欄位")
        assert translate("Open Roger's page").startswith("開啟")
    finally:
        set_language("en")


def test_slot_names_read_in_the_projects_chinese():
    from asteria.editor.project.data_translation import project_words

    words = project_words(_project(), "zh_TW")
    assert (words["Body"], words["Carried Weapons"]) == ("身體", "攜帶武器")


def test_a_grid_table_is_a_line_per_row_of_picks(app):
    from PySide6.QtWidgets import QComboBox

    from asteria.editor.rpg.game_systems_authoring import F
    from asteria.editor.rpg.game_systems_widget import RecordForm
    from asteria.editor.rpg.grid_table import GridTable

    controller = _game_start()
    rows = (F("slot_id", "Slot", "ref", source="equipment_slots"),
            F("equipment_id", "Gear", "ref", source="equipment"))  # fmt: skip
    field = F("worn", "Worn", "table", fields=rows, default=(), grid=True)
    form = RecordForm((field,), controller.references, document=controller.document)
    worn = [{"slot_id": "weapon", "equipment_id": "w_sunbrand"},
            {"slot_id": "head", "equipment_id": "w_staff"}]  # fmt: skip
    form.set_data({"worn": worn})
    grid = form.widgets["worn"]
    assert isinstance(grid, GridTable) and grid.table.rowCount() == 2
    gear = grid.table.cellWidget(0, 1)
    assert isinstance(gear, QComboBox) and gear.currentText() == "Sunbrand"
    assert not gear.itemIcon(gear.currentIndex()).isNull()  # its picture beside its name
    at = gear.findData("w_staff")
    gear.setCurrentIndex(at)
    gear.activated.emit(at)  # another piece, picked
    assert form.data()["worn"][0]["equipment_id"] == "w_staff"
    grid.table.cellWidget(0, 2).click()  # ✕ removes the line
    assert len(form.data()["worn"]) == 1


def test_a_popup_has_a_key_and_shows_in_the_players_language():
    import sys

    sys.path.insert(0, str(DEMO))
    import run_trial_smoke as smoke

    from asteria.editor.project import data_translation as dt

    project, game = smoke.load()
    assert dt.dialogue_without_keys(project) == 0  # the popups have their keys too
    shown = []
    game.notify = lambda text, **_k: shown.append(text)
    smoke.world(game, "SET_LOCALE", locale="zh-TW")
    smoke.world(game, "SHOW_POPUP", text="Six charms!", text_key="dlg.home_che.8")
    smoke.world(game, "SHOW_POPUP", text="Words of my own")  # no key: as written
    assert shown == ["六個護符！", "Words of my own"]


def test_the_popup_form_keeps_its_key_without_showing_it(app):
    from asteria.editor.events.world_command_form import WorldCommandForm

    form = WorldCommandForm()
    form.set_command("SHOW_POPUP", {"text": "Six charms!", "text_key": "dlg.home_che.8"})
    assert "text_key" not in form.fields and not form.other.isVisible()
    assert form.result_args()["text_key"] == "dlg.home_che.8"


def test_new_popup_words_drop_the_old_translation_and_the_line_hides_the_key(app):
    from asteria.editor.events.editing import describe_instruction
    from asteria.editor.events.world_command_form import WorldCommandForm
    from asteria.events.program import EventInstruction

    args = {"text": "Six charms!", "text_key": "dlg.home_che.8"}
    form = WorldCommandForm()
    form.set_command("SHOW_POPUP", args)
    form.fields["text"].set_value("Seven charms!")
    assert "text_key" not in form.result_args()  # the old Chinese was of the old words
    line = describe_instruction(EventInstruction("WORLD", {"command": "SHOW_POPUP", "args": args}))
    assert "Six charms!" in line and "dlg." not in line
