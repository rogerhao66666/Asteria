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
from asteria.presentation.battle_animation_timing import (
    BattleAnimationTimingProfile,
    BattleAnimationTimingRule,
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
    hero_clips = AnimationClipSet(
        {
            "idle": _clip("idle", [0], loop=True),
            "slash": _clip("slash", [1, 2, 3]),
            "hurt": _clip("hurt", [4]),
            "down": _clip("down", [5]),
        }
    )
    enemy_clips = AnimationClipSet(
        {
            "idle": _clip("idle", [0, 1], loop=True),
            "attack": _clip("attack", [2, 3]),
            "hit": _clip("hit", [4]),
            "ko": _clip("ko", [5]),
        }
    )
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
    coordinator.consume_timeline_cues(
        (
            PresentationCue(
                "hero.slash",
                ActionCue(
                    "hero_attack", 0.0, "animation", {"member_id": "hero", "role": "attack"}
                ),
            ),
            PresentationCue(
                "hero.slash",
                ActionCue("mimic_hit", 0.1, "animation", {"member_id": "mimic", "role": "hit"}),
            ),
        )
    )
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
        "hero",
        "sheet.hero",
        "clips.hero",
        BattleVisualAnchor(0, 0),
        {"idle": "idle", "hit": "hurt", "ko": "down"},
    )
    runtime = BattlePresentationRuntime(
        BattlePresentationScene("fallback", "bg", (visual,)), clips.get, sheets.get
    )
    coordinator = BattlePresentationCoordinator(runtime.scene)
    marker = {"damage": 123, "target_valid": True}
    coordinator.consume_timeline_cues(
        (
            PresentationCue(
                "missing",
                ActionCue("attack", 0.0, "animation", {"member_id": "hero", "role": "attack"}),
            ),
        )
    )
    result = runtime.apply_events(coordinator.drain())
    assert result == (False,)
    assert runtime.combatant("hero").role == BattleAnimationRole.IDLE
    assert marker == {"damage": 123, "target_valid": True}


def test_render_frame_uses_existing_texture_draw_and_anchor_facing():
    runtime = _runtime()
    frame = runtime.build_frame(Camera2D(width=320, height=180, zoom=2.0))
    assert frame.scene_id == "batch95.reference"
    assert frame.background_asset_id == "battle.bg.reference_clearing"
    assert [x.texture_asset_id for x in frame.combatant_draws] == [
        "10000000-0000-4000-8000-0000000000a1",
        "10000000-0000-4000-8000-0000000000a2",
    ]
    assert frame.combatant_draws[0].flip_x is False
    assert frame.combatant_draws[1].flip_x is True
    assert frame.combatant_draws[0].width == 32
    assert frame.combatant_draws[1].width == 64


def _sized_actor_runtime(cell_size, *, source_ratio=1.0, with_aura=False, transition_duration=0.0):
    texture = AssetRef("10000000-0000-4000-8000-0000000000b1", "texture")
    aura_texture = AssetRef("10000000-0000-4000-8000-0000000000b2", "texture")
    frames = [SpriteFrame(i * cell_size, 0, cell_size, cell_size) for i in range(2)]
    sheets = {"sized.actor": SpriteSheet(texture, frames)}
    if with_aura:
        sheets["sized.actor.aura"] = SpriteSheet(aura_texture, list(frames))
    clips = AnimationClipSet(
        {
            "idle": _clip("idle", [0], loop=True),
            "attack": _clip("attack", [1], loop=False),
            "hit": _clip("hit", [1], loop=False),
            "ko": _clip("ko", [1], loop=False),
        }
    )
    visual_options = {}
    if source_ratio != 1.0:
        visual_options["source_pixels_per_logical_pixel"] = source_ratio
    if with_aura:
        visual_options["aura_sprite_sheet_asset_id"] = "sized.actor.aura"
    visual = BattleCombatantVisual(
        "hero",
        "sized.actor",
        "sized.clips",
        BattleVisualAnchor(72, 104),
        {"idle": "idle", "attack": "attack", "hit": "hit", "ko": "ko"},
        **visual_options,
    )
    scene = BattlePresentationScene("sized.actor.scene", "battle.bg", (visual,))
    profile = BattleAnimationTimingProfile(
        (BattleAnimationTimingRule("attack", transition_duration=transition_duration),)
    )
    runtime = BattlePresentationRuntime(scene, lambda _asset_id: clips, sheets.get, profile)
    return runtime


