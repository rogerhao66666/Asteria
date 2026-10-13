import json

import pytest

from asteria.presentation.attachments import (
    Attachment,
    Socket,
    SocketKey,
    SocketRig,
    Transform2D,
    validate_attachments,
)


def T(x=0, y=0, r=0, sx=1, sy=1, **kw):
    return Transform2D(x, y, r, sx, sy, **kw)


def test_static_socket():
    s = Socket("hand_r", default=T(3, 4, 20))
    s.validate()
    assert s.sample(9).x == 3


def test_keyed_sampling_interpolates_continuous_values():
    s = Socket("hand", keys=(SocketKey(0, T(0, 0, 0)), SocketKey(2, T(10, 4, 90))))
    x = s.sample(1)
    assert x.x == pytest.approx(5)
    assert x.y == pytest.approx(2)
    assert x.rotation_deg == pytest.approx(45)


def test_keyed_sampling_can_step():
    s = Socket("hand", keys=(SocketKey(0, T(1), False), SocketKey(3, T(9))))
    assert s.sample(2).x == 1


def test_arbitrary_semantics_not_weapon_specific():
    rig = SocketRig()
    rig.add(Socket("head"))
    rig.add(Socket("effect_anchor"))
    xs = validate_attachments(
        rig,
        [Attachment("hat", "asset.hat", "head"), Attachment("aura", "vfx.aura", "effect_anchor")],
    )
    assert [x.asset_id for x in xs] == ["asset.hat", "vfx.aura"]


def test_hierarchy_validation():
    rig = SocketRig()
    rig.add(Socket("root"))
    rig.add(Socket("hand", parent="root"))
    assert rig.sockets["hand"].parent == "root"


def test_missing_parent_rejected():
    with pytest.raises(ValueError):
        SocketRig({"x": Socket("x", parent="nope")}).validate()


def test_cycle_rejected():
    with pytest.raises(ValueError):
        SocketRig({"a": Socket("a", "b"), "b": Socket("b", "a")}).validate()


def test_self_parent_rejected_on_add():
    with pytest.raises(ValueError):
        SocketRig().add(Socket("x", "x"))


def test_transform_validation():
    with pytest.raises(ValueError):
        Transform2D(opacity=1.1).validate()
    with pytest.raises(ValueError):
        Transform2D(scale_x=-1).validate()


def test_flip_is_explicit():
    t = Transform2D(flip_x=True)
    t.validate()
    assert t.flip_x


def test_duplicate_attachment_rejected():
    rig = SocketRig({"x": Socket("x")})
    with pytest.raises(ValueError):
        validate_attachments(rig, [Attachment("a", "1", "x"), Attachment("a", "2", "x")])


def test_unknown_attachment_socket_rejected():
    with pytest.raises(ValueError):
        validate_attachments(SocketRig(), [Attachment("a", "asset", "missing")])


def test_round_trip_serialization():
    rig = SocketRig()
    rig.add(
        Socket(
            "root",
            pivot_x=2,
            pivot_y=7,
            keys=(SocketKey(0, T(1, 2)), SocketKey(4, T(8, 9))),
            metadata={"author": "project"},
        )
    )
    payload = json.loads(json.dumps(rig.to_dict()))
    out = SocketRig.from_dict(payload)
    assert out.sockets["root"].pivot_y == 7 and out.sample("root", 2).x == pytest.approx(4.5)


def test_discrete_values_switch_at_key():
    s = Socket(
        "x",
        keys=(
            SocketKey(0, Transform2D(visible=True, z_offset=1)),
            SocketKey(2, Transform2D(visible=False, z_offset=9)),
        ),
    )
    assert s.sample(1).visible is True and s.sample(1).z_offset == 1
    assert s.sample(2).visible is False and s.sample(2).z_offset == 9


def test_pre_first_key_uses_default():
    s = Socket("x", default=T(7), keys=(SocketKey(3, T(9)),))
    assert s.sample(1).x == 7


def test_last_key_holds():
    s = Socket("x", keys=(SocketKey(1, T(4)), SocketKey(2, T(6))))
    assert s.sample(99).x == 6


def test_duplicate_key_frame_rejected():
    with pytest.raises(ValueError):
        Socket("x", keys=(SocketKey(1), SocketKey(1))).validate()


def test_negative_frame_rejected():
    with pytest.raises(ValueError):
        SocketKey(-1).validate()
