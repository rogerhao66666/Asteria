"""UI_PLAN_2 V1: the shared foundation of the in-game screen layouts - a screen's own
resolution, animation strips, bitmap fonts drawn by hand (set up in the editor) and the skill
tree's pieces as pictures of the author's own."""

import pytest

from asteria.presentation.library import BattlePresentationLibrary
from asteria.presentation.menu_layout import (
    EMPTY_CELL,
    MenuBitmapFont,
    MenuElement,
    MenuLayout,
    MenuTheme,
    screen_size,
)

RED, BLUE, GREEN = (255, 0, 0), (0, 0, 255), (0, 200, 0)


# --- data ------------------------------------------------------------------------------------
def test_new_element_and_theme_fields_are_written_only_when_set():
    assert MenuElement("frame").to_data() == {"element_id": "frame", "kind": "panel"}
    assert MenuTheme().to_data() == {}
    strip = MenuElement("arrow", "image", frames=4, frame_axis="y", fps=6, bitmap_font="pix")
    data = strip.to_data()
    assert data == {
        "element_id": "arrow",
        "kind": "image",
        "frames": 4,
        "frame_axis": "y",
        "fps": 6.0,
        "bitmap_font": "pix",
    }
    assert MenuElement.from_data(data) == strip
    assert MenuTheme(bitmap_font="pix").to_data() == {"bitmap_font": "pix"}
    with pytest.raises(ValueError):
        MenuElement("x", frame_axis="z")
    with pytest.raises(ValueError):
        MenuElement("x", frames=-1)


def test_a_bitmap_font_lists_its_cells_and_round_trips():
    font = MenuBitmapFont("pix", "ui/font.png", 6, 8, ("AB" + EMPTY_CELL + "C", "ab"))
    assert font.cells() == {"A": (0, 0), "B": (1, 0), "C": (3, 0), "a": (0, 1), "b": (1, 1)}
    data = font.to_data()
    assert data == {
        "font_id": "pix",
        "image": "ui/font.png",
        "cell_width": 6,
        "rows": ["AB⬚C", "ab"],
    }
    assert MenuBitmapFont.from_data(data) == font
    with pytest.raises(ValueError):
        MenuBitmapFont("x", colours="rainbow")
    with pytest.raises(ValueError):
        MenuBitmapFont.from_data({"font_id": "x", "glyphs": 3})


def test_the_library_writes_bitmap_fonts_only_when_there_are_some():
    library = BattlePresentationLibrary()
    assert "bitmap_font" not in library.to_data()["categories"]
    library.set("bitmap_font", "pix", MenuBitmapFont("pix", rows=("AB",)))
    data = library.to_data()
    assert data["categories"]["bitmap_font"] == {"pix": {"font_id": "pix", "rows": ["AB"]}}
    assert BattlePresentationLibrary.from_data(data).get("bitmap_font", "pix").rows == ("AB",)


def test_a_screen_with_its_own_resolution_measures_its_layout_in_it():
    assert screen_size("shop", (960, 540)) == (960, 540)
    assert screen_size("nowhere", (960, 540)) == (960, 540)


