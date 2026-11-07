"""An actor's picture in the database (from its combatant visual), and the tile palette laid
out in readable strips like RPG Maker's."""

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

PROJECT = Path(__file__).resolve().parents[1] / "reference_projects/complex_reference_rpg"


def _window(app):
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project
    from asteria.runtime.component_registry import default_component_registry

    project = Project.load_json(PROJECT / "project.asteria.json", default_component_registry())
    window = AsteriaEditorWindow(project)
    window.document.file_path = PROJECT / "project.asteria.json"
    window._resolve_project_resources()
    return window


def test_an_actor_shows_its_battle_picture_in_the_list_and_the_form(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel

    from asteria.editor.records.pictures import record_picture

    app = QApplication.instance() or QApplication([])
    window = _window(app)
    try:
        picture = record_picture(window.document, "hero_01", 56)
        assert picture is not None and not picture.isNull()
        assert max(picture.width(), picture.height()) <= 56
        assert record_picture(window.document, "no_such_record", 56) is None
        assert record_picture(window.document, "", 56) is None
        from asteria.editor.records.form import RecordForm

        forms = [f for f in window.findChildren(RecordForm) if f.document is window.document]
        assert forms, "the Database pages build record forms"
        form = forms[0]
        form.set_record({"actor_id": "hero_01", "display_name": "Hero 01"}, "hero_01")
        app.processEvents()
        portraits = [w for w in form.findChildren(QLabel) if w.objectName() == "FormPortrait"]
        assert len(portraits) == 1 and not portraits[0].pixmap().isNull()
    finally:
        window.runtime_monitor.stop()
        window.close()
        window.deleteLater()


def test_the_tile_palette_wraps_a_wide_tileset_into_strips(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication

    from asteria.editor.scene.tile_palette_widget import TileGrid

    QApplication.instance() or QApplication([])
    frames = [
        SimpleNamespace(x=col * 16, y=row * 16, width=16, height=16)
        for row in range(3)
        for col in range(20)
    ]
    tiles = {
        index: SimpleNamespace(frame_index=index, collision=False, terrain=None, tags=())
        for index in range(len(frames))
    }
    tileset = SimpleNamespace(tile_width=16, tile_height=16, tiles=tiles)
    grid = TileGrid()
    grid.resize(230, 400)
    grid.set_source(tileset, SimpleNamespace(frames=frames))
    assert grid._columns == 20 and grid._rows == 3
    assert grid.zoom() == 1 and grid._cell_px() == (16, 16)  # true size until zoomed
    grid.set_zoom(2)
    assert grid._cell_px() == (32, 32)
    assert grid.per_strip() == 7  # 230 px / 32 px
    assert grid.strips() == 3  # 20 columns in strips of 7
    for col, row in ((0, 0), (6, 2), (7, 0), (13, 1), (19, 2)):
        x, y, w, h = grid.rect_of(col, row)
        assert grid._cell_at(QPointF(x + w / 2, y + h / 2)) == (col, row)
    x, y, _w, _h = grid.rect_of(7, 0)
    assert x == 0 and y == 3 * 32 + grid.GAP  # the second strip starts under the first
    assert grid.minimumHeight() == 3 * (3 * 32 + grid.GAP) - grid.GAP
    grid.set_zoom(1)
    assert grid.per_strip() == 14 and grid.strips() == 2


def test_the_tile_palette_keeps_the_atlas_pages_whole(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication

    from asteria.editor.scene.tile_palette_widget import TileGrid

    QApplication.instance() or QApplication([])
    # two pages of 8 columns with two empty columns between, as a tileset is often drawn,
    # then an empty row and a third page of 4 columns
    frames = [
        SimpleNamespace(x=col * 16, y=row * 16, width=16, height=16)
        for row in (0, 1, 3)
        for col in (*range(8), *range(10, 18), *range(20, 24))
    ]
    tiles = {
        index: SimpleNamespace(frame_index=index, collision=False, terrain=None, tags=())
        for index in range(len(frames))
    }
    grid = TileGrid()
    grid.resize(14 * 16, 200)  # 14 columns fit: a page of 8 stays whole, two do not fit together
    grid.set_source(
        SimpleNamespace(tile_width=16, tile_height=16, tiles=tiles), SimpleNamespace(frames=frames)
    )
    assert grid._rows == 3  # the empty row is gone
    assert grid._pages == [(0, 7), (10, 17), (20, 23)]
    assert grid.strips() == 2  # page 1 alone; pages 2 and 3 share the next line (8 + 1 + 4)
    assert grid.rect_of(10, 0)[:2] == (0, 3 * 16 + grid.GAP)
    assert grid.rect_of(20, 0)[0] == 9 * 16  # a column between the two pages
    assert grid._frames[(20, 2)] == (20 * 16, 3 * 16, 16, 16)  # still the atlas picture
    for col in (0, 7, 10, 17, 20, 23):
        x, y, w, h = grid.rect_of(col, 2)
        assert grid._cell_at(QPointF(x + w / 2, y + h / 2)) == (col, 2)
    grid.resize(4 * 16, 200)  # narrower than a page: the page is cut into pieces of 4
    grid._fit()  # (a hidden widget gets no resize event; the window's palette does)
    assert grid.strips() == 2 + 2 + 1 and grid.rect_of(4, 0)[:2] == (0, grid._strip_height())


def test_the_tile_palette_reads_its_picture_again_only_when_the_file_changes(
    monkeypatch, tmp_path
):
    """Every editor refresh hands the palette its tileset again: the picture is decoded (and
    its see-through lanes found) once per file version, not on each refresh."""
    import os

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication

    from asteria.editor.scene.tile_palette_widget import TileGrid

    QApplication.instance() or QApplication([])
    picture = QImage(48, 16, QImage.Format_ARGB32)
    picture.fill(QColor(0, 0, 0, 0))
    for x in (*range(0, 16), *range(32, 48)):  # tiles 0 and 2 drawn, 1 left see-through
        for y in range(16):
            picture.setPixelColor(x, y, QColor(200, 50, 50, 255))
    path = tmp_path / "tiles.png"
    picture.save(str(path))
    frames = [SimpleNamespace(x=c * 16, y=0, width=16, height=16) for c in range(3)]
    tiles = {
        i: SimpleNamespace(frame_index=i, collision=False, terrain=None, tags=()) for i in range(3)
    }
    tileset = SimpleNamespace(tile_width=16, tile_height=16, tiles=tiles)
    grid = TileGrid()
    grid.set_source(tileset, SimpleNamespace(frames=frames), path)
    first = grid._image
    assert first is not None and grid._pages == [(0, 0), (2, 2)]  # the empty lane dropped
    grid.set_source(tileset, SimpleNamespace(frames=frames), path)
    assert grid._image is first and grid._pages == [(0, 0), (2, 2)]  # not decoded again
    later = path.stat().st_mtime_ns + 5_000_000_000
    os.utime(path, ns=(later, later))  # the artist saved the picture again
    grid.set_source(tileset, SimpleNamespace(frames=frames), path)
    assert grid._image is not first


def test_a_fighter_picks_its_battlefield_sheet_and_icon_from_lists(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.records.form import RecordForm
    from asteria.editor.records.sprite_sheet_picker import SpriteSheetPicker
    from asteria.editor.rpg.game_systems_widget import _IconPicker

    app = QApplication.instance() or QApplication([])
    window = _window(app)
    try:
        form = next(f for f in window.findChildren(RecordForm) if f.document is window.document)
        data = {"battlefield_asset_id": "battle.combatant.hero_01", "icon_asset_id": None}
        sheet = form.widget_for(data, "battlefield_asset_id", data["battlefield_asset_id"])
        assert isinstance(sheet, SpriteSheetPicker)
        assert sheet.text() == "battle.combatant.hero_01"
        assert sheet.preview.pixmap() is not None and not sheet.preview.pixmap().isNull()
        sheet._fill_all()
        listed = [sheet.combo.itemData(i) for i in range(sheet.combo.count())]
        assert "battle.combatant.hero_02" in listed and "battle.combatant.astral_tyrant" in listed
        assert not any(str(item).startswith("battle.fx.") for item in listed)  # no effects
        asked = []
        monkeypatch.setattr(  # a double-click opens the picture dialog (stubbed: a pick)
            "asteria.editor.records.sprite_sheet_picker.pick_sprite_sheet",
            lambda document, parent=None, battle=False: asked.append(battle) or "battle.fx.fire",
        )
        sheet.preview.doubleClicked.emit()
        assert asked == [True] and sheet.text() == "battle.fx.fire"  # any kind, if chosen
        sheet.setText("battle.combatant.hero_02")
        assert data["battlefield_asset_id"] == "battle.combatant.hero_02"
        icon = form.widget_for(data, "icon_asset_id", data["icon_asset_id"])
        assert isinstance(icon, _IconPicker) and icon.text() == ""
    finally:
        window.runtime_monitor.stop()
        window.close()
        window.deleteLater()
