import pytest

from asteria.presentation import (
    BattlePortraitPartyTemplateProfile,
    BattlePortraitPartyTemplateRuntime,
    BattlePortraitPartyZone,
    default_dungeon_portrait_party_profile,
)


def test_default_template_hides_portrait_party_bodies_but_keeps_hud():
    result = BattlePortraitPartyTemplateRuntime().resolve(
        portrait_party_ids=("p0", "p1", "p2", "p3"),
        battlefield_member_ids=("e0", "e1"),
    )
    party = [x for x in result.placements if x.member_id.startswith("p")]
    assert all(not x.battlefield_visible for x in party)
    assert all(x.hud_visible for x in party)
    assert all(x.hud_zone_id == "hud.party" for x in party)


def test_battlefield_members_remain_visible_and_have_explicit_zone():
    result = BattlePortraitPartyTemplateRuntime().resolve(
        portrait_party_ids=("p0",),
        battlefield_member_ids=("boss", "add"),
    )
    mapping = {x.member_id: x for x in result.placements}
    assert mapping["boss"].battlefield_visible
    assert mapping["boss"].battlefield_zone_id == "battle.front"
    assert mapping["add"].battlefield_visible


def test_template_does_not_infer_semantics_from_names():
    result = BattlePortraitPartyTemplateRuntime().resolve(
        portrait_party_ids=("enemy_named_portrait",),
        battlefield_member_ids=("player_named_battlefield",),
    )
    mapping = {x.member_id: x for x in result.placements}
    assert not mapping["enemy_named_portrait"].battlefield_visible
    assert mapping["player_named_battlefield"].battlefield_visible


def test_opaque_member_ids_work():
    result = BattlePortraitPartyTemplateRuntime().resolve(
        portrait_party_ids=("m.1", "m.2"),
        battlefield_member_ids=("m.8", "m.9"),
    )
    assert result.portrait_party_ids == ("m.1", "m.2")
    assert result.battlefield_member_ids == ("m.8", "m.9")


def test_project_can_show_party_bodies_without_gameplay_change():
    profile = BattlePortraitPartyTemplateProfile(
        "show-bodies",
        BattlePortraitPartyZone("front", 160, 60, 24, "left"),
        hide_portrait_party_bodies=False,
    )
    result = BattlePortraitPartyTemplateRuntime(profile).resolve(
        portrait_party_ids=("p0", "p1"),
        battlefield_member_ids=("e0",),
    )
    party = [x for x in result.placements if x.member_id.startswith("p")]
    assert all(x.battlefield_visible for x in party)
    assert all(x.hud_visible for x in party)


def test_battlefield_visibility_cap_is_presentation_overflow_only():
    profile = BattlePortraitPartyTemplateProfile(
        "crowded",
        BattlePortraitPartyZone("front", 160, 60, 18, "left"),
        max_visible_battlefield_members=3,
    )
    result = BattlePortraitPartyTemplateRuntime(profile).resolve(
        portrait_party_ids=("p0",),
        battlefield_member_ids=tuple(f"e{i}" for i in range(6)),
    )
    assert result.overflow_battlefield_ids == ("e3", "e4", "e5")
    assert len(result.battlefield_member_ids) == 6
    visible = [
        x.member_id
        for x in result.placements
        if x.battlefield_visible and x.member_id.startswith("e")
    ]
    assert visible == ["e0", "e1", "e2"]


def test_duplicate_member_across_roles_is_rejected():
    with pytest.raises(ValueError, match="duplicate member"):
        BattlePortraitPartyTemplateRuntime().resolve(
            portrait_party_ids=("same",), battlefield_member_ids=("same",)
        )


def test_hud_and_battlefield_roles_are_independent():
    result = BattlePortraitPartyTemplateRuntime().resolve(
        portrait_party_ids=("p0",),
        battlefield_member_ids=("boss",),
    )
    mapping = {x.member_id: x for x in result.placements}
    assert mapping["p0"].hud_zone_id == "hud.party"
    assert mapping["boss"].hud_zone_id == "hud.enemy"
    assert mapping["p0"].battlefield_zone_id is None
    assert mapping["boss"].battlefield_zone_id == "battle.front"


def test_default_profile_is_non_sideview_presentation_grammar():
    p = default_dungeon_portrait_party_profile()
    assert p.template_id == "asteria.dungeon_portrait_party.default"
    assert p.hide_portrait_party_bodies
    assert p.battlefield_zone.zone_id == "battle.front"


def test_party_size_is_not_capped_by_default():
    result = BattlePortraitPartyTemplateRuntime().resolve(
        portrait_party_ids=tuple(f"p{i}" for i in range(12)),
        battlefield_member_ids=("boss",),
    )
    assert len(result.portrait_party_ids) == 12
    assert not result.overflow_battlefield_ids
