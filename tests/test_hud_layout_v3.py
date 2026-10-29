"""UI_PLAN_2 V3: the action RPG HUD as layout data (``hud_action``): orbs from the author's
pictures or as bars, slots, keycap, cooldown strip, statuses, the bars of other resources and
the theme's colour per resource - and without a layout, the very same pixels as before."""

from pathlib import Path

import pytest

from asteria.presentation.menu_layout import MenuElement, MenuLayout, MenuTheme

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "arpg_demo"
MAGENTA, CYAN, GREEN = (255, 0, 255), (0, 255, 255), (0, 200, 0)


@pytest.fixture
def demo(monkeypatch):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    rt = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT, width=960, height=540
    )
    rt.open()
    rt._ui_mode = "field"
    rt.game.set_classes("", ["warrior"])
    for _ in range(3):
        rt._frame([], 1 / 60)
    yield rt
    rt.close()


def _hud(rt):
    """The HUD alone on black (the world is not drawn): its pixels."""
    rt.screen.fill((0, 0, 0))
    hud = rt.action_hud
    hud.bottom.hint_left = hud.bottom.HINT_SECONDS
    rt._menu_boxes = {}
    hud.draw_overlay(rt)
    return rt.pg.image.tobytes(rt.screen, "RGB")


def _layout(rt, *elements, theme=None):
    library = rt.project.battle_presentation_library
    library.set("menu_layout", "hud_action", MenuLayout("hud_action", tuple(elements)))
    if theme is not None:
        library.set("menu_theme", "default", theme)


def _picture(root, name, colour, size=(20, 20)):
    from PIL import Image

    path = root / "ui_test" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (*colour, 255)).save(path)
    return str(path)


def test_without_a_layout_the_hud_draws_as_before_and_says_where_its_pieces_are(demo):
    first = _hud(demo)
    assert _hud(demo) == first
    boxes = demo._menu_boxes["hud_action"]
    assert {"orb_life", "orb_second", "plate", "slot", "slot_main", "keycap", "exp"} <= set(boxes)
    # 960 x 540: the life orb's square (radius 42) sits at the bottom left
    assert boxes["orb_life"] == (18, 438, 84, 84)


def test_the_orb_moves_takes_the_authors_pictures_or_turns_into_a_bar(demo, tmp_path):
    empty = _picture(tmp_path, "empty.png", (40, 40, 40))
    fill = _picture(tmp_path, "fill.png", MAGENTA)
    _layout(
        demo,
        MenuElement("orb_life", "gauge", rect=(100, 100, 80, 80)),
        MenuElement("orb_life_empty", "image", image=empty),
        MenuElement("orb_life_fill", "image", image=fill),
    )
    state = demo.game.combat.state(demo.game.player)
    life = demo.game.player.get(__import__("asteria.runtime.combat", fromlist=["x"])
                                .CombatantComponent).life_resource  # fmt: skip
    pool = state.resources.get(life)
    state.resources.set_current(life, pool.maximum / 2)
    _hud(demo)
    assert demo.screen.get_at((140, 170))[:3] == MAGENTA  # the liquid: the lower half
    assert demo.screen.get_at((104, 104))[:3] == (40, 40, 40)  # empty above it
    assert demo._menu_boxes["hud_action"]["orb_life"] == (100, 100, 80, 80)
    _layout(
        demo,
        MenuElement("orb_life", "gauge", visible=False),
        MenuElement("life_bar", "gauge", rect=(20, 20, 200, 16), color=GREEN),
    )
    _hud(demo)
    assert demo.screen.get_at((40, 28))[:3] == GREEN  # half of the bar is filled
    assert demo.screen.get_at((210, 28))[:3] != GREEN
    assert demo.screen.get_at((60, 480))[:3] == (0, 0, 0)  # no orb


def test_slots_keycaps_and_the_plate_take_the_layouts_look(demo, tmp_path):
    slot = _picture(tmp_path, "slot.png", CYAN)
    _layout(
        demo,
        MenuElement("plate", "panel", rect=(200, 20, 600, 90), fill=(30, 0, 30, 255)),
        MenuElement("slot", "image", image=slot, cell=40, gap=12),
        MenuElement("keycap", "image", fill=(250, 250, 0, 255), color=(0, 0, 0)),
    )
    _hud(demo)
    boxes = demo._menu_boxes["hud_action"]
    assert boxes["plate"] == (200, 20, 600, 90)
    sx, sy, sw, sh = boxes["slot"]
    assert (sw, sh) == (40, 40) and 200 < sx < 800 and 20 < sy < 110  # moved with the plate
    assert demo.screen.get_at((sx + 20, sy + 30))[:3] == CYAN
    kx, ky, _kw, _kh = boxes["keycap"]
    assert demo.screen.get_at((kx + 2, ky + 8))[:3] == (250, 250, 0)


def test_a_cooldown_strip_shows_the_frame_for_the_time_left(demo, tmp_path):
    from PIL import Image

    path = tmp_path / "ui_test" / "cool.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    strip = Image.new("RGBA", (40, 10))
    for n, colour in enumerate((MAGENTA, CYAN, GREEN, (250, 250, 0))):
        for x in range(10):
            for y in range(10):
                strip.putpixel((n * 10 + x, y), (*colour, 255))
    strip.save(path)
    _layout(demo, MenuElement("cooldown", "image", image=str(path), frames=4))
    canvas = demo.menu_canvas("hud_action")
    rect = demo.pg.Rect(300, 300, 40, 40)
    demo.screen.fill((0, 0, 0))
    assert canvas.picture("cooldown", rect, 0.6, repeated=True, pictures_only=True)
    assert demo.screen.get_at((320, 320))[:3] == GREEN  # 60% done: the third frame


def test_the_theme_colours_a_resource_over_the_guess_from_its_name(demo):
    from asteria.runtime.hud_bottom import resource_color

    assert resource_color("mana") == ((18, 38, 120), (66, 128, 245))
    theme = MenuTheme(resource_colors={"mana": (200, 100, 0)})
    assert resource_color("mana", theme=theme) == ((90, 45, 0), (200, 100, 0))
    assert theme.to_data() == {"resource_colors": {"mana": [200, 100, 0]}}
    assert MenuTheme.from_data(theme.to_data()) == theme


def test_statuses_target_banner_and_fell_follow_the_layout(demo):
    game = demo.game
    for state_id in ("healing", "burning"):
        assert game.combat.apply_state(game.player, state_id)
    _layout(
        demo,
        MenuElement("statuses", "grid", rect=(500, 100, 300, 50), cell=50, gap=4),
        MenuElement("status_debuff", "image", fill=(250, 0, 0, 255)),
        MenuElement("fell", "panel", fill=(0, 0, 90, 255)),
    )
    game.player_down = 2.0
    try:
        _hud(demo)
    finally:
        game.player_down = 0.0
    boxes = demo._menu_boxes["hud_action"]
    assert boxes["statuses"] == (500, 100, 300, 50)
    assert demo.screen.get_at((5, 5))[:3] == (0, 0, 90)  # the author's fell tint
