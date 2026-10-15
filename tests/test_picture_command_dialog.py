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
        assert set(args) == {"picture_id", "x", "y", "scale", "opacity", "duration", "easing"}
        assert args["duration"] == 1.25

        dialog.command.setCurrentText("SET_PICTURE_FRAME")
        dialog.frame.setValue(3)
        assert dialog.result_args() == {"picture_id": "portal", "frame": 3}

        dialog.command.setCurrentText("ERASE_PICTURE")
        assert dialog.result_args() == {"picture_id": "portal"}
    finally:
        dialog.close()
