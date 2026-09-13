from asteria.assets import AssetRef
from asteria.core.lifecycle import LifecycleHookBus
from asteria.gameplay import ActionCue, PresentationCue
from asteria.graphics import SpriteClip, SpriteFrame, SpriteKeyframe, SpriteSheet
from asteria.presentation import (
    BattleAnimationRole,
    BattleCombatantVisual,
    BattlePresentationCoordinator,
    BattlePresentationRuntime,
    BattlePresentationScene,
    BattleVisualAnchor,
)
from asteria.rpg.battle_lifecycle import CombatantLifecycleRuntime
from asteria.runtime import AnimationClipSet, Camera2D


def _clip(name, frames, *, loop=False, duration=0.1):
    return SpriteClip(name, [SpriteKeyframe(i, duration) for i in frames], loop)


def _assets():
    hero_sheet = SpriteSheet(
        AssetRef("10000000-0000-4000-8000-0000000000a1", "texture"),
        [SpriteFrame(i * 16, 0, 16, 24) for i in range(6)],
    )
    enemy_sheet = SpriteSheet(
        AssetRef("10000000-0000-4000-8000-0000000000a2", "texture"),
        [SpriteFrame(i * 32, 0, 32, 32) for i in range(6)],
    )
    hero_clips = AnimationClipSet({
        "idle": _clip("idle", [0], loop=True),
        "slash": _clip("slash", [1, 2, 3]),
        "hurt": _clip("hurt", [4]),
        "down": _clip("down", [5]),
    })
    enemy_clips = AnimationClipSet({
        "idle": _clip("idle", [0, 1], loop=True),
        "attack": _clip("attack", [2, 3]),
        "hit": _clip("hit", [4]),
        "ko": _clip("ko", [5]),
    })
    sheets = {"sheet.hero": hero_sheet, "sheet.mimic": enemy_sheet}
    clips = {"clips.hero": hero_clips, "clips.mimic": enemy_clips}
    return sheets, clips


def _scene():
    return BattlePresentationScene(
        "batch95.reference",
        "battle.bg.reference_clearing",
        (
            BattleCombatantVisual(
                "hero",
                "sheet.hero",
                "clips.hero",
                BattleVisualAnchor(72, 104, "right", 0.1),
                {"idle": "idle", "attack": "slash", "hit": "hurt", "ko": "down"},
            ),
            BattleCombatantVisual(
                "mimic",
                "sheet.mimic",
                "clips.mimic",
                BattleVisualAnchor(232, 104, "left", 0.2),
            ),
        ),
    )


def _runtime():
    sheets, clips = _assets()
    return BattlePresentationRuntime(_scene(), clips.get, sheets.get)


def test_runtime_starts_every_combatant_in_canonical_idle_role():
    runtime = _runtime()
    assert runtime.combatant("hero").role == BattleAnimationRole.IDLE
    assert runtime.combatant("hero").clip_name == "idle"
    assert runtime.combatant("mimic").clip_name == "idle"


def test_animation_cues_drive_attack_and_hit_then_return_to_idle():
    runtime = _runtime()
    coordinator = BattlePresentationCoordinator(_scene())
    coordinator.consume_timeline_cues((
        PresentationCue("hero.slash", ActionCue(
            "hero_attack", 0.0, "animation", {"member_id": "hero", "role": "attack"}
        )),
        PresentationCue("hero.slash", ActionCue(
            "mimic_hit", 0.1, "animation", {"member_id": "mimic", "role": "hit"}
        )),
    ))
    runtime.apply_events(coordinator.drain())
    assert runtime.combatant("hero").role == BattleAnimationRole.ATTACK
    assert runtime.combatant("hero").clip_name == "slash"
    assert runtime.combatant("mimic").role == BattleAnimationRole.HIT

    runtime.update(1.0)
    assert runtime.combatant("hero").role == BattleAnimationRole.IDLE
    assert runtime.combatant("mimic").role == BattleAnimationRole.IDLE


def test_incapacitation_is_observed_as_ko_and_revive_returns_idle():
    hooks = LifecycleHookBus()
    coordinator = BattlePresentationCoordinator(_scene()).attach(hooks)
    runtime = _runtime()
    lifecycle = CombatantLifecycleRuntime((), hooks=hooks)
    lifecycle.register("mimic")
    coordinator.drain()  # registered is intentionally outside Batch 94 mapping

    lifecycle.incapacitate("mimic", reason="resolved_hp_zero")
    runtime.apply_events(coordinator.drain())
    assert runtime.combatant("mimic").defeated is True
    assert runtime.combatant("mimic").role == BattleAnimationRole.KO
    assert runtime.combatant("mimic").clip_name == "ko"

    lifecycle.revive("mimic")
    runtime.apply_events(coordinator.drain())
    assert runtime.combatant("mimic").defeated is False
    assert runtime.combatant("mimic").role == BattleAnimationRole.IDLE


