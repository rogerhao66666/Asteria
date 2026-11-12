"""D110: what a character starts wearing is the character's own (``starting_equipment``), put on
at New Game and on joining; Game Start shows it and opens the character; the labels
``actor.*`` / ``roster.*`` that no rule read are gone."""

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "reference_projects" / "full_verification_demo"
TEMPLATE = REPO / "src" / "asteria" / "templates" / "party_rpg" / "project.asteria.json"
PROJECTS = (DEMO / "project.asteria.json", TEMPLATE,
            REPO / "reference_projects" / "party_rpg_demo" / "project.asteria.json")  # fmt: skip


def _load(path=DEMO / "project.asteria.json"):
    from asteria.project import Project
    from asteria.runtime.component_registry import default_component_registry

    return Project.load_json(path, default_component_registry())


def test_an_actor_keeps_its_starting_equipment_and_writes_it_only_when_set():
    from asteria.rpg.characters.actors import ActorDefinition

    hero = ActorDefinition("hero", starting_equipment=[{"slot_id": "", "equipment_id": "sword"},
                                                        ("head", "cap")])  # fmt: skip
    assert hero.starting_equipment == (("", "sword"), ("head", "cap"))
    again = ActorDefinition.from_data(hero.to_data())
    assert again == hero
    assert "starting_equipment" not in ActorDefinition("plain").to_data()
    assert ActorDefinition.OPTIONAL_DATA["starting_equipment"] == []  # the page shows it empty


def test_a_new_game_dresses_every_character_from_their_own_page():
    project = _load()
    assert not project.game_start.rpg_state_data["loadouts"]  # nothing left in Game Start
    save = project.game_start.instantiate(project)
    loadouts = save.rpg_state.loadouts
    ring = [p.instance_id for p in loadouts["hero_01"].equipped("sub_weapon")]
    assert ring == ["w_demon_ring:hero_01"]
    assert len(loadouts["hero_01"].equipped("arsenal")) == 4
    assert [p.equipment.equipment_id for p in loadouts["hero_04"].equipped("weapon")] == [
        "w_dagger"
    ]  # Cael joins later: dressed all the same
    assert "spirit_knight" not in loadouts  # nothing to wear: no loadout, as before


def test_one_who_joins_with_no_loadout_puts_theirs_on_and_a_worn_one_stays():
    sys.path.insert(0, str(DEMO))
    import run_trial_smoke as smoke

    _project, game = smoke.load()
    state = game.save.rpg_state
    del state.loadouts["hero_03"]  # a save from before D110
    game.join_party("hero_03")
    assert [p.instance_id for p in state.loadouts["hero_03"].equipped("weapon")] == [
        "w_staff:hero_03"
    ]
    worn = state.loadouts["hero_04"]
    worn.unequip("weapon")
    game.join_party("hero_04")
    assert state.loadouts["hero_04"] is worn and not worn.equipped("weapon")  # theirs, kept


def test_a_starting_piece_the_project_cannot_put_on_is_a_problem():
    from asteria.rpg.characters.actors import ActorDefinition
    from asteria.rpg.items.starting_gear import starting_gear_errors

    db = _load().rpg_database
    data = db.actors["spirit_knight"].to_data()
    data["starting_equipment"] = [
        {"slot_id": "head", "equipment_id": "w_staff"},
        {"slot_id": "wings", "equipment_id": "w_staff"},
        {"slot_id": "", "equipment_id": "w_nothing"},
        {"slot_id": "", "equipment_id": "w_staff"},  # no slot: the gear's own
    ]
    db.actors["spirit_knight"] = ActorDefinition.from_data(data)
    assert starting_gear_errors(db) == [
        "actor spirit_knight starting equipment: w_staff does not go in the head slot",
        "actor spirit_knight starting equipment references unknown equipment slot wings",
        "actor spirit_knight starting equipment references unknown equipment w_nothing",
    ]
    assert any("w_nothing" in e for e in db.reference_errors())


@pytest.mark.parametrize("path", PROJECTS, ids=lambda p: p.parent.name)
def test_no_actor_kind_or_roster_labels_are_left(path):
    db = json.loads(path.read_text(encoding="utf-8"))["rpg_database"]
    tags = {t for a in db["actors"] for t in a["tags"]}
    assert not {t for t in tags if t.startswith(("actor.", "roster."))}
    kinds = {t["tag_id"] for t in db.get("tag_definitions", ())}
    assert not kinds & {"actor.*", "roster.*"}


