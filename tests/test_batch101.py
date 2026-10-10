import math
import pytest

from asteria.presentation.attachments import Attachment, GripTransform, Socket, SocketRig, Transform2D
from asteria.presentation.attachment_runtime import AttachmentRuntime
from asteria.presentation.actor_attachment import ActorAnimationPose, ActorAttachmentBinding
from asteria.presentation.render_integration import ActorVisualLayer, PresentationRenderComposer, RenderTransform
from asteria.presentation.presentation_state import PresentationStateCodec, capture_state, restore_state


class Animator:
    def presentation_pose(self):
        return ActorAnimationPose("one_hand_slash", 0)


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
    sword = Attachment("held", "iron_sword", "hand_r", grip=GripTransform(x=10, y=2, rotation_deg=5))
    katana = Attachment("held", "katana", "hand_r", grip=GripTransform(x=17, y=4, rotation_deg=-8))
    rt.attach(sword)
    a = rt.resolve("held", 0)
    rt.swap("held", katana)
    b = rt.resolve("held", 0)
    assert grip_world(a.transform, sword.grip) == pytest.approx((24, 20, 30))
    assert grip_world(b.transform, katana.grip) == pytest.approx((24, 20, 30))
    assert a.transform != b.transform  # asset origins differ; the hand target does not


def test_attachment_can_render_between_body_and_foreground_hand():
    rt = AttachmentRuntime(rig())
    rt.attach(Attachment("held", "sword", "hand_r", render_layer="held"))
    frame = ActorAttachmentBinding("hero", Animator(), rt).resolve()
    packets = PresentationRenderComposer().actor_packets(
        frame,
        "hero.body",
        actor_layers=(ActorVisualLayer("hero.hand_foreground", 20, "hand_foreground"),),
        layer_z={"held": 10},
    )
    assert [p.asset_id for p in packets] == ["hero.body", "sword", "hero.hand_foreground"]


def test_attachment_can_render_behind_character():
    rt = AttachmentRuntime(rig())
    rt.attach(Attachment("held", "spear", "hand_r", render_layer="behind"))
    frame = ActorAttachmentBinding("hero", Animator(), rt).resolve()
    packets = PresentationRenderComposer().actor_packets(frame, "hero.body")
    assert [p.asset_id for p in packets] == ["spear", "hero.body"]


def test_layer_names_are_project_extensible():
    rt = AttachmentRuntime(rig())
    rt.attach(Attachment("held", "custom", "hand_r", render_layer="between_coat_and_hand"))
    frame = ActorAttachmentBinding("hero", Animator(), rt).resolve()
    packets = PresentationRenderComposer().actor_packets(frame, "hero.body", layer_z={"between_coat_and_hand": 7.5})
    assert next(p for p in packets if p.asset_id == "custom").z == pytest.approx(7.5)


def test_grip_and_render_layer_roundtrip_presentation_state():
    rt = AttachmentRuntime(rig())
    spec = Attachment(
        "held", "sword", "hand_r", metadata={"kind": "generic"}, grip=GripTransform(9, 2, 12), render_layer="held"
    )
    rt.attach(spec)
    encoded = PresentationStateCodec.dumps(capture_state(rt))
    restored, _ = restore_state(PresentationStateCodec.loads(encoded))
    out = restored.instances["held"].spec
    assert out.grip == spec.grip
    assert out.render_layer == "held"
    assert out.metadata == {"kind": "generic"}


def test_legacy_attachment_defaults_remain_compatible():
    rt = AttachmentRuntime(rig())
    rt.attach(Attachment("hat", "hat", "hand_r"))
    out = rt.resolve("hat", 0)
    assert out.render_layer == "attachment"
    assert (out.transform.x, out.transform.y) == pytest.approx((24, 20))


def test_actor_root_transform_still_applies_after_grip_placement():
    rt = AttachmentRuntime(rig())
    g = GripTransform(5, 0)
    rt.attach(Attachment("held", "sword", "hand_r", grip=g))
    frame = ActorAttachmentBinding("hero", Animator(), rt).resolve()
    packet = next(
        p
        for p in PresentationRenderComposer().actor_packets(frame, "hero", actor_transform=RenderTransform(x=100, y=50))
        if p.asset_id == "sword"
    )
    x, y, _ = grip_world(packet.transform, g)
    assert (x, y) == pytest.approx((124, 70))
