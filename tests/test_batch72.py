import pytest

from asteria.presentation.animation_attachment import (
    AnimatedAttachmentBinding,
    AnimationAttachmentPlayer,
    AnimationClock,
    FrameTiming,
)
from asteria.presentation.attachment_runtime import AttachmentRuntime
from asteria.presentation.attachments import Attachment, Socket, SocketKey, SocketRig, Transform2D


def T(x=0, y=0, r=0, sx=1, sy=1, **kw):
    return Transform2D(x, y, r, sx, sy, **kw)


def runtime_with_keyed_hand():
    rig = SocketRig()
    rig.add(Socket("root", default=T(100, 50)))
    rig.add(
        Socket(
            "hand",
            parent="root",
            keys=(
                SocketKey(0, T(0, 0)),
                SocketKey(1, T(10, 0)),
                SocketKey(2, T(20, 10)),
            ),
        )
    )
    rt = AttachmentRuntime(rig)
    rt.attach(Attachment("held", "asset.sword", "hand"))
    return rt


def test_uniform_clock_maps_time_to_frame_and_subframe():
    clock = AnimationClock.uniform(4, 10)
    s = clock.sample(150)
    assert s.frame == 1
    assert s.subframe == pytest.approx(0.5)


def test_variable_frame_timing():
    clock = AnimationClock((FrameTiming(100), FrameTiming(300), FrameTiming(50)), loop=False)
    s = clock.sample(250)
    assert s.frame == 1
    assert s.subframe == pytest.approx(0.5)


def test_loop_wraps_without_changing_attachment_contract():
    clock = AnimationClock.uniform(2, 10, loop=True)
    assert clock.sample(250).frame == 0
    assert clock.sample(250).subframe == pytest.approx(0.5)


def test_non_loop_holds_last_frame():
    clock = AnimationClock.uniform(3, 10, loop=False)
    s = clock.sample(1000)
    assert (s.frame, s.subframe, s.finished) == (2, 1.0, True)


def test_binding_samples_socket_from_animation_clock():
    binding = AnimatedAttachmentBinding(runtime_with_keyed_hand(), AnimationClock.uniform(3, 10, loop=False))
    pose = binding.resolve_at(150)
    held = pose.attachments[0]
    assert pose.sample.frame == 1
    assert pose.sample.subframe == pytest.approx(0.5)
    assert held.transform.x == pytest.approx(115)
    assert held.transform.y == pytest.approx(55)


def test_binding_resolves_generic_non_weapon_attachment():
    rt = runtime_with_keyed_hand()
    rt.attach(Attachment("spark", "vfx.spark", "hand", local=T(2, 3)))
    binding = AnimatedAttachmentBinding(rt, AnimationClock.uniform(3, 10))
    pose = binding.resolve_at(100)
    assert {a.asset_id for a in pose.attachments} == {"asset.sword", "vfx.spark"}


def test_hidden_attachment_stays_bound_but_invisible():
    rt = runtime_with_keyed_hand()
    rt.set_visible("held", False)
    binding = AnimatedAttachmentBinding(rt, AnimationClock.uniform(3, 10))
    out = binding.resolve_one_at("held", 100)
    assert not out.transform.visible


def test_detached_attachment_disappears_from_pose():
    rt = runtime_with_keyed_hand()
    binding = AnimatedAttachmentBinding(rt, AnimationClock.uniform(3, 10))
    rt.detach("held")
    assert binding.resolve_at(100).attachments == ()


def test_player_update_advances_attachment_pose():
    player = AnimationAttachmentPlayer(
        AnimatedAttachmentBinding(runtime_with_keyed_hand(), AnimationClock.uniform(3, 10, loop=False))
    )
    pose = player.update(150)
    assert pose.sample.frame == 1
    assert pose.attachments[0].transform.x == pytest.approx(115)


def test_player_pause_freezes_time():
    player = AnimationAttachmentPlayer(
        AnimatedAttachmentBinding(runtime_with_keyed_hand(), AnimationClock.uniform(3, 10))
    )
    player.pause()
    a = player.update(100)
    b = player.update(100)
    assert a.sample == b.sample


def test_player_seek_supports_editor_scrub():
    player = AnimationAttachmentPlayer(
        AnimatedAttachmentBinding(runtime_with_keyed_hand(), AnimationClock.uniform(3, 10))
    )
    pose = player.seek(200)
    assert pose.sample.frame == 2
    assert pose.attachments[0].transform.x == pytest.approx(120)
    assert pose.attachments[0].transform.y == pytest.approx(60)


def test_non_loop_player_stops_after_finish():
    player = AnimationAttachmentPlayer(
        AnimatedAttachmentBinding(runtime_with_keyed_hand(), AnimationClock.uniform(3, 10, loop=False))
    )
    pose = player.update(1000)
    assert pose.sample.finished
    assert not player.playing


def test_invalid_clock_inputs_rejected():
    with pytest.raises(ValueError):
        AnimationClock(())
    with pytest.raises(ValueError):
        AnimationClock.uniform(0, 10)
    with pytest.raises(ValueError):
        AnimationClock.uniform(2, 0)
    with pytest.raises(ValueError):
        FrameTiming(0)


def test_negative_time_and_dt_rejected():
    clock = AnimationClock.uniform(2, 10)
    with pytest.raises(ValueError):
        clock.sample(-1)
    player = AnimationAttachmentPlayer(AnimatedAttachmentBinding(runtime_with_keyed_hand(), clock))
    with pytest.raises(ValueError):
        player.seek(-1)
    with pytest.raises(ValueError):
        player.update(-1)
