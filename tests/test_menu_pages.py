"""D87: the pause menu's pages (Status, Items, Equipment, Skills on their own), the Status
page's stat table with +, the Items page's tabs and filters, and Game Systems ▸ Menu Pages."""

import sys
from pathlib import Path

import pytest
from test_session_events import _project

from asteria.editor import EditorDocument
from asteria.editor.game_systems_authoring import FORMS, GameSystemsAuthoringController
from asteria.rpg.menu_rules import ItemCategory, ItemFilter, MenuRules, menu_rules

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
RULES = MenuRules(
    "pages",
    "Pages",
    pause_entries=("resume", "items", "status", "quit"),
    stat_graph="attributes",
    stat_rows=("power", "speed"),
    item_categories=(
        ItemCategory("all", "All"),
        ItemCategory("potions", "Potions", ("potion",), "icon:p"),
    ),
    item_filters=(
        ItemFilter("usable", "Usable", usable=True),
        ItemFilter("rare", "Rare", ("rare",)),
    ),
)


def test_menu_rules_round_trip_and_refuse_bad_data():
    assert MenuRules.from_data(RULES.to_data()) == RULES
    with pytest.raises(ValueError, match="unknown pause entries"):
        MenuRules("m", pause_entries=("status", "dance"))
    with pytest.raises(ValueError, match="the same"):
        MenuRules("m", item_categories=(ItemCategory("a"), ItemCategory("a")))
    assert ItemCategory("all").holds(("x",)) and not RULES.item_categories[1].holds(("x",))
    assert RULES.item_filters[0].keeps((), True) and not RULES.item_filters[0].keeps((), False)
    assert RULES.item_filters[1].keeps(("rare", "x"), False)


def _controller():
    document = EditorDocument(_project())
    return document, GameSystemsAuthoringController(document)


def test_menu_pages_are_a_game_systems_record_that_survives_the_form():
    document, api = _controller()
    api.create("menu_rules", RULES)
    data = api.form_data("menu_rules", "pages")
    assert {f.key for f in FORMS["menu_rules"]} <= set(data)
    api.edit("menu_rules", "pages", data)
    assert api.get("menu_rules", "pages") == RULES
    from asteria.rpg.actors import RpgDatabase

    restored = RpgDatabase.from_data(document.project.rpg_database.to_data())
    assert menu_rules(restored) == RULES
    entries = {e: (name, why_not) for e, name, why_not in api.references("pause_entries")}
    assert entries["items"] == ("Items", "") and "status" in entries
    assert entries["pets"] == ("Pets", "the game has pet species")  # D97: greyed, and why
    assert api.references("stat_graphs")[0] == "-"


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    value = AsteriaEditorWindow(_project())
    yield value
    value.document.mark_saved()
    value.close()
    app.processEvents()


def test_the_menu_pages_form_shows_and_applies(window):
    """D96: a page's blocks are a table; an Item List block shows its tabs, filters and
    details, and only those."""
    from asteria.rpg.menu_pages import MenuBlock, MenuPage

    page = MenuPage(
        "bag",
        "Bag",
        blocks=(
            MenuBlock("profile", "left", 190),
            MenuBlock("item_list", "right", item_categories=RULES.item_categories),
        ),
    )
    editor = window.game_systems_editor
    api = editor.controller
    api.create("menu_pages", page)
    editor.set_kind("pause_menu")  # D97: a page is a row of the Pause Menu
    editor.refresh("page:bag")
    assert editor.apply(), editor.status.text()
    assert api.get("menu_pages", "bag") == page
    blocks = editor.pause.form.widgets["blocks"]
    assert [blocks.list.item(i).text() for i in range(blocks.list.count())] == [
        "Profile  ·  Left",
        "Item List  ·  Right",
    ]
    blocks.list.setCurrentRow(1)
    form = blocks.detail
    shown = {k for k, row in form._rows.items() if id(row) not in form.grid._hidden}
    assert {"item_categories", "item_filters", "item_details"} <= shown
    assert not shown & {"stat_graph", "stat_columns", "stat_lines"}  # another kind's
    tabs = form.widgets["item_categories"]
    tabs.set_rows(
        [
            *tabs.values(),
            {"category_id": "keys", "display_name": "Keys", "tags": ["key"], "icon_id": ""},
        ]
    )
    blocks.move_row(-1)  # the bag first
    assert editor.apply(), editor.status.text()
    saved = api.get("menu_pages", "bag")
    assert [b.kind for b in saved.blocks] == ["item_list", "profile"]
    assert [c.category_id for c in saved.blocks[0].item_categories] == ["all", "potions", "keys"]


