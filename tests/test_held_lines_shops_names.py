"""Lines shown without waiting for a key (DIALOGUE ``wait`` false) and kept as a choice's
prompt; waiting for a shop to close (``rpg`` ``shop``); entering a name (NAME_INPUT) for a
variable or a creature; a pictured choice (PICTURE_CHOICE); an item's description; and the
shop, name and picture screens driven by keys (headless)."""

from pathlib import Path

import pytest

from asteria.events import EventProgram
from asteria.events.program import EventInstruction

ROOT = Path(__file__).resolve().parents[1] / "reference_projects"


def _world(command, **args):
    return EventInstruction("WORLD", {"command": command, "args": args})


def _until(source, name, value):
    condition = {"source": source, "name": name, "operator": "==", "value": value}
    return EventInstruction("WAIT", {"until": {**condition, "scope_id": None}})


def _game(*programs):
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.game_session import GameSessionRuntime

    path = ROOT / "octopath_demo" / "project.asteria.json"
    project = Project.load_json(path, EditorDocument().component_registry)
    for program_id, instructions in programs:
        project.event_programs.register(
            program_id, EventProgram(tuple(instructions), name=program_id)
        )
    return GameSessionRuntime(project, project.game_start.instantiate(project))


def test_a_held_line_lets_the_event_go_on_and_becomes_the_choices_prompt():
    choice = {
        "prompt": "",
        "choices": [{"text": "YES", "value": 1}, {"text": "NO", "value": 0}],
        "variable_name": "answer",
    }
    game = _game(
        (
            "ask",
            [
                EventInstruction("DIALOGUE", {"speaker": "", "text": "Welcome!"}),
                EventInstruction("DIALOGUE", {"speaker": "", "text": "Buy?", "wait": False}),
                EventInstruction("SET_SWITCH", {"name": "went_on", "value": True}),
                EventInstruction("CHOICE", choice),
            ],
        )
    )
    game.events.start("ask")
    game.update_events(0.0)
    assert game.pending_dialogue.line.text == "Welcome!"  # a plain line waits for a key
    game.acknowledge_dialogue()
    assert game.save.event_context.get_switch("went_on")  # the held line did not stop it
    request = game.pending_dialogue
    assert request.prompt == "Buy?" and game.held_dialogue is None
    game.choose(0)
    assert game.save.event_context.get_variable("answer") == 1


def test_a_held_line_stays_until_the_event_ends():
    game = _game(
        (
            "say",
            [
                EventInstruction("DIALOGUE", {"speaker": "", "text": "Thinking…", "wait": False}),
                EventInstruction("WAIT", {"seconds": 0.5}),
            ],
        )
    )
    game.events.start("say")
    game.update_events(0.0)
    assert game.pending_dialogue is None and game.held_dialogue.line.text == "Thinking…"
    game.update_events(1.0)
    game.update_events(0.0)
    assert game.held_dialogue is None


def test_names_go_to_a_variable_or_a_creature():
    game = _game(
        (
            "name",
            [
                _world(
                    "NAME_INPUT",
                    target="variable:hero",
                    max_length=7,
                    title="YOUR NAME?",
                    default="STU",
                ),  # fmt: skip
                _until("rpg", "name_input", ""),
                EventInstruction("SET_SWITCH", {"name": "named", "value": True}),
            ],
        )
    )
    game.events.start("name")
    game.update_events(0.0)
    assert game.name_input_request["max_length"] == 7
    assert not game.save.event_context.get_switch("named")
    assert game.finish_name_input("ROGER")
    game.update_events(0.0)
    assert game.save.event_context.get_variable("hero") == "ROGER"
    assert game.save.event_context.get_switch("named")
    with pytest.raises(Exception):  # noqa: B017 - a target that is neither kind
        game.request_name_input("hero")


def test_a_picture_choice_waits_and_gives_the_value():
    game = _game(
        (
            "pick",
            [
                _world("PICTURE_CHOICE", layout="starter", variable="starter"),
                _until("rpg", "picture_choice", ""),
                EventInstruction("SET_SWITCH", {"name": "picked", "value": True}),
            ],
        )
    )
    game.events.start("pick")
    game.update_events(0.0)
    assert game.picture_choice_request == {"layout": "starter", "variable": "starter"}
    game.finish_picture_choice(2)
    game.update_events(0.0)
    assert game.save.event_context.get_variable("starter") == 2
    assert game.save.event_context.get_switch("picked")


def test_an_item_keeps_its_description():
    from asteria.rpg.items import ItemDefinition

    item = ItemDefinition("potion", "POTION", description="Restores 20 HP.")
    assert ItemDefinition.from_data(item.to_data()).description == "Restores 20 HP."
    assert "description" not in ItemDefinition("x", "X").to_data()


# -- the screens, driven by keys (headless) ----------------------------------------------------
def _runtime(monkeypatch, manifest_field):
    pytest.importorskip("pygame")
    import sys

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, str(ROOT / "full_verification_demo"))
    import run_trial_smoke as smoke
    import trial_creatures

    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project, game = smoke.load()
    trial_creatures.install(project)
    folder = ROOT / "full_verification_demo"
    rt = PlayableTestRuntime(project, game.save, folder, width=960, height=640)
    rt.manifest.setdefault("field", {}).update(manifest_field)
    rt.open()
    rt._ui_mode = "field"
    return rt


