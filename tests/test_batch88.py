import pytest

from asteria.presentation.actor_attachment import ActorAnimationPose, ActorAttachmentFrame
from asteria.presentation.attachments import Transform2D
from asteria.presentation.render_integration import PresentationRenderComposer, RenderTransform, combine


def test_parent_rotation_rotates_child_offset():
    t = combine(RenderTransform(x=10, y=20, rotation_deg=90), RenderTransform(x=4, y=0))
    assert t.x == pytest.approx(10)
    assert t.y == pytest.approx(24)


def test_parent_scale_affects_child_offset():
    t = combine(RenderTransform(scale_x=2, scale_y=3), RenderTransform(x=4, y=5))
    assert (t.x, t.y) == pytest.approx((8, 15))


def test_flip_survives_renderer_boundary():
    t = combine(RenderTransform(flip_x=True), RenderTransform(flip_y=True))
    assert t.flip_x and t.flip_y


def test_parent_flip_mirrors_child_translation():
    t = combine(RenderTransform(x=10, flip_x=True), RenderTransform(x=3, y=2))
    assert (t.x, t.y) == pytest.approx((7, 2))


def test_double_flip_cancels():
    t = combine(RenderTransform(flip_x=True, flip_y=True), RenderTransform(flip_x=True, flip_y=True))
    assert not t.flip_x and not t.flip_y


def test_attachment_flip_is_not_discarded():
    pose = Transform2D(x=2, flip_x=True)
    frame = ActorAttachmentFrame(
        "a", ActorAnimationPose("idle", 0, 0), (type("R", (), {"asset_id": "hat", "transform": pose, "id": "hat"})(),)
    )
    packets = PresentationRenderComposer().actor_packets(frame, "actor")
    assert packets[1].transform.flip_x is True


def test_rotation_scale_and_flip_compose_together():
    t = combine(
        RenderTransform(x=5, y=5, rotation_deg=90, scale_x=2, scale_y=3, flip_x=True),
        RenderTransform(x=2, y=1, rotation_deg=10, scale_x=0.5, scale_y=2),
    )
    assert t.x == pytest.approx(2)
    assert t.y == pytest.approx(1)
    assert t.rotation_deg == pytest.approx(100)
    assert (t.scale_x, t.scale_y) == pytest.approx((1, 6))
    assert t.flip_x
