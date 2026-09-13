from asteria.assets import AssetRef
from asteria.gameplay import ActionCue, PresentationCue
from asteria.graphics import SpriteClip, SpriteFrame, SpriteKeyframe, SpriteSheet
from asteria.presentation import (
    BattleAnimationTimingProfile,
    BattleAnimationTimingRule,
    BattleCombatantVisual,
    BattleHitRhythm,
    BattlePresentationCoordinator,
    BattlePresentationRuntime,
    BattlePresentationScene,
    BattleVisualAnchor,
    easing_value,
)
from asteria.runtime import AnimationClipSet, Camera2D


def _clip(name, frames, duration=.1, loop=False):
    return SpriteClip(name, [SpriteKeyframe(i, duration) for i in frames], loop)


def _assets():
    sheet = SpriteSheet(
        AssetRef("20000000-0000-4000-8000-0000000000a1", "texture"),
        [SpriteFrame(i * 16, 0, 16, 16) for i in range(5)],
    )
    clips = AnimationClipSet({
        "idle": _clip("idle", [0], loop=True),
        "attack": _clip("attack", [1, 2, 3], duration=.1),
        "hit": _clip("hit", [4], duration=.1),
    })
    return sheet, clips


def _runtime(profile):
    sheet, clips = _assets()
    scene = BattlePresentationScene(
        "timing",
        "bg",
        (BattleCombatantVisual(
            "hero", "sheet", "clips", BattleVisualAnchor(80, 100),
            {"idle": "idle", "attack": "attack", "hit": "hit"},
        ),),
    )
    return BattlePresentationRuntime(
        scene,
        lambda key: clips if key == "clips" else None,
        lambda key: sheet if key == "sheet" else None,
        timing_profile=profile,
    )


def _attack_event(runtime):
    coordinator = BattlePresentationCoordinator(runtime.scene)
    coordinator.consume_timeline_cues((PresentationCue(
        "attack",
        ActionCue("attack", 0, "animation", {"member_id": "hero", "role": "attack"}),
    ),))
    return coordinator.drain()


def test_easing_library_is_deterministic_and_backend_neutral():
    assert easing_value("linear", .25) == .25
    assert round(easing_value("ease_in", .5), 6) == .25
    assert round(easing_value("ease_out", .5), 6) == .75
    assert round(easing_value("smoothstep", .5), 6) == .5


def test_transition_crossfade_emits_previous_and_current_sprite_draws():
    profile = BattleAnimationTimingProfile((
        BattleAnimationTimingRule("attack", transition_duration=.2, transition_easing="ease_out"),
    ))
    runtime = _runtime(profile)
    runtime.apply_events(_attack_event(runtime))

    frame0 = runtime.build_frame(Camera2D())
    assert len(frame0.combatant_draws) == 2
    assert frame0.combatant_draws[0].opacity == 1.0
    assert frame0.combatant_draws[1].opacity == 0.0

    runtime.update(.1)
    frame1 = runtime.build_frame(Camera2D())
    assert len(frame1.combatant_draws) == 2
    assert 0.0 < frame1.combatant_draws[0].opacity < 1.0
    assert 0.0 < frame1.combatant_draws[1].opacity < 1.0

    runtime.update(.1)
    frame2 = runtime.build_frame(Camera2D())
    assert len(frame2.combatant_draws) == 1
    assert frame2.combatant_draws[0].opacity == 1.0


def test_role_playback_rate_changes_only_animation_clock():
    slow = _runtime(BattleAnimationTimingProfile((
        BattleAnimationTimingRule("attack", playback_rate=.5),
    )))
    fast = _runtime(BattleAnimationTimingProfile((
        BattleAnimationTimingRule("attack", playback_rate=2.0),
    )))
    slow.apply_events(_attack_event(slow))
    fast.apply_events(_attack_event(fast))
    slow.update(.11)
    fast.update(.11)

    assert slow.combatant("hero").frame_index == 1
    assert fast.combatant("hero").frame_index >= 2
    assert slow.time == fast.time == .11


def test_recovery_hold_keeps_transient_pose_before_idle_return():
    profile = BattleAnimationTimingProfile((
        BattleAnimationTimingRule("attack", playback_rate=10.0, recovery_hold=.2),
    ))
    runtime = _runtime(profile)
    runtime.apply_events(_attack_event(runtime))
    runtime.update(.05)
    assert runtime.combatant("hero").role.value == "attack"
    assert runtime.combatant("hero").recovery_remaining > 0

    runtime.update(.1)
    assert runtime.combatant("hero").role.value == "attack"
    runtime.update(.1)
    assert runtime.combatant("hero").role.value == "idle"


def test_multi_hit_rhythm_generates_only_presentation_offsets():
    rhythm = BattleHitRhythm((.08, .12), accent_every=3, accent_delay=.05)
    assert rhythm.offsets(0) == ()
    assert rhythm.offsets(5) == (0.0, .08, .2, .33, .45)


def test_timing_profile_and_runtime_snapshot_roundtrip():
    profile = BattleAnimationTimingProfile(
        (
            BattleAnimationTimingRule("attack", playback_rate=1.25, transition_duration=.08, transition_easing="smoothstep", recovery_hold=.04),
            BattleAnimationTimingRule("hit", playback_rate=.9, transition_duration=.03),
        ),
        default_transition_duration=.01,
    )
    assert BattleAnimationTimingProfile.from_data(profile.to_data()) == profile

    runtime = _runtime(profile)
    runtime.apply_events(_attack_event(runtime))
    runtime.update(.04)
    snapshot = runtime.snapshot()

    restored = _runtime(profile)
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot


def test_default_profile_preserves_pre_batch109_single_draw_behavior():
    runtime = _runtime(BattleAnimationTimingProfile())
    runtime.apply_events(_attack_event(runtime))
    frame = runtime.build_frame(Camera2D())
    assert len(frame.combatant_draws) == 1
    assert frame.combatant_draws[0].opacity == 1.0
