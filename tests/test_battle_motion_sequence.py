from asteria.presentation import (
    BattleMotionBeat,
    BattleMotionRuntime,
    BattleMotionSequence,
    make_reference_smooth_attack_sequence,
)

def test_reference_sequence_has_premium_jrpg_channels_and_phases():
    seq=make_reference_smooth_attack_sequence(multi_hits=3)
    channels={x.channel for x in seq.beats}
    cues={x.cue for x in seq.beats}
    assert {"animation","vfx","camera","audio","ui","timing"} <= channels
    assert {"startup","cast","projectile","impact","floating_value","resource_motion","status","recovery","hit_stop"} <= cues

def test_subframe_runtime_releases_closely_spaced_beats_under_coarse_host_frame():
    seq=BattleMotionSequence("subframe",0.1,(
        BattleMotionBeat("a",0.010,"vfx","a"),
        BattleMotionBeat("b",0.015,"vfx","b"),
        BattleMotionBeat("c",0.020,"vfx","c"),
    ))
    r=BattleMotionRuntime(quantum=1/1000)
    r.start(seq)
    frame=r.update(1/30)
    assert tuple(x.beat_id for x in frame.released)==("a","b","c")

def test_hit_stop_pauses_presentation_time_only():
    seq=BattleMotionSequence("hitstop",0.2,(
        BattleMotionBeat("impact",0.05,"vfx","impact"),
        BattleMotionBeat("stop",0.05,"timing","hit_stop",duration=0.04,payload={"duration":0.04}),
        BattleMotionBeat("after",0.08,"animation","recovery"),
    ))
    r=BattleMotionRuntime(quantum=0.005)
    r.start(seq)
    r.update(0.055)
    t=r.time
    assert r.hit_stop_remaining > 0
    r.update(0.02)
    assert r.time == t
    r.update(0.03)
    assert r.time > t

def test_multi_hit_spacing_remains_authored_and_deterministic():
    seq=make_reference_smooth_attack_sequence(multi_hits=4)
    impacts=[x.at for x in seq.beats if x.cue=="impact"]
    assert impacts==[0.36,0.415,0.47,0.525]

def test_camera_vfx_audio_and_ui_can_share_exact_impact_timestamp():
    seq=make_reference_smooth_attack_sequence(multi_hits=1)
    at=next(x.at for x in seq.beats if x.beat_id=="impact.0")
    assert next(x.at for x in seq.beats if x.beat_id=="camera.hit.0")==at
    assert next(x.at for x in seq.beats if x.beat_id=="audio.hit.0")==at
    assert next(x.at for x in seq.beats if x.beat_id=="value.0")==at+0.010

def test_easing_metadata_survives_sequence_authoring():
    seq=make_reference_smooth_attack_sequence()
    projectile=next(x for x in seq.beats if x.beat_id=="projectile")
    recovery=next(x for x in seq.beats if x.beat_id=="recovery")
    assert projectile.easing=="ease_in"
    assert recovery.easing=="ease_in_out"

def test_transform_summon_and_boss_phase_are_generic_channels_not_gameplay_systems():
    seq=BattleMotionSequence("special",1.0,(
        BattleMotionBeat("transform",0.0,"animation","transform",member_id="hero",duration=0.3),
        BattleMotionBeat("summon.enter",0.2,"vfx","summon_enter",member_id="summon",duration=0.4),
        BattleMotionBeat("boss.phase",0.5,"screen_fx","phase_transition",member_id="boss",duration=0.5),
    ))
    assert tuple(x.cue for x in seq.beats)==("transform","summon_enter","phase_transition")

def test_persistent_status_vfx_can_overlap_recovery():
    seq=BattleMotionSequence("status",1.0,(
        BattleMotionBeat("status",0.2,"vfx","status_loop",target_id="target",duration=0.7),
        BattleMotionBeat("recovery",0.5,"animation","recovery",member_id="actor",duration=0.2),
    ))
    r=BattleMotionRuntime(quantum=0.01)
    r.start(seq)
    r.update(0.55)
    ids={x.beat_id for x in r.frame(()).active}
    assert {"status","recovery"} <= ids

def test_invalid_beat_beyond_sequence_duration_is_rejected():
    try:
        BattleMotionSequence("bad",0.1,(BattleMotionBeat("x",0.2,"vfx","x"),))
    except ValueError as e:
        assert "exceeds sequence duration" in str(e)
    else:
        raise AssertionError("expected ValueError")

def test_sequence_completes_deterministically():
    seq=make_reference_smooth_attack_sequence(multi_hits=2)
    r=BattleMotionRuntime(quantum=1/240)
    r.start(seq)
    while not r.frame(()).complete:
        r.update(1/60)
    assert abs(r.time-seq.duration) < 1e-12


def test_dense_motion_sequence_cost_tracks_released_beats_not_quantum_scan():
    beats=tuple(
        BattleMotionBeat(f"b{i}", i * 0.0002, "vfx", "spark", duration=0.001)
        for i in range(5000)
    )
    seq=BattleMotionSequence("dense",1.1,beats)
    r=BattleMotionRuntime(quantum=1/100000)
    r.start(seq)
    frame=r.update(1.0)
    metrics=r.metrics()
    assert len(frame.released)==5000
    assert metrics.released_beats==5000
    assert metrics.update_calls==1
    assert abs(r.time-1.0) < 1e-9


def test_quantum_is_policy_hint_not_choreography_correctness_requirement():
    seq=BattleMotionSequence("quantum-independent",0.2,(
        BattleMotionBeat("a",0.001,"vfx","a"),
        BattleMotionBeat("b",0.003,"audio","b"),
        BattleMotionBeat("c",0.007,"camera","c"),
    ))
    fine=BattleMotionRuntime(quantum=1/10000)
    coarse=BattleMotionRuntime(quantum=1/30)
    fine.start(seq); coarse.start(seq)
    a=fine.update(0.02); b=coarse.update(0.02)
    assert tuple(x.beat_id for x in a.released)==tuple(x.beat_id for x in b.released)==("a","b","c")
    assert fine.time==coarse.time==0.02