def test_the_editor_words_the_new_form_in_chinese():
    import json

    from asteria.editor.game_systems_authoring import _MENU_BLOCK

    table = json.loads(
        (
            Path(__file__).resolve().parents[1] / "src/asteria/editor/translations/zh_TW.json"
        ).read_text(encoding="utf-8")
    )
    words = table if "messages" not in table else table["messages"]
    labels = [f.label for f in (*FORMS["menu_rules"], *FORMS["menu_pages"], *_MENU_BLOCK)]
    labels += ["Pause Menu", "Menu Pages", "Data: menu pages (item tabs and filters)"]
    labels += ["Profile", "Stat Points", "Stat Details", "Item List", "Left", "Right", "Full"]
    missing = [w for w in labels if w not in json.dumps(words, ensure_ascii=False)]
    assert not missing, missing


# -- the pages in the Full Verification demo -------------------------------------------------
@pytest.fixture
def host(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, str(DEMO))
    import trial_ui_tour

    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=960, height=540
    )
    runtime.open()
    trial_ui_tour.prepare(runtime.game)
    yield runtime
    runtime.close()


def test_status_items_equipment_and_skills_are_entries_of_their_own(host):
    options = [key for key, _label in host._pause_menu.options]
    assert options[:7] == [
        *("resume", "status", "items"),
        "page:materials",  # D96: the demo's own page, after Items
        *("equipment", "enhance", "skills"),
    ]
    assert options.index("entry:camp") == options.index("settings") - 1
    words = dict(host._pause_menu.labels(host.game.tr))
    assert words["status"] == "Status" and words["items"] == "Items"
    host._open_pause_page("skills")  # the demo has skill trees: the tree, back to the menu
    assert host._ui_mode == "skills" and host._skill_tree.back == "pause"
    host._open_pause_page("equipment")
    assert host._ui_mode == "equipment"
    host._open_pause_page("items")
    assert host._ui_mode == "status" and host.status_menu.single
    host.status_menu.next_tab()
    assert host.status_menu.tab == "items"  # a page of its own has no tabs to change to


def test_menu_pages_order_the_pause_menu(host):
    from asteria.runtime.playtest.menu_pages import MenuPagesMixin

    host.project.rpg_database.menu_rules["trial_menu"] = MenuRules(
        "trial_menu", pause_entries=("items", "pets", "resume"), pause_hidden=("status", "quit")
    )
    options, _icons, _keys = MenuPagesMixin._pause_options(host)
    keys = [k for k, _ in options]
    listed = [k for k in keys if k in ("items", "pets", "resume")]
    assert listed == ["items", "pets", "resume"]  # the author's order
    assert keys[:2] == ["items", "page:materials"]  # left out: its place, after Items
    assert "status" not in keys and "quit" not in keys  # hidden
    assert keys[keys.index("settings") - 1] == "entry:camp"  # its place: before Settings
    old = MenuRules.from_data(  # version 1: the order showed only the entries it listed
        {"rules_id": "m", "version": 1, "pause_entries": ["items", "resume"]}
    )
    assert "status" in old.pause_hidden and "items" not in old.pause_hidden


def test_the_status_page_raises_a_stat_with_its_plus(host):
    host._open_pause_page("status")
    menu = host.status_menu
    rows = menu.stat_rows()
    assert [r.stat_id for r in rows] == [
        "str",
        "dex",
        "int",
        "luk",
        "vit",
        "vitality",
        "technique",
    ]
    assert menu.stat_points()[0][1] == 5.0
    before = rows[0].value
    assert menu.activate() is True  # Enter on the first row: +1 STR
    assert menu.stat_rows()[0].value == before + 1 and menu.stat_rows()[0].rank == 1
    assert menu.stat_points()[0][1] == 4.0
    assert [s for s, _label, _value in menu.detail_rows()][:2] == ["power", "magic"]
    allocation = host.game.save.rpg_state.progression_allocations["hero_01"]
    allocation.balances["stat_points"] = 0.0
    assert menu.allocate_stat("attr_dex") is False and "no points left" in menu.message


def test_the_items_page_has_tabs_and_filters(host):
    host._open_pause_page("items")
    menu = host.status_menu
    names = [menu.category_name(c) for c in menu.categories()]
    assert names == ["All", "Consumables", "Throwables", "Materials", "Weapons", "Armour"]
    everything = len(menu.rows())
    menu.next_category()
    consumables = {key for _k, key, _l, _d in menu.rows()}
    db = host.project.rpg_database
    assert consumables and all(
        "consumable" in db.items[k].tags
        or "potion" in db.items[k].tags
        or "cure" in db.items[k].tags
        or "concoction" in db.items[k].tags
        for k in consumables
    )
    menu.next_filter()  # usable now: the potions (D88 gave them a menu use)
    assert {key for _k, key, _l, _d in menu.rows()} == {"potion", "hi_potion"}
    menu.next_filter()  # potions
    assert {key for _k, key, _l, _d in menu.rows()} <= consumables and menu.rows()
    menu.next_filter()
    menu.next_filter()  # past the last filter: none again
    assert menu.filter == -1 and len(menu.rows()) == len(consumables)
    menu.category = 0
    assert len(menu.rows()) == everything


