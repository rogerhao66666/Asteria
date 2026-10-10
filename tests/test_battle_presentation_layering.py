from asteria.gameplay import ActionCue, PresentationCue
from asteria.presentation import (
    BattlePresentationChannelPolicy,
    BattlePresentationCoordinator,
    BattlePresentationLayeringProfile,
    BattlePresentationLayeringRuntime,
    BattlePresentationScene,
)


def _scene():
    return BattlePresentationScene("layering", "bg", ())


def _events(cues):
    coordinator = BattlePresentationCoordinator(_scene())
    coordinator.consume_timeline_cues(tuple(PresentationCue("combo", cue) for cue in cues))
    return coordinator.drain()


def test_shared_staging_context_is_injected_without_mutating_original_event():
    runtime = BattlePresentationLayeringRuntime()
    event = _events(
        (
            ActionCue(
                "slash",
                0,
                "vfx",
                {"effect_id": "slash", "staging": {"group_id": "impact:1", "layer": 4, "intensity": 1.5}},
            ),
        )
    )[0]
    original = dict(event.payload)

    processed = runtime.process((event,))[0]
    assert event.payload == original
    cue = processed.payload["cue"]
    staging = cue["payload"]["staging"]
    assert staging["group_id"] == "impact:1"
    assert staging["channel"] == "vfx"
    assert staging["layer"] == 4
    assert staging["intensity"] == 1.5


def test_channel_profile_scales_camera_audio_and_vfx_presentation_only():
    profile = BattlePresentationLayeringProfile(
        (
            BattlePresentationChannelPolicy("camera", layer=2, gain=1.5, bus="impact"),
            BattlePresentationChannelPolicy("audio", layer=3, gain=0.8, bus="sfx_heavy"),
            BattlePresentationChannelPolicy("vfx", layer=5, gain=2.0, bus="visual"),
        )
    )
    runtime = BattlePresentationLayeringRuntime(profile)
    events = _events(
        (
            ActionCue("cam", 0, "camera", {"amplitude": 2, "staging": {"intensity": 2}}),
            ActionCue("sfx", 0, "audio", {"sound_id": "hit", "staging": {"intensity": 0.5}}),
            ActionCue("fx", 0, "vfx", {"effect_id": "spark"}),
        )
    )
    camera, audio, vfx = runtime.process(events)

    cp = camera.payload["cue"]["payload"]
    ap = audio.payload["cue"]["payload"]
    vp = vfx.payload["cue"]["payload"]

    assert cp["amplitude"] == 6.0
    assert cp["staging"]["layer"] == 2
    assert ap["gain"] == 0.4
    assert ap["bus"] == "sfx_heavy"
    assert vp["intensity"] == 2.0
    assert vp["layer"] == 5


def test_same_group_can_coordinate_multiple_channels():
    runtime = BattlePresentationLayeringRuntime()
    events = _events(
        tuple(
            ActionCue(
                kind,
                0,
                cue_kind,
                {
                    "staging": {"group_id": "impact:boss", "priority": 9},
                    **payload,
                },
            )
            for kind, cue_kind, payload in (
                ("anim", "animation", {"member_id": "hero", "role": "attack"}),
                ("fx", "vfx", {"effect_id": "burst"}),
                ("cam", "camera", {"amplitude": 3}),
                ("screen", "screen_fx", {"effect": "flash"}),
                ("sfx", "audio", {"sound_id": "boom"}),
            )
        )
    )
    processed = runtime.process(events)
    contexts = [runtime.context_for_event(x) for x in processed]
    assert {x.group_id for x in contexts} == {"impact:boss"}
    assert {x.channel for x in contexts} == {"animation", "vfx", "camera", "screen_fx", "audio"}
    assert all(x.priority == 9 for x in contexts)


def test_profile_and_runtime_snapshot_roundtrip():
    profile = BattlePresentationLayeringProfile(
        (
            BattlePresentationChannelPolicy("audio", layer=2, gain=0.7, bus="impact"),
            BattlePresentationChannelPolicy("vfx", layer=8, gain=1.2, bus="default"),
        )
    )
    assert BattlePresentationLayeringProfile.from_data(profile.to_data()) == profile

    runtime = BattlePresentationLayeringRuntime(profile)
    runtime.process(_events((ActionCue("sfx", 0, "audio", {"sound_id": "hit"}),)))
    snapshot = runtime.snapshot()
    restored = BattlePresentationLayeringRuntime(profile)
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot


def test_layering_runtime_never_changes_non_timeline_gameplay_semantics():
    coordinator = BattlePresentationCoordinator(_scene())
    event = coordinator.push_custom("already.resolved", payload={"damage": 123, "target_valid": True})
    runtime = BattlePresentationLayeringRuntime()
    processed = runtime.process((event,))[0]
    assert processed == event
    assert processed.payload["damage"] == 123
