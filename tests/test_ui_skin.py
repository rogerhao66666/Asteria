"""UI skin: nine-patch pictures for panels and buttons, a font, all project data."""

import dataclasses

import pytest

from asteria.presentation import BattleUiLayoutProfile
from asteria.presentation.battle_ui_renderer import BattleUiRenderer, BattleUiTheme
from asteria.presentation.ui_skin import NinePatch, draw_nine_patch, skin_for


def _pg():
    pg = pytest.importorskip("pygame")
    pg.init()
    return pg


def test_the_nine_patch_keeps_corners_and_stretches_the_rest():
    pg = _pg()
    image = pg.Surface((6, 6), pg.SRCALPHA)
    colors = {
        (0, 0): (255, 0, 0),
        (5, 0): (0, 255, 0),
        (0, 5): (0, 0, 255),
        (5, 5): (255, 255, 0),
    }
    image.fill((40, 40, 40, 255))
    for xy, color in colors.items():
        image.set_at(xy, (*color, 255))
    for x in range(1, 5):  # the stretchy top edge
        image.set_at((x, 0), (200, 200, 200, 255))
    target = pg.Surface((30, 20), pg.SRCALPHA)
    draw_nine_patch(pg, target, image, (0, 0, 30, 20), NinePatch("x", 1, 1, 1, 1))
    assert target.get_at((0, 0))[:3] == (255, 0, 0)
    assert target.get_at((29, 0))[:3] == (0, 255, 0)
    assert target.get_at((0, 19))[:3] == (0, 0, 255)
    assert target.get_at((29, 19))[:3] == (255, 255, 0)
    assert target.get_at((15, 0))[:3] == (200, 200, 200)  # the edge reaches across the width
    assert target.get_at((15, 10))[:3] == (40, 40, 40)  # and the middle fills the rest
    scaled = pg.Surface((30, 20), pg.SRCALPHA)
    draw_nine_patch(pg, scaled, image, (0, 0, 30, 20), NinePatch("x", 1, 1, 1, 1, scale=3.0))
    assert scaled.get_at((2, 2))[:3] == (255, 0, 0)  # a corner is 3 px when drawn at 3x


def test_skins_are_picked_by_role_pattern_and_round_trip_in_the_theme():
    frame, plain = NinePatch("ui.frame", 3, 3, 3, 3, 2.0), NinePatch("ui.plain")
    theme = BattleUiTheme(
        panel_skins=(("hud:*", frame), ("button:selected", plain)),
        font_asset_id="ui.font",
        font_scale=1.5,
    )
    assert theme.panel_skin("hud:side") == frame and theme.panel_skin("button:selected") == plain
    assert theme.panel_skin("result") is None
    again = BattleUiTheme.from_data(theme.to_data())
    assert again == theme
    plain_data = BattleUiTheme().to_data()
    assert "panel_skins" not in plain_data and "font_asset_id" not in plain_data
    assert skin_for((("a*", frame),), "b") is None
    with pytest.raises(ValueError):
        NinePatch("")


def test_the_renderer_hands_a_matching_skin_to_the_backend():
    from asteria.presentation.battle_ui import BattleUiFrame, BattleUiPanel
    from asteria.presentation.battle_ui_renderer import HeadlessBattleUiBackend

    skin = NinePatch("ui.frame")
    theme = BattleUiTheme(panel_skins=(("hud:*", skin),))
    frame = BattleUiFrame(
        "s",
        "",
        (),
        (BattleUiPanel("a", 0, 0, 10, 10, "hud:side"), BattleUiPanel("b", 0, 0, 10, 10, "result")),
        (),
        (),
        (),
        (),
        (),
        (),
    )
    backend = HeadlessBattleUiBackend()
    BattleUiRenderer(backend, theme).render(frame)
    panels = [op for op in backend.ops if op[0] == "panel"]
    assert panels[0][3]["skin"] == skin and "skin" not in panels[1][3]


def test_row_buttons_give_every_menu_row_a_panel():
    layout = BattleUiLayoutProfile(virtual_width=320, virtual_height=180)
    assert layout.row_buttons is False
    on = dataclasses.replace(layout, row_buttons=True)
    assert on.row_buttons
    theme = BattleUiTheme()
    assert theme.panel_style("button")[0][3] == 0  # invisible until a skin or highlight asks
    assert theme.panel_style("button:selected")[0][3] > 0


def test_the_editor_keeps_skin_fields_when_a_theme_is_edited():
    from pathlib import Path

    from asteria.editor import EditorDocument
    from asteria.editor.integrated_authoring import IntegratedAuthoringControllers
    from asteria.project import Project

    root = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    library = project.battle_presentation_library
    key = library.ids("ui_theme")[0]
    theme = library.require("ui_theme", key)
    skinned = dataclasses.replace(
        theme,
        panel_skins=(("hud:*", NinePatch("ui.frame", 3, 3, 3, 3, 2.0)),),
        font_asset_id="ui.font",
        font_scale=1.25,
    )
    library.set("ui_theme", key, skinned)
    adapter = next(
        a
        for group in ("presentation_categories",)
        for a in getattr(IntegratedAuthoringControllers(EditorDocument(project)), group)()
        if a.category_id == "ui_theme"
    )
    record = adapter.get(key)
    again = adapter.decode(adapter.encode(record))
    assert again == record == skinned
    adapter.edit(key, again)
    assert adapter.get(key) == skinned
