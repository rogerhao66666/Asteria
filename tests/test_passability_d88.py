"""D88: every object of a map can be passable, block at its feet or block its whole picture
(the Inspector's Passability, as RPG Maker's "Through" and priority "Same as characters"); the
equipment screen's doll icons fill their place, set and previewed in the menu layout editor;
the Items page shows the chosen thing's details beside the list or behind a Details button."""

import json
import sys
from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.runtime.collision import Collider2DComponent

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


def _demo():
    from asteria.project import Project

    return Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)


def _entity(project, name):
    for scene in project.scenes():
        for entity in scene.entities():
            if entity.name == name:
                return entity
    raise KeyError(name)


# -- collider "fit" ---------------------------------------------------------------------------
def test_collider_fit_is_custom_by_default_and_old_colliders_migrate():
    from asteria.core.migration import migrate_component_fields

    assert Collider2DComponent().fit == "custom"
    old = {"shape": "box", "width": 10.0, "height": 8.0, "ladder": False}
    assert migrate_component_fields("asteria.Collider2D", dict(old), 3, 4) == old


def test_picture_box_covers_every_opaque_pixel_of_every_frame_from_the_pivot():
    from PIL import Image

    from asteria.graphics.character_placement import picture_box

    image = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    for x in range(4, 16):  # frame 0: 12 x 10 at (4, 6)
        for y in range(6, 16):
            image.putpixel((x, y), (255, 0, 0, 255))
    for x in range(22, 38):  # frame 1: 16 x 4 at (2, 14) of its frame
        for y in range(14, 18):
            image.putpixel((x, y), (0, 255, 0, 255))
    frames = [(0, 0, 20, 20, 0.5, 1.0), (20, 0, 20, 20, 0.5, 1.0)]
    width, height, offset_x, offset_y = picture_box(image, frames)
    # frame 0 spans x 4..16 and y 6..16; frame 1 x 2..18 and y 14..18 (pivot at (10, 20))
    assert (width, height) == (16, 12)
    assert (offset_x, offset_y) == (0, -8)
    assert picture_box(Image.new("RGBA", (8, 8)), [(0, 0, 8, 8, 0.5, 1.0)]) is None


# -- the editor's Passability --------------------------------------------------------------------
def test_the_demo_objects_block_their_picture_and_people_their_feet():
    from asteria.editor.passability import passability, picture_box

    project = _demo()
    chest = _entity(project, "Starfall Chest")
    collider = chest.get(Collider2DComponent)
    assert passability(chest) == "picture"
    box = picture_box(project, DEMO, chest)
    assert box == (collider.width, collider.height, collider.offset_x, collider.offset_y)
    house = _entity(project, "Roger's House")
    assert passability(house) == "picture" and house.get(Collider2DComponent).height > 40
    assert passability(_entity(project, "Mira")) == "feet"


def test_passability_is_one_undo_step_each_way():
    from asteria.editor.passability import build_passability_command, passability, picture_box

    project = _demo()
    document = EditorDocument(project)
    chest = _entity(project, "Starfall Chest")
    box = picture_box(project, DEMO, chest)
    document.execute(build_passability_command(chest, "through", box))
    assert passability(chest) == "through" and chest.get(Collider2DComponent).is_trigger
    document.execute(build_passability_command(chest, "feet", box))
    collider = chest.get(Collider2DComponent)
    assert passability(chest) == "feet" and collider.fit == "custom"
    document.undo()
    document.undo()
    assert passability(chest) == "picture"
    assert not build_passability_command(chest, "picture", box).commands  # already so
    with pytest.raises(ValueError, match="mode"):
        build_passability_command(chest, "fly", box)


def test_a_new_feet_box_is_added_for_an_object_with_only_a_picture():
    from asteria.core import Entity
    from asteria.editor.passability import build_passability_command, passability

    entity = Entity("bush")
    assert passability(entity) == "through"
    assert not build_passability_command(entity, "through").commands
    build_passability_command(entity, "feet", (20, 30, 0, -15)).redo()
    collider = entity.get(Collider2DComponent)
    assert (collider.width, collider.height) == (12.0, 8.0) and passability(entity) == "feet"
    with pytest.raises(ValueError, match="no picture"):
        build_passability_command(entity, "picture", None)


