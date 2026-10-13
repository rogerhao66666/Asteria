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


def grip_world(t, g):
    dx = g.x * t.scale_x * (-1 if t.flip_x else 1)
    dy = g.y * t.scale_y * (-1 if t.flip_y else 1)
    a = math.radians(t.rotation_deg)
    return (
        t.x + dx * math.cos(a) - dy * math.sin(a),
        t.y + dx * math.sin(a) + dy * math.cos(a),
        t.rotation_deg + (-g.rotation_deg if t.flip_x else g.rotation_deg),
    )


def make_runtime(grip=GripTransform(8, 3, 15)):
    rig = SocketRig()
    rig.add(Socket("hand_r", default=Transform2D(x=31, y=20, rotation_deg=30)))
    rt = AttachmentRuntime(rig)
    rt.attach(Attachment("held", "blade", "hand_r", grip=grip, render_layer="held"))
    return rt


def test_flip_aware_grip_placement_preserves_target():
    # Direct flipped socket target must still place the authored grip exactly.
    rig = SocketRig()
    rig.add(Socket("hand", default=Transform2D(x=17, y=9, rotation_deg=-20, flip_x=True)))
    g = GripTransform(7, 2, 0)
    rt = AttachmentRuntime(rig)
    rt.attach(Attachment("a", "asset", "hand", grip=g))
    out = rt.resolve("a", 0).transform
    x, y, _ = grip_world(out, g)
    assert (x, y) == pytest.approx((17, 9))
