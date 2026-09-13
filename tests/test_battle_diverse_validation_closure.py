from asteria.presentation import (
    BattleActionEntry,
    BattleActionMenuPolicy,
    BattleActionMenuRuntime,
    BattleActionWorkflowDefinition,
    BattleActionWorkflowRuntime,
    BattleHudGauge,
    BattleHudMember,
    BattlePresentationFrame,
    BattlePresentationScene,
    BattleTurnEntry,
    BattleTurnTimelineView,
    BattleUiComposer,
    BattleWorkflowOption,
    BattleWorkflowStep,
)
from asteria.runtime import Camera2D


def _scene():
    return BattlePresentationScene("closure.diverse", "bg", ())


def _frame():
    return BattlePresentationFrame("closure.diverse", "bg", ())


def _gauge(resource_id, label, current, maximum, presentation="bar", priority=0, segments=0):
    return BattleHudGauge(
        resource_id, label, current, 0, maximum, 0,
        0 if maximum == 0 else current / maximum,
        False, None, 0, presentation, segments, "primary", priority,
        True, True, False,
    )


def _member(member_id, gauges):
    return BattleHudMember(member_id, tuple(gauges), ())


def test_classic_turn_based_is_only_one_possible_configuration():
    members = (
        _member("knight", (_gauge("vital", "Vital", 80, 100), _gauge("mana", "Mana", 20, 30))),
        _member("mage", (_gauge("vital", "Vital", 55, 70), _gauge("mana", "Mana", 48, 60))),
    )
    menu = BattleActionMenuRuntime(BattleActionMenuPolicy(page_size=6))
    menu.set_entries((
        BattleActionEntry("blade", "Blade", category="weapon"),
        BattleActionEntry("ward", "Ward", category="stance"),
        BattleActionEntry("spark", "Spark", category="arcana"),
    ))
    ui = BattleUiComposer(_scene()).compose(
        Camera2D(), _frame(), hud_members=members,
        placement_by_member={"knight": "left", "mage": "left"},
        action_menu=menu.view,
    )
    assert {g.resource_id for g in ui.gauges} == {"vital", "mana"}
    assert any(x.text == "Blade" or x.text.endswith("Blade") for x in ui.texts)


def test_break_bp_style_uses_generic_resources_not_engine_semantics():
    member = _member("traveler", (
        _gauge("life", "Life", 400, 500, "bar", 100),
        _gauge("spirit", "Spirit", 24, 40, "bar", 80),
        _gauge("boost", "Boost", 3, 5, "pips", 90, 5),
        _gauge("guard_break", "Guard", 2, 6, "segmented_bar", 70, 6),
    ))
    ui = BattleUiComposer(_scene()).compose(
        Camera2D(), _frame(), hud_members=(member,),
        placement_by_member={"traveler": "left"},
    )
    modes = {g.resource_id: g.presentation for g in ui.gauges}
    assert modes["boost"] == "pips"
    assert modes["guard_break"] == "segmented_bar"
    assert "hp" not in modes and "mp" not in modes


def test_atb_style_can_present_action_gauge_and_timeline():
    member = _member("runner", (
        _gauge("stamina", "Stamina", 70, 100, "bar", 50),
        _gauge("initiative_meter", "ACT", 45, 100, "action_gauge", 100),
    ))
    timeline = BattleTurnTimelineView(
        "continuous", 0, 12.0,
        (
            BattleTurnEntry("runner", "blue", 12.5, 140, 1, True),
            BattleTurnEntry("beast", "red", 13.0, 90, 2, False),
        ),
        (), 1,
    )
    ui = BattleUiComposer(_scene()).compose(
        Camera2D(), _frame(), hud_members=(member,), timeline=timeline,
        placement_by_member={"runner": "left"},
        focus_member_id="runner",
    )
    assert any(g.resource_id == "initiative_meter" and g.presentation == "action_gauge" for g in ui.gauges)
    assert any(t.role == "timeline_current" and t.text == "runner" for t in ui.texts)


def test_large_party_validation_has_no_gameplay_party_cap():
    members = tuple(
        _member(f"unit{i}", (_gauge("life", "L", 100-i, 100, "bar", 100),))
        for i in range(12)
    )
    ui = BattleUiComposer(_scene()).compose(
        Camera2D(), _frame(), hud_members=members,
        placement_by_member={f"unit{i}": "left" for i in range(12)},
        focus_member_id="unit11",
    )
    visible_ids = {p.member_id for p in ui.panels if p.panel_id.startswith("hud:")}
    assert "unit11" in visible_ids
    assert len(visible_ids) < 12
    assert any(t.role == "hud_overflow" for t in ui.texts)


def test_custom_composition_flow_is_not_hardcoded_as_alchemy():
    definition = BattleActionWorkflowDefinition(
        "resonance_weave",
        "Resonance Weave",
        (
            BattleWorkflowStep("tone", "Choose Tone"),
            BattleWorkflowStep("sigils", "Choose Sigils", selection_mode="multiple", minimum_selections=2, maximum_selections=3),
        ),
        confirmation_label="Weave",
    )
    runtime = BattleActionWorkflowRuntime()
    runtime.begin(definition, (
        BattleWorkflowOption("solar", "Solar"),
        BattleWorkflowOption("lunar", "Lunar"),
    ))
    runtime.select("solar")
    runtime.advance((
        BattleWorkflowOption("a", "A"),
        BattleWorkflowOption("b", "B"),
        BattleWorkflowOption("c", "C"),
    ))
    runtime.select("a")
    runtime.select("c")
    runtime.advance()

    payload = runtime.selection_payload()
    assert runtime.view.complete
    assert payload["workflow_id"] == "resonance_weave"
    assert payload["selections"]["sigils"] == ["a", "c"]


def test_single_character_battle_is_valid():
    member = _member("solo", (
        _gauge("resolve", "Resolve", 7, 10, "ring", 100),
        _gauge("heat", "Heat", 42, 100, "number", 80),
    ))
    ui = BattleUiComposer(_scene()).compose(
        Camera2D(), _frame(), hud_members=(member,),
        placement_by_member={"solo": "center"},
        focus_member_id="solo",
    )
    panel = next(p for p in ui.panels if p.member_id == "solo")
    assert panel.x > 0
    assert any(g.presentation == "ring" for g in ui.gauges)
    assert any(t.role.startswith("resource_value:number") for t in ui.texts)


def test_opaque_side_ids_are_never_semantically_interpreted():
    members = (
        _member("a", (_gauge("life", "Life", 1, 1),)),
        _member("b", (_gauge("life", "Life", 1, 1),)),
        _member("c", (_gauge("life", "Life", 1, 1),)),
    )
    ui = BattleUiComposer(_scene()).compose(
        Camera2D(), _frame(), hud_members=members,
        side_by_member={"a": "guild_alpha", "b": "red", "c": "guild_alpha"},
    )
    panels = {p.member_id: p for p in ui.panels if p.panel_id.startswith("hud:")}
    assert panels["a"].x == panels["c"].x
    assert panels["a"].x != panels["b"].x