def test_the_template_has_its_slots_as_records_and_dresses_its_heroes():
    project = _load(TEMPLATE)
    slots = project.rpg_database.equipment_slots
    assert sorted(slots) == ["accessory", "weapon"] and slots["weapon"].capacity == 2
    save = project.game_start.instantiate(project)
    worn = save.rpg_state.loadouts["hero_01"].equipped("weapon")
    assert [p.equipment.equipment_id for p in worn] == ["w_sword", "w_spear"]


@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _page():
    from asteria.editor import EditorDocument
    from asteria.editor.rpg.game_start_authoring import GameStartAuthoringController
    from asteria.editor.rpg.game_start_widget import GameStartEditorWidget

    document = EditorDocument(_load())
    document.file_path = DEMO / "project.asteria.json"  # pictures are read beside it
    return GameStartEditorWidget(GameStartAuthoringController(document))


def test_game_start_shows_what_each_wears_and_opens_their_pages(app):
    page = _page()
    view = page.form.starting_wear
    rows = dict(view.rows())
    assert rows["Roger"][:3] == ["Body: Warden Plate", "Special: Warden Ring",
                                 "Main Weapon: Sunbrand"]  # fmt: skip
    assert rows["Cael"] == ["Main Weapon: Stiletto"] and rows["Spirit Rider"] == ["Nothing worn"]
    assert "worn" not in page.form.data()  # nothing to edit here
    opened = []
    view.window().navigate_to_problem = lambda problem: opened.append(problem.target)
    view.grid.itemAtPosition(0, 0).widget().click()
    view.grid.itemAtPosition(0, 1).widget().layout().itemAt(2).widget().click()
    assert opened == [("record", "rpg", "actors", "hero_01"),
                      ("record", "rpg", "equipment", "w_sunbrand")]  # fmt: skip


def test_a_loadout_game_start_still_holds_is_shown_as_kept(app):
    from asteria.editor.rpg.wearers import starting_wear

    project = _load()
    loadout = project.game_start.instantiate(project).rpg_state.loadouts["hero_02"].to_data()
    project.game_start.rpg_state_data["loadouts"] = {"hero_02": loadout}  # an older project
    (mira,) = [row for row in starting_wear(project) if row[0] == "hero_02"]
    assert mira[3] and mira[2] == (("weapon", "Main Weapon", "w_staff"),)


def test_the_actor_page_edits_starting_equipment(app):
    from asteria.editor.records.form_parts import EntryTable
    from asteria.editor.records.vocabulary import LABELS

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_d109_gear_wearers import _family

    form = _family("actors", "hero_04").editor
    (table,) = [t for t in form.findChildren(EntryTable) if t.key == "starting_equipment"]
    assert LABELS["starting_equipment"] == "Starting Equipment"
    assert form._data["starting_equipment"] == [{"slot_id": "weapon", "equipment_id": "w_dagger"}]


def test_the_new_words_in_chinese(app):
    from asteria.editor.ui.i18n import set_language, translate

    set_language("zh_TW")
    try:
        assert translate("Nothing worn") == "未穿戴"
        assert translate("Kept in Game Start (an older project)").startswith("保留")
        assert "初始裝備" in translate(
            "What this character wears when they first come in: put on at New Game, for a "
            "character who joins later too. No slot = the gear's own slot. Game Start ▸ "
            "Starting Equipment shows every character's."
        )
    finally:
        set_language("en")


def test_an_actor_edit_keeps_and_changes_its_starting_equipment_and_description():
    import dataclasses

    from asteria.editor import EditorDocument
    from asteria.editor.rpg.integrated_authoring import IntegratedAuthoringControllers

    document = EditorDocument(_load())
    controllers = IntegratedAuthoringControllers(document)
    (actors,) = [a for a in controllers.rpg_categories() if a.category_id == "actors"]
    cael = dataclasses.replace(actors.get("hero_04"), description="A duelist.")
    actors.edit("hero_04", cael)
    assert actors.get("hero_04").description == "A duelist."  # kept, not dropped
    data = actors.encode(actors.get("hero_04"))
    data["starting_equipment"] = [{"slot_id": "", "equipment_id": "w_staff"}]
    actors.edit("hero_04", actors.decode(data))
    edited = actors.get("hero_04")
    assert edited.starting_equipment == (("", "w_staff"),) and edited.description
    document.undo()
    assert actors.get("hero_04").starting_equipment == (("weapon", "w_dagger"),)
