import pytest
from asteria.presentation.attachments import SocketRig, Socket, SocketKey, Transform2D, Attachment
from asteria.presentation.attachment_runtime import AttachmentRuntime
from asteria.presentation.actor_attachment import ActorAnimationPose
from asteria.presentation.property_animation import *
from asteria.presentation.render_integration import RenderTransform
from asteria.presentation.e2e_pipeline import *


class Animator:
    def __init__(self, frame=0, sub=0.0):
        self.frame = frame
        self.sub = sub

    def presentation_pose(self):
        return ActorAnimationPose("project.custom.attack", self.frame, self.sub)


def actor(actor_id="hero", asset="char.hero", frame=0, sub=0):
    rig = SocketRig()
    rig.add(
        Socket("hand", default=Transform2D(x=4), keys=(SocketKey(0, Transform2D(x=4)), SocketKey(1, Transform2D(x=8))))
    )
    rt = AttachmentRuntime(rig)
    rt.attach(Attachment("held", "item.sword", "hand"))
    return SceneActorBinding(actor_id, asset, Animator(frame, sub), rt, RenderTransform(x=100, y=50))


def test_asset_to_actor_attachment_to_renderer_e2e():
    f = PresentationE2EPipeline((actor(),), asset_exists=lambda x: x in {"char.hero", "item.sword"}).sample(0)
    assert [p.asset_id for p in f.draw_packets] == ["char.hero", "item.sword"]
    assert f.draw_packets[1].transform.x == 104


def test_animator_subframe_reaches_renderer():
    f = PresentationE2EPipeline((actor(frame=0, sub=0.5),)).sample(0)
    assert f.draw_packets[1].transform.x == pytest.approx(106)


def test_continuous_actor_property_independent_of_sprite_frame():
    props = PropertyAnimator((PropertyCurve("actor.hero.x", (PropertyKey(0, 0), PropertyKey(100, 10))),))
    pipe = PresentationE2EPipeline((actor(),), props)
    assert pipe.sample(25).draw_packets[0].transform.x == pytest.approx(102.5)
    assert pipe.sample(26).draw_packets[0].transform.x == pytest.approx(102.6)


def test_generic_actor_property_fallback():
    props = PropertyAnimator((PropertyCurve("actor.opacity", (PropertyKey(0, 1), PropertyKey(100, 0.5))),))
    assert PresentationE2EPipeline((actor(),), props).sample(50).draw_packets[0].transform.opacity == pytest.approx(
        0.75
    )


def test_camera_material_vfx_audio_channels_flow():
    props = PropertyAnimator(
        (
            PropertyCurve("camera.zoom", (PropertyKey(0, 1), PropertyKey(100, 2))),
            PropertyCurve("material.glow", (PropertyKey(0, 0), PropertyKey(100, 1))),
            PropertyCurve("vfx.rate", (PropertyKey(0, 1), PropertyKey(100, 3))),
            PropertyCurve("audio.volume", (PropertyKey(0, 1), PropertyKey(100, 0))),
        )
    )
    c = PresentationE2EPipeline((actor(),), props).sample(50).channels
    assert c.camera["zoom"] == pytest.approx(1.5) and c.material["glow"] == pytest.approx(0.5)
    assert c.vfx["rate"] == pytest.approx(2) and c.audio["volume"] == pytest.approx(0.5)


def test_vibration_modulation_flows_through_e2e():
    props = PropertyAnimator(modulations=(Modulation("actor.hero.x", Oscillator(5, 10), Envelope(100)),))
    pipe = PresentationE2EPipeline((actor(),), props)
    assert pipe.sample(12.5).draw_packets[0].transform.x != pipe.sample(13.5).draw_packets[0].transform.x


def test_multiple_actors_deterministic():
    f = PresentationE2EPipeline((actor("b", "char.b"), actor("a", "char.a"))).sample(0)
    assert [(p.owner_id, p.component_id) for p in f.draw_packets] == [
        ("a", "actor"),
        ("a", "held"),
        ("b", "actor"),
        ("b", "held"),
    ]


def test_missing_actor_asset_rejected():
    with pytest.raises(ValueError, match="unknown asset"):
        PresentationE2EPipeline((actor(),), asset_exists=lambda _: False).sample(0)


def test_missing_attachment_asset_rejected():
    with pytest.raises(ValueError, match="item.sword"):
        PresentationE2EPipeline((actor(),), asset_exists=lambda x: x == "char.hero").sample(0)


def test_duplicate_actor_id_rejected():
    with pytest.raises(ValueError):
        PresentationE2EPipeline((actor(), actor()))


def test_arbitrary_clip_has_no_engine_semantics():
    f = PresentationE2EPipeline((actor(),)).sample(0)
    assert len(f.draw_packets) == 2


def test_negative_time_rejected():
    with pytest.raises(ValueError):
        PresentationE2EPipeline((actor(),)).sample(-1)
