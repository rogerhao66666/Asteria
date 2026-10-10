import pytest

from asteria.presentation import (
    BattleSideviewTemplateProfile,
    BattleSideviewTemplateRuntime,
    BattleSideviewZone,
    default_sideview_jrpg_profile,
)


def test_default_template_places_left_and_right_facing_center():
    result = BattleSideviewTemplateRuntime().resolve(
        left_member_ids=("alpha.enemy.1", "alpha.enemy.2"),
        right_member_ids=("omega.player.1", "omega.player.2"),
    )
    left = [x for x in result.placements if x.zone_id == "battle.left"]
    right = [x for x in result.placements if x.zone_id == "battle.right"]
    assert {x.facing for x in left} == {"right"}
    assert {x.facing for x in right} == {"left"}
    assert max(x.x for x in left) < min(x.x for x in right)


def test_template_does_not_infer_semantics_from_member_names():
    result = BattleSideviewTemplateRuntime().resolve(
        left_member_ids=("player_named_but_left",),
        right_member_ids=("enemy_named_but_right",),
    )
    mapping = {x.member_id: x.zone_id for x in result.placements}
    assert mapping["player_named_but_left"] == "battle.left"
    assert mapping["enemy_named_but_right"] == "battle.right"


def test_opaque_member_ids_work_without_player_enemy_keywords():
    result = BattleSideviewTemplateRuntime().resolve(
        left_member_ids=("m.17", "m.23"),
        right_member_ids=("m.91", "m.105"),
    )
    assert dict(result.zone_by_member) == {
        "m.17": "battle.left",
        "m.23": "battle.left",
        "m.91": "battle.right",
        "m.105": "battle.right",
    }


def test_hud_zones_are_explicit_and_independent_from_battlefield_zone():
    result = BattleSideviewTemplateRuntime().resolve(left_member_ids=("a",), right_member_ids=("b",))
    assert dict(result.hud_zone_by_member) == {"a": "hud.left", "b": "hud.right"}


def test_arbitrary_party_size_is_not_capped_by_default():
    result = BattleSideviewTemplateRuntime().resolve(
        left_member_ids=tuple(f"l{i}" for i in range(8)),
        right_member_ids=tuple(f"r{i}" for i in range(12)),
    )
    assert len(result.placements) == 20
    assert result.overflow_member_ids == ()
    assert all(x.visible for x in result.placements)


def test_project_profile_can_choose_presentation_visibility_cap_without_gameplay_cap():
    profile = BattleSideviewTemplateProfile(
        "compact",
        BattleSideviewZone("L", 40, 60, 16, "right"),
        BattleSideviewZone("R", 280, 60, 16, "left"),
        max_visible_per_zone=4,
    )
    result = BattleSideviewTemplateRuntime(profile).resolve(
        left_member_ids=tuple(f"l{i}" for i in range(7)),
        right_member_ids=tuple(f"r{i}" for i in range(6)),
    )
    assert sum(x.visible for x in result.placements) == 8
    assert result.overflow_member_ids == ("l4", "l5", "l6", "r4", "r5")
    assert len(result.placements) == 13


def test_duplicate_member_across_zones_is_rejected():
    with pytest.raises(ValueError, match="duplicate member"):
        BattleSideviewTemplateRuntime().resolve(left_member_ids=("same",), right_member_ids=("same",))


def test_project_can_reverse_or_replace_visual_grammar_without_core_change():
    profile = BattleSideviewTemplateProfile(
        "reverse",
        BattleSideviewZone("left.alt", 50, 70, 22, "left"),
        BattleSideviewZone("right.alt", 270, 70, 22, "right"),
        left_hud_zone_id="hud.a",
        right_hud_zone_id="hud.b",
    )
    result = BattleSideviewTemplateRuntime(profile).resolve(left_member_ids=("x",), right_member_ids=("y",))
    assert {x.member_id: x.facing for x in result.placements} == {"x": "left", "y": "right"}
    assert dict(result.hud_zone_by_member) == {"x": "hud.a", "y": "hud.b"}


def test_depth_is_authored_by_zone_order_not_semantic_role():
    result = BattleSideviewTemplateRuntime().resolve(
        left_member_ids=("boss", "summon", "ordinary"),
        right_member_ids=(),
    )
    depths = [x.depth for x in result.placements]
    assert depths == sorted(depths)


def test_default_profile_is_presentation_preset_only():
    p = default_sideview_jrpg_profile()
    assert p.template_id == "asteria.sideview_jrpg.default"
    assert p.left_zone.facing == "right"
    assert p.right_zone.facing == "left"
