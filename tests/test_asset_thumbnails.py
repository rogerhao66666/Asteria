import shutil
from pathlib import Path

from PySide6.QtWidgets import QApplication

from asteria.editor import EditorDocument
from asteria.editor.asset_thumbnails import asset_thumbnail
from asteria.editor.qt_texture_renderer import QtTextureCache
from asteria.editor.resource_resolver import resolve_project_resources
from asteria.project import Project

REF_DIR = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg"

_app = QApplication.instance() or QApplication([])


def _load(root=REF_DIR):
    path = root / "project.asteria.json"
    document = EditorDocument()
    project = Project.load_json(path, document.component_registry)
    document.set_project(project, file_path=path)
    resolve_project_resources(document)
    return document


def _record(document, kind):
    return next(r for r in document.project.assets.records() if r.kind == kind)


def test_texture_sprite_sheet_and_tileset_get_real_thumbnails():
    document = _load()
    cache = QtTextureCache()
    for kind in ("texture", "sprite_sheet", "tileset"):
        record = _record(document, kind)
        icon = asset_thumbnail(document, record, cache)
        assert icon is not None and not icon.isNull(), kind


def test_kinds_without_direct_art_fall_back_to_no_icon():
    document = _load()
    cache = QtTextureCache()
    record = _record(document, "tilemap")
    assert asset_thumbnail(document, record, cache) is None


def test_missing_texture_file_does_not_raise(tmp_path):
    root = tmp_path / "complex_reference_rpg"
    shutil.copytree(REF_DIR, root)
    document = _load(root)
    cache = QtTextureCache()
    record = _record(document, "sprite_sheet")
    texture_record = document.project.assets.get(
        document.asset_views.sprite_sheet(record.id).texture.asset_id
    )
    (root / texture_record.source_path).unlink()
    assert asset_thumbnail(document, record, cache) is None
