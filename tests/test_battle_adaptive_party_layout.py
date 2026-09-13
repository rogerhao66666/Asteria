from asteria.presentation import (
    BattleHudGauge,
    BattleHudMember,
    BattlePartyLayoutPolicy,
    BattlePresentationFrame,
    BattlePresentationScene,
    BattleUiComposer,
    BattleUiLayoutProfile,
)
from asteria.runtime import Camera2D


def _member(member_id, count=4):
    gauges = tuple(
        BattleHudGauge(
            f"r{i}", f"R{i}", i + 1, 0, 10, 0, (i + 1) / 10,
            False, None, i, "bar", 0, "primary", 100 - i, True, True, False
        )
        for i in range(count)
    )
    return BattleHudMember(member_id, gauges, ())


def _frame(scene_id="adaptive.party"):
    return BattlePresentationFrame(scene_id, "bg", ())


def test_policy_reduces_density_without_limiting_canonical_party_size():
    policy = BattlePartyLayoutPolicy()
    ids = tuple(f"member{i}" for i in range(12))
    result = policy.resolve(
        ids,
        zone_by_member={member_id: "left" for member_id in ids},
        available_height=120,
    )
    zone = result.zone("left")
    assert zone.density == "minimal"
    assert len(zone.visible_member_ids) < len(ids)
    assert len(zone.visible_member_ids) + len(zone.hidden_member_ids) == 12
    assert len(result.placements) == 12


def test_focus_member_is_kept_visible_when_zone_overflows():
    policy = BattlePartyLayoutPolicy(minimal_row_height=20)
    ids = tuple(f"m{i}" for i in range(10))
    result = policy.resolve(
        ids,
        zone_by_member={x: "left" for x in ids},
        focus_member_id="m9",
        available_height=60,
    )
    zone = result.zone("left")
    assert zone.visible_member_ids == ("m0", "m1", "m9")
    assert "m9" not in zone.hidden_member_ids
    assert zone.overflow_count == 7


def test_explicit_placement_is_generic_and_does_not_depend_on_side_names():
    policy = BattlePartyLayoutPolicy()
    result = policy.resolve(
        ("chemist", "dragon", "guest"),
        zone_by_member={"chemist": "right", "dragon": "left", "guest": "center"},
        available_height=140,
    )
    assert result.placement_for("chemist").zone == "right"
    assert result.placement_for("dragon").zone == "left"
    assert result.placement_for("guest").zone == "center"


def test_composer_compacts_large_party_and_prioritizes_resources():
    scene = BattlePresentationScene("adaptive.party", "bg", ())
    composer = BattleUiComposer(
        scene,
        BattleUiLayoutProfile(virtual_width=320, virtual_height=180),
        BattlePartyLayoutPolicy(
            expanded_row_height=42,
            compact_row_height=29,
            minimal_row_height=19,
            compact_resource_limit=2,
            minimal_resource_limit=1,
        ),
    )
    members = tuple(_member(f"m{i}", count=5) for i in range(8))
    placements = {f"m{i}": "left" for i in range(8)}
    ui = composer.compose(
        Camera2D(), _frame(), hud_members=members,
        placement_by_member=placements,
        focus_member_id="m7",
    )

    # All eight canonical members still exist; presentation uses overflow.
    visible_panels = [x for x in ui.panels if x.panel_id.startswith("hud:")]
    assert len(visible_panels) < 8
    assert any(x.text.startswith("+") and x.role == "hud_overflow" for x in ui.texts)
    assert any(x.member_id == "m7" for x in visible_panels)

    # Minimal density only exposes the highest-priority resource for each visible member.
    resources_by_member = {}
    for gauge in ui.gauges:
        resources_by_member.setdefault(gauge.member_id, []).append(gauge.resource_id)
    assert resources_by_member
    assert all(values == ["r0"] for values in resources_by_member.values())


def test_small_party_keeps_expanded_detail():
    scene = BattlePresentationScene("adaptive.party", "bg", ())
    composer = BattleUiComposer(scene)
    members = (_member("a", 3), _member("b", 3))
    ui = composer.compose(
        Camera2D(), _frame(), hud_members=members,
        placement_by_member={"a": "left", "b": "right"},
    )
    panels = {x.member_id: x for x in ui.panels if x.panel_id.startswith("hud:")}
    assert panels["a"].role == "hud:expanded"
    assert panels["b"].role == "hud:expanded"
    assert {(g.member_id, g.resource_id) for g in ui.gauges} == {
        ("a", "r0"), ("a", "r1"), ("a", "r2"),
        ("b", "r0"), ("b", "r1"), ("b", "r2"),
    }


def test_policy_roundtrip_is_project_configurable():
    policy = BattlePartyLayoutPolicy(
        expanded_row_height=46,
        compact_row_height=30,
        minimal_row_height=18,
        compact_resource_limit=4,
        minimal_resource_limit=2,
        compact_status_limit=5,
        minimal_status_limit=1,
        default_zone="center",
    )
    assert BattlePartyLayoutPolicy.from_data(policy.to_data()) == policy
