"""UI_PLAN_2 V2: the message window as layout data - the ordinary window through the
``dialogue`` / ``dialogue_choice`` layouts, the picture window as project data (no longer
manifest-only) with the editor's one-click conversion drawing the very same pixels."""

import json

import pytest

from asteria.events.dialogue import ChoiceRequest, DialogueChoice, DialogueLine, DialogueRequest
from asteria.presentation.dialogue_window import DialogueWindowStyle
from asteria.presentation.menu_layout import MenuElement, MenuLayout

GOLD = (255, 200, 0)


def _layout(runtime, screen_id, *elements):
    library = runtime.project.battle_presentation_library
    library.set("menu_layout", screen_id, MenuLayout(screen_id, tuple(elements)))


def _draw(runtime, request):
    from asteria.runtime.dialogue_screen import draw_message_window

    runtime.screen.fill((0, 0, 0))
    draw_message_window(runtime, request, getattr(request, "line", None))
    return runtime.pg.image.tobytes(runtime.screen, "RGB")


# --- data ------------------------------------------------------------------------------------
def test_the_picture_window_record_is_written_only_when_it_differs():
    assert DialogueWindowStyle().to_data() == {}
    style = DialogueWindowStyle(window="ui/win.png", font="pix", speeds=(20, 40, 120))
    data = style.to_data()
    assert data == {"window": "ui/win.png", "font": "pix", "speeds": [20.0, 40.0, 120.0]}
    assert DialogueWindowStyle.from_data(data) == style
    settings = style.settings()
    assert settings["font_id"] == "pix" and settings["window"] == "ui/win.png"
    assert settings["colours"] == [[98, 98, 98], [213, 213, 205]]
    assert "arrow" not in settings  # unset: the drawing code's own default
    assert DialogueWindowStyle(window="w.png", enabled=False).settings() is None
    assert DialogueWindowStyle().settings() is None  # no picture: the ordinary window
    with pytest.raises(ValueError):
        DialogueWindowStyle(line_height=0)
    with pytest.raises(ValueError):
        DialogueWindowStyle.from_data({"windw": "x"})


def test_a_manifest_window_reads_into_the_record():
    dialogue = {
        "window": "w.png",
        "text_area": [8, 4, 200, 30],
        "line_height": 14,
        "colours": [[1, 2, 3], [4, 5, 6]],
        "speeds": [10, 20],
        "arrow": "a.png",
        "choice_frame": "f.png",
        "choice_right": 230,
        "cancel_picks_last": True,
    }
    style = DialogueWindowStyle.from_manifest(dialogue, "pix", "ok.ogg")
    assert style.text_area == (8, 4, 200, 30) and style.line_height == 14
    assert style.letter_color == (1, 2, 3) and style.shadow_color == (4, 5, 6)
    assert style.speeds == (10.0, 20.0) and style.choice_right == 230
    assert style.choice_bottom is None and style.cancel_picks_last
    assert style.font == "pix" and style.confirm_sound == "ok.ogg"


# --- the ordinary window ---------------------------------------------------------------------
LINE = DialogueRequest(DialogueLine("Hello there", "Hana"))


def test_without_a_layout_the_window_is_the_engines(runtime):
    plain = _draw(runtime, LINE)
    canvas_boxes = runtime.__dict__.setdefault("_menu_boxes", {})
    assert _draw(runtime, LINE) == plain
    assert {"window", "speaker", "text", "continue"} <= set(canvas_boxes["dialogue"])
    # 960 x 540: the window is (60, 310, 840, 130), drawn in the engine's panel
    assert runtime.screen.get_at((300, 320))[:3] != (0, 0, 0)


def test_the_layout_moves_the_window_and_styles_its_pieces(runtime):
    _layout(
        runtime,
        "dialogue",
        MenuElement("window", rect=(100, 40, 500, 160), fill=(20, 60, 20, 255), border=GOLD),
        MenuElement("continue", "hint", visible=False),
        MenuElement("text", "text", rect=(130, 100, 400, 80), size=30, color=GOLD),
    )
    calls = []
    original = runtime.text

    def text(value, x, y, **kw):
        calls.append((str(value), int(x), int(y), kw.get("size"), kw.get("color")))
        return original(value, x, y, **kw)

    runtime.text = text
    _draw(runtime, LINE)
    assert runtime.screen.get_at((300, 190))[:3] == (20, 60, 20)  # the moved window
    assert ("Hana", 124, 52, 24, (255, 220, 124)) in calls  # the speaker follows it
    assert ("Hello there", 130, 100, 30, GOLD) in calls  # the line in its own text area
    assert not any(c[0].startswith("Enter") for c in calls)  # continue words hidden


