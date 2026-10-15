"""DragonBones 5.0 JSON import contract and unsupported-feature reporting."""

import json

import pytest

from asteria.editor.skeleton_view import load_rig
from asteria.graphics.dragonbones_import import (
    DragonBonesImportError,
    import_dragonbones_json,
    unsupported_parts,
)

RIG = {
    "name": "hero",
    "version": "5.0",
    "frameRate": 10,
    "armature": [
        {
            "name": "hero",
            "bone": [
                {"name": "root"},
                {
                    "name": "arm",
                    "parent": "root",
                    "length": 8,
                    "transform": {"x": 10, "y": 4, "skX": 30, "skY": 30},
                },
            ],
            "slot": [{"name": "hand", "parent": "arm", "displayIndex": 0}],
            "skin": [
                {
                    "name": "default",
                    "slot": [
                        {
                            "name": "hand",
                            "display": [
                                {"name": "closed", "path": "closed"},
                                {"name": "open", "path": "open"},
                            ],
                        }
                    ],
                }
            ],
            "animation": [
                {
                    "name": "wave",
                    "duration": 10,
                    "bone": [
                        {
                            "name": "arm",
                            "frame": [
                                {"duration": 5, "transform": {"skY": 0}},
                                {"duration": 5, "transform": {"skY": 40}},
                            ],
                        }
                    ],
                    "slot": [
                        {
                            "name": "hand",
                            "frame": [
                                {"duration": 5, "displayIndex": 0},
                                {"duration": 5, "displayIndex": 1},
                            ],
                        }
                    ],
                }
            ],
        }
    ],
}


def test_dragonbones_bones_slots_and_keyframes_import_to_shared_skeleton_model():
    skeleton = import_dragonbones_json(
        RIG,
        sheet_asset_id="hero_atlas",
        frames={"closed": 2, "open": 3},
    )

    arm = skeleton.bone("arm")
    assert (arm.x, arm.y, arm.rotation, arm.length) == (10, -4, -30, 8)
    assert skeleton.slots[0].bone_id == "arm" and skeleton.slots[0].frame == 2
    clip = skeleton.clips["wave"]
    assert clip.duration == pytest.approx(1.0)
    assert clip.sample("arm", "rotation", 0.75, 0) == pytest.approx(-40)
    assert clip.frame_for("hand", 0.75, 2) == 3


def test_unsupported_dragonbones_constructs_are_reported_and_not_imported_as_guesses():
    data = json.loads(json.dumps(RIG))
    data["armature"][0]["ik"] = [{"name": "leg"}]
    data["armature"][0]["animation"][0]["ffd"] = [{"name": "mesh"}]

    assert unsupported_parts(data) == ("ik constraints", "FFD deformation")


def test_armature_and_skin_selection_is_explicit_when_ambiguous():
    data = json.loads(json.dumps(RIG))
    data["armature"].append({**data["armature"][0], "name": "second"})
    with pytest.raises(DragonBonesImportError, match="armature_name"):
        import_dragonbones_json(data)
    assert import_dragonbones_json(data, armature_name="hero").skeleton_id == "hero"


def test_viewer_loader_dispatches_dragonbones_json(tmp_path):
    path = tmp_path / "hero.json"
    path.write_text(json.dumps(RIG), encoding="utf-8")

    skeleton, notes = load_rig(path, frames={"closed": 2, "open": 3})

    assert skeleton.skeleton_id == "hero" and notes == ()


def test_skew_mesh_visibility_and_custom_easing_are_explicitly_reported():
    data = json.loads(json.dumps(RIG))
    armature = data["armature"][0]
    armature["bone"][1]["transform"]["skX"] = 15
    armature["skin"][0]["slot"][0]["display"][0]["type"] = "mesh"
    armature["animation"][0]["bone"][0]["frame"][0]["tweenEasing"] = 0.5
    armature["animation"][0]["slot"][0]["frame"][1]["displayIndex"] = -1

    notes = unsupported_parts(data)

    assert "bone skew" in notes
    assert "mesh, child armature, and bounding-box displays" in notes
    assert "custom animation easing" in notes
    assert "slot visibility and color animation" in notes
