"""The Game Start form: reads the start state, writes it back undoably and validates."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.editor.game_start_authoring import (
    GameStartAuthoringController,
    GameStartAuthoringError,
)
from asteria.project import Project

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "party_rpg_demo"


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


def test_starting_gear_goes_into_the_equipment_bag(controller):
    """D98: Game Start ▸ Starting Gear: spare pieces in the bag, kept when written again; an
    older start state gains the bag's keys and keeps the rest as written."""
    before = dict(controller.project.game_start.rpg_state_data)
    gear = sorted(controller.references("equipment"))[:2]
    data = controller.form_data()
    assert data["gear"] == {}
    data["gear"] = {gear[0]: 2, gear[1]: 1}
    controller.apply(data)
    state = controller.project.game_start.rpg_state_data
    assert controller.form_data()["gear"] == {gear[0]: 2, gear[1]: 1}
    assert state["loadouts"] == before["loadouts"]  # the worn gear as it was written
    runtime = controller.project.game_start.instantiate(controller.project)
    bag = [g.equipment.equipment_id for g in runtime.rpg_state.equipment_bag]
    assert sorted(bag) == sorted([gear[0], gear[0], gear[1]])
    assert len({g.instance_id for g in runtime.rpg_state.equipment_bag}) == 3
    first = [p["instance_id"] for p in state["equipment_bag"]]
    data = controller.form_data()
    data["gear"] = {gear[0]: 1, gear[1]: 1}
    controller.apply(data)
    kept = [
        p["instance_id"] for p in controller.project.game_start.rpg_state_data["equipment_bag"]
    ]
    assert set(kept) <= set(first) and len(kept) == 2  # pieces it held are kept
    controller.document.undo()
    controller.document.undo()
    assert (
        "equipment_bag" not in controller.project.game_start.rpg_state_data
        or not (controller.project.game_start.rpg_state_data["equipment_bag"])
    )


def test_the_demo_starts_with_spare_gear():
    document = EditorDocument()
    path = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
    project = Project.load_json(path / "project.asteria.json", document.component_registry)
    bag = project.game_start.instantiate(project).rpg_state.equipment_bag
    slots = {g.equipment.slot for g in bag}
    assert len(bag) >= 80 and {"weapon", "armor", "accessory", "head", "legs", "feet"} <= slots
