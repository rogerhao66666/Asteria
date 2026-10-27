"""Menu screen layouts (U2): the model, drawing through a layout, the editor's controller and
the off-screen preview.

A screen with no layout draws exactly as before; a layout moves, resizes, recolours, reskins or
hides one element and adds the author's own; the editor changes layouts one undo step at a
time; the preview opens every screen the way the game opens it.
"""

import sys
from pathlib import Path

import pytest

from asteria.presentation.menu_layout import (
    SCREEN_IDS,
    MenuElement,
    MenuLayout,
    MenuSlotPlace,
    MenuTheme,
    anchored_rect,
    resolve_rect,
    screen_spec,
)

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))


def test_a_layout_and_a_theme_go_to_data_and_back():
    layout = MenuLayout(
        "equipment",
        elements=(
            MenuElement(
                "doll",
                "doll",
                rect=(40, 96, 392, 524),
                image="ui/doll.png",
                slots=(MenuSlotPlace("head", (56, 28, 64, 64)),),
            ),  # fmt: skip
            MenuElement(
                "extra.note",
                "text",
                rect=(10, 10, 200, 30),
                anchor="bottomright",
                text="key:equipment.title|Equipment",
                layer=-1,
            ),  # fmt: skip
        ),
        background_color=(10, 20, 30),
        dim=120,
        music="audio/menu.ogg",
    )
    assert MenuLayout.from_data(layout.to_data()) == layout
    assert layout.to_data()["elements"][0] == {
        "element_id": "doll",
        "kind": "doll",
        "rect": [40, 96, 392, 524],
        "image": "ui/doll.png",
        "slots": [{"slot_id": "head", "rect": [56, 28, 64, 64]}],
    }  # only what differs from an empty element
    theme = MenuTheme(font_latin="ui/font.ttf", text_color=(250, 240, 220),
                      sounds=(("move", "audio/tick.ogg"),))  # fmt: skip
    assert MenuTheme.from_data(theme.to_data()) == theme
    assert theme.sound("move") == "audio/tick.ogg" and theme.sound("buy") == ""


def test_an_anchored_rect_is_measured_from_its_corner():
    size = (1280, 720)
    for anchor in ("topleft", "center", "bottomright", "right"):
        rect = anchored_rect((100, 50, 200, 80), anchor, size)
        assert resolve_rect(rect, anchor, size) == (100, 50, 200, 80)
    # the rect's corner from the screen's: flush with the bottom right is (-w, -h)
    assert anchored_rect((1080, 640, 200, 80), "bottomright", size) == (-200, -80, 200, 80)


def test_every_screen_has_a_spec_with_named_elements():
    for screen_id in SCREEN_IDS:
        spec = screen_spec(screen_id)
        ids = [e[0] for e in spec.elements]
        assert ids and len(ids) == len(set(ids)), screen_id
    with pytest.raises(ValueError):
        MenuElement("x", "nonsense")


@pytest.fixture
def host(monkeypatch):
    import real_window

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    if not real_window.enabled():
        monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
        monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    project.battle_presentation_library._records["menu_layout"].clear()  # the engine's look
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=1280, height=720
    )
    runtime.open()
    runtime._menu_boxes = {}
    yield runtime
    runtime.close()


def _draw(host, screen_id):
    from asteria.runtime.menu_preview import open_menu_screen

    host._ui_mode = "field"
    open_menu_screen(host, screen_id)
    for _ in range(2):
        host._frame([], 0.0)
    return host.pg.image.tobytes(host.capture(), "RGB"), dict(host._menu_boxes[screen_id])


def _set(host, layout):
    host.project.battle_presentation_library.set("menu_layout", layout.screen_id, layout)


def test_an_empty_layout_draws_the_screen_as_before(host):
    before, boxes = _draw(host, "pause")
    _set(host, MenuLayout("pause"))
    after, again = _draw(host, "pause")
    assert after == before and again == boxes


def test_a_layout_moves_hides_and_adds_elements(host):
    _pixels, boxes = _draw(host, "pause")
    x, y, w, h = boxes["frame"]
    _set(
        host,
        MenuLayout(
            "pause",
            elements=(
                MenuElement("frame", "panel", rect=(x + 100, y + 20, w, h), fill=(80, 20, 20)),
                MenuElement("title", "text", visible=False),
                MenuElement("extra.banner", "panel", rect=(0, 0, 300, 40), fill=(0, 90, 0)),
            ),
        ),
    )
    pixels, moved = _draw(host, "pause")
    assert moved["frame"] == (x + 100, y + 20, w, h)
    assert "title" not in moved  # hidden: not drawn
    assert moved["extra.banner"] == (0, 0, 300, 40)
    assert host.capture().get_at((150, 20))[:3] == (0, 90, 0)


