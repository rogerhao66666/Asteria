from asteria.presentation import (
    BattleCameraFeedbackFrame,
    BattleCombatantVisual,
    BattleFeedbackLabel,
    BattleFeedbackRuntime,
    BattleFloatingValue,
    BattleHudGauge,
    BattleHudMember,
    BattleHudStatusIcon,
    BattlePresentationFrame,
    BattlePresentationScene,
    BattleResultView,
    BattleTargetIndicator,
    BattleTurnEntry,
    BattleTurnTimelineView,
    BattleUiComposer,
    BattleUiLayoutProfile,
    BattleValueKind,
    BattleVisualAnchor,
)
from asteria.runtime import Camera2D, TextureDraw


def scene():
    return BattlePresentationScene(
        "battle.reference",
        "bg.arena",
        (
            BattleCombatantVisual("hero", "hero.sheet", "hero.clips", BattleVisualAnchor(70, 100)),
            BattleCombatantVisual(
                "mimic", "mimic.sheet", "mimic.clips", BattleVisualAnchor(240, 94)
            ),
        ),
    )


def battle_frame():
    return BattlePresentationFrame(
        "battle.reference",
        "bg.arena",
        (TextureDraw("hero.sheet", (0, 0, 16, 16), 62, 84, 16, 16),),
    )


def hud_members():
    return (
        BattleHudMember(
            "hero",
            (
                BattleHudGauge("hp", "HP", 75, 0, 100, 0, 0.75, False, None, 0),
                BattleHudGauge("mp", "MP", 13, 0, 40, 0, 0.325, False, None, 10),
            ),
            (BattleHudStatusIcon("poison", "Poison", "status.poison", 1, 2.0, "mimic", 0),),
        ),
        BattleHudMember(
            "mimic", (BattleHudGauge("hp", "HP", 45, 0, 80, 0, 0.5625, False, None, 0),), ()
        ),
    )


def timeline():
    return BattleTurnTimelineView(
        "continuous",
        2,
        4.0,
        (
            BattleTurnEntry("hero", "heroes", 5.0, 100, 1, True),
            BattleTurnEntry("mimic", "enemies", 7.0, 30, 2, False),
        ),
        (),
        1,
    )


def test_composer_builds_one_adapter_ready_battle_ui_frame():
    frame = BattleUiComposer(scene()).compose(
        Camera2D(),
        battle_frame(),
        hud_members=hud_members(),
        timeline=timeline(),
        side_by_member={"hero": "heroes", "mimic": "enemies"},
    )
    assert frame.scene_id == "battle.reference"
    assert frame.background_asset_id == "bg.arena"
    assert len(frame.combatant_draws) == 1
    assert {x.panel_id for x in frame.panels} >= {"hud:hero", "hud:mimic", "timeline"}
    assert {(x.member_id, x.resource_id) for x in frame.gauges} == {
        ("hero", "hp"),
        ("hero", "mp"),
        ("mimic", "hp"),
    }
    assert any(x.asset_id == "status.poison" for x in frame.icons)
    assert any(x.text == "hero" and x.role == "timeline_current" for x in frame.texts)


def test_enemy_hud_is_laid_out_on_opposite_side_without_gameplay_inference():
    composer = BattleUiComposer(
        scene(), BattleUiLayoutProfile(virtual_width=320, virtual_height=180)
    )
    frame = composer.compose(
        Camera2D(),
        battle_frame(),
        hud_members=hud_members(),
        side_by_member={"hero": "heroes", "mimic": "enemies"},
    )
    hero = next(x for x in frame.panels if x.panel_id == "hud:hero")
    mimic = next(x for x in frame.panels if x.panel_id == "hud:mimic")
    assert hero.x < 160 < mimic.x


def test_feedback_and_target_markers_are_projected_from_existing_presentation_state():
    feedback = BattleFeedbackRuntime()
    feedback.values = [
        BattleFloatingValue(1, "mimic", "hero", 27, BattleValueKind.DAMAGE, (), "normal", 0.2, 0.9)
    ]
    feedback.labels = [BattleFeedbackLabel(2, "mimic", "WEAK", "interaction:normal", 0.1, 0.65)]
    camera_frame = BattleCameraFeedbackFrame(
        0,
        0,
        (),
        (BattleTargetIndicator("mimic", True, 240, 94, 240, 94),),
    )
    frame = BattleUiComposer(scene()).compose(
        Camera2D(),
        battle_frame(),
        feedback=feedback,
        camera_feedback=camera_frame,
    )
    assert any(x.text == "27" and x.member_id == "mimic" for x in frame.texts)
    assert any(x.text == "WEAK" for x in frame.texts)
    assert frame.markers[0].member_id == "mimic" and frame.markers[0].primary


def test_finished_result_creates_overlay_without_reapplying_rewards():
    result = BattleResultView(
        True,
        "Victory",
        ("heroes",),
        ("enemies",),
        (),
        ("boss",),
        (),
        (),
        (),
        1,
    )
    frame = BattleUiComposer(scene()).compose(Camera2D(), battle_frame(), result=result)
    assert any(x.panel_id == "battle_result" for x in frame.panels)
    assert any(x.text == "Victory" and x.role == "result_headline" for x in frame.texts)


def test_composer_rejects_scene_mismatch():
    import pytest

    wrong = BattlePresentationFrame("other", "bg.arena", ())
    with pytest.raises(ValueError):
        BattleUiComposer(scene()).compose(Camera2D(), wrong)
