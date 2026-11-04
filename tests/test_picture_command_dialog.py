"""Picture world commands expose structured operands and a real position preview."""

import pytest

from asteria.assets import AssetRecord
from asteria.editor.model import EditorDocument
from asteria.editor.picture_command_dialog import PictureCommandDialog
from asteria.project import Project


@pytest.fixture(scope="module")
def app():
    widgets = pytest.importorskip("PySide6.QtWidgets")
    return widgets.QApplication.instance() or widgets.QApplication([])


def test_show_picture_dialog_builds_arguments_and_previews_sheet_frame(app, tmp_path):
    from PySide6.QtGui import QColor, QImage

    image = QImage(8, 4, QImage.Format_ARGB32)
    image.fill(QColor("red"))
    for x in range(4, 8):
        for y in range(4):
            image.setPixelColor(x, y, QColor("blue"))
    path = tmp_path / "pictures.png"
    assert image.save(str(path))
    project = Project("Pictures")
    record = project.assets.add(
        AssetRecord.create(kind="texture", source_path="pictures.png", name="Pictures")
    )
    document = EditorDocument(project, file_path=tmp_path / "project.asteria")
    dialog = PictureCommandDialog("SHOW_PICTURE", document=document)
    try:
        dialog.picture_id.setText("boss_intro")
        dialog.asset_id.setText(record.id)
        dialog.x.setValue(120)
        dialog.y.setValue(80)
        dialog.columns.setValue(2)
        dialog.frame.setValue(1)

        args = dialog.result_args()
        frame = dialog.frame_pixmap().toImage()
        assert args["picture_id"] == "boss_intro"
        assert args["asset_id"] == record.id
        assert args["x"] == 120 and args["y"] == 80
        assert args["columns"] == 2 and args["frame"] == 1
        assert QColor(frame.pixelColor(1, 1)) == QColor("blue")
    finally:
        dialog.close()


def test_move_frame_and_erase_dialogs_only_emit_supported_fields(app):
    dialog = PictureCommandDialog(
        "MOVE_PICTURE",
        {"picture_id": "portal", "x": 20, "y": 30, "duration": 1.25},
    )
    try:
        args = dialog.result_args()
        assert set(args) == {
            "picture_id", "x", "y", "scale", "opacity", "tint", "tint_color", "duration",
            "easing", "delay",
        }  # fmt: skip
        assert args["duration"] == 1.25

        dialog.command.setCurrentText("SET_PICTURE_FRAME")
        dialog.frame.setValue(3)
        assert dialog.result_args() == {"picture_id": "portal", "frame": 3}

        dialog.command.setCurrentText("ERASE_PICTURE")
        assert dialog.result_args() == {"picture_id": "portal"}
    finally:
        dialog.close()


def test_the_preview_holds_its_dialog_weakly(app):
    """As the Dialogue preview: a preview keeping its dialog while the dialog held it made a
    cycle that PySide6 6.12 crashed collecting."""
    import gc
    import weakref

    dialog = PictureCommandDialog("SHOW_PICTURE")
    assert dialog.preview.owner is dialog
    assert dialog not in gc.get_referents(dialog.preview.__dict__)
    gone = weakref.ref(dialog)
    dialog.close()
    del dialog
    assert gone() is None  # freed by reference counting, without the cycle collector


def test_colours_are_picked_and_the_rest_chosen_from_lists(app, tmp_path):
    project = Project("Pictures")
    record = project.assets.add(
        AssetRecord.create(kind="texture", source_path="p.png", name="Sunset Sky")
    )
    document = EditorDocument(project, file_path=tmp_path / "project.asteria")
    args = {
        "picture_id": "sky",
        "asset_id": record.id,
        "tint_color": "255, 0, 16",
        "shadow_color": [1, 2, 3],
        "text_color": "not a colour",
        "layer": "screen",  # what this dialog once wrote: the game reads a number
    }
    dialog = PictureCommandDialog("SHOW_PICTURE", args, document=document)
    try:
        assert dialog.asset_id.name.text() == "Sunset Sky"
        assert [key for key, _icon in dialog.asset_id.library.choices()] == [record.id]
        out = dialog.result_args()
        assert (out["tint_color"], out["shadow_color"]) == ("255,0,16", "1,2,3")
        assert out["text_color"] == "not a colour"  # kept until another is picked
        assert out["layer"] == 0 and out["click_event"] == "" and out["font"] == ""
        dialog.text_color.button.set_color("#102030")
        dialog.text_color.button.changed.emit()
        assert dialog.result_args()["text_color"] == "16,32,48"
        dialog.tint_color.tick.setChecked(False)
        assert dialog.result_args()["tint_color"] == ""
        dialog.picture_id.setCurrentIndex(dialog.picture_id.findData(dialog.picture_id.NEW))
        assert dialog.picture_id.text() == "picture"
        dialog.command.setCurrentText("ERASE_PICTURE")
        assert dialog.command.itemText(dialog.command.currentIndex()) == "Erase Picture"
    finally:
        dialog.close()


def test_browse_makes_a_picture_from_anywhere_one_of_the_projects(app, tmp_path):
    from PySide6.QtGui import QColor, QImage

    from asteria.editor.image_tools import PictureLibrary

    outside = tmp_path / "elsewhere"
    outside.mkdir()
    image = QImage(2, 2, QImage.Format_RGB32)
    image.fill(QColor("red"))
    assert image.save(str(outside / "night_sky.png"))
    folder = tmp_path / "game"
    folder.mkdir()
    project = Project("Pictures")
    document = EditorDocument(project, file_path=folder / "project.asteria")
    library = PictureLibrary(document)
    made = library.import_file(outside / "night_sky.png")
    assert library.name_of(made) == "Night Sky"
    assert (folder / "pictures" / "night_sky.png").is_file()
    assert library.import_file(outside / "night_sky.png") == made  # the same file: one picture
    assert [key for key, _icon in library.choices()] == [made]


