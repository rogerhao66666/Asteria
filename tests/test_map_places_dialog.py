"""Behavior Trees: a tree's places are picked by clicking a scene's map."""

from __future__ import annotations

from pathlib import Path

import pytest

from asteria.editor import i18n
from asteria.editor.behavior_tree_authoring import parse_points

DEMO = (
    Path(__file__).resolve().parents[1]
    / "reference_projects"
    / "full_verification_demo"
    / "project.asteria.json"
)
WOODS = "Whispering Woods"  # where goblins run the demo's foe_patrol


@pytest.fixture
def page(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.behavior_tree_widget import BehaviorTreeEditorWidget
    from asteria.editor.resource_resolver import resolve_project_resources
    from asteria.project import Project

    QApplication.instance() or QApplication([])
    document = EditorDocument()
    document.set_project(Project.load_json(DEMO, document.component_registry), file_path=DEMO)
    resolve_project_resources(document)
    return BehaviorTreeEditorWidget(document)


def _on_a_new_node(page, kind):
    page.create_tree("every_kind")
    assert page.add_child(kind), page.last_error
    assert page.select_node((1,))
    return page.api.get("every_kind").node((1,))


def _dialog(page, tree_id, places, many=True):
    from asteria.editor.map_places_dialog import MapPlacesDialog

    dialog = MapPlacesDialog(page.api.document, tree_id, places, many=many)
    dialog.resize(800, 600)
    dialog.show()
    return dialog


def _click_world(canvas, x, y):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    at = canvas.camera.world_to_screen(x, y)
    QTest.mouseClick(canvas, Qt.LeftButton, Qt.NoModifier, QPoint(round(at[0]), round(at[1])))


def _answering(monkeypatch, answer, *clicks):
    """The dialog opens, is clicked at world places as the author would, and is answered."""
    from asteria.editor.map_places_dialog import MapPlacesDialog

    seen = []

    def exec_(dialog):
        dialog.resize(800, 600)
        dialog.show()
        for x, y in clicks:
            _click_world(dialog.canvas, x, y)
        seen.append(dialog)
        return answer

    monkeypatch.setattr(MapPlacesDialog, "exec", exec_)
    return seen


def _near(found, wanted):
    """A screen pixel of the whole map is more than a world unit."""
    return all(abs(a - b) <= 2 for a, b in zip(found, wanted, strict=True))


# -- which scene it opens on ---------------------------------------------------------------------
def test_it_opens_on_a_scene_where_a_character_runs_the_tree(page):
    from asteria.editor.map_places_dialog import scene_for_tree

    project = page.api.document.project
    assert scene_for_tree(project, "foe_patrol").name == WOODS
    assert _dialog(page, "foe_patrol", []).canvas.scene.name == WOODS


def test_a_tree_nobody_runs_opens_on_the_startup_scene(page):
    from asteria.editor.map_places_dialog import scene_for_tree

    project = page.api.document.project
    assert scene_for_tree(project, "every_kind").id == project.startup_scene_id
    assert _dialog(page, "every_kind", []).canvas.scene.id == project.startup_scene_id


def test_another_scene_is_picked_from_a_list_and_the_map_follows(page):
    dialog = _dialog(page, "foe_patrol", [(40.0, 40.0)])
    first = dialog.canvas.bounds
    box = dialog.scene_box
    assert box.count() == len(list(page.api.document.project.scenes()))
    box.setCurrentIndex(box.findText("Catacombs"))
    assert dialog.canvas.scene.name == "Catacombs"
    assert dialog.canvas.bounds != first
    assert dialog.places() == [(40.0, 40.0)], "the places stay as they are"


# -- a click is the value ------------------------------------------------------------------------
def test_a_click_adds_a_patrol_place_and_ok_saves_the_datas_own_form(page, monkeypatch):
    _on_a_new_node(page, "patrol")
    assert page.fields["points"].places() == [(0.0, 0.0), (32.0, 0.0)]
    seen = _answering(monkeypatch, 1, (200, 120), (300, 160))
    assert page.fields["points"].pick_button.isEnabled()
    page.fields["points"].pick_button.click()
    places = seen[0].places()
    assert places[:2] == [(0.0, 0.0), (32.0, 0.0)], "the existing places stay first"
    assert len(places) == 4
    assert _near(places[2], (200, 120)) and _near(places[3], (300, 160))
    assert all(float(x).is_integer() and float(y).is_integer() for x, y in places)
    saved = page.api.get("every_kind").node((1,)).params["points"]
    assert parse_points(saved) == places
    assert saved == "; ".join(f"{x:g},{y:g}" for x, y in places)
    assert page.fields["points"].places() == places, "the page shows what was saved"
    assert page.path == (1,), "the node stays selected"


def test_a_click_sets_the_move_to_place_and_the_last_click_wins(page, monkeypatch):
    from PySide6.QtWidgets import QPushButton

    _on_a_new_node(page, "move_to")
    seen = _answering(monkeypatch, 1, (100, 100), (220, 140))
    button = next(b for b in page.findChildren(QPushButton) if b.text() == "Pick on Map…")
    button.click()
    assert len(seen[0].places()) == 1
    params = page.api.get("every_kind").node((1,)).params
    assert isinstance(params["x"], int | float) and isinstance(params["y"], int | float)
    assert _near((params["x"], params["y"]), (220, 140))
    assert page.fields["x"].number() == params["x"]


def test_cancel_changes_nothing(page, monkeypatch):
    node = _on_a_new_node(page, "patrol")
    before = node.params.get("points", "")
    _answering(monkeypatch, 0, (200, 120))
    page.pick_on_map()
    assert page.api.get("every_kind").node((1,)).params.get("points", "") == before
    assert page.fields["points"].places() == [(0.0, 0.0), (32.0, 0.0)]


def test_a_tree_is_saved_only_when_ok_is_pressed_not_on_a_click(page):
    _on_a_new_node(page, "patrol")
    before = page.api.get("every_kind").node((1,)).params.get("points", "")
    dialog = _dialog(page, "every_kind", page.fields["points"].places())
    _click_world(dialog.canvas, 100, 100)
    assert len(dialog.places()) == 3
    assert page.api.get("every_kind").node((1,)).params.get("points", "") == before


def test_a_drag_moves_the_view_and_adds_no_place(page):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    dialog = _dialog(page, "foe_patrol", [])
    canvas = dialog.canvas
    pan = canvas.camera.pan_x
    QTest.mousePress(canvas, Qt.LeftButton, Qt.NoModifier, QPoint(200, 200))
    QTest.mouseMove(canvas, QPoint(260, 200))
    QTest.mouseRelease(canvas, Qt.LeftButton, Qt.NoModifier, QPoint(260, 200))
    assert canvas.camera.pan_x != pan
    assert dialog.places() == []


def test_a_wrong_click_is_taken_back_and_ok_waits_for_a_place(page):
    from PySide6.QtWidgets import QDialogButtonBox

    dialog = _dialog(page, "foe_patrol", [(10.0, 10.0)])
    ok = dialog.buttons.button(QDialogButtonBox.Ok)
    assert dialog.remove_last.isVisible() and ok.isEnabled()
    dialog.remove_last.click()
    assert dialog.places() == []
    assert not ok.isEnabled() and not dialog.remove_last.isEnabled()
    _click_world(dialog.canvas, 100, 100)
    assert len(dialog.places()) == 1
    assert ok.isEnabled() and dialog.remove_last.isEnabled()


def test_one_place_has_nothing_to_take_back(page):
    assert not _dialog(page, "foe_patrol", [(10.0, 10.0)], many=False).remove_last.isVisible()


# -- the map shows the places --------------------------------------------------------------------
def test_existing_places_are_numbered_markers_on_the_map(page):
    from PySide6.QtGui import QColor

    from asteria.editor.map_point_picker import _CHOSEN

    dialog = _dialog(page, "every_kind", [(200.0, 120.0), (400.0, 200.0)])
    canvas = dialog.canvas
    assert canvas.places == [(200.0, 120.0), (400.0, 200.0)] and canvas.numbered
    picture = canvas.grab().toImage()
    ratio = picture.devicePixelRatio()
    x, y = canvas.camera.world_to_screen(200.0, 120.0)
    # beside the number, inside the dot
    color = QColor(picture.pixel(round((x + 7) * ratio), round(y * ratio)))
    assert color.name() == QColor(_CHOSEN).name()
    assert not _dialog(page, "every_kind", [(1.0, 1.0)], many=False).canvas.numbered


def test_a_place_in_the_map_s_corner_shows_whole(page):
    canvas = _dialog(page, "every_kind", [(0.0, 0.0)]).canvas
    x0, y0, x1, y1 = canvas.bounds
    for wx, wy in ((x0, y0), (x1, y1)):
        x, y = canvas.camera.world_to_screen(wx, wy)
        assert 10 <= x <= canvas.width() - 10 and 10 <= y <= canvas.height() - 10


def test_a_place_nobody_could_stand_on_is_said_and_not_refused(page, monkeypatch):
    from asteria.editor.map_places_dialog import CHARACTER_STUCK

    dialog = _dialog(page, "every_kind", [(99999.0, 99999.0)])
    assert 0 in dialog.canvas.blocked
    assert "Place 1: This place is outside the map." in dialog.warning.text()
    assert dialog.warning.isVisible()
    assert dialog.places() == [(99999.0, 99999.0)]
    assert "stuck" in CHARACTER_STUCK and "player" not in CHARACTER_STUCK


def test_a_character_does_not_block_a_place_with_its_own_body(page):
    """Goblin Slinger 1 runs the tree and is solid: its own spot is a place it can stand on."""
    from asteria.core import world_position
    from asteria.editor.map_places_dialog import characters_running, scene_for_tree

    scene = scene_for_tree(page.api.document.project, "foe_patrol")
    x, y = world_position(characters_running(scene, "foe_patrol")[0])
    dialog = _dialog(page, "foe_patrol", [(x, y)])
    assert dialog.canvas.blocked == frozenset(), dialog.warning.text()


# -- the Game Start's map stays as it was ------------------------------------------------------
def test_the_game_start_s_map_is_still_about_the_player(page):
    from asteria.editor.map_point_picker import MapPointPicker, PlayerMapCanvas, spot_problem

    picker = MapPointPicker(page.api.document)
    assert isinstance(picker.canvas, PlayerMapCanvas)
    assert "the player starts here" in picker.canvas.toolTip()
    assert picker.canvas.minimumHeight() == picker.canvas.maximumHeight() == 260
    project = page.api.document.project
    scene = project.scene(project.startup_scene_id)
    assert spot_problem(page.api.document, scene, None, -500.0, -500.0) == (
        "This place is outside the map."
    )


# -- the words -----------------------------------------------------------------------------------
@pytest.fixture
def chinese():
    i18n.CURRENT["language"] = "zh_TW"
    yield
    i18n.CURRENT["language"] = i18n.DEFAULT


@pytest.mark.parametrize(
    "words",
    [
        "Pick on Map…",
        "Pick Places on the Map",
        "Pick a Place on the Map",
        "Remove Last",
        "Place {number}: {problem}",
        "A character would be stuck here: a wall or an object is in the way.",
        "Click: adds a place to walk to.\nDrag: move the view.\n"
        "Pinch or Ctrl + scroll: zoom in and out.",
        "Click: the character goes here.\nDrag: move the view.\n"
        "Pinch or Ctrl + scroll: zoom in and out.",
    ],
)
def test_every_new_word_has_its_chinese(chinese, words):
    assert i18n.translate(words) != words
