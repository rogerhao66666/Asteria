from copy import deepcopy

from asteria.gameplay import ActionCue, PresentationCue
from asteria.presentation import (
    BattleCameraFeedbackRuntime,
    BattleCombatantVisual,
    BattlePresentationCoordinator,
    BattlePresentationScene,
    BattleVisualAnchor,
)
from asteria.runtime import Camera2D


def _scene():
    return BattlePresentationScene(
        "batch97.reference",
        "battle.bg.reference_clearing",
        (
            BattleCombatantVisual("hero", "sheet.hero", "clips.hero", BattleVisualAnchor(72, 104)),
            BattleCombatantVisual(
                "mimic", "sheet.mimic", "clips.mimic", BattleVisualAnchor(232, 104, "left")
            ),
        ),
    )


def test_camera_cue_is_presentation_only_and_does_not_mutate_base_camera_or_payload():
    scene = _scene()
    coordinator = BattlePresentationCoordinator(scene)
    runtime = BattleCameraFeedbackRuntime(scene)
    payload = {
        "effect": "hit_shake",
        "amplitude_x": 2.0,
        "amplitude_y": 1.0,
        "duration": 0.2,
        "frequency": 20,
    }
    before = deepcopy(payload)
    coordinator.consume_timeline_cues(
        (PresentationCue("slash", ActionCue("impact", 0.1, "camera", payload)),)
    )
    base = Camera2D(10, 20, 320, 180, 2.0)
    assert runtime.apply_events(coordinator.drain()) == (True,)
    view = runtime.camera_view(base)
    assert (base.x, base.y) == (10, 20)
    assert (view.x, view.y) != (base.x, base.y)
    assert payload == before


def test_screen_fx_cue_is_deterministic_view_state_including_hit_stop_metadata():
    scene = _scene()
    coordinator = BattlePresentationCoordinator(scene)
    runtime = BattleCameraFeedbackRuntime(scene)
    coordinator.consume_timeline_cues(
        (
            PresentationCue(
                "slash",
                ActionCue(
                    "freeze",
                    0.1,
                    "screen_fx",
                    {"effect": "hit_stop", "duration": 0.08, "strength": 1.0},
                ),
            ),
        )
    )
    runtime.apply_events(coordinator.drain())
    assert runtime.screen_fx[0].effect == "hit_stop"
    runtime.update(0.04)
    snap = runtime.snapshot()
    restored = BattleCameraFeedbackRuntime(scene)
    restored.restore(snap)
    assert restored.snapshot() == snap
    runtime.update(0.05)
    restored.update(0.05)
    assert runtime.snapshot() == restored.snapshot()
    assert restored.screen_fx == []


def test_target_indicator_mirrors_canonical_selection_without_revalidating_targets():
    scene = _scene()
    coordinator = BattlePresentationCoordinator(scene)
    runtime = BattleCameraFeedbackRuntime(scene)
    marker = {"canonical_selection": ("mimic",), "legal": True}
    coordinator.push_target_selection(
        marker["canonical_selection"], primary_target_id="mimic", source_id="hero"
    )
    runtime.apply_events(coordinator.drain())
    frame = runtime.build_frame(Camera2D(width=320, height=180))
    assert len(frame.targets) == 1
    assert frame.targets[0].member_id == "mimic"
    assert frame.targets[0].primary is True
    assert marker == {"canonical_selection": ("mimic",), "legal": True}


def test_target_indicator_skips_missing_visual_but_preserves_selection_state():
    scene = _scene()
    coordinator = BattlePresentationCoordinator(scene)
    runtime = BattleCameraFeedbackRuntime(scene)
    coordinator.push_target_selection(("offscreen_summon",), primary_target_id="offscreen_summon")
    runtime.apply_events(coordinator.drain())
    assert runtime.target_ids == ("offscreen_summon",)
    assert runtime.build_frame(Camera2D()).targets == ()


def test_camera_impulse_lifetime_and_offset_are_deterministic():
    scene = _scene()
    coordinator = BattlePresentationCoordinator(scene)
    runtime = BattleCameraFeedbackRuntime(scene)
    coordinator.consume_timeline_cues(
        (
            PresentationCue(
                "hit",
                ActionCue(
                    "shake",
                    0,
                    "camera",
                    {"effect": "shake", "amplitude": 3, "duration": 0.2, "frequency": 10},
                ),
            ),
        )
    )
    runtime.apply_events(coordinator.drain())
    assert runtime.camera_offset() == (3.0, 3.0)
    runtime.update(0.05)
    snap = runtime.snapshot()
    restored = BattleCameraFeedbackRuntime(scene)
    restored.restore(snap)
    assert restored.camera_offset() == runtime.camera_offset()
    runtime.update(0.16)
    restored.update(0.16)
    assert runtime.impulses == restored.impulses == []


def test_target_selection_rejects_only_malformed_presentation_payload_not_gameplay_legality():
    coordinator = BattlePresentationCoordinator(_scene())
    try:
        coordinator.push_target_selection(("mimic", "mimic"), primary_target_id="mimic")
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate presentation ids should be rejected")

    # An unknown member is accepted: legality/existence is not presentation's job.
    event = coordinator.push_target_selection(("unknown",), primary_target_id="unknown")
    assert event.payload["target_ids"] == ["unknown"]
