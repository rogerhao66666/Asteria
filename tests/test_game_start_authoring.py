"""The Game Start form: reads the start state, writes it back undoably and validates."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.editor.game_start_authoring import (
    GameStartAuthoringController,
    GameStartAuthoringError,
)
from asteria.project import Project

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "party_rpg_demo"


@pytest.fixture
def controller():
    document = EditorDocument()
    document.project = Project.load_json(
        ROOT / "project.asteria.json", document.component_registry
    )
    return GameStartAuthoringController(document)


def test_form_reads_party_pets_and_items(controller):
    data = controller.form_data()
    assert len(data["party_actor_ids"]) == 4
    assert data["pets"] and data["pets"][0]["species_id"] == "frost_lynx"
    assert isinstance(data["items"], dict)


def test_apply_is_undoable_and_round_trips(controller):
    data = controller.form_data()
    data["pets"] = data["pets"] + [{"species_id": "ember_hound", "level": 7, "nickname": "Ash"}]
    data["active_pet"] = 2
    data["items"] = {**data["items"], next(iter(controller.references("items"))): 3}
    controller.apply(data)
    again = controller.form_data()
    assert [p["species_id"] for p in again["pets"]] == ["frost_lynx", "ember_hound"]
    assert again["active_pet"] == 2
    runtime = controller.project.game_start.instantiate(controller.project)
    assert runtime.rpg_state.active_pet_id == "ember_hound#1"
    controller.document.undo()
    assert len(controller.form_data()["pets"]) == 1


def test_invalid_data_is_rejected_and_nothing_changes(controller):
    before = controller.project.game_start
    data = controller.form_data()
    data["pets"] = [{"species_id": "no_such_species", "level": 1}]
    with pytest.raises(GameStartAuthoringError):
        controller.apply(data)
    data = controller.form_data()
    data["party_actor_ids"] = ["nobody"]
    with pytest.raises(GameStartAuthoringError):
        controller.apply(data)
    assert controller.project.game_start is before


def test_the_widget_edits_and_applies(controller):
    from PySide6.QtWidgets import QApplication

    from asteria.editor.game_start_widget import GameStartEditorWidget

    QApplication.instance() or QApplication([])

    widget = GameStartEditorWidget(controller)
    data = widget.form.data()
    assert data["player_facing"] == controller.project.game_start.player_facing
    widget.form.set_data({**data, "player_facing": "left"})
    assert widget.apply()
    assert controller.project.game_start.player_facing == "left"


def test_starting_gear_goes_into_the_equipment_bag(controller):
    """D98: Game Start ▸ Starting Gear: spare pieces in the bag, kept when written again; an
    older start state gains the bag's keys and keeps the rest as written."""
    before = dict(controller.project.game_start.rpg_state_data)
    gear = sorted(controller.references("equipment"))[:2]
    data = controller.form_data()
    assert data["gear"] == {}
    data["gear"] = {gear[0]: 2, gear[1]: 1}
    controller.apply(data)
    state = controller.project.game_start.rpg_state_data
    assert controller.form_data()["gear"] == {gear[0]: 2, gear[1]: 1}
    assert state["loadouts"] == before["loadouts"]  # the worn gear as it was written
    runtime = controller.project.game_start.instantiate(controller.project)
    bag = [g.equipment.equipment_id for g in runtime.rpg_state.equipment_bag]
    assert sorted(bag) == sorted([gear[0], gear[0], gear[1]])
    assert len({g.instance_id for g in runtime.rpg_state.equipment_bag}) == 3
    first = [p["instance_id"] for p in state["equipment_bag"]]
    data = controller.form_data()
    data["gear"] = {gear[0]: 1, gear[1]: 1}
    controller.apply(data)
    kept = [
        p["instance_id"] for p in controller.project.game_start.rpg_state_data["equipment_bag"]
    ]
    assert set(kept) <= set(first) and len(kept) == 2  # pieces it held are kept
    controller.document.undo()
    controller.document.undo()
    assert (
        "equipment_bag" not in controller.project.game_start.rpg_state_data
        or not (controller.project.game_start.rpg_state_data["equipment_bag"])
    )


