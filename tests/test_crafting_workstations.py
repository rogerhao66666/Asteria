"""Workstations and the crafting screen (U4).

A workstation is data: its tabs pick recipes by tag, it may show undiscovered recipes as ???,
limit how many are made at once and add a disassembly tab. The screen lists each tab's recipes
with their products' icons, shows materials held / needed, the success chance and quality
tiers, makes several at once and breaks items down. The demo's Alchemy Table and Forge stand in
Hearthfold; the editor lists workstations and gives each one its own menu layout.
"""

import sys
from pathlib import Path

import pytest

from asteria.rpg.composition import (
    CompositionOutput,
    CompositionRecipeDefinition,
    CompositionSelection,
)
from asteria.rpg.workstations import WorkstationCategory, WorkstationDefinition

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))


def _recipe(recipe_id, tags):
    return CompositionRecipeDefinition(
        recipe_id,
        selections=(CompositionSelection("a", ("x",)),),
        outputs=(CompositionOutput("y"),),
        tags=tags,
    )


def test_a_workstation_goes_to_data_and_back_and_sorts_recipes_into_tabs():
    station = WorkstationDefinition(
        "forge",
        "Forge",
        categories=(
            WorkstationCategory("ingots", "Ingots", ("smelt",)),
            WorkstationCategory("rest", "Everything else"),
        ),
        max_quantity=10,
        disassembly=True,
        craft_sound="heal",
    )
    assert WorkstationDefinition.from_data(station.to_data()) == station
    assert station.category_of(_recipe("a", ("smelt",))) == "ingots"
    assert station.category_of(_recipe("b", ("bomb",))) == "rest"  # the tab without tags
    with pytest.raises(ValueError):
        WorkstationDefinition("x", max_quantity=0)
    with pytest.raises(ValueError):
        WorkstationDefinition("x", categories=(WorkstationCategory("a"), WorkstationCategory("a")))


@pytest.fixture
def host(monkeypatch):
    import real_window

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    if not real_window.enabled():
        monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
        monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("ASTERIA_MUTE", "1")
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=1280, height=720
    )
    runtime.open()
    yield runtime
    runtime.close()


def _key(host, key, frames=1):
    pg = host.pg
    for kind in (pg.KEYDOWN, pg.KEYUP):
        pg.event.post(pg.event.Event(kind, key=key, mod=0, unicode="", scancode=0))
        host._frame(pg.event.get(), 1 / 60)
    for _ in range(frames):
        host._frame([], 1 / 60)


def test_the_alchemy_table_has_tabs_icons_hidden_recipes_and_makes_several(host):
    pg, game = host.pg, host.game
    inventory = game.save.rpg_state.inventory
    inventory.add("healing_herb", 5)
    inventory.add("bat_wing", 2)
    host._open_crafting("alchemy", back="field")
    screen = host._crafting_screen
    host._frame([], 1 / 60)
    assert [t for t, _w in screen.tabs()] == ["potions", "gems", "fusion", "cards", "disassemble"]
    rows = {r.recipe_id: r for r in screen.rows()}
    potion = rows["brew_potion"]
    assert potion.known and potion.icon_id.endswith("P_Red01.png") and potion.makes == 2
    elixir = rows["brew_elixir"]
    assert not elixir.known and elixir.name == "???"  # waits to be discovered
    assert list(rows).index("brew_elixir") == len(rows) - 1  # the hidden ones come last
    screen.index = list(rows).index("brew_potion")
    _key(host, pg.K_RIGHT)
    _key(host, pg.K_RIGHT)
    _key(host, pg.K_RIGHT)
    assert screen.quantity == 2  # the bat wings allow two
    texts = [w for w, _c, _s in screen.detail_lines()]
    assert any("2 / 2" in t for t in texts) and any("100%" in t for t in texts)
    potions = inventory.count("potion")
    _key(host, pg.K_RETURN)
    assert inventory.count("potion") == potions + 4 and inventory.count("bat_wing") == 0
    assert screen.message.startswith("Crafted") and screen.quantity == 1
    hi = rows["brew_hi_potion"]
    screen.index = list(rows).index("brew_hi_potion")
    texts = [w for w, _c, _s in screen.detail_lines()]
    assert hi.qualities and any("Masterwork 90%+" in t for t in texts)
    _key(host, pg.K_TAB)
    assert screen.page == "gems"
    assert all(r.recipe_id.startswith("craft_") for r in screen.rows())
    host.capture()


