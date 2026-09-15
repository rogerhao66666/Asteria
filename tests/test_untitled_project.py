import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from asteria.editor.shell import AsteriaEditorWindow
from asteria.editor.starter_project import (
    build_untitled_project,
    materialize_starter_assets,
)
from asteria.editor.storage import save_document
from asteria.editor.tile_edit import build_paint_command, tile_at

_app = QApplication.instance() or QApplication([])


def test_untitled_project_is_paintable_before_it_is_saved():
    window = AsteriaEditorWindow()
    document = window.document

    assert document.project is not None
    assert document.file_path is None
    # Resolved from the bundled starter pack, not from a project folder.
    source = window.viewport.render_source
    assert source is not None
    assert source.tileset is not None and source.sprite_sheet is not None
    assert window.tile_palette.list.count() == 16

    document.mark_saved()
    window.close(); _app.processEvents()


def test_painting_an_untitled_project_survives_the_first_save(tmp_path):
    window = AsteriaEditorWindow()
    source = window.viewport.render_source
    layer = source.tilemap.layers[0]
    window.document.execute(build_paint_command(source.tilemap, layer, [(3, 4)], 5))

    project_dir = tmp_path / "MyGame"
    saved = save_document(window.document, project_dir / "project.asteria.json")
    window.close()

    # The first save is what gives the bundled tileset — and the demo
    # character's sprite sheet — a home on disk.
    written = {p.relative_to(project_dir).as_posix() for p in project_dir.rglob("*") if p.is_file()}
    assert written == {
        "project.asteria.json",
        "tiles/environment_atlas.png",
        "tiles/environment.sprite_sheet.json",
        "tiles/environment.tileset.json",
        "tiles/map001.tilemap.json",
        "characters/characters_atlas.png",
        "characters/characters.sprite_sheet.json",
    }

    reopened = AsteriaEditorWindow()
    assert reopened.open_project_path(saved)
    reloaded = reopened.viewport.render_source
    assert tile_at(reloaded.tilemap, reloaded.tilemap.layers[0], 3, 4) == 5
    reopened.document.mark_saved()
    reopened.close(); _app.processEvents()


def test_materialize_never_overwrites_files_that_already_exist(tmp_path):
    project = build_untitled_project()
    first = materialize_starter_assets(project, tmp_path)
    assert first

    atlas = tmp_path / "tiles" / "environment_atlas.png"
    atlas.write_bytes(b"hand-edited art")
    assert materialize_starter_assets(project, tmp_path) == ()
    assert atlas.read_bytes() == b"hand-edited art"


def test_a_project_without_starter_assets_materializes_nothing(tmp_path):
    from asteria.core import Scene
    from asteria.project import Project

    project = Project("Game")
    project.add_scene(Scene("Main"))
    assert materialize_starter_assets(project, tmp_path) == ()
    assert not list(tmp_path.iterdir())