def test_the_passability_preview_marks_the_blocking_box_in_red():
    from asteria.editor.passability import passability_preview

    project = _demo()
    image = passability_preview(project, DEMO, _entity(project, "Starfall Chest"))
    reds = sum(1 for r, g, b, _a in image.getdata() if r > 200 and g < 120 and b < 120)
    assert image.width > 100 and reds > 50


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    value = AsteriaEditorWindow(_demo())
    value.document.file_path = DEMO / "project.asteria.json"
    yield value, app
    value.document.mark_saved()
    value.close()
    app.processEvents()


def test_the_inspector_sets_and_previews_passability(window):
    from PySide6.QtWidgets import QComboBox, QLabel

    window, app = window
    chest = _entity(window.document.project, "Starfall Chest")
    window.inspector.show_entity(chest)
    combo = window.inspector._passability_combo
    assert isinstance(combo, QComboBox) and combo.currentData() == "picture"
    preview = window.inspector.findChild(QLabel, "PassabilityPreview")
    assert preview is not None and not preview.pixmap().isNull()
    combo.setCurrentIndex(0)  # Passable
    app.processEvents()
    assert chest.get(Collider2DComponent).is_trigger
    window.document.undo()
    assert not chest.get(Collider2DComponent).is_trigger


def test_the_editor_words_passability_in_chinese():
    from asteria.editor.menu_layout_widget import SlotsField
    from asteria.editor.passability import MODE_LABELS

    table = json.loads(
        (
            Path(__file__).resolve().parents[1] / "src/asteria/editor/translations/zh_TW.json"
        ).read_text(encoding="utf-8")
    )["exact"]
    words = ["Passability", "Player", "Measure the Picture Again", "Preview", "Size From"]
    words += list(MODE_LABELS.values()) + list(SlotsField.TIPS) + list(SlotsField.TIPS.values())
    assert [w for w in words if w not in table] == []


# -- the demo walks into a chest --------------------------------------------------------------
@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, str(DEMO))
    import trial_ui_tour

    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = _demo()
    value = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=960, height=540
    )
    value.open()
    trial_ui_tour.prepare(value.game)
    yield value
    value.close()


def _walk(rt, start, key, frames=90):
    from asteria.core import Transform

    pg = rt.pg
    rt._ui_mode = "field"
    transform = rt.game.player.get(Transform)
    transform.x, transform.y = start
    for _ in range(5):
        rt.step(1 / 60)
    pg.event.post(pg.event.Event(pg.KEYDOWN, key=key, mod=0, unicode="", scancode=0))
    for _ in range(frames):
        rt.step(1 / 60)
    pg.event.post(pg.event.Event(pg.KEYUP, key=key, mod=0, unicode="", scancode=0))
    rt.step(1 / 60)
    transform = rt.game.player.get(Transform)
    return transform.x, transform.y


def test_the_player_cannot_walk_into_the_chest_but_still_enters_the_house(runtime):
    chest = _entity(runtime.project, "Starfall Chest")
    collider = chest.get(Collider2DComponent)
    from asteria.core import Transform

    at = chest.get(Transform)
    bottom = at.y + collider.offset_y + collider.height / 2
    _x, y = _walk(runtime, (at.x, bottom + 36), runtime.pg.K_UP)
    assert y >= bottom  # stopped below the chest's picture, not inside it
    _walk(runtime, (608, 150), runtime.pg.K_UP)
    assert runtime.game.scene.name == "Roger's House"


# -- doll icons ---------------------------------------------------------------------------------
def test_a_slot_place_keeps_its_icon_settings():
    from asteria.presentation.menu_layout import MenuSlotPlace

    place = MenuSlotPlace("weapon", (0, 0, 10, 10))
    assert "icon_scale" not in place.to_data()  # defaults are not written
    fancy = MenuSlotPlace(
        "weapon",
        (1, 2, 30, 20),
        icon_scale=1.5,
        icon_rotate=-45,
        icon_trim=True,
        icon_fit="stretch",
    )
    again = MenuSlotPlace.from_data(fancy.to_data())
    assert again == fancy and again.icon_rotate == 315
    with pytest.raises(ValueError):
        MenuSlotPlace("weapon", (0, 0, 10, 10), icon_scale=9)
    with pytest.raises(ValueError):
        MenuSlotPlace("weapon", (0, 0, 10, 10), icon_fit="tile")


