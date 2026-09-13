from asteria.gameplay import ActionCue, PresentationCue
from asteria.presentation import (
    BattlePresentationCoordinator,
    BattlePresentationDirection,
    BattlePresentationDirector,
    BattlePresentationDirectorProfile,
    BattlePresentationDirectorRule,
    BattlePresentationEventKind,
    BattlePresentationScene,
)


def _scene():
    return BattlePresentationScene("director", "bg", ())


def _events(cues):
    coordinator = BattlePresentationCoordinator(_scene())
    coordinator.consume_timeline_cues(tuple(
        PresentationCue("timeline", cue) for cue in cues
    ))
    return coordinator.drain()


def test_default_director_is_zero_delay_passthrough():
    director = BattlePresentationDirector()
    events = _events((
        ActionCue("anim", 0, "animation", {"member_id": "hero", "role": "attack"}),
        ActionCue("vfx", 0, "vfx", {"effect_id": "slash"}),
    ))
    released = director.ingest(events)
    assert released == events
    assert director.pending_count == 0
    assert director.hold_remaining == 0


def test_profile_can_stage_presentation_cue_without_changing_event_payload():
    profile = BattlePresentationDirectorProfile((
        BattlePresentationDirectorRule(
            BattlePresentationEventKind.TIMELINE_CUE.value,
            "vfx",
            BattlePresentationDirection("impact", delay=.12, priority=5),
        ),
    ))
    director = BattlePresentationDirector(profile)
    event = _events((ActionCue("vfx", 0, "vfx", {"effect_id": "slash"}),))[0]
    original = dict(event.payload)

    assert director.ingest((event,)) == ()
    assert event.payload == original
    assert director.update(.1).released_events == ()
    advance = director.update(.02)
    assert advance.released_events == (event,)
    assert advance.active_beat == "impact"


def test_authored_director_metadata_overrides_profile_and_supports_hit_stop_hold():
    profile = BattlePresentationDirectorProfile((
        BattlePresentationDirectorRule(
            BattlePresentationEventKind.TIMELINE_CUE.value,
            "camera",
            BattlePresentationDirection("impact", delay=.2, hold=.01),
        ),
    ))
    director = BattlePresentationDirector(profile)
    event = _events((ActionCue(
        "shake", 0, "camera",
        {
            "effect": "shake",
            "director": {"delay": 0, "hold": .08, "beat": "heavy_impact"},
        },
    ),))[0]

    assert director.ingest((event,)) == (event,)
    assert director.active_beat == "heavy_impact"
    assert director.hold_remaining == .08

    first = director.update(.03)
    assert first.presentation_dt == 0
    assert first.holding
    second = director.update(.06)
    assert round(second.presentation_dt, 6) == .01
    assert second.hold_remaining == 0


def test_hold_pauses_only_presentation_time_not_wall_clock_contract():
    director = BattlePresentationDirector()
    event = _events((ActionCue(
        "impact", 0, "screen_fx",
        {"effect": "flash", "director": {"hold": .05}},
    ),))[0]
    director.ingest((event,))
    assert director.time == 0
    advance = director.update(.02)
    assert advance.presentation_dt == 0
    assert director.time == 0
    advance = director.update(.05)
    assert round(advance.presentation_dt, 6) == .02
    assert round(director.time, 6) == .02


def test_director_snapshot_roundtrip_preserves_pending_choreography():
    profile = BattlePresentationDirectorProfile((
        BattlePresentationDirectorRule(
            BattlePresentationEventKind.TIMELINE_CUE.value,
            "audio",
            BattlePresentationDirection("accent", delay=.25, priority=2),
        ),
    ))
    director = BattlePresentationDirector(profile)
    event = _events((ActionCue("sfx", 0, "audio", {"sound_id": "hit"}),))[0]
    director.ingest((event,))
    director.update(.1)
    snapshot = director.snapshot()

    restored = BattlePresentationDirector(profile)
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot
    assert restored.pending_count == 1
    assert restored.update(.15).released_events[0].sequence == event.sequence


def test_profile_roundtrip_is_project_owned_policy():
    profile = BattlePresentationDirectorProfile((
        BattlePresentationDirectorRule("*", "animation", {"beat": "anticipation", "delay": .04}),
        BattlePresentationDirectorRule("*", "vfx", {"beat": "impact", "delay": .09, "hold": .03}),
    ))
    assert BattlePresentationDirectorProfile.from_data(profile.to_data()) == profile
