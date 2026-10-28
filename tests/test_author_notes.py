"""Every record's Note, and Players See It on every description the game shows (D100): the
notes stay in the editor, an unticked description never reaches the game, and the game shows
the descriptions of tags, equipment slots, enemies and jobs."""

import sys
from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.editor.game_systems_authoring import FORMS, GameSystemsAuthoringController
from asteria.rpg.actors import RpgDatabase

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


def _document():
    from asteria.editor.storage import load_document

    document = EditorDocument()
    load_document(document, str(DEMO / "project.asteria.json"))
    return document


def test_the_database_keeps_notes_and_hidden_descriptions():
    db = RpgDatabase()
    db.author_notes = {"items": {"potion": "Balance after the boss"}, "classes": {}}
    db.hidden_descriptions = {"tag": {"weapon": True}}
    again = RpgDatabase.from_data(db.to_data())
    assert again.author_notes == {"items": {"potion": "Balance after the boss"}}
    assert again.description_hidden("tag", "weapon")
    assert not again.description_hidden("tag", "cure")
    assert "author_notes" not in RpgDatabase().to_data()  # nothing written when empty


def test_every_game_systems_form_ends_with_a_note():
    for kind, fields in FORMS.items():
        if kind in ("menu_rules", "menu_pages", "menu_entries"):
            continue
        assert fields[-1].key == "author_note", kind
    keys = [f.key for f in FORMS["tag_definitions"]]
    assert keys[keys.index("description") + 1] == "description_shown"
    assert "description_shown" not in [f.key for f in FORMS["derived_stats"]]
    derived = next(f for f in FORMS["derived_stats"] if f.key == "description")
    assert derived.label == "Description (editor only)"  # the game never shows it


def test_a_note_and_players_see_it_are_one_undo_step():
    document = _document()
    systems = GameSystemsAuthoringController(document)
    db = document.project.rpg_database
    data = systems.form_data("tag_definitions", "cure", info=False)
    assert data["author_note"] == "" and data["description_shown"] is True
    data["author_note"] = "Keep it short"
    data["description_shown"] = False
    systems.edit("tag_definitions", "cure", data)
    assert db.author_notes["tag_definitions"]["cure"] == "Keep it short"
    assert db.description_hidden("tag", "cure")
    assert "author_note" not in db.tag_definitions["cure"].to_data()  # beside, not inside
    document.undo()
    assert "cure" not in db.author_notes.get("tag_definitions", {})
    assert not db.description_hidden("tag", "cure")
    # decode() takes the form's data as it is
    data = systems.form_data("quest_boards", "hearthfold_board", info=False)
    assert systems.decode("quest_boards", data).board_id == "hearthfold_board"


@pytest.fixture
def host(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, str(DEMO))
    import trial_ui_tour

    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=960, height=540
    )
    runtime.open()
    trial_ui_tour.prepare(runtime.game)
    yield runtime
    runtime.close()


def test_an_item_lists_what_its_shown_tags_mean(host):
    game = host.game
    game.set_locale("zh-TW")
    assert game.tag_meanings(("consumable", "cure")) == ("治療藥：解除異常狀態。",)  # one shown
    db = game.project.rpg_database
    db.hidden_descriptions["tag"]["cure"] = True
    assert game.tag_meanings(("cure",)) == ()


def test_slots_enemies_and_jobs_describe_themselves(host):
    from asteria.runtime.game_menus import bestiary_rows

    game = host.game
    db = game.project.rpg_database
    arsenal = db.equipment_slots["arsenal"]
    assert game.description_of(arsenal).startswith("Weapons the hero carries")
    assert "capability" not in game.description_of(arsenal)  # that part is the makers' note
    db.hidden_descriptions["slot"] = {"arsenal": True}
    assert game.description_of(arsenal, "") == ""
    enemy_id = next(iter(sorted(db.enemies)))
    db.enemies[enemy_id] = type(db.enemies[enemy_id]).from_data(
        {**db.enemies[enemy_id].to_data(), "description": "Hides in the reeds."}
    )
    game.world.bestiary[enemy_id] = {"seen": 1}
    row = next(r for r in bestiary_rows(game) if r[1])
    assert row[7] == "Hides in the reeds."
    drawn = " ".join(host._bestiary_detail(row).split("\n"))
    assert "Hides in the reeds." in drawn


def test_game_data_records_have_a_note_box_and_players_see_it():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel

    from asteria.editor.authoring_hub_widget import AdapterFamilyWidget
    from asteria.editor.integrated_authoring import IntegratedAuthoringControllers

    QApplication.instance() or QApplication([])
    document = _document()
    db = document.project.rpg_database
    family = AdapterFamilyWidget(
        "Game Data", IntegratedAuthoringControllers(document).rpg_categories(), document=document
    )
    family.category.setCurrentIndex(family.category.findData("items"))
    family.select_ids(["antidote"])
    box = family.note_box
    assert box.key == "antidote" and box.shown is not None  # the game shows items' words
    assert box.shown.parent() is not box  # it stands under the description, in the form
    box.text.setPlainText("Cheaper than the shop's")
    box.flush()
    assert db.author_notes["items"]["antidote"] == "Cheaper than the shop's"
    page = family.editor.widget()
    assert box.parent() is page  # the form's last block: it scrolls with the fields
    assert box.text.toPlainText() == "Cheaper than the shop's"  # typing never rebuilt it
    box.shown.setChecked(False)
    assert db.description_hidden("item", "antidote")
    document.undo()
    assert not db.description_hidden("item", "antidote")
    family.category.setCurrentIndex(family.category.findData("actors"))
    family.select_ids([next(iter(sorted(db.actors)))])
    assert family.note_box.shown is None  # the game never shows an actor's description
    labels = [w.text() for w in family.editor.findChildren(QLabel)]
    assert any(x.startswith("Description (editor only)") for x in labels), labels
    family.deleteLater()


def test_players_see_it_stands_on_the_description_line():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.game_systems_widget import RecordForm

    QApplication.instance() or QApplication([])
    form = RecordForm(FORMS["tag_definitions"], lambda _kind: ())
    switch = form.widgets["description_shown"]
    assert switch.text() == "Players See It"
    assert "description_shown" not in form._rows  # no row of its own
    assert switch.parent() is form._rows["description"]  # beside the description's label
    form.deleteLater()
