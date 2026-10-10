import pytest
from asteria.presentation.attachments import *
from asteria.presentation.attachment_runtime import *
from asteria.presentation.actor_attachment import ActorAnimationPose
from asteria.presentation.e2e_pipeline import *
from asteria.presentation.property_animation import *
from asteria.presentation.render_integration import RenderTransform
from asteria.presentation.session_persistence import *


class Animator:
    def __init__(self, frame=0, sub=0.5):
        self.frame = frame
        self.sub = sub

    def presentation_pose(self):
        return ActorAnimationPose("project.any", self.frame, self.sub)


def make_pipeline():
    rig = SocketRig()
    rig.add(
        Socket("hand", default=Transform2D(x=2), keys=(SocketKey(0, Transform2D(x=2)), SocketKey(1, Transform2D(x=6))))
    )
    rt = AttachmentRuntime(rig)
    rt.attach(Attachment("blade", "asset.sword", "hand", metadata={"slot": "anything"}))
    rt.attach(Attachment("aura", "asset.aura", "hand"))
    rt.set_visible("aura", False)
    props = PropertyAnimator(
        (
            PropertyCurve("actor.hero.x", (PropertyKey(0, 0), PropertyKey(1000, 100, Ease.EASE_IN_OUT))),
            PropertyCurve("camera.zoom", (PropertyKey(0, 1), PropertyKey(1000, 1.4))),
        ),
        (Modulation("actor.hero.y", Oscillator(3, 20), Envelope(800, 0, 1)),),
    )
    assets = {"actor.hero", "asset.sword", "asset.aura"}
    return PresentationE2EPipeline(
        (SceneActorBinding("hero", "actor.hero", Animator(), rt, RenderTransform(x=10), {"tag": "persist"}),),
        props,
        assets.__contains__,
    )


def test_save_close_reload_renderer_equivalence():
    p = make_pipeline()
    t = 237.5
    before = p.sample(t)
    text = SessionCodec.dumps(capture_session(p, t))
    del p
    restored = restore_session(
        SessionCodec.loads(text), lambda _: Animator(), {"actor.hero", "asset.sword", "asset.aura"}.__contains__
    )
    after = restored.sample(t)
    assert after == before


def test_continue_after_reload():
    p = make_pipeline()
    text = SessionCodec.dumps(capture_session(p, 250))
    r = restore_session(
        SessionCodec.loads(text), lambda _: Animator(), {"actor.hero", "asset.sword", "asset.aura"}.__contains__
    )
    assert r.sample(400).draw_packets != r.sample(250).draw_packets


def test_playhead_survives():
    s = capture_session(make_pipeline(), 321.25)
    assert SessionCodec.loads(SessionCodec.dumps(s)).playhead_ms == 321.25


def test_stable_attachment_identity_and_metadata():
    s = SessionCodec.loads(SessionCodec.dumps(capture_session(make_pipeline(), 10)))
    r = restore_session(s, lambda _: Animator())
    inst = r.actors[0].attachments.instances["blade"]
    assert inst.spec.asset_id == "asset.sword" and inst.spec.metadata["slot"] == "anything"


def test_hidden_lifecycle_survives():
    r = restore_session(
        SessionCodec.loads(SessionCodec.dumps(capture_session(make_pipeline(), 10))), lambda _: Animator()
    )
    assert r.actors[0].attachments.instances["aura"].state is AttachmentState.HIDDEN
    assert all(x.asset_id != "asset.aura" for x in r.sample(10).draw_packets)


def test_curves_and_vibration_continue_identically():
    p = make_pipeline()
    s = capture_session(p, 100)
    r = restore_session(SessionCodec.loads(SessionCodec.dumps(s)), lambda _: Animator())
    for t in (100, 123.25, 500, 799):
        assert r.properties.sample(t) == pytest.approx(p.properties.sample(t))


def test_asset_preflight_still_applies_after_reload():
    s = SessionCodec.loads(SessionCodec.dumps(capture_session(make_pipeline(), 10)))
    r = restore_session(s, lambda _: Animator(), lambda asset: asset != "asset.sword")
    with pytest.raises(ValueError, match="unknown asset"):
        r.sample(10)


def test_actor_base_transform_and_metadata_survive():
    r = restore_session(
        SessionCodec.loads(SessionCodec.dumps(capture_session(make_pipeline(), 10))), lambda _: Animator()
    )
    a = r.actors[0]
    assert a.base_transform.x == 10 and a.metadata["tag"] == "persist"


def test_socket_subframe_state_reconstructed():
    p = make_pipeline()
    s = SessionCodec.loads(SessionCodec.dumps(capture_session(p, 10)))
    r = restore_session(s, lambda _: Animator())
    # animator subframe=.5; keyed hand socket must still resolve the same after reconstruction
    assert r.sample(10).draw_packets == p.sample(10).draw_packets


def test_bad_session_schema_rejected():
    with pytest.raises(ValueError, match="unsupported session schema"):
        SessionCodec.loads('{"schema_version":999,"playhead_ms":0,"actors":[]}')


def test_duplicate_actor_rejected():
    a = ActorSession("x", "a", RenderTransform(), "{}", {})
    with pytest.raises(ValueError, match="duplicate actor"):
        PresentationSession((a, a), 0)


def test_negative_playhead_rejected():
    with pytest.raises(ValueError, match="negative playhead"):
        PresentationSession((), -1)


def test_multiple_actor_restore():
    p = make_pipeline()
    # use independently captured actor runtime but same shared properties
    rig = SocketRig()
    rig.add(Socket("root"))
    rt = AttachmentRuntime(rig)
    actors = p.actors + (SceneActorBinding("npc", "actor.npc", Animator(0, 0), rt),)
    p2 = PresentationE2EPipeline(actors, p.properties)
    s = SessionCodec.loads(SessionCodec.dumps(capture_session(p2, 55)))
    r = restore_session(s, lambda _: Animator())
    assert [a.actor_id for a in r.actors] == ["hero", "npc"]