def test_the_demo_starts_with_spare_gear():
    document = EditorDocument()
    path = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
    project = Project.load_json(path / "project.asteria.json", document.component_registry)
    bag = project.game_start.instantiate(project).rpg_state.equipment_bag
    slots = {g.equipment.slot for g in bag}
    assert len(bag) >= 80 and {"weapon", "armor", "accessory", "head", "legs", "feet"} <= slots


def _page(controller, width):
    from PySide6.QtWidgets import QApplication

    from asteria.editor.game_start_widget import GameStartEditorWidget

    qapp = QApplication.instance() or QApplication([])
    widget = GameStartEditorWidget(controller)
    widget.resize(width, 800)
    widget.show()
    qapp.processEvents()
    return widget, qapp


@pytest.mark.parametrize("width", [640, 1000, 1500])
def test_no_name_on_the_page_is_cut_or_runs_into_its_number(controller, width):
    from PySide6.QtWidgets import QLabel, QSpinBox

    from asteria.editor.record_form import AmountTable

    widget, qapp = _page(controller, width)
    data = widget.form.data()
    widget.form.widgets["items"].values["a_very_long_item_name_that_stays_whole"] = 3.0
    widget.form.widgets["items"]._build()
    widget.form._line_up()
    qapp.processEvents()
    tables = [w for w in widget.form.widgets.values() if isinstance(w, AmountTable)]
    assert len({t.name_width for t in tables}) == 1  # their columns line up across the cards
    for table in tables:
        assert table.grid.minimumSize().width() <= table.width()
        for label in table.findChildren(QLabel):
            if label.isVisible() and label.text():
                assert label.width() >= label.sizeHint().width()
    assert data["position"] is None and not isinstance(widget.form.widgets["position"], QSpinBox)
    # a name longer than the whole row wraps, and the row still stays on the page
    gear = widget.form.widgets["gear"]
    gear.values[" ".join(["a very long name"] * 12)] = 1.0
    gear._build()
    qapp.processEvents()
    assert gear.grid.minimumSize().width() <= gear.width()
    widget.close()


def test_the_page_is_cards_and_one_switch_sets_the_whole_position(controller):
    widget, _qapp = _page(controller, 1000)
    form = widget.form
    assert list(form.cards) == [
        "Starting Place",
        "Party",
        "Starting Currencies",
        "Starting Items",
        "Starting Gear",
        "Starting Pets",
    ]
    # where it starts stands beside the party when there is room
    assert form.cards["Starting Place"].y() == form.cards["Party"].y()
    place = form.widgets["position"]
    place.set_value([12, 34])
    assert place.x.isEnabled() and form.data()["position"] == [12, 34]
    assert widget.apply()
    assert controller.project.game_start.player_position == (12.0, 34.0)
    widget.form.widgets["position"].set_value(None)
    assert not widget.form.widgets["position"].y.isEnabled()
    assert widget.apply()
    assert controller.project.game_start.player_position is None
    # a card folds by its title
    card = widget.form.cards["Starting Gear"]
    card.title.click()
    assert not card.body.isVisibleTo(card)
    widget.close()


def test_the_first_pet_is_picked_by_name_only_when_there_is_a_choice(controller):
    widget, qapp = _page(controller, 1000)
    form = widget.form
    data = form.data()
    species = data["pets"][0]["species_id"]
    pick = form.widgets["active_pet"]
    form.set_data({**data, "pets": data["pets"][:1], "active_pet": 0})
    qapp.processEvents()
    assert not pick.isVisible()  # one pet: nothing to choose
    two = [*data["pets"][:1], {"species_id": species, "nickname": "Ash", "level": 2}]
    form.set_data({**data, "pets": two, "active_pet": 2})
    qapp.processEvents()
    assert pick.isVisible() and pick.currentText() == "2. Ash"
    assert form.data()["active_pet"] == 2
    assert widget.apply()
    assert widget.controller.form_data()["active_pet"] == 2
    widget.close()


