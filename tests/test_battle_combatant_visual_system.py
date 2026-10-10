import pytest

from asteria.presentation import (
    BattleCombatantVisualProfile,
    BattleCombatantVisualRuntime,
    BattleVisualAssetSet,
    BattleVisualStateDefinition,
    BattleVisualTransform,
    default_jrpg_visual_states,
)


def profile(profile_id="hero", *, battlefield_visible=True, hud_visible=True, transform=None):
    return BattleCombatantVisualProfile(
        profile_id,
        BattleVisualAssetSet(
            f"{profile_id}.battle",
            f"{profile_id}.portrait",
            f"{profile_id}.small",
            f"{profile_id}.icon",
        ),
        default_jrpg_visual_states(),
        transform or BattleVisualTransform(),
        battlefield_visible=battlefield_visible,
        hud_visible=hud_visible,
    )


def test_battlefield_portrait_small_portrait_and_icon_are_independent_assets():
    r = BattleCombatantVisualRuntime()
    v = r.register("hero", profile())
    assert v.battlefield_asset_id == "hero.battle"
    assert v.portrait_asset_id == "hero.portrait"
    assert v.small_portrait_asset_id == "hero.small"
    assert v.icon_asset_id == "hero.icon"


def test_default_visual_states_cover_common_battle_roles():
    ids = {x.state_id for x in default_jrpg_visual_states()}
    assert {"idle", "attack", "cast", "hit", "guard", "ko", "revive", "status", "transform"} <= ids


def test_unknown_visual_state_falls_back_to_idle_without_gameplay_semantics():
    r = BattleCombatantVisualRuntime()
    r.register("hero", profile())
    v = r.set_state("hero", "project.unknown")
    assert v.state_id == "idle"
    assert v.clip_role == "idle"


def test_large_boss_supports_scale_anchor_offset_and_z_order():
    transform = BattleVisualTransform(
        scale_x=2.8,
        scale_y=2.8,
        anchor_x=0.5,
        anchor_y=0.92,
        offset_x=-18,
        offset_y=6,
        z_order=40,
    )
    r = BattleCombatantVisualRuntime()
    v = r.register("boss", profile("boss", transform=transform))
    assert v.transform.scale_x == 2.8
    assert v.transform.anchor_y == 0.92
    assert v.transform.offset_x == -18
    assert v.transform.z_order == 40


def test_portrait_party_template_can_hide_battlefield_body_but_keep_hud_visible():
    r = BattleCombatantVisualRuntime()
    v = r.register("hero", profile(battlefield_visible=False, hud_visible=True))
    assert not v.battlefield_visible
    assert v.hud_visible


def test_visibility_can_change_without_changing_combatant_state_or_assets():
    r = BattleCombatantVisualRuntime()
    r.register("hero", profile())
    before = r.state("hero")
    after = r.set_visibility("hero", battlefield_visible=False)
    assert before.state_id == after.state_id == "idle"
    assert before.battlefield_asset_id == after.battlefield_asset_id
    assert not after.battlefield_visible and after.hud_visible


def test_transform_can_replace_visual_profile_for_same_member():
    r = BattleCombatantVisualRuntime()
    r.register("hero", profile("normal"))
    v = r.replace_profile("hero", profile("overdrive"), state_id="transform")
    assert v.member_id == "hero"
    assert v.profile_id == "overdrive"
    assert v.state_id == "transform"
    assert v.battlefield_asset_id == "overdrive.battle"


def test_enemy_player_boss_and_summon_use_same_profile_type():
    r = BattleCombatantVisualRuntime()
    for member_id in ("player", "enemy", "boss", "summon"):
        r.register(member_id, profile(member_id))
    assert {r.state(x).profile_id for x in ("player", "enemy", "boss", "summon")} == {
        "player",
        "enemy",
        "boss",
        "summon",
    }


def test_duplicate_member_visual_registration_is_rejected():
    r = BattleCombatantVisualRuntime()
    r.register("hero", profile())
    with pytest.raises(ValueError, match="duplicate visual member"):
        r.register("hero", profile("other"))


def test_visual_profile_requires_idle_fallback_state():
    with pytest.raises(ValueError, match="requires idle state"):
        BattleCombatantVisualProfile(
            "broken",
            BattleVisualAssetSet("broken.battle"),
            (BattleVisualStateDefinition("attack", "attack"),),
        )


def test_snapshot_keeps_member_profile_state_and_visibility():
    r = BattleCombatantVisualRuntime()
    r.register("boss", profile("boss"))
    r.set_state("boss", "guard")
    r.set_visibility("boss", hud_visible=False)
    snap = r.snapshot()
    state = snap["members"]["boss"]
    assert state["profile_id"] == "boss"
    assert state["state_id"] == "guard"
    assert state["battlefield_visible"]
    assert not state["hud_visible"]
