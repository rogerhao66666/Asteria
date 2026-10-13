"""AST-11: the asset pipeline's safe auto-fixes and atlas packing are reachable from the editor's
Asset list -
preview before / after, a backup of the original, confirmation for fixes that lose pixels, and an
atlas PNG
with a JSON of named regions."""

import json

import pytest
from PIL import Image

from asteria.assets import AssetRecord
from asteria.core import Scene
from asteria.project import Project


def _image(path, size, box, alpha=255):
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    for x in range(box[0], box[2]):
        for y in range(box[1], box[3]):
            image.putpixel((x, y), (200, 40, 40, alpha))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


@pytest.fixture
def window(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.storage import save_document

    QApplication.instance() or QApplication([])
    _image(tmp_path / "assets" / "hero.png", (16, 16), (4, 4, 10, 12))
    _image(tmp_path / "assets" / "soft.png", (8, 8), (0, 0, 8, 8), alpha=100)
    _image(tmp_path / "assets" / "coin.png", (6, 6), (1, 1, 5, 5))
    project = Project("Game")
    project.add_scene(Scene("Map"))
    for name in ("hero", "soft", "coin"):
        project.assets.add(AssetRecord.create(kind="texture", source_path=f"assets/{name}.png"))
    editor = AsteriaEditorWindow(project)
    save_document(editor.document, tmp_path / "game.asteria.json")
    editor.refresh_asset_list()
    yield editor
    editor.close()


def _select(window, *names):
    for i in range(window.asset_list.count()):
        item = window.asset_list.item(i)
        item.setSelected(any(f"{n}.png" in item.text() for n in names))


def test_auto_fix_previews_then_crops_and_keeps_the_original(window, tmp_path):
    _select(window, "hero")
    seen = {}

    def hook(dialog):
        dialog.fix.setCurrentIndex(dialog.fix.findData("crop_transparent_border"))
        seen["before"] = dialog.before.pixmap().width()
        seen["after"] = dialog.after.pixmap().width()
        seen["text"] = dialog.report.text()
        dialog.apply()

    report = window.auto_fix_selected_image(dialog_hook=hook)
    assert report is not None and report.after_size == (6, 8)
    assert seen["before"] > 0 and seen["after"] > 0 and "16x16 → 6x8" in seen["text"]
    with Image.open(tmp_path / "assets" / "hero.png") as fixed:
        assert fixed.size == (6, 8)
    with Image.open(tmp_path / "assets" / "hero.bak.png") as original:
        assert original.size == (16, 16)


def test_a_fix_that_loses_pixels_needs_confirmation(window, tmp_path):
    _select(window, "soft")

    def refuse(dialog):
        dialog.fix.setCurrentIndex(dialog.fix.findData("normalize_alpha"))
        assert dialog.preview_report.destructive
        assert dialog.apply(confirm=False) is None

    assert window.auto_fix_selected_image(dialog_hook=refuse) is None
    assert not (tmp_path / "assets" / "soft.bak.png").exists()

    def accept(dialog):
        dialog.fix.setCurrentIndex(dialog.fix.findData("normalize_alpha"))
        dialog.apply(confirm=True)

    assert window.auto_fix_selected_image(dialog_hook=accept) is not None
    assert (tmp_path / "assets" / "soft.bak.png").exists()


def test_pack_selected_images_into_an_atlas_with_named_regions(window, tmp_path):
    _select(window, "hero", "coin")
    image, meta = window.pack_selected_images(tmp_path / "out" / "atlas.png")
    regions = json.loads(meta.read_text())["regions"]
    assert set(regions) == {"hero", "coin"}
    with Image.open(image) as atlas:
        for x, y, w, h in regions.values():
            assert x + w <= atlas.width and y + h <= atlas.height
    assert window.selected_asset_images() and len(window.selected_asset_images()) == 2