# -- the map: a place picked by clicking -------------------------------------------------------
DEMOS = Path(__file__).resolve().parents[1] / "reference_projects"


def _map_page(name="full_verification_demo", width=1000):
    from PySide6.QtWidgets import QApplication

    from asteria.editor.game_start_widget import GameStartEditorWidget
    from asteria.editor.resource_resolver import resolve_project_resources

    qapp = QApplication.instance() or QApplication([])
    path = DEMOS / name / "project.asteria.json"
    document = EditorDocument()
    document.project = Project.load_json(path, document.component_registry)
    document.file_path = path
    resolve_project_resources(document)
    widget = GameStartEditorWidget(GameStartAuthoringController(document))
    widget.resize(width, 800)
    widget.show()
    qapp.processEvents()
    return widget, qapp


def _click_world(canvas, x, y):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    at = canvas.camera.world_to_screen(x, y)
    QTest.mouseClick(canvas, Qt.LeftButton, Qt.NoModifier, QPoint(round(at[0]), round(at[1])))


def test_a_click_on_the_map_is_where_the_game_starts():
    from asteria.core import Transform
    from asteria.runtime.game_session import GameSessionRuntime

    widget, qapp = _map_page()
    canvas = widget.form.map.canvas
    assert widget.form.data()["position"] is None
    assert canvas.player_place() == (608.0, 152.0)  # the switch off: the scene's own place
    _click_world(canvas, 352, 208)
    qapp.processEvents()
    x, y = widget.form.data()["position"]
    assert abs(x - 352) <= 2 and abs(y - 208) <= 2  # a screen pixel is more than a world unit
    assert widget.form.widgets["position"].check.isChecked()
    assert widget.auto_apply()
    project = widget.controller.project
    assert project.game_start.player_position == (float(x), float(y))
    session = GameSessionRuntime(project, project.game_start.instantiate(project))
    placed = session.player.get(Transform)
    assert (placed.x, placed.y) == (float(x), float(y))
    widget.close()


def test_turned_on_the_switch_starts_from_where_the_player_is():
    widget, qapp = _map_page()
    point = widget.form.widgets["position"]
    assert (point.x.value(), point.y.value()) == (608, 152)
    assert widget.form.data()["position"] is None  # shown, not chosen
    point.check.setChecked(True)
    qapp.processEvents()
    assert widget.form.data()["position"] == [608, 152]
    assert widget.form.map.canvas.point == (608.0, 152.0)
    widget.close()


def test_the_map_follows_the_scene_the_facing_and_the_boxes():
    widget, qapp = _map_page()
    form, picker = widget.form, widget.form.map
    first = picker.canvas.bounds
    scene_box = form.widgets["scene_id"]
    scene_box.setCurrentIndex((scene_box.currentIndex() + 1) % scene_box.count())
    qapp.processEvents()
    assert picker.canvas.scene.id == form.data()["scene_id"]
    assert picker.canvas.bounds != first
    facing = form.widgets["player_facing"]
    facing.setCurrentIndex(facing.findData("left"))
    qapp.processEvents()
    assert picker.canvas.facing == "left"
    form.widgets["position"].check.setChecked(True)
    form.widgets["position"].x.setValue(40)
    qapp.processEvents()
    assert picker.canvas.point[0] == 40.0
    widget.close()


def test_the_map_is_really_painted():
    from PySide6.QtGui import QColor

    widget, _qapp = _map_page()
    canvas = widget.form.map.canvas
    picture = canvas.grab().toImage()
    colors = {
        QColor(picture.pixel(x, y)).name()
        for x in range(0, picture.width(), 16)
        for y in range(0, picture.height(), 16)
    }
    assert len(colors) > 12  # tiles and objects, not an empty square
    widget.close()


