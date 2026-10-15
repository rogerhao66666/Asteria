"""2D skeleton animation: bone hierarchy, keyframes, easing, blending, IK and sprite draws."""

from math import cos, hypot, radians, sin

import pytest

from asteria.graphics.skeleton import (
    Bone,
    Key,
    Skeleton,
    SkeletonClip,
    Slot,
    solve_two_bone,
)


def _arm():
    return Skeleton(
        "arm",
        bones=(
            Bone("root"),
            Bone("upper", "root", x=10, y=0, length=20),
            Bone("lower", "upper", x=20, y=0, length=10),
        ),
        slots=(
            Slot("hand", "lower", "sheet", frame=2, offset_x=10, z=2),
            Slot("sleeve", "upper", "sheet", frame=1, z=1),
            Slot("hidden", "root", "sheet", visible=False),
        ),
    )


def _near(a, b, eps=1e-6):
    return abs(a - b) < eps


def test_rest_pose_stacks_the_bones_along_the_x_axis():
    pose = _arm().pose()
    assert (pose["upper"].x, pose["upper"].y) == (10, 0)
    assert (pose["lower"].x, pose["lower"].y) == (30, 0)
    assert _arm().tip(pose, "lower") == (40, 0)


def test_rotating_a_parent_swings_its_children():
    clip = SkeletonClip("bend", 1.0, tracks={("upper", "rotation"): [Key(0, 90)]})
    skeleton = _arm()
    skeleton.clips = {"bend": clip}
    pose = skeleton.pose("bend", 0.0)
    assert _near(pose["lower"].x, 10) and _near(pose["lower"].y, 20)  # 20 along "down" (+y)
    assert _near(pose["lower"].rotation, 90)


def test_parent_scale_stretches_the_childs_offset():
    clip = SkeletonClip("big", 1.0, tracks={("upper", "scale_x"): [Key(0, 2.0)]})
    skeleton = _arm()
    skeleton.clips = {"big": clip}
    pose = skeleton.pose("big", 0.0)
    assert _near(pose["lower"].x, 10 + 20 * 2) and pose["lower"].scale_x == 2.0


def test_keys_interpolate_with_their_easing_and_the_clip_loops():
    keys = [Key(0, 0, "linear"), Key(1, 100, "step"), Key(2, 0)]
    clip = SkeletonClip("c", 2.0, tracks={("root", "x"): keys})
    assert clip.sample("root", "x", 0.5, 0) == 50
    assert clip.sample("root", "x", 1.5, 0) == 100  # a step key holds until the next one
    assert clip.sample("root", "x", 2.5, 0) == 50  # looped: 2.5 -> 0.5
    assert clip.sample("root", "y", 0.5, 7) == 7  # unkeyed: the default
    eased = SkeletonClip("e", 1.0, tracks={("root", "x"): [Key(0, 0, "ease_in"), Key(1, 10)]})
    assert eased.sample("root", "x", 0.5, 0) == pytest.approx(2.5)
    out = SkeletonClip("o", 1.0, tracks={("root", "x"): [Key(0, 0, "ease_out"), Key(1, 10)]})
    assert out.sample("root", "x", 0.5, 0) == pytest.approx(7.5)


def test_a_clip_that_does_not_loop_holds_its_last_value():
    clip = SkeletonClip("once", 1.0, loop=False, tracks={("root", "x"): [Key(0, 0), Key(1, 10)]})
    assert clip.sample("root", "x", 5.0, 0) == 10 and clip.sample("root", "x", -1, 0) == 0


def test_blending_mixes_two_clips_and_turns_the_short_way_round():
    skeleton = _arm()
    skeleton.clips = {
        "a": SkeletonClip("a", 1.0, tracks={("upper", "rotation"): [Key(0, 350)]}),
        "b": SkeletonClip("b", 1.0, tracks={("upper", "rotation"): [Key(0, 10)]}),
    }
    mid = skeleton.pose("a", 0, blend="b", blend_time=0, weight=0.5)
    assert _near(mid["upper"].rotation % 360, 0)  # not 180: 350 -> 10 crosses zero
    assert skeleton.pose("a", 0, blend="b", weight=0.0)["upper"].rotation == 350
    with pytest.raises(KeyError):
        skeleton.pose("missing")


def test_slot_frames_switch_over_time_and_draws_sort_by_z():
    skeleton = _arm()
    skeleton.clips = {"wave": SkeletonClip("wave", 2.0, frames={"hand": ((0.0, 2), (1.0, 5))})}
    pose = skeleton.pose("wave", 1.5)
    draws = skeleton.draws(pose, "wave", 1.5, origin=(100, 50), scale=2.0)
    assert [d.slot_id for d in draws] == ["sleeve", "hand"]  # hidden slot skipped, z order
    hand = draws[1]
    assert hand.frame == 5 and draws[0].frame == 1
    assert (hand.x, hand.y) == (100 + (30 + 10) * 2.0, 50) and hand.scale_x == 2.0