def test_high_resolution_visual_scales_source_frames_to_same_logical_bounds():
    camera = Camera2D(width=320, height=180, zoom=1.5)
    standard = _sized_actor_runtime(64).build_frame(camera).combatant_draws[0]
    high_resolution = (
        _sized_actor_runtime(128, source_ratio=2.0).build_frame(camera).combatant_draws[0]
    )

    assert standard.source == (0, 0, 64, 64)
    assert high_resolution.source == (0, 0, 128, 128)
    assert (high_resolution.screen_x, high_resolution.screen_y) == (
        standard.screen_x,
        standard.screen_y,
    )
    assert (
        (high_resolution.width, high_resolution.height)
        == (standard.width, standard.height)
        == (96, 96)
    )


def test_high_resolution_aura_and_transition_share_scaled_bounds():
    runtime = _sized_actor_runtime(128, source_ratio=2.0, with_aura=True, transition_duration=0.2)
    assert runtime.combatant("hero").set_role("attack")

    draws = runtime.build_frame(Camera2D(width=320, height=180, zoom=1.5)).combatant_draws

    assert [draw.texture_asset_id for draw in draws] == [
        "10000000-0000-4000-8000-0000000000b2",
        "10000000-0000-4000-8000-0000000000b2",
        "10000000-0000-4000-8000-0000000000b1",
        "10000000-0000-4000-8000-0000000000b1",
    ]
    assert [draw.source for draw in draws] == [
        (0, 0, 128, 128),
        (128, 0, 128, 128),
        (0, 0, 128, 128),
        (128, 0, 128, 128),
    ]
    assert {(draw.screen_x, draw.screen_y, draw.width, draw.height) for draw in draws} == {
        (60.0, 60.0, 96.0, 96.0),
    }


def test_legacy_visual_data_defaults_source_pixel_ratio_to_one():
    visual = BattleCombatantVisual(
        "hero", "sized.actor", "sized.clips", BattleVisualAnchor(72, 104), {"idle": "idle"}
    )
    legacy_payload = visual.to_data()
    legacy_payload.pop("source_pixels_per_logical_pixel", None)
    restored = BattleCombatantVisual.from_data(legacy_payload)

    draw = _sized_actor_runtime(64).build_frame(Camera2D(width=320, height=180)).combatant_draws[0]
    assert restored.source_pixels_per_logical_pixel == 1.0
    assert "source_pixels_per_logical_pixel" not in visual.to_data()
    assert (draw.width, draw.height) == (64, 64)


def test_non_default_source_pixel_ratio_round_trips():
    visual = BattleCombatantVisual(
        "hero",
        "sheet",
        "clips",
        BattleVisualAnchor(0, 0),
        source_pixels_per_logical_pixel=2.0,
    )

    restored = BattleCombatantVisual.from_data(visual.to_data())

    assert visual.to_data()["source_pixels_per_logical_pixel"] == 2.0
    assert restored.source_pixels_per_logical_pixel == 2.0


def test_battle_visual_rejects_non_positive_or_non_finite_source_pixel_ratio():
    from pytest import raises

    for ratio in (0.0, -1.0, float("nan"), float("inf")):
        with raises(
            ValueError, match="source_pixels_per_logical_pixel must be finite and positive"
        ):
            BattleCombatantVisual(
                "hero",
                "sheet",
                "clips",
                BattleVisualAnchor(0, 0),
                source_pixels_per_logical_pixel=ratio,
            )


def test_aura_sheet_tracks_actor_frame_and_draws_behind_character():
    sheets, clips = _assets()
    base = sheets["sheet.hero"]
    sheets["sheet.hero.aura"] = SpriteSheet(
        AssetRef("10000000-0000-4000-8000-0000000000a3", "texture"),
        list(base.frames),
    )
    visual = BattleCombatantVisual(
        "hero",
        "sheet.hero",
        "clips.hero",
        BattleVisualAnchor(72, 104, "left", 0.1),
        {"idle": "idle", "attack": "slash", "hit": "hurt", "ko": "down"},
        aura_sprite_sheet_asset_id="sheet.hero.aura",
    )
    scene = BattlePresentationScene("battle.aura", "battle.bg", (visual,))
    runtime = BattlePresentationRuntime(scene, clips.get, sheets.get)

    draws = runtime.build_frame(Camera2D(width=320, height=180)).combatant_draws

    assert [draw.texture_asset_id for draw in draws] == [
        "10000000-0000-4000-8000-0000000000a3",
        "10000000-0000-4000-8000-0000000000a1",
    ]
    aura, character = draws
    assert aura.layer < character.layer
    assert aura.source == character.source == (0, 0, 16, 24)
    assert (aura.screen_x, aura.screen_y, aura.width, aura.height) == (
        character.screen_x,
        character.screen_y,
        character.width,
        character.height,
    )
    assert aura.opacity == character.opacity == 1.0
    assert aura.flip_x is character.flip_x is True

    from asteria.presentation import CombatantOverlay

    runtime.set_overlay("hero", CombatantOverlay("sheet.weapon", ((0, 0, 8, 12),)))
    runtime.combatant("hero").set_role("attack")
    attack_draws = runtime.build_frame(Camera2D(width=320, height=180)).combatant_draws
    assert attack_draws[-1].texture_asset_id == "sheet.weapon"
    assert (
        max(draw.layer for draw in attack_draws if draw.texture_asset_id != "sheet.weapon")
        < attack_draws[-1].layer
    )


