import pytest

from asteria.presentation.attachments import Socket, SocketKey
from asteria.presentation.presentation_state import (
    Attachment,
    AttachmentRecord,
    AttachmentRuntime,
    AttachmentState,
    Ease,
    Envelope,
    Modulation,
    Oscillator,
    PresentationState,
    PresentationStateCodec,
    PropertyAnimator,
    PropertyCurve,
    PropertyKey,
    SocketRig,
    Transform2D,
    capture_state,
    restore_state,
)


def fixture():
    r = SocketRig()
    r.add(Socket("hand", default=Transform2D(x=3), keys=(SocketKey(1, Transform2D(x=7)),)))
    rt = AttachmentRuntime(r)
    a = rt.attach(Attachment("held", "asset.sword", "hand", metadata={"slot": "any"}))
    a.runtime_data["trail"] = True
    rt.attach(Attachment("aura", "asset.aura", "hand"))
    rt.set_visible("aura", False)
    rt.attach(Attachment("old", "asset.old", "hand"))
    rt.detach("old")
    pa = PropertyAnimator(
        (PropertyCurve("camera.zoom", (PropertyKey(0, 1), PropertyKey(100, 1.3, Ease.EASE_OUT))),),
        (Modulation("camera.x", Oscillator(3, 20), Envelope(120, 10)),),
    )
    return rt, pa


def test_json_round_trip_all_state():
    rt, pa = fixture()
    s = capture_state(rt, pa, 42.5, {"scene": "demo"})
    s2 = PresentationStateCodec.loads(PresentationStateCodec.dumps(s))
    assert PresentationStateCodec.encode(s2) == PresentationStateCodec.encode(s)


def test_restore_attachment_lifecycle_and_runtime_data():
    rt, pa = fixture()
    rr, _ = restore_state(PresentationStateCodec.loads(PresentationStateCodec.dumps(capture_state(rt, pa))))
    assert rr.instances["held"].state is AttachmentState.ACTIVE and rr.instances["held"].runtime_data["trail"] is True
    assert rr.instances["aura"].state is AttachmentState.HIDDEN
    assert rr.instances["old"].state is AttachmentState.DETACHED


def test_restore_same_resolved_pose():
    rt, pa = fixture()
    rr, _ = restore_state(capture_state(rt, pa))
    assert rr.resolve("held", 1).transform == rt.resolve("held", 1).transform


def test_curves_and_vibration_survive():
    rt, pa = fixture()
    _, p2 = restore_state(PresentationStateCodec.loads(PresentationStateCodec.dumps(capture_state(rt, pa))))
    assert p2.sample(25) == pytest.approx(pa.sample(25))


def test_stable_ids_and_asset_refs_survive():
    rt, pa = fixture()
    rr, _ = restore_state(PresentationStateCodec.loads(PresentationStateCodec.dumps(capture_state(rt, pa))))
    assert rr.instances["held"].spec.asset_id == "asset.sword" and rr.instances["held"].spec.id == "held"


def test_playhead_and_metadata_survive():
    rt, pa = fixture()
    s = PresentationStateCodec.loads(PresentationStateCodec.dumps(capture_state(rt, pa, 88.25, {"x": 1})))
    assert s.playhead_ms == 88.25 and s.metadata == {"x": 1}


def test_schema_rejects_unknown_version():
    with pytest.raises(ValueError):
        PresentationStateCodec.decode({"schema_version": 999})


def test_negative_playhead_rejected():
    rt, _ = fixture()
    with pytest.raises(ValueError):
        PresentationState(rt.rig, playhead_ms=-1)


def test_duplicate_attachment_identity_rejected():
    rt, _ = fixture()
    a = rt.instances["held"].spec
    with pytest.raises(ValueError):
        PresentationState(rt.rig, (AttachmentRecord(a), AttachmentRecord(a)))


def test_deterministic_serialization():
    rt, pa = fixture()
    s = capture_state(rt, pa)
    assert PresentationStateCodec.dumps(s) == PresentationStateCodec.dumps(s)
