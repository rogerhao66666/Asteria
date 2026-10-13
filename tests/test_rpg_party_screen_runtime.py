from asteria.presentation import PartyScreenProfile, PartyScreenRuntime
from asteria.rpg.targeting import (
    BattleFormationRuntime,
    BattlePlacement,
    FormationDefinition,
    FormationSlotDefinition,
)


def _formation():
    definition = FormationDefinition(
        "field",
        (
            FormationSlotDefinition(
                "vanguard", x=0, y=0, tags=("front",), adjacent_to=("center",)
            ),
            FormationSlotDefinition(
                "center", x=1, y=0, tags=("middle",), adjacent_to=("vanguard", "rear")
            ),
            FormationSlotDefinition("rear", x=2, y=0, tags=("back",), adjacent_to=("center",)),
        ),
    )
    return BattleFormationRuntime(
        definition,
        (
            BattlePlacement("a", "vanguard"),
            BattlePlacement("b", "center"),
            BattlePlacement("c", "rear"),
        ),
    )


def test_party_screen_projects_active_reserve_without_mutating_membership():
    roster = ("a", "b", "c", "d", "e")
    active = ("a", "b", "c")
    runtime = PartyScreenRuntime()
    view = runtime.project(roster, active_member_ids=active)

    assert tuple(x.member_id for x in view.roster) == roster
    assert tuple(x.member_id for x in view.roster if x.active) == active
    assert tuple(x.member_id for x in view.roster if x.reserve) == ("d", "e")
    assert view.focused_member_id == "a"


def test_formation_projection_preserves_project_slot_semantics_as_tags_only():
    runtime = PartyScreenRuntime(
        PartyScreenProfile(slot_labels={"vanguard": "Lead", "rear": "Rear"})
    )
    view = runtime.project(
        ("a", "b", "c"),
        active_member_ids=("a", "b", "c"),
        formation=_formation(),
    )
    slots = {x.slot_id: x for x in view.formation_slots}
    assert slots["vanguard"].label == "Lead"
    assert slots["vanguard"].tags == ("front",)
    assert slots["vanguard"].member_id == "a"
    assert slots["center"].adjacent_to == ("rear", "vanguard") or slots["center"].adjacent_to == (
        "vanguard",
        "rear",
    )


def test_custom_groups_are_opaque_presentation_groups():
    profile = PartyScreenProfile(
        group_order=("deployed", "bench", "summons"),
        group_labels={"deployed": "Field", "bench": "Bench", "summons": "Summons"},
    )
    runtime = PartyScreenRuntime(profile)
    view = runtime.project(
        ("a", "b", "c", "d"),
        active_member_ids=("a", "b"),
        group_by_member={"a": "deployed", "b": "deployed", "c": "bench", "d": "summons"},
    )
    assert [x.group_id for x in view.groups] == ["deployed", "bench", "summons"]
    assert view.groups[2].member_ids == ("d",)


def test_large_roster_uses_display_overflow_without_gameplay_cap():
    profile = PartyScreenProfile(visible_limits={"active": 4, "reserve": 5})
    runtime = PartyScreenRuntime(profile)
    roster = tuple(f"unit{i}" for i in range(20))
    active = tuple(f"unit{i}" for i in range(8))
    view = runtime.project(roster, active_member_ids=active)

    active_group = next(x for x in view.groups if x.group_id == "active")
    reserve_group = next(x for x in view.groups if x.group_id == "reserve")
    assert len(active_group.member_ids) == 8
    assert len(active_group.visible_member_ids) == 4
    assert active_group.overflow_count == 4
    assert len(reserve_group.member_ids) == 12
    assert reserve_group.overflow_count == 7


def test_focus_is_presentation_only():
    runtime = PartyScreenRuntime()
    roster = ("a", "b", "c")
    runtime.project(roster, active_member_ids=("a", "b"))
    runtime.focus("c")

    assert runtime.view.focused_member_id == "c"
    assert next(x for x in runtime.view.roster if x.member_id == "c").focused
    assert tuple(x.member_id for x in runtime.view.roster) == roster
    assert next(x for x in runtime.view.roster if x.member_id == "c").reserve


def test_focus_retention_in_overflow_does_not_reorder_canonical_group():
    profile = PartyScreenProfile(visible_limits={"reserve": 2})
    runtime = PartyScreenRuntime(profile)
    roster = ("a", "b", "c", "d")
    runtime.project(roster, active_member_ids=("a",))
    runtime.focus("d")
    view = runtime.project(roster, active_member_ids=("a",))
    reserve = next(x for x in view.groups if x.group_id == "reserve")
    assert reserve.member_ids == ("b", "c", "d")
    assert "d" in reserve.visible_member_ids
    assert reserve.member_ids != reserve.visible_member_ids


def test_profile_roundtrip():
    profile = PartyScreenProfile(
        group_order=("field", "reserve"),
        group_labels={"field": "Field"},
        member_labels={"a": "Aria"},
        slot_labels={"slot_x": "Slot X"},
        visible_limits={"reserve": 6},
    )
    assert PartyScreenProfile.from_data(profile.to_data()) == profile


def test_snapshot_restore_roundtrip():
    profile = PartyScreenProfile(
        member_labels={"a": "Aria"},
        visible_limits={"reserve": 2},
    )
    runtime = PartyScreenRuntime(profile)
    runtime.project(("a", "b", "c", "d"), active_member_ids=("a", "b"), formation=_formation())
    runtime.focus("c")
    snapshot = runtime.snapshot()

    restored = PartyScreenRuntime(profile)
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot


def test_rejects_unknown_active_or_formation_members():
    import pytest

    runtime = PartyScreenRuntime()
    with pytest.raises(ValueError):
        runtime.project(("a",), active_member_ids=("ghost",))

    formation = _formation()
    with pytest.raises(ValueError):
        runtime.project(("a", "b"), active_member_ids=("a", "b"), formation=formation)