def test_the_pages_draw_fitted_in_chinese_with_clicks_where_they_show(host):
    host.game.set_locale("zh-TW")
    host._open_pause_page("status")
    host.pointer.drawn.clear()
    with host.menu_fit():
        host._draw_status_menu()
    assert all(
        x + w <= 960 and y + h <= 540
        for (x, y, w, h), *_ in [(s.rect,) for s in host.pointer.drawn]
    )
    plus = [s for s in host.pointer.drawn if s.key == "return"]
    assert len(plus) == 7  # one + per stat (STR DEX INT LUK VIT HP MP)
    words = dict(host._pause_menu.labels(host.game.tr))
    assert words["status"] == "狀態" and words["items"] == "道具" and words["skills"] == "技能"


def test_default_item_tabs_without_menu_pages():
    from asteria.runtime.status_menu import StatusMenu

    class Game:
        project = _project()
        tr = staticmethod(lambda key, english, **values: english.format(**values))

    db = Game.project.rpg_database
    db.menu_rules.clear()
    menu = StatusMenu.__new__(StatusMenu)
    menu.game, menu.pause_rules, menu.pages, menu.page_id, menu.tab = Game, None, {}, "", "items"
    tabs = [c.category_id for c in menu.categories()]
    assert tabs[0] == "all"
    assert tabs == (["all", "item", "equipment"] if db.items and db.equipment else ["all"])
    assert [f.filter_id for f in menu.filters()] == ["usable"]


def test_the_pause_menu_lists_every_entry_to_tick_and_move(window):
    """D97: Game Systems ▸ Pause Menu lists the whole menu in the game's order; an unticked
    entry is hidden, a moved one keeps its new place, and one the game cannot show is grey."""
    from PySide6.QtCore import QModelIndex, Qt

    editor = window.game_systems_editor
    api = editor.controller
    assert not api.ids("menu_rules")  # made when the order is first changed
    editor.set_kind("pause_menu")
    order = editor.pause.order
    rows = [order.list.item(i) for i in range(order.list.count())]
    assert [r.data(Qt.UserRole) for r in rows][:3] == ["resume", "status", "items"]
    assert all(r.checkState() == Qt.Checked for r in rows)
    pets = next(r for r in rows if r.data(Qt.UserRole) == "pets")
    assert "pet species" in pets.toolTip()  # grey: the game has no pet species
    assert order.order() == []  # the engine's order: nothing written
    rows[1].setCheckState(Qt.Unchecked)  # hide Status: saved at once
    assert api.get("menu_rules", "pause").pause_hidden == ("status",)
    assert order.list.model().moveRow(QModelIndex(), 2, QModelIndex(), 0)  # Items to the top
    rules = api.get("menu_rules", "pause")
    assert rules.pause_entries[:3] == ("items", "resume", "status")
    assert rules.pause_hidden == ("status",)
    order._engine_order()  # Back to the Engine's Order: the ticks stay
    assert order.order() == [] and order.hidden() == ["status"]


def test_the_pause_menu_adds_and_removes_pages_and_event_entries(window):
    """D97: New Page / New Event Entry add a row named by the author (its id made from the
    name), the row's page edits it, and Delete takes it out of the menu and its order;
    Status, Items and the other built-in entries cannot be deleted, a changed Status page
    goes back to the engine's."""
    from PySide6.QtCore import Qt

    from asteria.editor.pause_menu_widget import _new_id

    editor = window.game_systems_editor
    api = editor.controller
    editor.set_kind("pause_menu")
    pause = editor.pause
    assert pause.new_page("Key Items") and pause.selected == "page:key_items"
    assert api.get("menu_pages", "key_items").display_name == "Key Items"
    assert "page_id" not in pause.form.widgets  # the id is made from the name
    pause.form.widgets["display_name"].setText("Keys")
    assert editor.apply(), editor.status.text()
    assert pause.order.list.currentItem().text() == "Page: Keys"
    assert pause.new_entry("Make Camp") and pause.selected == "entry:make_camp"
    assert {"entry_id", "order"}.isdisjoint(pause.form.widgets)  # its place: the list's
    pause.order.list.item(0).setCheckState(Qt.Unchecked)  # the order is written now
    assert pause.delete_record("menu_entries", "make_camp")
    assert "make_camp" not in api.ids("menu_entries")
    assert all("make_camp" not in e for e in api.get("menu_rules", "pause").pause_entries)
    pause.refresh("status")
    assert pause.form is not None and "status" not in api.ids("menu_pages")  # the engine's
    pause.form.widgets["display_name"].setText("Member")
    assert pause.apply() and api.get("menu_pages", "status").display_name == "Member"
    assert pause.delete_record("menu_pages", "status")  # Back to the Engine's Page
    pause.refresh("settings")
    assert pause.form is None  # a built-in screen: nothing to edit, only what it opens
    assert _new_id("鑰匙", (), "page") == "page" and _new_id("A b", ("a_b",), "x") == "a_b2"
