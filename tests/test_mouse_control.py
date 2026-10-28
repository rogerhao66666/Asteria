"""Mouse control (D85): menus, dialogue and battles answer the mouse - hovering a row moves the
cursor there, a left click picks it, a right click goes back, the wheel moves - and the
project's input map can turn it off."""

from pathlib import Path

import pygame as pg
import pytest

from asteria.runtime.input_map import InputActionMap
from asteria.runtime.pointer import PointerLayer


def _centre(spot):
    x, y, w, h = spot.rect
    return x + w // 2, y + h // 2


def _move(pos):
    return pg.event.Event(pg.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0))


def _click(pos, button=1):
    return pg.event.Event(pg.MOUSEBUTTONDOWN, pos=pos, button=button)


def _frames(runtime, *batches):
    for events in batches:
        runtime._frame(list(events), 1 / 60)


def _spots(runtime):
    """The hotspots the last frame drew (what the pointer can hit next)."""
    return list(runtime.pointer.drawn)


# --- the layer ---------------------------------------------------------------------------------


def test_the_layer_turns_clicks_into_key_presses_and_releases_them():
    pg.init()
    layer = PointerLayer(pg)
    picked = []
    layer.add((10, 10, 100, 20), lambda: picked.append("row"))  # drawn this frame
    events = layer.translate([_move((50, 20))])  # the next frame's events
    assert picked == ["row"]  # hovering moves the cursor
    layer.add((10, 10, 100, 20), lambda: picked.append("row"))
    events = layer.translate([_click((50, 20))])
    assert picked == ["row", "row"]
    assert [(e.type, e.key) for e in events] == [(pg.KEYDOWN, pg.K_RETURN)]
    events = layer.translate([])
    assert [(e.type, e.key) for e in events] == [(pg.KEYUP, pg.K_RETURN)]  # released


def test_a_click_off_every_hotspot_passes_on_and_right_click_is_escape():
    pg.init()
    layer = PointerLayer(pg)
    layer.add((10, 10, 100, 20))
    click = _click((500, 500))
    events = layer.translate([click, _click((5, 5), button=3)])
    assert events[0] is click  # a picture or a figure on the map still gets it
    assert (events[1].type, events[1].key) == (pg.KEYDOWN, pg.K_ESCAPE)
    assert layer.translate([], enabled=False)[0].type == pg.KEYUP
    assert layer.translate([_click((5, 5), button=3)], enabled=False)[0].type == (
        pg.MOUSEBUTTONDOWN
    )  # turned off: the mouse is left alone


def test_the_wheel_moves_only_where_something_can_be_pointed_at():
    pg.init()
    layer = PointerLayer(pg)
    wheel = pg.event.Event(pg.MOUSEWHEEL, x=0, y=-1)
    assert layer.translate([wheel]) == [wheel]  # nothing drawn: a skill tree zooms with it
    layer.add((0, 0, 10, 10))
    events = layer.translate([wheel])
    assert (events[0].type, events[0].key) == (pg.KEYDOWN, pg.K_DOWN)


def test_the_input_map_keeps_the_switch_only_when_it_is_off():
    on = InputActionMap.default()
    assert on.mouse and "mouse" not in on.to_data()
    off = InputActionMap.from_data({**on.to_data(), "mouse": False})
    assert not off.mouse and off.to_data()["mouse"] is False
    from asteria.runtime.input_rebinding import effective_input_map

    assert not effective_input_map(off, {"confirm": []}).mouse  # the player's bindings keep it


# --- the game's own screens --------------------------------------------------------------------


