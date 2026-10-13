from copy import deepcopy

from asteria.gameplay import ActionCue, PresentationCue
from asteria.presentation import (
    BattleFeedbackProfile,
    BattleFeedbackRuntime,
    BattlePresentationCoordinator,
    BattlePresentationScene,
    BattleValueKind,
)
from asteria.rpg.gauge_composition import GaugeCompositionResult, GaugeThresholdResult
from asteria.rpg.interactions import (
    InteractionDisposition,
    OutcomeCheckResult,
    OutcomeResolutionResult,
    ValueResolutionResult,
)


def _coordinator():
    return BattlePresentationCoordinator(
        BattlePresentationScene("feedback", "battle.bg.reference", ())
    )


def _profile():
    return BattleFeedbackProfile(
        outcome_tag_labels={
            "outcome.weak": "WEAK",
            "outcome.resist": "RESIST",
        },
        disposition_labels={
            "nullify": "IMMUNE",
            "absorb": "ABSORB",
        },
        threshold_labels={"guard_break": "BREAK"},
        value_duration=1.0,
        label_duration=0.5,
        vfx_default_duration=0.4,
    )


def _value(value=42, disposition=InteractionDisposition.NORMAL, tags=()):
    return ValueResolutionResult(
        50.0,
        float(value),
        disposition,
        ("rule.reference",),
        tuple(tags),
        (("rule.reference", 50.0, float(value)),),
    )


def test_resolved_value_is_presented_without_recomputing_or_mutating_result():
    coordinator = _coordinator()
    runtime = BattleFeedbackRuntime(_profile())
    result = _value(75, tags=("outcome.weak",))
    before = deepcopy(result)

    coordinator.push_resolved_value(result, target_id="mimic", source_id="hero")
    assert runtime.apply_events(coordinator.drain()) == (True,)

    assert result == before
    assert len(runtime.values) == 1
    shown = runtime.values[0]
    assert shown.target_id == "mimic"
    assert shown.source_id == "hero"
    assert shown.value == 75
    assert shown.kind == BattleValueKind.DAMAGE
    assert [x.label for x in runtime.labels] == ["WEAK"]


def test_outcome_result_combines_already_resolved_check_tags_and_interaction_tags():
    coordinator = _coordinator()
    runtime = BattleFeedbackRuntime(_profile())
    resolved = OutcomeResolutionResult(
        (OutcomeCheckResult("hit", True, True, 1.0, 0.1, ("outcome.weak",)),),
        _value(20, tags=("outcome.resist",)),
    )
    coordinator.push_resolved_value(resolved, target_id="mimic")
    runtime.apply_events(coordinator.drain())
    assert [x.label for x in runtime.labels] == ["RESIST", "WEAK"]
    assert runtime.values[0].outcome_tags == ("outcome.resist", "outcome.weak")


def test_nullify_and_absorb_labels_are_profile_driven_not_re_resolved():
    for disposition, expected in (
        (InteractionDisposition.NULLIFY, "IMMUNE"),
        (InteractionDisposition.ABSORB, "ABSORB"),
    ):
        coordinator = _coordinator()
        runtime = BattleFeedbackRuntime(_profile())
        result = _value(0 if disposition == InteractionDisposition.NULLIFY else 18, disposition)
        coordinator.push_resolved_value(result, target_id="mimic", value_kind="resource")
        runtime.apply_events(coordinator.drain())
        assert runtime.labels[0].label == expected
        assert runtime.values[0].disposition == disposition.value


def test_gauge_threshold_feedback_consumes_resolved_threshold_only():
    coordinator = _coordinator()
    runtime = BattleFeedbackRuntime(_profile())
    result = GaugeCompositionResult(
        "poise.reference",
        "hero",
        "mimic",
        "hit",
        ("impact.poise",),
        (),
        (
            GaugeThresholdResult(
                "guard_break", "mimic", "poise", 12, 0, True, -2.0, 0, "battle.break"
            ),
        ),
    )
    before = deepcopy(result)
    events = coordinator.push_gauge_result(result)
    assert len(events) == 1
    runtime.apply_events(coordinator.drain())
    assert result == before
    assert [(x.target_id, x.label, x.reason_id) for x in runtime.labels] == [
        ("mimic", "BREAK", "threshold:guard_break")
    ]


def test_unmapped_threshold_remains_valid_but_creates_no_label():
    coordinator = _coordinator()
    runtime = BattleFeedbackRuntime(_profile())
    result = GaugeCompositionResult(
        "heat",
        "hero",
        "mimic",
        "hit",
        (),
        (),
        (GaugeThresholdResult("overheat", "mimic", "heat", 90, 100),),
    )
    coordinator.push_gauge_result(result)
    assert runtime.apply_events(coordinator.drain()) == (False,)
    assert runtime.labels == []


def test_vfx_and_audio_timeline_cues_are_backend_neutral_queues():
    coordinator = _coordinator()
    runtime = BattleFeedbackRuntime(_profile())
    coordinator.consume_timeline_cues(
        (
            PresentationCue(
                "slash",
                ActionCue(
                    "slash_vfx",
                    0.1,
                    "vfx",
                    {"member_id": "mimic", "asset_id": "vfx.slash", "duration": 0.25},
                ),
            ),
            PresentationCue(
                "slash",
                ActionCue(
                    "slash_sfx", 0.1, "audio", {"member_id": "mimic", "asset_id": "sfx.slash"}
                ),
            ),
        )
    )
    assert runtime.apply_events(coordinator.drain()) == (True, True)
    assert runtime.vfx[0].payload["asset_id"] == "vfx.slash"
    audio = runtime.drain_audio()
    assert len(audio) == 1 and audio[0].payload["asset_id"] == "sfx.slash"
    assert runtime.drain_audio() == ()


def test_feedback_lifetime_ordering_and_snapshot_restore_are_deterministic():
    coordinator = _coordinator()
    runtime = BattleFeedbackRuntime(_profile())
    coordinator.push_resolved_value(_value(10, tags=("outcome.weak",)), target_id="mimic")
    coordinator.consume_timeline_cues(
        (
            PresentationCue(
                "fx", ActionCue("spark", 0.0, "vfx", {"target_id": "mimic", "duration": 0.75})
            ),
        )
    )
    runtime.apply_events(coordinator.drain())
    runtime.update(0.25)
    snapshot = runtime.snapshot()

    restored = BattleFeedbackRuntime(_profile())
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot
    restored.update(0.26)
    runtime.update(0.26)
    assert restored.snapshot() == runtime.snapshot()
    assert restored.labels == []  # 0.5s label lifetime expired
    assert len(restored.values) == 1
    assert len(restored.vfx) == 1

    restored.update(0.5)
    assert restored.values == []
    assert restored.vfx == []


def test_profile_round_trip_keeps_project_defined_semantics():
    profile = _profile()
    assert BattleFeedbackProfile.from_data(profile.to_data()) == profile
