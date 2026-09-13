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
    BattleUiComposer,
    BattleUiPolishProfile,
    BattleUiRenderer,
    BattleUiTheme,
    BattleWorkflowOption,
    BattleWorkflowStep,
    HeadlessBattleUiBackend,
)
from asteria.runtime import Camera2D


def _scene():
    return BattlePresentationScene("premium.ui", "bg", ())


def _frame():
    return BattlePresentationFrame("premium.ui", "bg", ())


def _member(member_id):
    return BattleHudMember(
        member_id,
        (
            BattleHudGauge("hp", "HP", 70, 0, 100, 0, .7, False, None, 0),
            BattleHudGauge("bp", "BP", 3, 0, 5, 0, .6, False, None, 10, "pips", 5),
        ),
        (),
    )


def test_focus_member_gets_premium_emphasis_without_changing_other_members():
    composer = BattleUiComposer(_scene(), polish=BattleUiPolishProfile(focus_member_emphasis=True))
    ui = composer.compose(
        Camera2D(),
        _frame(),
        hud_members=(_member("a"), _member("b")),
        placement_by_member={"a": "left", "b": "right"},
        focus_member_id="a",
    )
    panels = {x.member_id: x for x in ui.panels if x.panel_id.startswith("hud:")}
    assert panels["a"].role.endswith(":focus")
    assert not panels["b"].role.endswith(":focus")

    backend = HeadlessBattleUiBackend()
    theme = BattleUiTheme()
    BattleUiRenderer(backend, theme).render(ui)
    focus = next(x for x in backend.ops if x[0] == "panel" and x[1] == "hud:a")
    normal = next(x for x in backend.ops if x[0] == "panel" and x[1] == "hud:b")
    assert focus[3]["border"] == theme.panel_focus_border
    assert normal[3]["border"] == theme.panel_border


def test_action_menu_uses_interaction_surface_and_selected_hierarchy():
    runtime = BattleActionMenuRuntime(BattleActionMenuPolicy(page_size=4))
    runtime.set_entries((
        BattleActionEntry("slash", "Slash", category="weapon", cost_text="3 SP"),
        BattleActionEntry("guard", "Guard", category="stance"),
        BattleActionEntry("locked", "Limit", category="special", enabled=False, disabled_reason="Not ready"),
    ))
    composer = BattleUiComposer(_scene(), polish=BattleUiPolishProfile(interaction_width=170))
    ui = composer.compose(Camera2D(), _frame(), action_menu=runtime.view)

    panel = next(x for x in ui.panels if x.panel_id == "action_menu")
    selected = next(x for x in ui.texts if x.role == "action_selected")
    disabled = next(x for x in ui.texts if x.role == "action_disabled")
    assert panel.role == "interaction:action_menu"
    assert panel.width == 170
    assert selected.text.startswith("▶ ")
    assert disabled.text.strip() == "Limit"

    backend = HeadlessBattleUiBackend()
    theme = BattleUiTheme()
    BattleUiRenderer(backend, theme).render(ui)
    selected_op = next(x for x in backend.ops if x[0] == "text" and x[2] == "action_selected")
    disabled_op = next(x for x in backend.ops if x[0] == "text" and x[2] == "action_disabled")
    assert selected_op[4]["color"] == theme.text_selected
    assert selected_op[4]["size"] == theme.font_size + 1
    assert disabled_op[4]["color"] == theme.text_disabled


def test_workflow_selected_option_has_clear_visual_role():
    runtime = BattleActionWorkflowRuntime()
    definition = BattleActionWorkflowDefinition(
        "mix",
        "Concoct",
        (BattleWorkflowStep("base", "Choose Base"),),
    )
    runtime.begin(definition, (
        BattleWorkflowOption("herb", "Herb"),
        BattleWorkflowOption("powder", "Powder"),
    ))
    runtime.select("herb")

    ui = BattleUiComposer(_scene()).compose(
        Camera2D(), _frame(), action_workflow=runtime.view
    )
    panel = next(x for x in ui.panels if x.panel_id == "action_workflow")
    selected = next(x for x in ui.texts if x.role == "workflow_option_selected")
    assert panel.role == "interaction:workflow"
    assert selected.text.startswith("✓ ")


def test_polish_profile_is_project_owned_and_roundtrips():
    profile = BattleUiPolishProfile(
        interaction_width=174,
        interaction_padding=8,
        interaction_row_height=13,
        selected_prefix="> ",
        selected_option_prefix="* ",
        page_separator=" of ",
    )
    assert BattleUiPolishProfile.from_data(profile.to_data()) == profile


def test_theme_new_hierarchy_fields_roundtrip():
    theme = BattleUiTheme(
        panel_focus_border=(250, 210, 100, 255),
        interaction_border=(140, 160, 210, 255),
        text_disabled=(90, 100, 120, 255),
        text_selected=(255, 230, 140, 255),
    )
    restored = BattleUiTheme.from_data(theme.to_data())
    assert restored == theme
    assert restored.panel_style("interaction:action_menu")[1] == theme.interaction_border
