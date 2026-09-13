from asteria.presentation import (
    BattleUiFrame,
    BattleUiGaugeBar,
    BattleUiIcon,
    BattleUiMarker,
    BattleUiPanel,
    BattleUiRenderer,
    BattleUiText,
    BattleUiTheme,
    HeadlessBattleUiBackend,
)


def frame():
    return BattleUiFrame(
        "battle.reference",
        "bg.arena",
        (),
        (
            BattleUiPanel("hud:hero", 8, 120, 112, 40, "hud", "hero"),
            BattleUiPanel("battle_result", 62, 32, 196, 116, "result"),
        ),
        (
            BattleUiText("hero", 12, 124, "member_name", "left", "hero"),
            BattleUiText("75/100", 116, 138, "gauge_value", "right", "hero"),
            BattleUiText("27", 240, 72, "value:damage", "center", "mimic"),
            BattleUiText("Victory", 160, 44, "result_headline", "center"),
        ),
        (
            BattleUiGaugeBar("hero", "hp", "HP", 38, 138, 54, 5, .75, 75, 100),
            BattleUiGaugeBar("hero", "limit", "LIMIT", 38, 148, 54, 5, 1.0, 100, 100),
        ),
        (BattleUiIcon("status.poison", 12, 154, "status", "hero", "Poison"),),
        (BattleUiMarker("mimic", 240, 94, True),),
        (),
        (),
    )


def test_renderer_executes_stable_ui_command_order():
    backend = HeadlessBattleUiBackend()
    BattleUiRenderer(backend).render(frame())
    kinds = [x[0] for x in backend.ops]
    assert kinds == [
        "begin",
        "panel", "panel",
        "gauge", "gauge",
        "icon",
        "marker",
        "text", "text", "text", "text",
        "end",
    ]


def test_theme_applies_result_emphasis_damage_and_full_gauge_styles():
    backend = HeadlessBattleUiBackend()
    theme = BattleUiTheme()
    BattleUiRenderer(backend, theme).render(frame())

    result_panel = next(x for x in backend.ops if x[0] == "panel" and x[1] == "battle_result")
    assert result_panel[3]["fill"] == theme.result_fill
    assert result_panel[3]["border"] == theme.result_border

    damage = next(x for x in backend.ops if x[0] == "text" and x[1] == "27")
    headline = next(x for x in backend.ops if x[0] == "text" and x[1] == "Victory")
    assert damage[4]["color"] == theme.damage_text
    assert headline[4]["color"] == theme.text_emphasis
    assert headline[4]["size"] == theme.headline_font_size

    full_gauge = next(x for x in backend.ops if x[0] == "gauge" and x[2] == "limit")
    assert full_gauge[4]["fill"] == theme.gauge_full


def test_theme_roundtrip_preserves_project_owned_visual_policy():
    theme = BattleUiTheme(
        font_size=11,
        headline_font_size=19,
        panel_radius=6,
        text_emphasis=(240, 210, 100, 255),
    )
    assert BattleUiTheme.from_data(theme.to_data()) == theme


def test_renderer_has_no_gameplay_input_or_mutation_surface():
    backend = HeadlessBattleUiBackend()
    renderer = BattleUiRenderer(backend)
    result = renderer.render(frame())
    assert result.scene_id == "battle.reference"
