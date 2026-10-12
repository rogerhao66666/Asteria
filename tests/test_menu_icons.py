"""AST-07: items and equipment carry an optional icon (any project icon asset, a cell of an atlas, a legacy
asset or a PNG path); the game's shop, item and equipment menus draw it; the Database editor offers the
project's icons; an MV import keeps each record's IconSet icon."""

from pathlib import Path

import pytest

from asteria.rpg import EquipmentDefinition, ItemDefinition
from asteria.runtime.menu_icons import icon_source, record_icon_id

REFERENCE = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"


def _reference():
    from asteria.editor import EditorDocument
    from asteria.project import Project

    return Project.load_json(REFERENCE / "project.asteria.json", EditorDocument().component_registry)


def test_icon_id_is_optional_data_and_round_trips():
    plain = ItemDefinition("leaf", "Leaf")
    assert "icon_id" not in plain.to_data()  # nothing written when unset: older data stays byte-identical
    item = ItemDefinition.from_data(ItemDefinition("leaf", "Leaf", icon_id="icon.leaf").to_data())
    assert item.icon_id == "icon.leaf"
    sword = EquipmentDefinition.from_data(EquipmentDefinition("sword", slot="weapon", icon_id="x.png").to_data())
    assert sword.icon_id == "x.png" and "icon_id" not in EquipmentDefinition("axe", slot="weapon").to_data()


def test_icon_sources_atlas_cell_legacy_record_and_plain_path():
    project = _reference()
    db = project.rpg_database
    assert all(i.icon_id for i in db.items.values()) and all(e.icon_id for e in db.equipment.values())
    uri, region = icon_source(project, db.items["ether_leaf"].icon_id)
    assert uri == "playable_assets/item_icons.png" and region[2:] == (18, 18)  # one cell of the atlas
    assert icon_source(project, "playable_assets/fx_heal.png") == ("playable_assets/fx_heal.png", None)
    assert icon_source(project, "no_such_icon") is None and icon_source(project, "") is None
    assert record_icon_id(project, "candidate", "weapon_01") == "icon.weapon_01"


def test_the_shop_and_the_item_and_equipment_menus_draw_the_icons(runtime):
    from test_game_menus import _add_content

    _add_content(runtime.project)
    drawn = []
    original = runtime._draw_icon

    def record(icon_id, x, y, size=22):
        shown = original(icon_id, x, y, size)
        drawn.append((icon_id, shown))
        return shown

    runtime._draw_icon = record
    icon = runtime.icon_image("icon.ether_leaf", 22)
    assert icon is not None and max(icon.get_size()) == 22  # the 18x18 cell, scaled to fit
    assert runtime.icon_image("no_such_icon") is None  # a missing icon shows the name only
    game = runtime.game
    game.open_shop("apothecary")
    runtime._ui_mode = "field"
    runtime._frame([], 0.016)
    runtime._frame([], 0.016)  # the first frame opens the shop, the next draws it
    assert runtime._ui_mode == "shop"
    assert ("icon.ether_leaf", True) in drawn  # the buy tab lists ether_leaf (boss_emblem is sell-only)
    game.save.rpg_state.inventory.add("ether_leaf", 2)
    game.save.rpg_state.inventory.add("weapon_02", 1)
    runtime.open_status_menu(back="field")
    menu = runtime.status_menu
    drawn.clear()
    menu.tab = "items"
    runtime._draw_status_menu()
    assert ("icon.ether_leaf", True) in drawn
    menu.tab = "equipment"
    drawn.clear()
    runtime._draw_status_menu()
    icons = dict(zip([r[1] for r in menu.rows()], menu.row_icons(), strict=True))
    assert icons.get("weapon_02") == "icon.weapon_02" and ("icon.weapon_02", True) in drawn
    assert any(i for k, i in icons.items() if k == "weapon")  # a slot shows its equipped item's icon
    runtime.release_resource_scope("field")
    assert runtime._icon_cache == {}


def test_the_database_editor_offers_the_project_icons_and_applies_a_choice():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QComboBox

    from asteria.editor import EditorDocument
    from asteria.editor.authoring_hub_widget import AdapterFamilyWidget
    from asteria.editor.integrated_authoring import IntegratedAuthoringControllers

    QApplication.instance() or QApplication([])
    project = _reference()
    document = EditorDocument(project)
    document.file_path = REFERENCE / "project.asteria.json"
    family = AdapterFamilyWidget(
        "Database", IntegratedAuthoringControllers(document).rpg_categories(), document=document
    )
    family.category.setCurrentIndex(family.category.findData("items"))
    family.select_ids(["ether_leaf"])
    tree = family.editor
    combo = None
    for i in range(tree.topLevelItem(0).childCount()):
        child = tree.topLevelItem(0).child(i)
        if child.data(0, 0x0100) == ("icon_id",):
            combo = tree.itemWidget(child, 1)
    assert isinstance(combo, QComboBox) and combo.currentText() == "icon.ether_leaf"
    assert combo.findText("icon.weapon_01") > 0 and not combo.itemIcon(combo.findText("icon.weapon_01")).isNull()
    combo.setCurrentText("icon.moon_shard")
    family.apply_selected()
    assert project.rpg_database.items["ether_leaf"].icon_id == "icon.moon_shard"
    document.undo()
    assert project.rpg_database.items["ether_leaf"].icon_id == "icon.ether_leaf"


@pytest.mark.mv_reference
def test_an_mv_import_keeps_each_records_iconset_icon():
    from asteria.assets.local_reference import discover_mv_projects, resolve_rpg_maker_mv_root
    from asteria.assets.rpg_maker_mv_project import RPGMakerMVProjectImporter

    repo = Path(__file__).resolve().parents[1]
    try:
        layout = discover_mv_projects(resolve_rpg_maker_mv_root(repo))[0]
    except (IndexError, FileNotFoundError, ValueError):
        pytest.skip("no local RPG Maker MV reference project")
    project = RPGMakerMVProjectImporter.import_project(layout, map_ids=(1,)).project
    with_icons = [i for i in project.rpg_database.items.values() if i.icon_id]
    assert with_icons
    uri, region = icon_source(project, with_icons[0].icon_id)
    assert uri.endswith("IconSet.png") and region[2:] == (32, 32)
    equipped = [e for e in project.rpg_database.equipment.values() if e.icon_id]
    assert equipped and all(e.icon_id.startswith("mv.icon.") for e in equipped)


def test_the_asset_list_thumbnail_of_an_icon_is_its_cell():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.asset_thumbnails import ImageCache, canonical_asset_thumbnail

    QApplication.instance() or QApplication([])
    project = _reference()
    document = EditorDocument(project)
    document.file_path = REFERENCE / "project.asteria.json"
    cache = ImageCache()
    leaf = canonical_asset_thumbnail(document, project.assets.resolve("icon.ether_leaf"), cache)
    sword = canonical_asset_thumbnail(document, project.assets.resolve("icon.weapon_01"), cache)
    assert leaf is not None and sword is not None
    assert leaf.pixmap(18, 18).toImage() != sword.pixmap(18, 18).toImage()  # each shows its own cell


def test_equipment_carried_in_the_bag_shows_its_name_and_icon_in_the_items_tab(runtime):
    game = runtime.game
    game.save.rpg_state.inventory.add("weapon_03", 1)
    runtime.open_status_menu(back="field")
    menu = runtime.status_menu
    menu.tab = "items"
    rows = dict(
        zip([r[1] for r in menu.rows()], zip([r[2] for r in menu.rows()], menu.row_icons(), strict=True), strict=True)
    )
    assert rows["weapon_03"] == ("Weapon 03", "icon.weapon_03")