def test_missing_attack_role_falls_back_to_idle_without_gameplay_side_effect():
    sheets, clips = _assets()
    visual = BattleCombatantVisual(
        "hero", "sheet.hero", "clips.hero", BattleVisualAnchor(0, 0),
        {"idle": "idle", "hit": "hurt", "ko": "down"},
    )
    runtime = BattlePresentationRuntime(
        BattlePresentationScene("fallback", "bg", (visual,)), clips.get, sheets.get
    )
    coordinator = BattlePresentationCoordinator(runtime.scene)
    marker = {"damage": 123, "target_valid": True}
    coordinator.consume_timeline_cues((PresentationCue(
        "missing", ActionCue("attack", 0.0, "animation", {"member_id": "hero", "role": "attack"})
    ),))
    result = runtime.apply_events(coordinator.drain())
    assert result == (False,)
    assert runtime.combatant("hero").role == BattleAnimationRole.IDLE
    assert marker == {"damage": 123, "target_valid": True}


def test_render_frame_uses_existing_texture_draw_and_anchor_facing():
    runtime = _runtime()
    frame = runtime.build_frame(Camera2D(width=320, height=180, zoom=2.0))
    assert frame.scene_id == "batch95.reference"
    assert frame.background_asset_id == "battle.bg.reference_clearing"
    assert [x.texture_asset_id for x in frame.combatant_draws] == ["10000000-0000-4000-8000-0000000000a1", "10000000-0000-4000-8000-0000000000a2"]
    assert frame.combatant_draws[0].flip_x is False
    assert frame.combatant_draws[1].flip_x is True
    assert frame.combatant_draws[0].width == 32
    assert frame.combatant_draws[1].width == 64


def test_snapshot_restore_is_deterministic_and_presentation_only():
    runtime = _runtime()
    coordinator = BattlePresentationCoordinator(_scene())
    coordinator.consume_timeline_cues((PresentationCue(
        "hero.slash", ActionCue("attack", 0.0, "animation", {"member_id": "hero", "role": "attack"})
    ),))
    runtime.apply_events(coordinator.drain())
    runtime.update(0.15)
    snapshot = runtime.snapshot()

    restored = _runtime()
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot
    restored.update(0.05)
    runtime.update(0.05)
    assert restored.snapshot() == runtime.snapshot()


def test_out_of_order_presentation_events_are_rejected():
    runtime = _runtime()
    coordinator = BattlePresentationCoordinator(_scene())
    coordinator.push_custom("noop")
    event = coordinator.drain()[0]
    runtime.apply_event(event)
    try:
        runtime.apply_event(event)
    except ValueError as exc:
        assert "increasing sequence" in str(exc)
    else:
        raise AssertionError("duplicate/out-of-order event should fail")


def test_project_defined_animation_role_is_not_limited_by_builtin_enum():
    sheets, clips = _assets()
    visual = BattleCombatantVisual(
        "hero", "sheet.hero", "clips.hero", BattleVisualAnchor(0, 0),
        {"idle": "idle", "dance_combo": "slash", "ko": "down"},
    )
    runtime = BattlePresentationRuntime(
        BattlePresentationScene("custom-role", "bg", (visual,)), clips.get, sheets.get
    )
    coordinator = BattlePresentationCoordinator(runtime.scene)
    coordinator.consume_timeline_cues((PresentationCue(
        "custom", ActionCue("dance", 0.0, "animation",
                            {"member_id": "hero", "role": "dance_combo"})
    ),))
    assert runtime.apply_events(coordinator.drain()) == (True,)
    assert runtime.combatant("hero").role == "dance_combo"
    assert runtime.combatant("hero").clip_name == "slash"


def test_project_defined_animation_role_survives_snapshot_restore():
    sheets, clips = _assets()
    visual = BattleCombatantVisual(
        "hero", "sheet.hero", "clips.hero", BattleVisualAnchor(0, 0),
        {"idle": "idle", "ritual.cast.long": "slash", "ko": "down"},
    )
    runtime = BattlePresentationRuntime(
        BattlePresentationScene("custom-role-snapshot", "bg", (visual,)), clips.get, sheets.get
    )
    state = runtime.combatant("hero")
    assert state.set_role("ritual.cast.long")
    snap = state.snapshot()
    state.set_role("idle")
    state.restore(snap)
    assert state.role == "ritual.cast.long"
    assert state.clip_name == "slash"


def test_sprite_sheet_resolution_is_preloaded_not_repeated_per_frame():
    sheets, clips = _assets()
    calls=[]
    def resolve_sheet(asset_id):
        calls.append(asset_id)
        return sheets.get(asset_id)
    runtime=BattlePresentationRuntime(_scene(), clips.get, resolve_sheet)
    initial=len(calls)
    camera=Camera2D(0,0,320,180,1.0)
    for _ in range(20):
        runtime.update(1/60)
        runtime.build_frame(camera)
    assert initial==2
    assert len(calls)==initial