def test_battle_visual_aura_asset_id_round_trips_and_old_payloads_stay_valid():
    visual = BattleCombatantVisual(
        "hero",
        "sheet.hero",
        "clips.hero",
        BattleVisualAnchor(72, 104),
        {"idle": "idle"},
        aura_sprite_sheet_asset_id="sheet.hero.aura",
    )

    restored = BattleCombatantVisual.from_data(visual.to_data())
    legacy_data = visual.to_data()
    legacy_data.pop("aura_sprite_sheet_asset_id")
    legacy = BattleCombatantVisual.from_data(legacy_data)

    assert restored.aura_sprite_sheet_asset_id == "sheet.hero.aura"
    assert legacy.aura_sprite_sheet_asset_id is None


def test_aura_sheet_must_match_character_frame_layout():
    from pytest import raises

    sheets, clips = _assets()
    base = sheets["sheet.hero"]
    mismatched_frames = list(base.frames)
    mismatched_frames[0] = SpriteFrame(0, 0, 15, 24)
    sheets["sheet.hero.aura"] = SpriteSheet(
        AssetRef("10000000-0000-4000-8000-0000000000a3", "texture"),
        mismatched_frames,
    )
    visual = BattleCombatantVisual(
        "hero",
        "sheet.hero",
        "clips.hero",
        BattleVisualAnchor(72, 104),
        {"idle": "idle"},
        aura_sprite_sheet_asset_id="sheet.hero.aura",
    )

    with raises(ValueError, match="aura sprite sheet frame layout"):
        BattlePresentationRuntime(
            BattlePresentationScene("battle.aura", "battle.bg", (visual,)),
            clips.get,
            sheets.get,
        )


def test_snapshot_restore_is_deterministic_and_presentation_only():
    runtime = _runtime()
    coordinator = BattlePresentationCoordinator(_scene())
    coordinator.consume_timeline_cues(
        (
            PresentationCue(
                "hero.slash",
                ActionCue("attack", 0.0, "animation", {"member_id": "hero", "role": "attack"}),
            ),
        )
    )
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
        "hero",
        "sheet.hero",
        "clips.hero",
        BattleVisualAnchor(0, 0),
        {"idle": "idle", "dance_combo": "slash", "ko": "down"},
    )
    runtime = BattlePresentationRuntime(
        BattlePresentationScene("custom-role", "bg", (visual,)), clips.get, sheets.get
    )
    coordinator = BattlePresentationCoordinator(runtime.scene)
    coordinator.consume_timeline_cues(
        (
            PresentationCue(
                "custom",
                ActionCue("dance", 0.0, "animation", {"member_id": "hero", "role": "dance_combo"}),
            ),
        )
    )
    assert runtime.apply_events(coordinator.drain()) == (True,)
    assert runtime.combatant("hero").role == "dance_combo"
    assert runtime.combatant("hero").clip_name == "slash"


def test_project_defined_animation_role_survives_snapshot_restore():
    sheets, clips = _assets()
    visual = BattleCombatantVisual(
        "hero",
        "sheet.hero",
        "clips.hero",
        BattleVisualAnchor(0, 0),
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
    calls = []

    def resolve_sheet(asset_id):
        calls.append(asset_id)
        return sheets.get(asset_id)

    runtime = BattlePresentationRuntime(_scene(), clips.get, resolve_sheet)
    initial = len(calls)
    camera = Camera2D(0, 0, 320, 180, 1.0)
    for _ in range(20):
        runtime.update(1 / 60)
        runtime.build_frame(camera)
    assert initial == 2
    assert len(calls) == initial