def test_the_shop_draws_through_its_layout(host):
    _pixels, boxes = _draw(host, "shop")
    rows = boxes["rows"]
    _set(host, MenuLayout("shop", elements=(MenuElement("rows", "list", rect=(600, 200, 500, 300),
                                                        row_height=48),)))  # fmt: skip
    _pixels, moved = _draw(host, "shop")
    assert moved["rows"] == (600, 200, 500, 300) != rows


def test_the_editor_changes_a_layout_one_undo_step_at_a_time():
    from asteria.editor import EditorDocument
    from asteria.editor.menu_layout_authoring import MenuLayoutAuthoringController
    from asteria.editor.storage import load_document

    document = EditorDocument()
    load_document(document, str(DEMO / "project.asteria.json"))
    controller = MenuLayoutAuthoringController(document)
    assert controller.layout("pause") is None
    controller.change("pause", "frame", rect=(10, 10, 400, 300))
    assert controller.layout("pause").element("frame").rect == (10, 10, 400, 300)
    extra = controller.add_element("pause", "text", rect=(0, 0, 100, 30))
    assert extra == "extra.text" and extra in controller.element_ids("pause")
    assert controller.add_element("pause", "text") == "extra.text_2"
    document.undo()
    document.undo()
    assert controller.element_ids("pause") == [e[0] for e in screen_spec("pause").elements]
    document.undo()
    assert controller.layout("pause") is None  # nothing left: the engine's layout
    controller.change("pause", "title", color=(255, 0, 0))
    controller.copy_from("game_over", "pause")
    assert controller.layout("game_over").element("title").color == (255, 0, 0)
    controller.reset("game_over")
    assert controller.layout("game_over") is None
    controller.change_theme(text_color=(1, 2, 3))
    assert controller.theme().text_color == (1, 2, 3)
    document.undo()
    assert controller.theme() is None
    customised = {s for s, _t, c in controller.screens() if c}
    assert "pause" in customised and "equipment" in customised  # the demo's doll


def test_the_preview_draws_every_screen_and_where_its_elements_are(monkeypatch):
    from asteria.editor import EditorDocument
    from asteria.editor.storage import load_document
    from asteria.runtime.menu_preview import MenuPreview

    monkeypatch.setenv("ASTERIA_MUTE", "1")
    document = EditorDocument()
    load_document(document, str(DEMO / "project.asteria.json"))
    preview = MenuPreview(document.project, DEMO)
    try:
        for screen_id in SCREEN_IDS:
            try:
                surface, boxes = preview.render(
                    screen_id, "zh-TW" if screen_id == "shop" else None
                )
            except KeyError:  # a screen the demo has no use for (the action RPG HUD)
                assert screen_spec(screen_id).group == "game", screen_id
                continue
            assert surface.get_size() == (1280, 720)
            assert boxes, screen_id
        _surface, boxes = preview.render("equipment")
        assert boxes["doll"] == (40, 96, 392, 524)  # the demo's Lucifer doll
    finally:
        preview.close()


def test_the_layout_page_outlines_moves_and_edits_elements(monkeypatch):
    """Presentation ▸ Menu Screens ▸ Layout: the screen drawn with its outlines, a drag moves
    an element, the inspector's fields change it, Ctrl+Z puts it back."""
    monkeypatch.setenv("ASTERIA_MUTE", "1")
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.menu_layout_widget import MenuLayoutWorkspace
    from asteria.editor.storage import load_document

    QApplication.instance() or QApplication([])
    document = EditorDocument()
    load_document(document, str(DEMO / "project.asteria.json"))
    page = MenuLayoutWorkspace(document)
    try:
        page.screen_id = "pause"
        page.rebuild()
        assert not page.boxes  # hidden: nothing drawn yet
        page.show()
        # and a layout per workstation, quest board, recruiting office and gacha banner, and
        # the "During play" heading
        assert page.screen_list.count() == len(SCREEN_IDS) + 5 + 1
        assert set(page.canvas.boxes) >= {"frame", "options", "title"}
        frame = page.boxes["frame"]
        page.pick("frame")
        assert page.inspector.engine_place.isChecked()
        assert (page.inspector.x.value(), page.inspector.y.value()) == frame[:2]
        page._moved("frame", (frame[0] + 40, frame[1], frame[2], frame[3]))
        assert page.boxes["frame"][0] == frame[0] + 40
        page.inspector.font_size.setValue(30)
        page._inspected()
        assert page.controller.element("pause", "frame").size == 30
        document.undo()
        document.undo()
        assert page.controller.layout("pause") is None
        page.screen_id = "equipment"
        page.rebuild()
        page.pick("doll")
        assert page.inspector.form.isRowVisible(page.inspector.slots)
        assert len(page.inspector.slots.places()) == 15  # the demo doll's places (D92: 6 carried)
    finally:
        page.close()
