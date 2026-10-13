import math

import pytest

from asteria.presentation.attachment_runtime import AttachmentRuntime
from asteria.presentation.attachments import (
    Attachment,
    GripTransform,
    Socket,
    SocketRig,
    Transform2D,
)


def rig():
    r = SocketRig()
    r.add(Socket("hand_r", default=Transform2D(x=24, y=20, rotation_deg=30)))
    return r


def grip_world(asset_transform, grip):
    sx = grip.x * asset_transform.scale_x
    sy = grip.y * asset_transform.scale_y
    a = math.radians(asset_transform.rotation_deg)
    return (
        asset_transform.x + sx * math.cos(a) - sy * math.sin(a),
        asset_transform.y + sx * math.sin(a) + sy * math.cos(a),
        asset_transform.rotation_deg + grip.rotation_deg,
    )


def test_authored_grip_lands_on_socket_position_and_orientation():
    rt = AttachmentRuntime(rig())
    g = GripTransform(x=8, y=3, rotation_deg=15)
    rt.attach(Attachment("held", "iron_sword", "hand_r", grip=g))
    out = rt.resolve("held", 0).transform
    x, y, rotation = grip_world(out, g)
    assert (x, y) == pytest.approx((24, 20))
    assert rotation == pytest.approx(30)


def test_different_assets_can_share_same_body_motion_without_socket_changes():
    rt = AttachmentRuntime(rig())
    sword = Attachment(
        "held", "iron_sword", "hand_r", grip=GripTransform(x=10, y=2, rotation_deg=5)
    )
    katana = Attachment("held", "katana", "hand_r", grip=GripTransform(x=17, y=4, rotation_deg=-8))
    rt.attach(sword)
    a = rt.resolve("held", 0)
    rt.swap("held", katana)
    b = rt.resolve("held", 0)
    assert grip_world(a.transform, sword.grip) == pytest.approx((24, 20, 30))
    assert grip_world(b.transform, katana.grip) == pytest.approx((24, 20, 30))
    assert a.transform != b.transform  # asset origins differ; the hand target does not


def test_legacy_attachment_defaults_remain_compatible():
    rt = AttachmentRuntime(rig())
    rt.attach(Attachment("hat", "hat", "hand_r"))
    out = rt.resolve("hat", 0)
    assert out.render_layer == "attachment"
    assert (out.transform.x, out.transform.y) == pytest.approx((24, 20))