def test_a_fitted_icon_fills_its_box_by_whole_pixels(runtime):
    icon = "playable_assets/icons_7soul/W_Staff02.png"
    small = runtime.fitted_icon(icon, (32, 32))
    trimmed = runtime.fitted_icon(icon, (96, 40), trim=True)
    stretched = runtime.fitted_icon(icon, (96, 40), trim=True, fit="stretch")
    assert small.get_width() <= 32 and small.get_height() <= 32
    assert trimmed.get_width() <= 96 and trimmed.get_height() <= 40
    assert max(trimmed.get_size()) > 32  # the empty edges went: the picture grew
    assert stretched.get_size() == (96, 40)
    assert runtime.fitted_icon("", (10, 10)) is None


def test_the_slots_table_reads_the_icon_columns():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.menu_layout_widget import SlotsField
    from asteria.presentation.menu_layout import MenuSlotPlace

    QApplication.instance() or QApplication([])
    field = SlotsField()
    place = MenuSlotPlace("weapon", (4, 8, 60, 30), icon_scale=1.5, icon_trim=True)
    field.setPlaces((place,))
    assert field.places() == (place,)


def test_the_layout_preview_dresses_its_member(runtime):
    from asteria.runtime.menu_preview import MenuPreview

    game = runtime.game
    actor = game.save.rpg_state.party_active_actor_ids[0]
    MenuPreview._dress(game)
    worn = game.save.rpg_state.loadouts[actor].to_data()["equipped"]
    assert sum(1 for items in worn.values() if items) >= 4


# -- the Items page's details -----------------------------------------------------------------
def test_the_items_page_details_an_item_and_a_piece(runtime):
    runtime._open_pause_page("items")
    menu = runtime.status_menu
    menu.category = 1  # Consumables
    keys = [key for _k, key, _l, _d in menu.rows()]
    menu.row = keys.index("potion")
    detail = menu.detail()
    assert detail.name == "Potion" and "menu" in detail.description
    assert dict(detail.facts)["Use here"] == "yes"
    runtime.game.gain_equipment("w_sunbrand")
    menu.category = 4  # Weapons
    rows = menu.rows()
    assert rows and rows[0][0] == "piece" and menu.row_icons()[0]
    menu.row = 0
    piece = menu.detail()
    assert piece.facts and piece.kind
    menu.activate()
    assert menu.message == "Wear it from Equipment"


def test_an_item_with_no_menu_use_says_so_and_a_potion_works(runtime):
    runtime._open_pause_page("items")
    menu = runtime.status_menu
    keys = [key for _k, key, _l, _d in menu.rows()]
    menu.row = keys.index("card_acolyte_item")
    assert menu.activate() is None
    assert menu.message == "Acolyte Card can't be used from the menu"
    menu.row = [key for _k, key, _l, _d in menu.rows()].index("potion")
    assert menu.activate().used  # a member who never fought has a snapshot made for it


def test_item_details_can_be_a_panel_a_button_or_off(runtime):
    from asteria.rpg.menu_rules import MenuRules

    assert MenuRules.from_data({"rules_id": "m", "item_details": "button"}).item_details == (
        "button"
    )
    with pytest.raises(ValueError, match="item_details"):
        MenuRules("m", item_details="popup")
    runtime.game.set_locale("zh-TW")
    runtime._open_pause_page("items")
    menu = runtime.status_menu
    runtime.pointer.drawn.clear()
    with runtime.menu_fit():
        runtime._draw_status_menu()
    assert menu.details_mode == "panel"
    from asteria.rpg.menu_pages import MenuBlock, MenuPage

    pages = runtime.project.rpg_database.menu_pages  # D96: the Items page's Item List block
    block = pages["items"].blocks[0]
    data = {**block.to_data(), "item_details": "button"}
    pages["items"] = MenuPage("items", "Items", blocks=(MenuBlock.from_data(data),))
    runtime._open_pause_page("items")
    menu = runtime.status_menu
    assert menu.details_mode == "button"
    runtime.pointer.drawn.clear()
    with runtime.menu_fit():
        runtime._draw_status_menu()
    assert any(s.key == "d" for s in runtime.pointer.drawn)
    pg = runtime.pg
    event = pg.event.Event(pg.KEYDOWN, key=pg.K_d, mod=0, unicode="d", scancode=0)
    runtime._status_input([event])
    assert menu.details_open
    event = pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE, mod=0, unicode="", scancode=0)
    runtime._status_input([event])
    assert not menu.details_open and runtime._ui_mode == "status"
