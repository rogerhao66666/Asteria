from asteria.presentation.fidelity import HighFidelityClip, FrameTiming, CAPABILITIES
from asteria.presentation.fidelity_import import SourceFrame, FidelitySource, FidelityImporter
from asteria.presentation.animation_attachment import AnimationClock
from asteria.presentation.attachments import Socket, SocketKey, SocketRig, Transform2D


def test_high_resolution_24_frame_variable_timing_import():
    frames=tuple(SourceFrame(f"hero.hd.{i:02d}", 768, 1024, 33.0 + (i%5)*7.0, True, (384, 980)) for i in range(24))
    report=FidelityImporter().import_source(FidelitySource("hero.hd.detail",frames))
    assert report.clip.frame_size == (768,1024)
    assert len(report.clip.frames) == 24
    assert [t.duration_ms for t in report.clip.timings] == [f.duration_ms for f in frames]
    assert report.alpha_preserved and report.timing_preserved and report.resolution_preserved
    assert CAPABILITIES.arbitrary_resolution and CAPABILITIES.arbitrary_frame_count and CAPABILITIES.per_frame_timing


def test_32_frame_animation_clock_has_no_small_frame_cap():
    durations=tuple(20.0+i for i in range(32))
    clock=AnimationClock(tuple(__import__('asteria.presentation.animation_attachment',fromlist=['FrameTiming']).FrameTiming(x) for x in durations),loop=False)
    assert len(clock.frames)==32
    assert clock.duration_ms == sum(durations)
    assert clock.sample(sum(durations)-0.1).frame == 31


def test_32_frame_socket_track_supports_dense_authored_motion():
    keys=tuple(SocketKey(i,Transform2D(x=float(i)*1.25,y=float(i%4),rotation_deg=float(i)*3.0)) for i in range(32))
    rig=SocketRig(); rig.add(Socket("hand_r",keys=keys))
    assert rig.sample("hand_r",31).x == 31*1.25
    mid=rig.sample("hand_r",10,0.5)
    assert 12.5 < mid.x < 13.75
