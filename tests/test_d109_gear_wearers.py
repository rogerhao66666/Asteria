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
    assert tag_label("roster.01", names) == "Roster: 01"  # not "Party Slot"
    assert tag_label("actor.playable", names) == "Actor Kind: Playable"
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

    return GameStartAuthoringController(EditorDocument(_project()))


def test_roger_starts_wearing_the_ring_and_the_chest_holds_charms_only():
    controller = _game_start()
    worn = controller.form_data()["worn"]
    ring = {"actor_id": "hero_01", "slot_id": "sub_weapon", "equipment_id": "w_demon_ring"}
    assert ring in worn
    chest = controller.project.event_programs.require("home.chest").to_data()
    assert "w_demon_ring" not in str(chest)


def test_starting_equipment_is_a_table_that_keeps_what_it_does_not_change():
    import copy

    from asteria.editor.rpg.game_start_authoring import GameStartAuthoringError

    controller = _game_start()
    before = controller.project.game_start.to_data()
    data = controller.form_data()
    controller.apply(copy.deepcopy(data))
    assert controller.project.game_start.to_data() == before  # nothing changed: kept as it was
    data["worn"].append({"actor_id": "spirit_knight", "slot_id": "", "equipment_id": "w_staff"})
    controller.apply(data)  # a hero with no loadout yet; no slot: the gear's own
    loadouts = controller.project.game_start.rpg_state_data["loadouts"]
    assert [p["instance_id"] for p in loadouts["spirit_knight"]["equipped"]["weapon"]] == [
        "w_staff:spirit_knight"
    ]
    controller.document.undo()
    assert controller.project.game_start.to_data() == before
    data = controller.form_data()
    data["worn"].append({"actor_id": "hero_02", "slot_id": "head", "equipment_id": "w_staff"})
    with pytest.raises(GameStartAuthoringError, match="does not go in the Head slot"):
        controller.apply(data)


def test_the_starting_equipment_card_and_its_words_in_chinese(app):
    from asteria.editor.rpg.game_start_authoring import GAME_START_CARDS
    from asteria.editor.ui.i18n import set_language, translate

    assert ("Starting Equipment", "weapon", ("worn",)) in GAME_START_CARDS
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
