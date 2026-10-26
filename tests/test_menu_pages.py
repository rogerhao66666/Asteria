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
    entries = dict(p if isinstance(p, tuple) else (p, p) for p in api.references("pause_entries"))
    assert entries["items"] == "Items" and "status" in entries
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
    editor = window.game_systems_editor
    api = editor.controller
    api.create("menu_rules", RULES)
    editor.set_kind("menu_rules")
    editor.refresh("pages")
    assert editor.apply(), editor.status.text()
    assert api.get("menu_rules", "pages") == RULES
    table = editor.form.widgets["item_categories"]
    table.set_rows(
        [
            *table.values(),
            {"category_id": "keys", "display_name": "Keys", "tags": ["key"], "icon_id": ""},
        ]
    )
    assert editor.apply(), editor.status.text()
    assert [c.category_id for c in api.get("menu_rules", "pages").item_categories] == [
        "all",
        "potions",
        "keys",
    ]


def test_the_editor_words_the_new_form_in_chinese():
    import json

    table = json.loads(
        (
            Path(__file__).resolve().parents[1] / "src/asteria/editor/translations/zh_TW.json"
        ).read_text(encoding="utf-8")
    )
    words = table if "messages" not in table else table["messages"]
    labels = [f.label for f in FORMS["menu_rules"]]
    labels += ["Menu Pages (status, items)", "Data: menu pages (item tabs and filters)"]
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
    assert options[:6] == ["resume", "status", "items", "equipment", "enhance", "skills"]
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
        "trial_menu", pause_entries=("items", "pets", "resume", "save")
    )
    options, _icons, _keys = MenuPagesMixin._pause_options(host)
    assert [k for k, _ in options] == ["items", "pets", "resume", "save", "entry:camp"]


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
    menu.game, menu.rules = Game, None
    tabs = [c.category_id for c in menu.categories()]
    assert tabs[0] == "all"
    assert tabs == (["all", "item", "equipment"] if db.items and db.equipment else ["all"])
    assert [f.filter_id for f in menu.filters()] == ["usable"]
