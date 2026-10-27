"""D96: the game menu's pages are records of blocks (Game Systems ▸ Menu Pages), each block a
kind with its own settings and a place; Status and Items are two such pages, and a project's
own page is a pause entry of its own."""

import sys
from pathlib import Path

import pytest

from asteria.rpg.menu_pages import MenuBlock, MenuPage, default_pages, menu_pages, page_entries
from asteria.rpg.menu_rules import ItemCategory, MenuRules

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


def test_a_block_keeps_only_its_own_kinds_settings():
    tabs = (ItemCategory("keys", "Keys", ("key",)),)
    block = MenuBlock("profile", "left", 190, item_categories=tabs, stat_graph="attributes")
    assert block.item_categories == () and block.stat_graph == ""
    assert block.to_data() == {"kind": "profile", "place": "left", "height": 190}
    bag = MenuBlock("item_list", item_categories=tabs, item_details="button")
    assert MenuBlock.from_data(bag.to_data()) == bag
    with pytest.raises(ValueError, match="kind"):
        MenuBlock("map")
    with pytest.raises(ValueError, match="place"):
        MenuBlock("profile", "middle")


def test_a_page_reads_its_settings_from_its_blocks():
    rules = MenuRules("old", stat_graph="attributes", item_details="off")
    pages = default_pages(rules)  # a project written before D96: its settings fill the pages
    assert [b.kind for b in pages["status"].blocks] == ["profile", "stat_points", "stat_details"]
    assert pages["status"].rules().stat_graph == "attributes"
    assert pages["items"].rules().item_details == "off"
    assert pages["items"].interactive() == "item_list"
    assert pages["status"].interactive() == "stat_points"
    page = MenuPage.from_data(pages["status"].to_data())
    assert page == pages["status"]
    with pytest.raises(ValueError, match="unknown pause entries"):
        MenuRules("m", pause_entries=("pages",))
    assert MenuRules("m", pause_entries=("status", "page:keys")).pause_entries[-1] == "page:keys"


def test_the_blocks_are_laid_out_in_their_columns():
    from asteria.runtime.playtest.menu_pages import menu_page_boxes

    status = default_pages()["status"]
    boxes = [box for _block, box in menu_page_boxes(status.blocks, (44, 84, 1192, 536))]
    left_w = min(560, int((1192 - 24) * 0.45))
    assert boxes[0] == (44, 84, left_w, 190)  # the profile: its own height
    assert boxes[1] == (44, 84 + 202, left_w, 536 - 202)  # the stat table: the rest
    assert boxes[2] == (44 + left_w + 20, 84, 1192 - left_w - 20, 536)  # details: the right
    two = (MenuBlock("item_list"), MenuBlock("profile"))
    full = [box for _b, box in menu_page_boxes(two, (0, 0, 800, 412))]
    assert full == [(0, 0, 800, 200), (0, 212, 800, 200)]  # no columns: they share the page


# -- the Full Verification demo -----------------------------------------------------------------
@pytest.fixture
def host(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, str(DEMO))
    import trial_ui_tour

    from asteria.editor import EditorDocument
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


def test_the_demo_writes_its_pages_as_blocks(host):
    db = host.project.rpg_database
    assert sorted(db.menu_pages) == ["items", "materials", "status"]
    (rules,) = db.menu_rules.values()
    assert not rules.item_categories and not rules.stat_lines  # each page's own now
    assert page_entries(db) == ["page:materials"]
    assert menu_pages(db)["status"].block("stat_details").stat_lines


def test_a_page_of_the_projects_own_opens_from_the_pause_menu(host):
    words = dict(host._pause_menu.labels(host.game.tr))
    assert words["page:materials"] == "Materials"
    assert not host._pause_menu.icons.get("page:materials")  # D98: no icon in the demo
    host._open_pause_page("page:materials")
    menu = host.status_menu
    assert host._ui_mode == "status" and menu.single and menu.page_id == "materials"
    assert menu.tab == "items"  # its Item List takes the cursor
    assert [menu.category_name(c) for c in menu.categories()] == ["Materials"]
    db = host.project.rpg_database
    assert menu.rows() and all("material" in db.items[k].tags for _k, k, _l, _d in menu.rows())
    host.pointer.drawn.clear()
    with host.menu_fit():
        host._draw_status_menu()
    assert len(host.pointer.drawn) > len(menu.rows())  # its rows and tabs take clicks


def test_a_page_left_out_of_the_order_keeps_its_place_and_a_hidden_one_is_not_shown(host):
    from asteria.runtime.playtest.menu_pages import MenuPagesMixin

    db = host.project.rpg_database
    (rule_id,) = db.menu_rules
    db.menu_rules[rule_id] = MenuRules(rule_id, pause_entries=("page:materials", "items"))
    options, _icons, _keys = MenuPagesMixin._pause_options(host)
    keys = [k for k, _ in options]
    assert keys.index("page:materials") < keys.index("items")  # the author's order
    db.menu_rules[rule_id] = MenuRules(rule_id, pause_entries=("items", "resume"))
    options, _icons, _keys = MenuPagesMixin._pause_options(host)
    assert [k for k, _ in options][:2] == ["items", "page:materials"]  # its place: after Items
    db.menu_rules[rule_id] = MenuRules(rule_id, pause_hidden=("page:materials",))
    options, _icons, _keys = MenuPagesMixin._pause_options(host)
    assert "page:materials" not in [k for k, _ in options]
