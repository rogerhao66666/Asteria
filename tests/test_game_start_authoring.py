"""The Game Start form: reads the start state, writes it back undoably and validates."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.editor.game_start_authoring import (
    GameStartAuthoringController,
    GameStartAuthoringError,
)
from asteria.project import Project

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "octopath_demo"


@pytest.fixture
def controller():
    document = EditorDocument()
    document.project = Project.load_json(
        ROOT / "project.asteria.json", document.component_registry
    )
    return GameStartAuthoringController(document)


def test_form_reads_party_pets_and_items(controller):
    data = controller.form_data()
    assert len(data["party_actor_ids"]) == 4
    assert data["pets"] and data["pets"][0]["species_id"] == "frost_lynx"
    assert isinstance(data["items"], dict)


def test_apply_is_undoable_and_round_trips(controller):
    data = controller.form_data()
    data["pets"] = data["pets"] + [{"species_id": "ember_hound", "level": 7, "nickname": "Ash"}]
    data["active_pet"] = 2
    data["items"] = {**data["items"], next(iter(controller.references("items"))): 3}
    controller.apply(data)
    again = controller.form_data()
    assert [p["species_id"] for p in again["pets"]] == ["frost_lynx", "ember_hound"]
    assert again["active_pet"] == 2
    runtime = controller.project.game_start.instantiate(controller.project)
    assert runtime.rpg_state.active_pet_id == "ember_hound#1"
    controller.document.undo()
    assert len(controller.form_data()["pets"]) == 1


def test_invalid_data_is_rejected_and_nothing_changes(controller):
    before = controller.project.game_start
    data = controller.form_data()
    data["pets"] = [{"species_id": "no_such_species", "level": 1}]
    with pytest.raises(GameStartAuthoringError):
        controller.apply(data)
    data = controller.form_data()
    data["party_actor_ids"] = ["nobody"]
    with pytest.raises(GameStartAuthoringError):
        controller.apply(data)
    assert controller.project.game_start is before


def test_the_widget_edits_and_applies(controller):
    from PySide6.QtWidgets import QApplication

    from asteria.editor.game_start_widget import GameStartEditorWidget

    QApplication.instance() or QApplication([])

    widget = GameStartEditorWidget(controller)
    data = widget.form.data()
    assert data["player_facing"] == controller.project.game_start.player_facing
    widget.form.set_data({**data, "player_facing": "left"})
    assert widget.apply()
    assert controller.project.game_start.player_facing == "left"