def test_a_place_the_player_cannot_stand_on_is_said_and_not_refused():
    """On a wall tile, in a solid object, off the map; and what the field itself then does."""
    from asteria.core import Transform
    from asteria.runtime.game_session import GameSessionRuntime
    from asteria.runtime.tilemap_field import TileMapField

    widget, qapp = _map_page()
    form, picker = widget.form, widget.form.map
    point = form.widgets["position"]
    for place, stuck in (((352, 208), False), ((8, 300), True), ((608, 100), True)):
        point.set_value(list(place))
        form._show_place()
        qapp.processEvents()
        assert bool(picker.warning.text()) is stuck, place
        assert form.data()["position"] == list(place)  # the author may mean it
        assert widget.auto_apply()
        project = widget.controller.project
        session = GameSessionRuntime(project, project.game_start.instantiate(project))
        field = TileMapField(session, DEMOS / "full_verification_demo")
        field.controller.speed = 72.0  # this demo's walking speed comes from the playable game
        body = session.player.get(Transform)
        moved = 0.0
        for action in ("move_right", "move_left", "move_down", "move_up"):
            before = (body.x, body.y)
            for _ in range(10):
                field.step({action: 1.0}, 1 / 60)
            moved += abs(body.x - before[0]) + abs(body.y - before[1])
        assert (moved > 1.0) is not stuck, place  # the warning says what the field does
    point.set_value([9000, 9000])
    form._show_place()
    assert "outside" in picker.warning.text()
    widget.close()


@pytest.mark.parametrize("name", ["full_verification_demo", "arpg_demo", "party_rpg_demo"])
def test_a_demo_starts_on_a_place_that_is_not_warned_about(name):
    widget, _qapp = _map_page(name)
    assert widget.form.map.warning.text() == ""
    widget.close()


def test_a_position_that_is_not_a_whole_number_survives_the_page():
    from asteria.runtime.game_start import GameStartDefinition

    widget, _qapp = _map_page()
    project = widget.controller.project
    old = project.game_start
    project.game_start = GameStartDefinition(
        old.scene_id,
        old.player_entity_id,
        old.player_facing,
        (64.5, 232.25),
        old.rpg_state_data,
        old.event_context_data,
    )
    widget.refresh()
    assert widget.auto_apply()
    assert project.game_start.player_position == (64.5, 232.25)
    widget.close()


# -- long lists, narrow pages, the project's own words ------------------------------------------
def test_a_long_list_starts_folded_and_says_what_it_holds():
    widget, qapp = _map_page()
    card = widget.form.cards["Starting Gear"]
    assert not card.is_open() and not card.body.isVisible()
    assert card.summary.isVisible() and "Archon Robe" in card.summary.text()
    assert widget.form.cards["Starting Currencies"].is_open()  # a short one stays open
    card.set_open(True)
    qapp.processEvents()
    assert card.body.isVisible() and not card.summary.isVisible()
    widget.refresh()  # the author's folds stay when the page is built again
    assert widget.form.cards["Starting Gear"].is_open()
    widget.close()


def test_a_long_list_can_be_searched():
    from PySide6.QtWidgets import QApplication, QLabel

    QApplication.instance() or QApplication([])
    from asteria.editor.record_form import AmountTable

    values = {f"thing_{i}": 1 for i in range(13)}
    table = AmountTable(values, ())
    assert not table.find.isHidden()
    table.find.setText("thing 12")
    shown = [w.text() for w in table.findChildren(QLabel) if not w.isHidden() and w.text()]
    assert shown == ["Thing 12"]
    assert len(table.values) == 13  # only what is shown changes
    assert AmountTable({"a": 1}, ()).find.isHidden()