def test_the_pause_menu_follows_the_pointer_and_a_click_opens_the_row(runtime):
    runtime._ui_mode = "pause"
    runtime._pause_menu.index = 0
    _frames(runtime, [])
    rows = _spots(runtime)
    options = [key for key, _label in runtime._pause_menu.labels(runtime.game.tr)]
    assert len(rows) == min(len(options), (runtime.height - 130) // 34)  # the rows that fit
    target = options.index("settings")
    _frames(runtime, [_move(_centre(rows[target]))])
    assert runtime._pause_menu.index == target
    _frames(runtime, [_click(_centre(_spots(runtime)[target]))])
    assert runtime._ui_mode == "settings"
    _frames(runtime, [], [_click((5, 5), button=3)])
    assert runtime._ui_mode == "pause"  # a right click goes back


def test_a_click_reads_on_and_picks_a_choice(runtime):
    from asteria.events import EventProgram
    from asteria.events.program import EventInstruction

    choice = {
        "prompt": "Which?",
        "choices": [{"text": "One", "value": 0}, {"text": "Two", "value": 1},
                    {"text": "Three", "value": 2}],
        "variable_name": "picked",
    }  # fmt: skip
    program = EventProgram(
        (EventInstruction("DIALOGUE", {"text": "Hello"}), EventInstruction("CHOICE", choice)),
        name="ask",
    )
    runtime.project.event_programs.register("ask", program)
    runtime._ui_mode = "field"  # (the game opens on its title)
    game = runtime.game
    game.events.start("ask")
    game.update_events(0.0)
    _frames(runtime, [])
    assert game.pending_dialogue.line is not None
    _frames(runtime, [_click((runtime.width // 2, 40))])  # anywhere on the screen reads on
    _frames(runtime, [], [])
    assert game.pending_dialogue is not None and game.pending_dialogue.choices
    spots = _spots(runtime)[1:]  # the screen behind (a click off the options does nothing)
    assert len(spots) == 3
    _frames(runtime, [_move(_centre(spots[2]))])
    assert runtime._choice_cursor == 2
    _frames(runtime, [_click(_centre(_spots(runtime)[2]))], [], [])  # "Two"
    assert game.save.event_context.get_variable("picked") == 1


def test_mouse_control_off_leaves_the_menus_to_the_keys(runtime):
    runtime.input.input_map.mouse = False
    runtime._ui_mode = "pause"
    runtime._pause_menu.index = 0
    _frames(runtime, [])
    rows = _spots(runtime)
    _frames(runtime, [_move(_centre(rows[2]))], [_click(_centre(rows[2]))])
    assert runtime._ui_mode == "pause" and runtime._pause_menu.index == 0


def test_battle_commands_and_targets_answer_the_pointer(runtime):
    game = runtime.game
    runtime._ui_mode = "field"
    game.start_encounter("boss_room")
    runtime._advance_to_hero_turn()
    for _ in range(400):  # until the hero's command menu is up
        _frames(runtime, [])
        if _spots(runtime) and not runtime._presentation_busy():
            break
    commands = runtime.battle_commands
    spots = _spots(runtime)
    assert spots[0].key == "tab"  # the category strip: a click opens the next category
    rows = spots[1:]
    _frames(runtime, [_move(_centre(rows[2]))])
    assert (commands.mode, commands.cursor) == ("command", 2)
    _frames(runtime, [_click(_centre(_spots(runtime)[1]))])  # the first skill: its targets
    assert commands.mode == "target"
    _frames(runtime, [])
    targets = [s for s in _spots(runtime) if s.rect[0] < runtime.width / 2]  # the enemies
    assert len(targets) == len(commands.entries(runtime._battle_actor())) >= 2
    _frames(runtime, [_move(_centre(targets[1]))])
    assert commands.cursor == 1  # pointing at an enemy aims at it
    _frames(runtime, [_click((5, 5), button=3)], [])
    assert commands.mode == "command"  # a right click steps back


DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


@pytest.fixture
def creature_runtime(monkeypatch):
    """The Full Verification game with the creature party and the creature battle screen."""
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.syspath_prepend(str(DEMO))
    import run_trial_smoke as smoke
    import trial_creatures

    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project, game = smoke.load()
    trial_creatures.install(project)
    rt = PlayableTestRuntime(project, game.save, DEMO, width=960, height=640)
    rt.manifest.setdefault("battle", {})["style"] = "creature"
    rt.open()
    rt._ui_mode = "field"
    yield rt
    rt.close()


def test_the_creature_battle_commands_moves_and_party_answer_the_pointer(creature_runtime):
    rt = creature_runtime
    rt.game.add_pet("cub", level=5)
    rt.game.add_pet("wolf", level=6)
    rt.game.start_encounter("wild_cubs")
    for frame in range(2000):  # the intro plays, the lines read on with clicks
        screen = rt._creature_battle
        if screen is not None and screen.phase == "command" and not screen.steps:
            break
        _frames(rt, [_click((5, 5))] if _spots(rt) and frame % 3 == 0 else [])
    screen = rt._creature_battle
    assert screen.phase == "command"
    _frames(rt, [])
    commands = _spots(rt)
    assert len(commands) == 4  # FIGHT BAG / PARTY RUN
    _frames(rt, [_move(_centre(commands[2]))])
    assert screen.cursor == 2
    _frames(rt, [_click(_centre(_spots(rt)[0]))])
    assert screen.phase == "fight"
    _frames(rt, [])
    moves = _spots(rt)
    assert moves and len(moves) == len(screen._moves())
    _frames(rt, [_click((5, 5), button=3)])
    assert screen.phase == "command"  # a right click: back to the commands
    _frames(rt, [], [_click(_centre(_spots(rt)[2]))])  # PARTY
    assert screen.phase == "party"
    _frames(rt, [])
    slots = _spots(rt)
    assert len(slots) == len(screen._party()) + 1  # + CANCEL
    _frames(rt, [_click(_centre(slots[-1]))])
    assert screen.phase == "command"


def _open(runtime, name):
    if name == "status":
        runtime.open_status_menu(back="pause")
    elif name == "slots":
        runtime.open_slots("save", back="pause")
    elif name == "equipment":
        runtime.open_equipment_screen(back="pause")
    elif name == "enhance":
        runtime.open_enhance_screen(back="pause")
    elif name == "controls":
        from asteria.runtime.input_rebinding import ControlsMenu

        runtime.controls_menu = ControlsMenu(runtime.project.input_map, tr=runtime.game.tr)
        runtime._ui_mode = "controls"
    elif name == "settings":
        runtime._settings_menu.index = 0
        runtime._ui_mode = "settings"
    elif name in ("backlog", "music", "credits", "skill_slots"):
        from asteria.runtime import extras_screens

        screen = {
            "backlog": extras_screens.BacklogScreen,
            "music": extras_screens.MusicRoomScreen,
            "credits": extras_screens.CreditsScreen,
            "skill_slots": extras_screens.AbilitySlotsScreen,
        }[name]
        runtime._extra_screen = screen(runtime)
        runtime._ui_mode = "extra"
    else:
        runtime._list_scroll = 0
        runtime._ui_mode = name


@pytest.mark.parametrize(
    "name",
    ["status", "slots", "equipment", "enhance", "settings", "quests", "achievements",
     "bestiary", "skill_slots"],
)  # fmt: skip
def test_every_menu_screen_marks_what_the_pointer_can_hit(runtime, name):
    runtime._ui_mode = "pause"
    _open(runtime, name)
    _frames(runtime, [])
    spots = _spots(runtime)
    assert spots, name
    for spot in spots:  # pointing at each one is safe and keeps the screen open
        _frames(runtime, [_move(_centre(spot))])
        _frames(runtime, [])
    assert runtime._ui_mode == ("extra" if name == "skill_slots" else name)


def test_the_pointer_moves_each_screens_own_cursor(runtime):
    runtime._ui_mode = "pause"
    _open(runtime, "slots")
    _frames(runtime, [])
    _frames(runtime, [_move(_centre(_spots(runtime)[2]))])
    assert runtime.slot_menu.row == 2
    _open(runtime, "settings")
    _frames(runtime, [])
    rows = [s for s in _spots(runtime) if s.pick is not None]
    _frames(runtime, [_move(_centre(rows[2]))])
    assert runtime._settings_menu.index == 2
    _open(runtime, "equipment")
    _frames(runtime, [])
    screen = runtime._gear_screen
    _frames(runtime, [_move(_centre(_spots(runtime)[1]))])
    assert (screen.focus, screen.place) == ("doll", 1)
    _frames(runtime, [_click(_centre(_spots(runtime)[1]))])
    assert runtime._ui_mode == "equipment"  # Enter on a place: what fits (or a note)


def test_a_click_on_the_title_is_the_rows_key(runtime):
    assert runtime._ui_mode == "title"
    _frames(runtime, [])
    new_game, _load = _spots(runtime)
    assert (new_game.key, _load.key) == ("n", "l")
    _frames(runtime, [_click((5, 5), button=3)])
    assert runtime.running  # a right click does not quit from the title
    _frames(runtime, [_click(_centre(new_game))])
    assert runtime._ui_mode == "field"


def test_quick_clicks_are_separate_presses():
    pg.init()
    layer = PointerLayer(pg)
    kinds = []
    for _ in range(6):  # a click on every frame
        layer.add((0, 0, 10, 10))
        events = layer.translate([_click((5, 5))])
        kinds.append([(e.type, e.key) for e in events])
    down, up = (pg.KEYDOWN, pg.K_RETURN), (pg.KEYUP, pg.K_RETURN)
    assert all(not (down in k and up in k) for k in kinds)  # never up and down at once
    assert sum(down in k for k in kinds) >= 2


def test_the_creature_menu_shop_and_name_screens_answer_the_pointer(creature_runtime):
    from asteria.presentation.creature_screens import CreatureScreenSettings
    from asteria.rpg.economy import ShopDefinition, ShopEntry
    from asteria.rpg.items import ItemDefinition
    from asteria.runtime.creature_menu import CreatureMenuScreen
    from asteria.runtime.creature_shop import CreatureShopScreen
    from asteria.runtime.name_input import NameInputScreen

    rt = creature_runtime
    rt.game.add_pet("cub", level=5)
    entries = [{"id": "bag", "label": "BAG", "screen": "bag"},
               {"id": "party", "label": "PARTY", "screen": "party"}]  # fmt: skip
    record = CreatureScreenSettings("field.creature_menu", {"entries": entries})
    rt.project.battle_presentation_library.set("creature_screen", record.screen_id, record)
    rt._creature_menu = menu = CreatureMenuScreen(rt)
    rt._ui_mode = "creature_menu"
    _frames(rt, [])
    rows = _spots(rt)
    assert len(rows) == len(menu.entries()) >= 2
    _frames(rt, [_move(_centre(rows[1]))])
    assert menu.cursor == 1
    _frames(rt, [_click((5, 5), button=3)])
    assert menu.done  # a right click closes the start menu

    db = rt.project.rpg_database
    db.add_item(ItemDefinition("test_potion", "POTION"))
    db.add_shop(ShopDefinition("test_mart", "MART", [
        ShopEntry("test_potion", buy_prices={"gold": 300.0})
    ]))  # fmt: skip
    rt.game.open_shop("test_mart")
    rt._creature_shop = shop = CreatureShopScreen(rt)
    rt._ui_mode = "creature_shop"
    _frames(rt, [])
    _frames(rt, [_click(_centre(_spots(rt)[0]))], [])  # BUY
    assert shop.phase == "buy"
    _frames(rt, [])
    goods = _spots(rt)
    assert len(goods) == len(shop.goods()) + 1  # + CANCEL
    _frames(rt, [_move(_centre(goods[-1]))])
    assert shop.buy_cursor == len(shop.goods())

    rt._name_input = name = NameInputScreen(rt, {"max_length": 7, "variable": "who"})
    rt._ui_mode = "name_input"
    _frames(rt, [])
    keys = _spots(rt)
    _frames(rt, [_click(_centre(keys[0]))], [])  # the first letter
    assert name.text == name.rows()[0][0]
    _frames(rt, [_click(_centre(keys[-2]))], [])  # BACK
    assert name.text == ""


def test_the_editor_turns_mouse_control_off_with_undo(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel

    from asteria.editor import EditorDocument
    from asteria.editor.i18n import translate
    from asteria.editor.input_map_widget import InputMapWidget
    from asteria.project import Project

    QApplication.instance() or QApplication([])
    ref = DEMO.parent / "complex_reference_rpg" / "project.asteria.json"
    document = EditorDocument()
    document.set_project(Project.load_json(ref, document.component_registry), file_path=ref)
    widget = InputMapWidget(document)
    assert widget.mouse.isChecked()  # on unless the author turns it off
    widget.mouse.setChecked(False)
    assert not document.project.input_map.mouse
    data = document.project.to_data()
    again = Project.from_data(data, document.component_registry)
    assert not again.input_map.mouse  # saved with the project
    document.undo()
    widget.refresh()
    assert document.project.input_map.mouse and widget.mouse.isChecked()
    help_mark = widget.findChild(QLabel, "InputMapMouseHelp")
    assert help_mark.text() == "ⓘ" and "right click" in help_mark.toolTip()  # help on hover
    assert translate("Mouse control", "zh_TW") == "滑鼠操作"
    assert translate(help_mark.toolTip(), "zh_TW").startswith("選單、對話與戰鬥")


# --- the rest: rebinding, long menus, the hint, click to move ----------------------------------


def test_a_click_while_rebinding_is_not_the_key_bound(runtime):
    runtime._ui_mode = "pause"
    _open(runtime, "controls")
    _frames(runtime, [])
    menu = runtime.controls_menu
    menu.row = 0
    action = menu.select()
    before = menu.input_map.bindings(action)
    _frames(runtime, [])  # drawn while waiting for the key
    _frames(runtime, [_click((300, 130))], [], [])  # on the second row
    assert menu.capturing == action and menu.row == 0  # still waiting for a key or a pad
    assert menu.input_map.bindings(action) == before
    _frames(runtime, [_click((5, 5), button=3)])
    assert menu.capturing is None  # a right click cancels, as Esc does


def test_a_pause_menu_taller_than_the_window_scrolls_to_its_last_row(runtime):
    runtime._ui_mode = "pause"
    runtime.height = 300  # room for five rows
    options = [key for key, _label in runtime._pause_menu.labels(runtime.game.tr)]
    assert len(options) > 5
    runtime._pause_menu.index = len(options) - 1
    _frames(runtime, [])
    rows = _spots(runtime)
    assert len(rows) == 5 and rows[-1].rect[1] + rows[-1].rect[3] < 300
    _frames(runtime, [_move(_centre(rows[0]))], [])
    assert runtime._pause_menu.index == len(options) - 5  # the top row shown
    assert _spots(runtime)[0].rect == rows[0].rect  # pointing does not scroll the rows
    runtime._pause_menu.index = 0
    _frames(runtime, [])
    _frames(runtime, [_move(_centre(_spots(runtime)[4]))])
    assert runtime._pause_menu.index == 4


def test_the_mouse_hint_shows_once_the_mouse_is_used(runtime):
    runtime._ui_mode = "pause"
    _frames(runtime, [])
    assert not runtime.pointer.used
    _frames(runtime, [_move((5, 5))])
    assert runtime.pointer.used
    drawn = []
    real = runtime.text
    runtime.text = lambda words, *a, **k: drawn.append(words) or real(words, *a, **k)
    runtime._draw_mouse_hint()
    assert drawn == ["Click: choose   Right click: back"]
    import json

    import asteria.rpg

    table = Path(asteria.rpg.__file__).parent / "built_in_text" / "zh-TW.json"
    assert (
        json.loads(table.read_text(encoding="utf-8"))["entries"]["hint.mouse"]
        == "點擊：選擇   右鍵：返回"
    )
    key = pg.event.Event(pg.KEYDOWN, key=pg.K_DOWN, mod=0, unicode="", scancode=0)
    _frames(runtime, [key])
    drawn.clear()
    runtime._draw_mouse_hint()
    assert drawn == []  # back on the keys


def test_click_to_move_is_off_unless_the_author_turns_it_on():
    on = InputActionMap.default()
    assert not on.click_move and "click_move" not in on.to_data()
    on.click_move = True
    assert InputActionMap.from_data(on.to_data()).click_move


def test_click_to_move_walks_the_player_to_the_clicked_spot(runtime):
    from asteria.core import Transform

    runtime._ui_mode = "field"
    _frames(runtime, [])
    player = runtime.game.player.get(Transform)
    start = (player.x, player.y)
    goal = (start[0] - 32.0, start[1])  # away from the figure on the right (a click on it talks)
    screen = runtime._field_screen_xy(*goal)
    _frames(runtime, [_click(screen)], *[[]] * 30)
    assert (player.x, player.y) == start  # off: a click on the map does nothing
    runtime.input.input_map.click_move = True
    _frames(runtime, [_click(screen)], *[[]] * 120)
    assert abs(player.x - goal[0]) + abs(player.y - goal[1]) < 12
    assert runtime._click_path is None  # arrived
    _frames(runtime, [_click(runtime._field_screen_xy(*start))], [], [])
    assert runtime._click_path is not None
    key = pg.event.Event(pg.KEYDOWN, key=pg.K_UP, mod=0, unicode="", scancode=0)
    _frames(runtime, [key])
    assert runtime._click_path is None  # a key takes over


def test_the_editor_turns_click_to_move_on_with_undo(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel

    from asteria.editor import EditorDocument
    from asteria.editor.i18n import translate
    from asteria.editor.input_map_widget import InputMapWidget
    from asteria.project import Project

    QApplication.instance() or QApplication([])
    ref = DEMO.parent / "complex_reference_rpg" / "project.asteria.json"
    document = EditorDocument()
    document.set_project(Project.load_json(ref, document.component_registry), file_path=ref)
    widget = InputMapWidget(document)
    assert not widget.click_move.isChecked()  # off unless the author turns it on
    widget.click_move.setChecked(True)
    again = Project.from_data(document.project.to_data(), document.component_registry)
    assert again.input_map.click_move  # saved with the project
    widget.mouse.setChecked(False)
    assert not widget.click_move.isEnabled()  # it needs mouse control
    document.undo()
    document.undo()
    widget.refresh()
    assert not document.project.input_map.click_move and not widget.click_move.isChecked()
    mark = widget.findChild(QLabel, "InputMapClickMoveHelp")
    assert mark.text() == "ⓘ" and translate("Click to move", "zh_TW") == "點擊移動"
    assert translate(mark.toolTip(), "zh_TW").startswith("在地圖上按左鍵")


def test_click_to_move_on_a_figure_walks_up_and_talks(runtime):
    from asteria.core import Transform
    from asteria.runtime.components2d import Interaction2DComponent

    runtime._ui_mode = "field"
    runtime.input.input_map.click_move = True
    _frames(runtime, [])
    figure = next(
        e
        for e in runtime.game.scene.entities()
        if e.try_get(Interaction2DComponent) is not None
        and e.get(Interaction2DComponent).trigger == "action"
    )
    spot = figure.get(Transform)
    player = runtime.game.player.get(Transform)
    player.x, player.y = spot.x + 80.0, spot.y  # away from it, to its right
    runtime.game.save.player_position = (player.x, player.y)
    _frames(runtime, [_click(runtime._field_screen_xy(spot.x, spot.y))])
    for _ in range(180):
        _frames(runtime, [])
        if runtime.game.event_busy:
            break
    assert runtime.game.event_busy  # its event started, as the interact key would start it
    assert runtime.game.facing == "left"  # facing the figure
    reach = figure.get(Interaction2DComponent).range
    assert abs(player.x - spot.x) <= reach and player.x > spot.x


def test_click_to_move_skips_a_side_view_action_scene(runtime):
    from asteria.runtime.character_control import CharacterController2DComponent

    game = runtime.game
    assert runtime._click_move_scene()  # the field
    controller = CharacterController2DComponent()
    game.player.add_component(controller)
    type(game).action_scene = property(lambda self: True)
    try:
        controller.mode = "topdown"
        assert runtime._click_move_scene()  # seen from above: a click walks
        controller.mode = "platformer"
        assert not runtime._click_move_scene()  # a platformer's player jumps instead
    finally:
        del type(game).action_scene


def test_the_full_verification_demo_keeps_the_mouse_but_draws_no_hint():
    """D99: the demo blanks ``hint.mouse`` in both its languages; clicks still work."""
    import json

    from asteria.rpg.localization import LocaleTable, Localizer

    demo = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
    data = json.loads((demo / "project.asteria.json").read_text(encoding="utf-8"))
    tables = [LocaleTable.from_data(t) for t in data["rpg_database"]["locale_tables"]]
    for locale in ("en", "zh-TW"):
        assert Localizer(tables, default_locale="en", locale=locale).tr("hint.mouse", "x") == ""
    assert data.get("input_map", {}).get("mouse", True) is not False