def test_the_disassembly_tab_breaks_items_down(host):
    game = host.game
    inventory = game.save.rpg_state.inventory
    inventory.add("ruby_item", 2)
    host._open_crafting("alchemy", back="field")
    screen = host._crafting_screen
    screen.tab = [t for t, _w in screen.tabs()].index("disassemble")
    rows = [r.item_id for r in screen.rows()]
    assert "ruby_item" in rows
    screen.index = rows.index("ruby_item")
    owned = inventory.count("ruby_item")
    screen.change_quantity(owned + 5)
    assert screen.quantity == owned  # no more than the bag holds
    ore = inventory.count("iron_ore")
    screen.confirm()
    assert inventory.count("ruby_item") == 0 and inventory.count("iron_ore") == ore + owned


def test_the_forge_limits_how_many_and_a_station_without_data_still_opens(host):
    game = host.game
    inventory = game.save.rpg_state.inventory
    inventory.add("iron_ore", 40)
    inventory.add("coal", 40)
    host._open_crafting("forge", back="field")
    screen = host._crafting_screen
    assert [t for t, _w in screen.tabs()] == ["ingots", "throwing", "orbs"]
    screen.tab = 1
    rows = [r.recipe_id for r in screen.rows()]
    screen.index = rows.index("forge_iron_ball")
    screen.change_quantity(50)
    assert screen.quantity == 10  # the forge's own limit
    gold = next(r for r in CraftingRows(screen, 0) if r.recipe_id == "smelt_gold")
    assert gold.chance == pytest.approx(0.8)
    screen.tab = 2
    assert all(not r.known for r in screen.rows())  # both orbs wait to be discovered
    host._crafting_screen.close()
    from asteria.runtime.crafting_screen import CraftingScreen

    bare = CraftingScreen(game, "nowhere")
    assert [t for t, _w in bare.tabs()] == [""]  # one tab of every recipe it can make
    assert bare.station_name() == "Nowhere"


def CraftingRows(screen, tab):  # noqa: N802 - reads like the rows of a tab
    screen.tab = tab
    return screen.rows()


def test_the_editor_lists_workstations_and_each_has_its_own_layout(monkeypatch):
    monkeypatch.setenv("ASTERIA_MUTE", "1")
    from asteria.editor import EditorDocument
    from asteria.editor.game_systems_authoring import GameSystemsAuthoringController
    from asteria.editor.menu_layout_authoring import MenuLayoutAuthoringController
    from asteria.editor.storage import load_document
    from asteria.runtime.menu_preview import MenuPreview

    document = EditorDocument()
    load_document(document, str(DEMO / "project.asteria.json"))
    systems = GameSystemsAuthoringController(document)
    assert systems.ids("workstations") == ("alchemy", "forge")
    data = systems.form_data("workstations", "forge")
    data["max_quantity"] = 5
    systems.edit("workstations", "forge", systems.decode("workstations", data))
    assert document.project.rpg_database.workstations["forge"].max_quantity == 5
    document.undo()
    assert document.project.rpg_database.workstations["forge"].max_quantity == 10
    layouts = MenuLayoutAuthoringController(document)
    ids = [s for s, _t, _c in layouts.screens()]
    assert ids[ids.index("crafting") + 1 : ids.index("crafting") + 3] == [
        "crafting.alchemy",
        "crafting.forge",
    ]
    layouts.change("crafting.forge", "rows", rect=(48, 124, 400, 500))
    preview = MenuPreview(document.project, DEMO)
    try:
        _surface, forge = preview.render("crafting.forge")
        assert forge["rows"] == (48, 124, 400, 500)  # the forge's own layout
        assert {"tabs", "detail", "title"} <= set(forge)
        _surface, shared = preview.render("crafting")
        assert shared["rows"] != forge["rows"]  # the other stations keep the shared one
        _surface, alchemy = preview.render("crafting.alchemy")
        assert alchemy["rows"] == shared["rows"]
    finally:
        preview.close()