def test_a_narrow_list_keeps_two_columns_by_wrapping_its_names():
    from PySide6.QtWidgets import QApplication, QLabel

    from asteria.editor.record_form import AmountTable

    qapp = QApplication.instance() or QApplication([])
    values = {"flawless_sapphire_of_the_north": 1, "moonstone_necklace": 2, "ruby": 3}
    table = AmountTable(values, ())
    table.resize(460, 300)
    table.show()
    qapp.processEvents()
    assert table.per_row == 2
    assert table.grid.minimumSize().width() <= table.width()
    wrapped = [w for w in table.findChildren(QLabel) if w.isVisible() and w.wordWrap()]
    assert wrapped
    for label in wrapped:
        assert label.height() >= label.heightForWidth(label.width())  # every line of it shows
    assert table._arrange(250)[0] == 1  # too narrow for two: one, and still on the page
    table.resize(1200, 300)  # and wide again: back to one line each
    qapp.processEvents()
    assert table.per_row >= 2 and not [
        w for w in table.findChildren(QLabel) if w.isVisible() and w.wordWrap()
    ]
    table.close()


def test_a_record_with_no_picture_shows_its_kind_beside_those_with_one():
    from PySide6.QtWidgets import QLabel

    widget, _qapp = _map_page()
    table = widget.form.widgets["items"]
    bare = next(key for key in table.values if table._picture(key) is None)
    assert table.no_picture == "item"
    cell = table._name_cell(bare)
    assert cell.findChildren(QLabel)[0].pixmap() is not None
    assert not cell.findChildren(QLabel)[0].pixmap().isNull()
    widget.close()


def test_the_project_s_own_names_show_in_the_editor_s_language():
    from PySide6.QtWidgets import QApplication

    from asteria.editor import i18n
    from asteria.editor.data_translation import project_words
    from asteria.editor.record_form import AmountTable

    app = QApplication.instance() or QApplication([])
    widget, _qapp = _map_page()
    project = widget.controller.project
    words = project_words(project, "zh_TW")
    assert words["Alchemy Salt"] == "鍊金鹽" and words["Star Stones"] == "星石"
    assert project_words(project, "fr") == {}
    i18n.use_project(project)
    i18n.install(app, "zh_TW")
    try:
        assert i18n.translate("Alchemy Salt") == "鍊金鹽"
        assert i18n.translate("Save") != "鍊金鹽"  # the editor's own words first
        assert i18n.translate("Not a record at all") == "Not a record at all"
        table = AmountTable({"alchemy_salt": 1}, ())
        assert table._wanted("alchemy_salt") < 120  # the column is as wide as what is shown
    finally:
        i18n.set_language(i18n.DEFAULT)
        i18n.use_project(None)
    assert i18n.translate("Alchemy Salt") == "Alchemy Salt"
    assert project.rpg_database.items["alchemy_salt"].display_name == "Alchemy Salt"
    widget.close()


def test_the_game_data_list_shows_the_project_s_own_names_and_finds_them():
    from PySide6.QtWidgets import QApplication

    from asteria.editor import i18n
    from asteria.editor.authoring_hub_widget import AdapterFamilyWidget
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.workspace import WorkspaceMode

    app = QApplication.instance() or QApplication([])
    path = DEMOS / "full_verification_demo" / "project.asteria.json"
    i18n.install(app, "zh_TW")
    try:
        window = AsteriaEditorWindow(None)
        project = Project.load_json(path, window.document.component_registry)
        window.set_project(project, file_path=path)  # the shell tells i18n which project is open
        window.workspace.set_mode(WorkspaceMode.RPG)
        family = window.rpg_authoring.findChildren(AdapterFamilyWidget)[0]
        family.category.setCurrentIndex(family.category.findData("actors"))
        app.processEvents()
        shown = [family.browser.item(r).text() for r in range(family.browser.count())]
        assert "羅傑" in shown and "Roger" not in shown
        assert family.selected_id  # the rows still stand for their records
        family.search.setText("羅傑")
        family.refresh()
        assert [family.browser.item(r).text() for r in range(family.browser.count())] == ["羅傑"]
        window.close()
    finally:
        i18n.set_language(i18n.DEFAULT)
        i18n.use_project(None)
    assert project.rpg_database.actors["hero_01"].display_name == "Roger"