# --- drawing ---------------------------------------------------------------------------------
def _glyph_sheet(path, cells=3, cell=(6, 8)):
    """Three white glyphs: a 2-wide bar, a 4-wide bar and a full-cell block."""
    from PIL import Image

    image = Image.new("RGBA", (cell[0] * cells, cell[1]), (0, 0, 0, 0))
    for n, width in enumerate((2, 4, cell[0])):
        for x in range(width):
            for y in range(cell[1]):
                image.putpixel((n * cell[0] + x, y), (255, 255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _font(runtime, **fields):
    path = runtime.resource_root / "ui" / "pix.png"
    _glyph_sheet(path)
    spec = MenuBitmapFont("pix", str(path), 6, 8, ("ABC",), **fields)
    runtime.project.battle_presentation_library.set("bitmap_font", "pix", spec)
    return spec


def test_glyph_widths_are_measured_from_the_drawn_pixels(runtime):
    _font(runtime)
    font = runtime.bitmap_font("pix")
    assert font.widths["A"] == 3 and font.widths["B"] == 5 and font.widths["C"] == 7
    assert font.widths[" "] == 3  # half a cell
    assert font.covers("AB C") and not font.covers("AZ")
    assert runtime.text_size("AB", 16, font="bitmap:pix") == (16, 16)  # scale 2
    _font(runtime, fixed_width=True, widths=(("A", 9),))
    font = runtime.bitmap_font("pix")  # the spec changed: made again
    assert font.widths["A"] == 9 and font.widths["B"] == 7


def test_text_draws_in_the_bitmap_font_and_falls_back_for_what_it_lacks(runtime):
    _font(runtime)
    runtime.screen.fill((0, 0, 0))
    rect = runtime.text("AC", 10, 10, size=8, color=RED, font="bitmap:pix")
    assert rect.topleft == (10, 10) and rect.size == (10, 8)
    assert runtime.screen.get_at((10, 10))[:3] == RED  # A's bar, tinted
    assert runtime.screen.get_at((12, 10))[:3] == (0, 0, 0)  # past A's 2 pixels
    assert runtime.screen.get_at((13, 10))[:3] == RED  # C starts after A's 3
    runtime.screen.fill((0, 0, 0))
    rect = runtime.text("中文", 10, 10, size=20, font="bitmap:pix")  # not in it: the fonts
    from asteria.platform.pygame_battle_ui import cjk_font_path

    if cjk_font_path(runtime.pg) is not None:  # without a CJK system font there is none to use
        assert rect.width > 20
    library = runtime.project.battle_presentation_library
    library.set("menu_theme", "default", MenuTheme(bitmap_font="pix"))
    runtime.screen.fill((0, 0, 0))
    rect = runtime.text("B", 40, 40, size=16, color=BLUE)  # the theme's font, scale 2
    assert rect.size == (10, 16) and runtime.screen.get_at((40, 40))[:3] == BLUE


def test_keep_and_two_tone_fonts_keep_their_own_colours(runtime):
    _font(runtime, colours="keep")
    runtime.screen.fill((0, 0, 0))
    runtime.text("A", 0, 0, size=8, color=RED, font="bitmap:pix")
    assert runtime.screen.get_at((0, 0))[:3] == (255, 255, 255)
    _font(runtime, colours="two_tone")
    runtime.screen.fill((0, 0, 0))
    runtime.text("A", 0, 0, size=8, color=GREEN, font="bitmap:pix")
    assert runtime.screen.get_at((0, 0))[:3] == GREEN


def test_a_strip_shows_the_frame_the_screen_asks_for_or_the_clocks(runtime):
    from PIL import Image

    path = runtime.resource_root / "ui" / "strip.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    strip = Image.new("RGBA", (40, 10))
    for n, colour in enumerate((RED, GREEN, BLUE, (250, 250, 0))):
        for x in range(10):
            for y in range(10):
                strip.putpixel((n * 10 + x, y), (*colour, 255))
    strip.save(path)
    element = MenuElement("extra.arrow", "image", (0, 0, 10, 10), image=str(path), frames=4)
    library = runtime.project.battle_presentation_library
    library.set("menu_layout", "shop", MenuLayout("shop", (element,)))
    canvas = runtime.menu_canvas("shop")
    image = runtime.skin_image(str(path))
    assert canvas.strip_frame(image, element, 2).get_at((0, 0))[:3] == BLUE
    assert canvas.strip_frame(image, element, 0.3).get_at((0, 0))[:3] == GREEN  # 30% in
    assert canvas.strip_frame(image, element).get_at((0, 0))[:3] == RED  # no fps: frame 0
    runtime.screen.fill((0, 0, 0))
    assert canvas.picture("extra.arrow", (100, 100, 10, 10), frame=3)
    assert runtime.screen.get_at((5, 5))[:3] == (250, 250, 0)  # at the layout's place
    small = runtime.pg.Surface((40, 30))
    canvas = runtime.menu_canvas("shop", size=(40, 30), target=small)
    assert canvas.area == (40, 30) and canvas.screen is small
    canvas.picture("extra.arrow", (0, 0, 10, 10), frame=1)
    assert small.get_at((5, 5))[:3] == GREEN  # drawn on the screen's own small surface


def test_the_skill_tree_takes_the_authors_node_frames_and_line_colours(runtime):
    from asteria.runtime.skill_tree_screen import SkillTreeScreen

    screen = SkillTreeScreen(runtime)
    if screen.graph() is None:
        pytest.skip("the reference project has no skill tree")
    runtime.screen.fill((0, 0, 0))
    screen.draw()
    plain = runtime.pg.image.tobytes(runtime.screen, "RGB")
    screen.draw()
    assert runtime.pg.image.tobytes(runtime.screen, "RGB") == plain  # the same every time
    graph = screen.graph()
    node = graph.nodes[0]
    status = screen.status(graph, node)
    layout = MenuLayout(
        "skill_tree",
        (
            MenuElement(f"node_{status}", "image", fill=(255, 0, 255, 255)),
            MenuElement("link_met", "panel", color=GREEN, size=5),
        ),
    )
    runtime.project.battle_presentation_library.set("menu_layout", "skill_tree", layout)
    runtime.screen.fill((0, 0, 0))
    screen.draw()
    x, y = (int(v) for v in screen.node_point(graph, node.node_id))
    assert runtime.screen.get_at((x - 40, y + 15))[:3] == (255, 0, 255)


def test_a_legacy_font_json_becomes_an_editable_font():
    from asteria.graphics.bitmap_font import spec_from_legacy

    data = {"cell": 8, "columns": 4, "line": 10, "widths": [3, 4, 5, 6, 7],
            "chars": {"A": 0, "B": 1, "D": 3, "E": 4}}  # fmt: skip
    spec = spec_from_legacy(data, "fonts/old.png", "old")
    assert spec.rows == ("AB" + EMPTY_CELL + "D", "E")
    assert dict(spec.widths) == {"A": 3, "B": 4, "D": 6, "E": 7}
    assert spec.colours == "two_tone" and spec.line == 10 and spec.scale == 1
    assert spec.cells() == {"A": (0, 0), "B": (1, 0), "D": (3, 0), "E": (0, 1)}