def test_slot_offset_rotates_with_the_bone():
    skeleton = _arm()
    skeleton.clips = {"c": SkeletonClip("c", 1.0, tracks={("lower", "rotation"): [Key(0, 90)]})}
    pose = skeleton.pose("c", 0)
    (hand,) = [d for d in skeleton.draws(pose, "c", 0) if d.slot_id == "hand"]
    assert _near(hand.x, 30) and _near(hand.y, 10)  # offset 10 along the bone, which points +y


@pytest.mark.parametrize("target", [(15, 5), (-8, 10), (0, -14), (12, 12)])
@pytest.mark.parametrize("bend", [1, -1])
def test_two_bone_ik_reaches_a_reachable_target(target, bend):
    upper, lower = 10.0, 8.0
    first, second = solve_two_bone((0, 0), upper, lower, target, bend=bend)
    elbow = (upper * cos(radians(first)), upper * sin(radians(first)))
    end = (
        elbow[0] + lower * cos(radians(first + second)),
        elbow[1] + lower * sin(radians(first + second)),
    )
    assert hypot(end[0] - target[0], end[1] - target[1]) < 1e-6


def test_two_bone_ik_straightens_toward_an_unreachable_target():
    first, second = solve_two_bone((0, 0), 10, 8, (100, 0))
    assert (first, second) == (0.0, 0.0)
    first, _ = solve_two_bone((0, 0), 10, 8, (0, -100))
    assert _near(first, -90)


def test_the_bend_direction_flips_the_elbow():
    up = solve_two_bone((0, 0), 10, 10, (10, 0), bend=1)
    down = solve_two_bone((0, 0), 10, 10, (10, 0), bend=-1)
    assert up[0] == pytest.approx(-down[0]) and up[1] == pytest.approx(-down[1])
    assert up[0] != 0


def test_validation():
    with pytest.raises(ValueError):
        Skeleton("s", bones=(Bone("a"), Bone("a")))
    with pytest.raises(ValueError):
        Skeleton("s", bones=(Bone("child", "parent"), Bone("parent")))  # parent must come first
    with pytest.raises(ValueError):
        Skeleton("s", bones=(Bone("a"),), slots=(Slot("s", "ghost"),))
    with pytest.raises(ValueError):
        SkeletonClip("c", 0)
    with pytest.raises(ValueError):
        SkeletonClip("c", 1.0, tracks={("a", "spin"): [Key(0, 1)]})
    with pytest.raises(ValueError):
        SkeletonClip("c", 1.0, tracks={("a", "x"): [Key(2, 1)]})
    with pytest.raises(ValueError):
        Key(0, 1, "wobble")
    with pytest.raises(ValueError):
        solve_two_bone((0, 0), 0, 5, (1, 1))
    with pytest.raises(ValueError):
        Bone("a", x=float("nan"))


def test_sprite_rows_become_texture_draws_rotating_about_the_pivot():
    from types import SimpleNamespace

    from asteria.graphics.skeleton import SpriteDraw
    from asteria.runtime.skeleton_draw import to_texture_draws

    frame = SimpleNamespace(x=0, y=0, width=10, height=20, pivot_x=5, pivot_y=20)  # feet pivot
    sheet = SimpleNamespace(frames=[frame], texture=SimpleNamespace(asset_id="tex"))
    row = SpriteDraw("s", "sheet", 0, 100.0, 50.0, 0.0, 2.0, 2.0, 3)
    (draw,) = to_texture_draws([row], {"sheet": sheet}.get, layer=1)
    assert (draw.width, draw.height) == (20, 40) and draw.layer == 4
    assert (draw.screen_x, draw.screen_y) == (90.0, 10.0)  # the pivot (feet) sits on (100, 50)
    turned = SpriteDraw("s", "sheet", 0, 100.0, 50.0, 90.0, 1.0, 1.0, 0)
    (draw,) = to_texture_draws([turned], {"sheet": sheet}.get)
    centre = (draw.screen_x + draw.width / 2, draw.screen_y + draw.height / 2)
    assert centre == pytest.approx((110.0, 50.0)) and draw.rotation_deg == 90.0
    flipped = SpriteDraw("s", "sheet", 0, 0.0, 0.0, 0.0, -1.0, 1.0, 0)
    assert to_texture_draws([flipped], {"sheet": sheet}.get)[0].flip_x
    assert to_texture_draws([row], {}.get) == []  # an unknown sheet is skipped
