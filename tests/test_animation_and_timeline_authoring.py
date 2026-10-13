"""CB10: animation editor (EDT-05/ANI-04/AST-02) and action timeline editor (EDT-06) APIs."""

from pathlib import Path

import pytest
from PIL import Image

from asteria.editor import EditorDocument
from asteria.editor.action_timeline_authoring import ActionTimelineController, ActionTimelineError
from asteria.editor.animation_authoring import (
    AnimationAuthoringController,
    AnimationAuthoringError,
)
from asteria.project import Project

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"
SHEET = "battle.combatant.hero_01"


@pytest.fixture
def document():
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    return EditorDocument(project, file_path=ROOT / "project.asteria.json")


def _resolver(project):
    from asteria.runtime.battle_visuals import BattleVisualResolver

    return BattleVisualResolver(project, lambda uri: Image.open(ROOT / uri).size)


def test_animation_edits_are_undoable_and_reach_the_runtime_resolver(document):
    api = AnimationAuthoringController(document)
    assert SHEET in api.sheets() and api.grid(SHEET) == (8, 1)
    before = _resolver(document.project).clip_duration(SHEET, "attack")
    api.set_clip(SHEET, "attack", frame_duration=0.2)
    assert _resolver(document.project).clip_duration(SHEET, "attack") == pytest.approx(0.2 * 5)
    api.add_clip(SHEET, "victory", [0, 2, 0, 2], 0.25, loop=True)
    api.set_events(SHEET, "victory", 1, ["cheer"])
    assert api.preview_events(SHEET, "victory", 0.6)[0] == (0.25, "cheer")
    assert api.preview_frame(SHEET, "victory", 0.3) == 2
    api.set_pivot(SHEET, 0.5, 0.9)
    document.undo()
    document.undo()
    document.undo()
    assert "victory" not in api.data(SHEET)["clips"]
    document.undo()
    assert _resolver(document.project).clip_duration(SHEET, "attack") == pytest.approx(before)
    document.redo()
    assert api.data(SHEET)["clips"]["attack"]["frame_duration"] == 0.2


def test_animation_validation_blocks_bad_data(document):
    api = AnimationAuthoringController(document)
    with pytest.raises(AnimationAuthoringError):
        api.set_clip(SHEET, "idle", frames=[0, 99])  # outside the 8-frame sheet
    with pytest.raises(AnimationAuthoringError):
        api.set_frame_size(SHEET, 60, 64)  # 512 px is not a grid of 60
    with pytest.raises(AnimationAuthoringError):
        api.set_pivot(SHEET, 1.5, 1.0)
    with pytest.raises(AnimationAuthoringError):
        api.add_clip(SHEET, "idle", [0])  # name taken
    api.rename_clip(SHEET, "hit", "hurt")
    api.remove_clip(SHEET, "hurt")
    assert "hit" not in api.data(SHEET)["clips"] and api.problems(SHEET) == []


def test_timeline_edits_are_undoable_and_drive_the_battle_choreography(document):
    api = ActionTimelineController(document)
    assert "fire_arc" in api.sequences()
    api.move_beat("fire_arc", "impact", 0.5)
    from asteria.runtime.battle_visuals import BattleVisualResolver  # noqa: F401

    sequence = _resolver(document.project).motion_sequence("fire_arc")
    assert next(b.at for b in sequence.beats if b.beat_id == "impact") == 0.5
    api.add_beat("fire_arc", "extra_shake", 0.6, "camera", "shake", amplitude=3, duration=0.1)
    preview = api.preview("fire_arc", 0.55)
    assert all(at <= 0.55 for at, _, _, _ in preview["released"])  # extra_shake at 0.6 not yet
    assert (0.5, "animation", "hit", "@target") in preview["released"]
    with pytest.raises(ActionTimelineError):
        api.add_beat("fire_arc", "bad", 0.1, "vfx", "battle.fx.nope")
    with pytest.raises(ActionTimelineError):
        api.add_beat("fire_arc", "bad", 0.1, "animation", "dance")
    with pytest.raises(ActionTimelineError):
        api.set_duration("fire_arc", 0.2)  # beats after the end
    api.create("thunder", 1.0)
    api.duplicate("fire_arc", "fire_arc_copy")
    api.delete("thunder")
    document.undo()
    assert "thunder" in api.sequences()
    document.undo()
    document.undo()
    document.undo()
    document.undo()
    sequence = _resolver(document.project).motion_sequence("fire_arc")
    assert next(b.at for b in sequence.beats if b.beat_id == "impact") == 0.32