def _frames(rt, count, events=()):
    for i in range(count):
        rt._frame(list(events) if i == 0 else [], 1 / 60)


def _key(rt, key):
    pg = rt.pg
    for kind in (pg.KEYDOWN, pg.KEYUP):
        pg.event.post(pg.event.Event(kind, key=key, mod=0, unicode="", scancode=0))
        _frames(rt, 1, pg.event.get())
    _frames(rt, 2)


def test_the_creature_shop_buys_with_a_count_and_a_yes(monkeypatch):
    from asteria.rpg.economy import ShopDefinition, ShopEntry
    from asteria.rpg.items import ItemDefinition

    rt = _runtime(monkeypatch, {"creature_shop": {"map_front_at": [72, 72]}})
    try:
        db, game, pg = rt.project.rpg_database, rt.game, rt.pg
        db.add_item(ItemDefinition("test_potion", "POTION", description="Heals."))
        db.add_shop(ShopDefinition("test_mart", "MART", [
            ShopEntry("test_potion", buy_prices={"gold": 300.0}, sell_prices={"gold": 150.0})
        ]))  # fmt: skip
        game.save.rpg_state.currencies["gold"] = 1000.0
        game.open_shop("test_mart")
        _frames(rt, 2)
        assert rt._ui_mode == "creature_shop"
        shop = rt._creature_shop
        _key(rt, pg.K_RETURN)  # BUY
        assert shop.phase == "buy"
        _key(rt, pg.K_RETURN)  # POTION: how many
        _key(rt, pg.K_UP)  # 2
        _key(rt, pg.K_UP)  # 3
        assert shop.phase == "buy_count" and shop.count == 3
        _key(rt, pg.K_UP)  # 4 (and no more: 1000 / 300 = 3, so it wraps to 1)
        assert shop.count == 1
        _key(rt, pg.K_DOWN)  # wraps to the most that can be paid
        assert shop.count == 3
        _key(rt, pg.K_RETURN)
        assert shop.phase == "buy_confirm" and "900" in shop.note
        _key(rt, pg.K_RETURN)  # YES
        assert game.save.rpg_state.inventory.count("test_potion") == 3
        assert game.save.rpg_state.currencies["gold"] == 100.0
        _key(rt, pg.K_RETURN)  # the thanks
        _key(rt, pg.K_ESCAPE)  # back to BUY / SELL / QUIT
        assert shop.phase == "menu"
        _key(rt, pg.K_ESCAPE)  # QUIT
        assert rt._ui_mode == "field" and game.open_shop_id is None
    finally:
        rt.close()


def test_the_name_screen_types_pages_and_finishes(monkeypatch):
    rt = _runtime(monkeypatch, {})
    try:
        game, pg = rt.game, rt.pg
        game.request_name_input("variable:hero", max_length=3, default="STU")
        _frames(rt, 2)
        assert rt._ui_mode == "name_input"
        screen = rt._name_input
        _key(rt, pg.K_RETURN)  # A
        _key(rt, pg.K_TAB)  # the lower-case page
        _key(rt, pg.K_RIGHT)
        _key(rt, pg.K_RETURN)  # b
        _key(rt, pg.K_ESCAPE)  # B deletes it
        _key(rt, pg.K_RETURN)  # b
        _key(rt, pg.K_RETURN)  # b: full - the cursor goes to OK
        assert screen.text == "Abb" and screen.button() == "ok"
        _key(rt, pg.K_RETURN)
        assert rt._ui_mode == "field" and game.save.event_context.get_variable("hero") == "Abb"
        game.request_name_input("variable:hero", max_length=3, default="STU")
        _frames(rt, 2)
        rt._name_input.cx, rt._name_input.cy = len(rt._name_input.columns()), 3  # OK
        _key(rt, pg.K_RETURN)  # nothing typed: the default
        assert game.save.event_context.get_variable("hero") == "STU"
    finally:
        rt.close()


def test_the_picture_choice_moves_confirms_and_backs_out(monkeypatch):
    layout = {"options": [{"value": "a", "at": [60, 64]}, {"value": "b", "at": [120, 88]}],
              "start": 1}  # fmt: skip
    rt = _runtime(monkeypatch, {"picture_choices": {"two": layout}})
    try:
        game, pg = rt.game, rt.pg
        game.request_picture_choice("two", "pick")
        _frames(rt, 2)
        screen = rt._picture_choice
        assert rt._ui_mode == "picture_choice" and screen.index == 1
        _key(rt, pg.K_LEFT)
        _key(rt, pg.K_RETURN)
        assert screen.phase == "confirm"
        _key(rt, pg.K_ESCAPE)  # NO: back to choosing
        assert screen.phase == "pick"
        _key(rt, pg.K_RETURN)
        _key(rt, pg.K_RETURN)  # YES
        assert rt._ui_mode == "field" and game.save.event_context.get_variable("pick") == "a"
    finally:
        rt.close()