def _picture_dialog(tmp_path, **args):
    from PySide6.QtGui import QColor, QImage

    image = QImage(8, 8, QImage.Format_ARGB32)
    image.fill(QColor(200, 40, 40))
    for y in range(8):
        image.setPixelColor(0, y, QColor(40, 40, 200))  # a column to see it scroll and wave
    image.setPixelColor(7, 7, QColor(0, 0, 0, 0))
    image.save(str(tmp_path / "pic.png"))
    project = Project("Pictures")
    record = project.assets.add(
        AssetRecord.create(kind="texture", source_path="pic.png", name="Pic")
    )
    document = EditorDocument(project)
    document.file_path = tmp_path / "project.asteria.json"
    return PictureCommandDialog(
        "SHOW_PICTURE", {"picture_id": "a", "asset_id": record.id, **args}, document=document
    )


def test_the_preview_tints_like_the_game_and_keeps_the_see_through(app, tmp_path):
    dialog = _picture_dialog(tmp_path, tint=0.5, tint_color="0,0,255")
    image, is_words = dialog.picture_image()
    assert not is_words
    pixel = image.pixelColor(4, 4)  # colour x 0.5 + tint x 0.5
    assert abs(pixel.red() - 100) <= 2 and abs(pixel.green() - 20) <= 2
    assert abs(pixel.blue() - 147) <= 2
    assert image.pixelColor(7, 7).alpha() == 0
    # no tint colour ticked: white, as the game
    dialog.tint_color.tick.setChecked(False)
    assert dialog.picture_image()[0].pixelColor(4, 4).green() > 140


def test_the_preview_scrolls_waves_and_cycles_as_time_goes_by(app, tmp_path):
    dialog = _picture_dialog(tmp_path)
    assert not dialog.moves()
    dialog.scroll_x.setValue(2)
    assert dialog.moves()
    image = dialog.picture_image(age=1.0)[0]
    assert image.pixelColor(2, 4).blue() > 150 and image.pixelColor(0, 4).blue() < 100
    dialog.scroll_x.setValue(0)
    dialog.wave_amplitude.setValue(2)
    dialog.wave_length.setValue(8)
    waved = dialog.picture_image(age=0.0)[0]
    assert waved.pixelColor(2, 2).blue() > 150  # sin at a quarter of the length: 2 pixels over
    assert waved.pixelColor(0, 0).blue() > 150  # sin at 0: not at all
    dialog.wave_amplitude.setValue(0)
    # a sheet goes on from its frame, round again or stopping at the last
    dialog.columns.setValue(4)
    dialog.frame_rate.setValue(2)
    assert dialog.moves()
    left = dialog.frame_pixmap(age=0.0).toImage().pixelColor(0, 4)
    assert left.blue() > 150  # the first cell starts with the blue column
    assert dialog.frame_pixmap(age=0.5).toImage().pixelColor(0, 4).blue() < 100
    from asteria.editor.picture_preview import cycled_frame

    assert cycled_frame(1, 2, 4, True, 2.0) == 1
    assert cycled_frame(1, 2, 4, False, 2.0) == 3
    assert cycled_frame(1, 0, 4, True, 2.0) == 1


def test_the_preview_draws_words_in_their_colours_and_font(app, tmp_path):
    from PySide6.QtGui import QColor, QImage

    from asteria.editor.menu_layout_authoring import MenuLayoutAuthoringController
    from asteria.presentation.menu_layout import MenuBitmapFont

    dialog = _picture_dialog(tmp_path, text="Hi", text_color="0,255,0", shadow_color="255,0,0")
    image, is_words = dialog.picture_image()
    assert is_words  # words win over the picture, as in the game

    def colors(picture):
        return {
            (c.red() > 128, c.green() > 128, c.blue() > 128)
            for x in range(picture.width())
            for y in range(picture.height())
            for c in [picture.pixelColor(x, y)]
            if c.alpha() > 200
        }

    assert (False, True, False) in colors(image) and (True, False, False) in colors(image)
    dialog.shadow_color.tick.setChecked(False)
    assert (True, False, False) not in colors(dialog.picture_image()[0])
    # a bitmap font: cut from its sheet, in the words' colour
    sheet = QImage(8, 4, QImage.Format_ARGB32)
    sheet.fill(QColor(255, 255, 255))
    sheet.save(str(tmp_path / "font.png"))
    record = dialog.document.project.assets.add(
        AssetRecord.create(kind="texture", source_path="font.png", name="Font")
    )
    font = MenuBitmapFont("mine", image=record.id, cell_width=4, cell_height=4, rows=("Hi",))
    MenuLayoutAuthoringController(dialog.document).set_font(font)
    dialog.font.setText("mine")
    image = dialog.picture_image()[0]
    assert (image.width(), image.height()) == (10, 4)  # two cells, each 4 wide + 1 of spacing
    assert image.pixelColor(1, 1).green() == 255 and image.pixelColor(1, 1).red() == 0


def test_every_field_redraws_the_preview_and_the_blend_adds_light(app, tmp_path):
    from unittest import mock

    dialog = _picture_dialog(tmp_path)
    assert not dialog.adds_light()
    dialog.blend.setText("add")
    assert dialog.adds_light()
    with mock.patch.object(type(dialog.preview), "update") as redraw:
        dialog.tint.setValue(0.5)
        dialog.tint_color.tick.setChecked(True)
        dialog.words.setText("Hello")
        dialog.text_align.setText("center")
        dialog.frame_loop.setChecked(False)
    assert redraw.call_count >= 5
    dialog.preview.resize(400, 300)
    assert not dialog.preview.grab().isNull()