def test_letters_are_typed_at_the_layouts_speed(runtime, monkeypatch):
    _layout(runtime, "dialogue", MenuElement("text", "text", fps=10))
    clock = {"now": 1000}
    monkeypatch.setattr(runtime.pg.time, "get_ticks", lambda: clock["now"])
    shown = []
    original = runtime.text

    def text(value, x, y, **kw):
        shown.append(str(value))
        return original(value, x, y, **kw)

    runtime.text = text
    _draw(runtime, LINE)
    clock["now"] = 1500  # half a second: five letters
    shown.clear()
    _draw(runtime, LINE)
    assert "Hello" in shown and "Hello there" not in shown
    clock["now"] = 5000
    shown.clear()
    _draw(runtime, LINE)
    assert "Hello there" in shown


def test_the_choice_layout_sets_columns_rows_and_the_chosen_frame(runtime):
    request = ChoiceRequest("Which?", tuple(DialogueChoice(w, n) for n, w in
                                            enumerate(("One", "Two", "Three"))))  # fmt: skip
    calls = []
    original = runtime.text

    def text(value, x, y, **kw):
        calls.append((str(value), int(x), int(y)))
        return original(value, x, y, **kw)

    runtime.text = text
    _draw(runtime, request)
    assert ("> 1. One", 84, 356) in calls and ("   2. Two", 354, 356) in calls
    _layout(
        runtime,
        "dialogue_choice",
        MenuElement("choices", "list", columns=1, row_height=40, selection_fill=GOLD),
    )
    calls.clear()
    _draw(runtime, request)
    assert ("   1. One", 84, 356) in calls  # the frame marks it, not the "> "
    assert ("   2. Two", 84, 396) in calls  # one column, 40 a row
    assert runtime.screen.get_at((80, 360))[:3] == GOLD


# --- the picture window ----------------------------------------------------------------------
def _legacy_files(root):
    """A 240 x 48 window, a two-tone font (A, B, space) and a manifest naming them."""
    from PIL import Image

    (root / "ui").mkdir(exist_ok=True)
    Image.new("RGBA", (240, 48), (250, 250, 250, 255)).save(root / "ui" / "window.png")
    sheet = Image.new("RGBA", (32, 8), (0, 0, 0, 0))
    for x in range(5):
        for y in range(7):
            sheet.putpixel((x, y), (255, 255, 255, 255))  # A: a block
            sheet.putpixel((8 + x, y), (255, 255, 255, 255) if x % 2 else (0, 0, 0, 0))
        sheet.putpixel((x + 1, 7), (128, 128, 128, 255))  # A's shadow
    sheet.save(root / "ui" / "font.png")
    font = {"image": "font.png", "cell": 8, "columns": 4, "widths": [6, 6, 4],
            "chars": {"A": 0, "B": 1, " ": 2}}  # fmt: skip
    (root / "ui" / "font.json").write_text(json.dumps(font), encoding="utf-8")
    path = root / "playable_test_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["dialogue"] = {"window": "ui/window.png", "font": "ui/font.json", "speed": 0,
                            "text_area": [12, 10, 200, 30], "line_height": 12}  # fmt: skip
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def test_the_converted_picture_window_draws_the_manifests_pixels(runtime, document_for):
    manifest = _legacy_files(runtime.resource_root)
    runtime.manifest = manifest
    line = DialogueRequest(DialogueLine("AB BA", "Hana"))

    def picture():
        runtime.__dict__.pop("_dialogue_window_cache", None)
        runtime.screen.fill((0, 0, 0))
        runtime._draw_dialogue_window(line.line)
        return runtime.pg.image.tobytes(runtime.screen, "RGB")

    from_manifest = picture()
    assert runtime.screen.get_at((480, 530))[:3] == (250, 250, 250)  # the window, scaled
    document = document_for(runtime.project, runtime.resource_root)
    from asteria.editor.menu_layout_authoring import MenuLayoutAuthoringController

    controller = MenuLayoutAuthoringController(document)
    style = controller.import_dialogue_manifest(runtime.resource_root)
    assert style.font == "dialogue" and controller.font("dialogue").colours == "two_tone"
    runtime.manifest = {**manifest, "dialogue": {}}  # the manifest no longer has it
    assert runtime.dialogue_settings()["font_id"] == "dialogue"
    assert picture() == from_manifest  # the project data draws the very same pixels
    document.undo()
    document.undo()
    assert runtime.dialogue_settings() == {}


@pytest.fixture
def document_for():
    def make(project, root):
        from asteria.editor import EditorDocument

        document = EditorDocument()
        document.set_project(project, file_path=root / "project.asteria.json")
        return document

    return make
