"""The field's start menu in a creature game's art (runtime/creature_menu.py): rows shown by
switches, switching party places, bag pockets, the dex's seen / owned, options kept in
variables, saving to a slot, and the time played."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

MENU = {
    "entries": [
        {"id": "dex", "label": "DEX", "screen": "dex", "switch": "got_dex"},
        {"id": "party", "label": "TEAM", "screen": "party"},
        {"id": "bag", "label": "BAG", "screen": "bag"},
        {"id": "card", "label": "\\V[hero]", "screen": "card"},
        {"id": "save", "label": "SAVE", "screen": "save"},
        {"id": "option", "label": "OPTION", "screen": "options"},
        {"id": "exit", "label": "EXIT", "screen": "close"},
    ],
    "bag": {
        "pockets": [
            {"name": "ITEMS", "picture": "items", "tag": ""},
            {"name": "BALLS", "picture": "balls", "tag": "capture"},
        ]
    },
    "options": {"options": [{"id": "text_speed", "label": "SPEED", "values": ["A", "B", "C"]}]},
}


class _Keys:
    def __init__(self):
        self.down = set()

    def just_pressed(self, name):
        return name in self.down


def _menu(monkeypatch, tmp_path):
    import pygame
    import run_trial_smoke as smoke
    import trial_creatures

    from asteria.runtime.creature_menu import CreatureMenuScreen

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project, game = smoke.load()
    trial_creatures.install(project, party_size=3)
    pygame.display.init()
    pygame.font.init()
    screen = pygame.display.set_mode((480, 320))
    runtime = SimpleNamespace(
        game=game,
        pg=pygame,
        manifest={"field": {"creature_menu": MENU}, "battle": {"creature_screen": {}}},
        resource_root=tmp_path,
        input=_Keys(),
        screen=screen,
    )
    return CreatureMenuScreen(runtime), runtime, game


def _press(menu, runtime, *names):
    for name in names:
        runtime.input.down = {name}
        menu.update(1 / 60)
        menu.draw()
    runtime.input.down = set()


def test_rows_follow_their_switches_and_names_expand(monkeypatch, tmp_path):
    menu, runtime, game = _menu(monkeypatch, tmp_path)
    game.save.event_context.set_variable("hero", "MIRA")
    labels = [label for _id, label, _screen in menu.entries()]
    assert labels == ["TEAM", "BAG", "MIRA", "SAVE", "OPTION", "EXIT"]
    game.save.event_context.set_switch("got_dex", True)
    assert menu.entries()[0][1] == "DEX"
    _press(menu, runtime, "move_up", "confirm")  # the last row: EXIT
    assert menu.done


def test_switching_two_party_places_reorders_the_save(monkeypatch, tmp_path):
    menu, runtime, game = _menu(monkeypatch, tmp_path)
    a, b = game.add_pet("cub", level=5), game.add_pet("wolf", level=6)
    menu.open("party")
    _press(menu, runtime, "confirm", "move_down", "confirm")  # the first one: SWITCH
    assert menu.switch_from == 0
    _press(menu, runtime, "move_down", "confirm")  # with the second
    order = [p.instance_id for p in game.party_pets()]
    assert order[:2] == [b.instance_id, a.instance_id]
    menu.list_cursor = 0
    _press(menu, runtime, "confirm", "confirm")  # SUMMARY
    assert menu.phase == "summary"
    _press(menu, runtime, "move_right", "move_right")
    assert menu.page == 2


def test_bag_pockets_take_items_by_tag_and_capture_rules(monkeypatch, tmp_path):
    menu, runtime, game = _menu(monkeypatch, tmp_path)
    inventory = game.save.rpg_state.inventory
    inventory.add("pet_ball", 2)
    potion = next(i for i in sorted(game.project.rpg_database.items) if "potion" in i)
    inventory.add(potion, 1)
    assert dict(menu.pocket_items(1)) == {"pet_ball": 2}
    assert potion in dict(menu.pocket_items(0)) and "pet_ball" not in dict(menu.pocket_items(0))
    menu.open("bag")
    menu.pocket = 1
    _press(menu, runtime, "confirm", "move_down", "confirm")  # TOSS one ball
    assert inventory.count("pet_ball") == 1 and "1" in menu.note


def test_dex_seen_and_owned(monkeypatch, tmp_path):
    import json

    menu, runtime, game = _menu(monkeypatch, tmp_path)
    entries = [
        {"number": 1, "species": "cub", "name": "CUB"},
        {"number": 2, "species": "wolf", "name": "WOLF"},
        {"number": 3, "species": "fox", "name": "FOX"},
    ]
    (tmp_path / "dex.json").write_text(json.dumps(entries))
    menu.menu["dex"] = {"entries": "dex.json"}
    assert menu.dex_rows() == []
    game.world.note_enemy("wolf", "seen")
    assert menu.dex_status("wolf") == (True, False) and len(menu.dex_rows()) == 2
    game.add_pet("cub", level=5)
    assert menu.dex_status("cub") == (True, True)


def test_options_are_kept_in_variables(monkeypatch, tmp_path):
    menu, runtime, game = _menu(monkeypatch, tmp_path)
    menu.open("options")
    _press(menu, runtime, "move_right", "move_right")
    assert game.save.event_context.get_variable("option.text_speed") == 2
    _press(menu, runtime, "move_right")
    assert game.save.event_context.get_variable("option.text_speed") == 0


def test_saving_writes_the_slot(monkeypatch, tmp_path):
    menu, runtime, game = _menu(monkeypatch, tmp_path)
    menu.open("save")
    _press(menu, runtime, "confirm")
    assert menu.save_step[0] == "saving"
    for _ in range(60):
        menu.update(1 / 60)
    assert menu.save_step[0] == "saved"
    assert list((tmp_path / "saves").iterdir())
    menu.update(0.5)
    _press(menu, runtime, "confirm")
    assert menu.done


@pytest.mark.parametrize("seconds,clock", [(59, "0:00"), (3725, "1:02")])
def test_the_clock_reads_the_time_played(monkeypatch, tmp_path, seconds, clock):
    menu, runtime, game = _menu(monkeypatch, tmp_path)
    game.world.add_counter("play.seconds", seconds)
    assert menu._clock() == clock
