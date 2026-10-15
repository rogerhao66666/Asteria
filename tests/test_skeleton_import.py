"""Spine-style JSON import: bones, slots, timelines, curves, y flip and what is skipped."""

import json

import pytest

from asteria.graphics.skeleton_import import (
    SkeletonImportError,
    import_spine_json,
    unsupported_parts,
)

RIG = {
    "skeleton": {"name": "hero"},
    "bones": [
        {"name": "root"},
        {"name": "arm", "parent": "root", "x": 10, "y": 4, "length": 20, "rotation": 30},
    ],
    "slots": [
        {"name": "body", "bone": "root", "attachment": "torso"},
        {"name": "hand", "bone": "arm", "attachment": "fist"},
        {"name": "ghost", "bone": "arm"},
    ],
    "animations": {
        "wave": {
            "bones": {
                "arm": {
                    "rotate": [
                        {"time": 0, "value": 0},
                        {"time": 0.5, "angle": 40, "curve": "stepped"},
                        {"time": 1.0, "value": 0, "curve": [0.25, 0, 0.75, 1]},
                    ],
                    "translate": [{"time": 0, "x": 0, "y": 0}, {"time": 1, "x": 6, "y": 2}],
                },
                "root": {"scale": [{"time": 0, "x": 1, "y": 1}, {"time": 1, "x": 2, "y": 1}]},
            },
            "slots": {
                "hand": {
                    "attachment": [{"time": 0, "name": "fist"}, {"time": 0.6, "name": "open"}]
                }
            },
        }
    },
}
FRAMES = {"torso": 1, "fist": 2, "open": 3}


def test_bones_and_slots_come_over_with_the_y_axis_flipped():
    skeleton = import_spine_json(RIG, sheet_asset_id="sheet", frames=FRAMES)
    arm = skeleton.bone("arm")
    assert (arm.x, arm.y, arm.rotation, arm.length) == (10.0, -4.0, -30.0, 20.0)
    slots = {s.slot_id: s for s in skeleton.slots}
    assert slots["hand"].frame == 2 and slots["body"].z < slots["hand"].z
    assert not slots["ghost"].visible  # no attachment: nothing to draw
    kept = import_spine_json(RIG, flip_y=False)
    assert kept.bone("arm").y == 4.0 and kept.bone("arm").rotation == 30.0


def test_timelines_become_clip_tracks_with_curves():
    skeleton = import_spine_json(RIG, frames=FRAMES)
    clip = skeleton.clips["wave"]
    assert clip.duration == 1.0
    assert clip.sample("arm", "rotation", 0.25, 0) == pytest.approx(-20.0)  # flipped, linear
    assert clip.sample("arm", "rotation", 0.75, 0) == pytest.approx(-40.0)  # stepped: held
    assert clip.sample("arm", "x", 0.9999, 0) == pytest.approx(6.0, abs=1e-2)
    assert clip.sample("arm", "y", 0.9999, 0) == pytest.approx(-2.0, abs=1e-2)
    assert clip.sample("root", "scale_x", 0.9999, 1.0) == pytest.approx(2.0, abs=1e-2)
    assert clip.frame_for("hand", 0.7, 2) == 3 and clip.frame_for("hand", 0.1, 9) == 2


def test_the_imported_rig_poses_and_draws():
    skeleton = import_spine_json(RIG, sheet_asset_id="sheet", frames=FRAMES)
    pose = skeleton.pose("wave", 0.0)
    assert (pose["arm"].x, pose["arm"].y) == (10.0, -4.0)
    draws = skeleton.draws(pose, "wave", 0.7)
    assert [d.slot_id for d in draws] == ["body", "hand"]  # the hidden slot is skipped
    assert [d.frame for d in draws] == [1, 3]


def test_split_axis_timelines_and_scale_option():
    data = {
        "bones": [{"name": "root", "length": 10}],
        "animations": {
            "a": {
                "bones": {
                    "root": {
                        "translatex": [{"time": 0, "value": 0}, {"time": 1, "value": 5}],
                        "translatey": [{"time": 0, "value": 0}, {"time": 1, "value": 5}],
                        "scalex": [{"time": 0, "value": 1}, {"time": 1, "value": 3}],
                    }
                }
            }
        },
    }
    skeleton = import_spine_json(data, scale=2.0)
    clip = skeleton.clips["a"]
    assert skeleton.bone("root").length == 20.0
    assert clip.sample("root", "x", 0.9999, 0) == pytest.approx(10.0, abs=1e-2)
    assert clip.sample("root", "y", 0.9999, 0) == pytest.approx(-10.0, abs=1e-2)
    assert clip.sample("root", "scale_x", 0.9999, 1) == pytest.approx(3.0, abs=1e-2)


def test_a_parsed_file_round_trips_through_json_text():
    skeleton = import_spine_json(json.loads(json.dumps(RIG)), frames=FRAMES)
    assert set(skeleton.clips) == {"wave"} and len(skeleton.bones) == 2


def test_what_is_skipped_is_reported_not_guessed():
    data = {**RIG, "skins": [{"name": "default"}], "ik": [{"name": "leg"}]}
    assert unsupported_parts(data) == ("skins", "ik")
    assert unsupported_parts(RIG) == ()


def test_bad_files_are_refused():
    with pytest.raises(SkeletonImportError):
        import_spine_json({})
    with pytest.raises(SkeletonImportError):
        import_spine_json({"bones": [{"x": 1}]})
    with pytest.raises(ValueError):  # a child listed before its parent
        import_spine_json({"bones": [{"name": "b", "parent": "a"}, {"name": "a"}]})
