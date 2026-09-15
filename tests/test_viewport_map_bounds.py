import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from asteria.editor.shell import AsteriaEditorWindow

_app = QApplication.instance() or QApplication([])


def test_default_view_draws_one_to_one_cells_and_centres_the_map():
    from asteria.editor.viewport_widget import DEFAULT_ZOOM

    window = AsteriaEditorWindow()
    viewport = window.viewport
    viewport.resize(900, 700)
    viewport.reset_view()

    # 48px tiles need no magnification to be a comfortable cell.
    assert viewport.camera.zoom == DEFAULT_ZOOM
    assert viewport._cell_size() == (48.0, 48.0)

    rect = viewport.map_screen_rect()
    assert abs(rect.center().x() - viewport.width() // 2) <= 1
    assert abs(rect.center().y() - viewport.height() // 2) <= 1

    window.document.mark_saved()
    window.close(); _app.processEvents()


def test_the_starter_map_ships_with_a_character_standing_on_it():
    window = AsteriaEditorWindow()
    scene = window.document.project.scenes()[0]
    names = [entity.name for entity in scene.entities()]
    assert "Hero" in names

    from asteria.core import Transform
    from asteria.runtime import ActorLinkComponent, SpriteRenderer2D

    hero = next(e for e in scene.entities() if e.name == "Hero")
    assert hero.try_get(ActorLinkComponent).actor_id == "hero"
    assert hero.try_get(SpriteRenderer2D).sprite_sheet_asset_id
    # Standing in the middle of the map, not parked at the origin.
    transform = hero.get(Transform)
    map_x, map_y, map_w, map_h = window.viewport.map_world_rect()
    assert map_x < transform.x < map_x + map_w
    assert map_y < transform.y <= map_y + map_h

    # And it actually draws: a sprite sheet that resolves, like the tiles.
    from asteria.editor.entity_render import build_entity_sprite_draws

    draws = build_entity_sprite_draws(
        scene, window.viewport.camera, window.document.asset_views.sprite_sheet
    )
    assert len(draws) == 1

    window.document.mark_saved()
    window.close(); _app.processEvents()


def test_empty_cell_field_is_whole_cells_inside_the_viewport():
    window = AsteriaEditorWindow()
    viewport = window.viewport
    viewport.resize(500, 400)
    viewport.reset_view()

    field = viewport.grid_field_rect()
    step_x, step_y = viewport._cell_size()
    # Never larger than the pane — trimmed down to whole cells, never up.
    assert field.left() >= 0 and field.top() >= 0
    assert field.left() + field.width() <= viewport.width()
    assert field.top() + field.height() <= viewport.height()
    assert field.width() % step_x == 0
    assert field.height() % step_y == 0
    # At most one partial cell trimmed off each edge.
    assert viewport.width() - field.width() < 2 * step_x
    assert viewport.height() - field.height() < 2 * step_y

    # Phase-aligned with the map, so its border sits on a cell boundary.
    map_rect = viewport.map_screen_rect()
    assert (map_rect.left() - field.left()) % step_x == 0
    assert (map_rect.top() - field.top()) % step_y == 0

    window.document.mark_saved()
    window.close(); _app.processEvents()


def test_zoom_label_reads_100_percent_at_the_default_view():
    from asteria.editor.shell import AsteriaEditorWindow

    window = AsteriaEditorWindow()
    window.resize(1200, 800)
    _app.processEvents()
    window.viewport.reset_view()
    window.viewport.grab()  # zoomChanged only fires from a real paint pass
    assert window.zoom_label.text() == "100%"

    window.viewport.zoom_in()
    window.viewport.grab()
    assert window.zoom_label.text() == "125%"

    window.document.mark_saved()
    window.close(); _app.processEvents()


def test_map_bounds_match_the_tile_map_extent():
    window = AsteriaEditorWindow()
    viewport = window.viewport
    source = viewport.render_source

    x, y, width, height = viewport.map_world_rect()
    assert (x, y) == (0.0, 0.0)
    assert width == 20 * source.tilemap.tile_width
    assert height == 15 * source.tilemap.tile_height

    window.document.mark_saved()
    window.close(); _app.processEvents()


def test_viewport_paints_with_and_without_a_map():
    window = AsteriaEditorWindow()
    viewport = window.viewport
    viewport.resize(640, 480)
    assert not viewport.grab().isNull()

    # An entity-only scene has no bounds to draw, and must still paint.
    viewport.render_source = None
    assert viewport.map_world_rect() is None
    assert not viewport.grab().isNull()

    window.document.mark_saved()
    window.close(); _app.processEvents()


def test_the_tile_grid_is_drawn_over_the_map_not_under_it():
    window = AsteriaEditorWindow()
    viewport = window.viewport
    viewport.resize(400, 300)
    viewport.camera.pan_x = 0.0
    viewport.camera.pan_y = 0.0
    viewport.camera.zoom = 1.0

    with_grid = viewport.grab().toImage()
    # Filled map tiles cover the whole sheet, so a grid painted before them
    # would leave the result pixel-identical to having no grid at all.
    viewport._paint_map_grid = lambda painter: None
    without_grid = viewport.grab().toImage()
    assert with_grid != without_grid

    window.document.mark_saved()
    window.close(); _app.processEvents()


def test_placed_characters_snap_onto_a_tile_cell():
    window = AsteriaEditorWindow()
    viewport = window.viewport
    viewport.resize(640, 480)
    tile = viewport.render_source.tilemap.tile_width

    x, y = window.scene_controller.placement_position()
    # Bottom-centre of some cell, because sprite frames pivot there.
    assert (x - tile / 2) % tile == 0
    assert y % tile == 0
    map_x, map_y, map_w, map_h = viewport.map_world_rect()
    assert map_x <= x <= map_x + map_w
    assert map_y <= y <= map_y + map_h

    window.document.mark_saved()
    window.close(); _app.processEvents()


def test_placement_falls_back_to_the_view_centre_without_a_map():
    window = AsteriaEditorWindow()
    viewport = window.viewport
    viewport.render_source = None
    viewport.camera.pan_x = 0.0
    viewport.camera.pan_y = 0.0
    viewport.camera.zoom = 1.0

    x, y = window.scene_controller.placement_position()
    assert x == pytest.approx(max(1, viewport.width()) / 2)
    assert y == pytest.approx(max(1, viewport.height()) / 2)

    window.document.mark_saved()
    window.close(); _app.processEvents()
