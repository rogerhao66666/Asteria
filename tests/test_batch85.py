from asteria.presentation.actor_attachment import ActorAnimationPose
from asteria.presentation.attachment_runtime import AttachmentRuntime
from asteria.presentation.attachments import Attachment, Socket, SocketRig, Transform2D
from asteria.presentation.e2e_pipeline import PresentationE2EPipeline, SceneActorBinding
from asteria.presentation.property_animation import (
    Ease,
    Envelope,
    Modulation,
    Oscillator,
    PropertyAnimator,
    PropertyCurve,
    PropertyKey,
)
from asteria.presentation.stress_profile import profile_pipeline


class Anim:
    def __init__(self, i):
        self.i = i

    def presentation_pose(self):
        return ActorAnimationPose("project.clip", 0, (self.i % 10) / 10)


def workload(nactors=100, nattach=6):
    actors = []
    for i in range(nactors):
        rig = SocketRig()
        rig.add(Socket("root", default=Transform2D(x=float(i % 7))))
        rt = AttachmentRuntime(rig)
        for j in range(nattach):
            rt.attach(Attachment(f"a{j}", f"fx.{j}", "root", Transform2D(x=j * 0.25, z_offset=j)))
        actors.append(SceneActorBinding(f"actor{i}", f"char.{i}", Anim(i), rt))
    curves = (PropertyCurve("camera.zoom", (PropertyKey(0, 1), PropertyKey(1000, 1.2, Ease.EASE_IN_OUT))),)
    mods = (Modulation("camera.x", Oscillator(2, 24), Envelope(1000)),)
    return PresentationE2EPipeline(actors, PropertyAnimator(curves, mods))


def test_large_packet_count():
    assert len(workload(120, 8).sample(123.456).draw_packets) == 1080


def test_large_frame_deterministic():
    p = workload(80, 5)
    assert p.sample(321.125) == p.sample(321.125)


def test_continuous_sampling_changes_vibration():
    p = workload(2, 1)
    assert p.sample(10).channels.camera["x"] != p.sample(10.5).channels.camera["x"]


def test_ordering_stable_under_load():
    f = workload(100, 6).sample(50)
    keys = [(x.z, x.owner_id or "", x.component_id or "", x.asset_id) for x in f.draw_packets]
    assert keys == sorted(keys)


def test_no_canonical_mutation_after_repeated_sampling():
    p = workload(30, 4)
    before = [a.attachments.snapshot() for a in p.actors]
    for i in range(200):
        p.sample(i * 4.1667)
    assert [a.attachments.snapshot() for a in p.actors] == before


def test_profile_counts():
    s = profile_pipeline(workload(20, 3), [0, 16.67, 33.34, 50])
    assert (s.frames, s.packets, s.max_packets_per_frame) == (4, 320, 80)
    assert s.elapsed_ms >= 0 and s.ms_per_frame >= 0


def test_empty_profile():
    s = profile_pipeline(workload(1, 0), [])
    assert s.frames == 0 and s.packets == 0 and s.ms_per_frame == 0


def test_60_frame_stress_smoke():
    s = profile_pipeline(workload(50, 5), (i * (1000 / 60) for i in range(60)))
    assert s.frames == 60 and s.packets == 18000
