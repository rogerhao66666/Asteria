"""A dark place's lit circle (SET_LIGHT: at once or growing, waited for with ``rpg`` ``light``,
kept to its scene, drawn by the field view) and SET_POSITION keeping an axis where the entity
stands (a person stays where a route left it, for good)."""

from pathlib import Path

import pytest

from asteria.events import EventProgram
from asteria.events.program import EventInstruction

ROOT = Path(__file__).resolve().parents[1] / "reference_projects"


def _world(command, **args):
    return EventInstruction("WORLD", {"command": command, "args": args})


def _game(*programs):
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.game_session import GameSessionRuntime

    path = ROOT / "party_rpg_demo" / "project.asteria.json"
    project = Project.load_json(path, EditorDocument().component_registry)
    for program_id, instructions in programs:
        project.event_programs.register(
            program_id, EventProgram(tuple(instructions), name=program_id)
        )
    return GameSessionRuntime(project, project.game_start.instantiate(project))


def test_the_light_is_set_grows_and_is_waited_for():
    moving = {"source": "rpg", "name": "light", "operator": "==", "value": "",
              "scope_id": None}  # fmt: skip
    game = _game(
        ("dark", [_world("SET_LIGHT", radius=24)]),
        (
            "brighten",
            [
                _world("SET_LIGHT", off=True, speed=60.0),
                EventInstruction("WAIT", {"until": moving}),
                EventInstruction("SET_SWITCH", {"name": "lit", "value": True}),
            ],
        ),
    )
    game.events.start("dark")
    game.update_events(0.0)
    assert game.light_radius() == 24.0
    game.events.start("brighten")
    game.update_events(0.0)
    assert game.light_moving() and not game.save.event_context.get_switch("lit")
    game._light_frame(1.0)
    assert game.light_radius() == 84.0  # 60 units a second
    for _ in range(10):
        game._light_frame(1.0)
    game.update_events(0.0)
    assert game.light_radius() is None and game.save.event_context.get_switch("lit")


def test_the_light_belongs_to_its_scene():
    from asteria.core import Scene

    game = _game()
    game.set_light(32)
    here = game.scene
    game.scene = Scene("Elsewhere")
    assert game.light_radius() is None
    game.scene = here
    assert game.light_radius() == 32.0


def test_the_field_view_draws_the_dark_round_the_player(monkeypatch):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    root = ROOT / "arpg_demo"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    rt = PlayableTestRuntime(
        project, project.game_start.instantiate(project), root, width=960, height=540
    )
    rt.open()
    rt._ui_mode = "field"
    try:
        from asteria.core import Transform

        rt._frame([], 1 / 60)
        t = rt.game.player.get(Transform)
        cx, cy = rt.tile_view.world_to_screen(t.x - 16, t.y - 8)  # beside the player
        middle, corner = (round(cx), round(cy)), (5, 5)
        lit = (tuple(rt.screen.get_at(middle))[:3], tuple(rt.screen.get_at(corner))[:3])
        rt.game.set_light(24)
        rt._frame([], 1 / 60)
        assert tuple(rt.screen.get_at(corner))[:3] == (0, 0, 0)  # far from the player: dark
        assert tuple(rt.screen.get_at(middle))[:3] == lit[0]  # the circle shows the field
        rt.game.set_light(None)
        rt._frame([], 1 / 60)
        assert tuple(rt.screen.get_at(corner))[:3] != (0, 0, 0)  # (the camera eases: not equal)
    finally:
        rt.close()


def test_set_position_keeps_the_axes_it_is_not_given():
    from asteria.core import Transform

    game = _game()
    person = next(
        e for e in game.scene.entities() if e is not game.player and e.try_get(Transform)
    )
    t = person.get(Transform)
    x, y = t.x, t.y
    game.project.event_programs.register(
        "stay",
        EventProgram(
            (_world("SET_POSITION", entity=person.name, permanent=True),), name="stay"
        ),  # fmt: skip
    )
    game.events.start("stay")
    game.update_events(0.0)
    assert (t.x, t.y) == (x, y)
    kept = game.save.event_context.get_variable(f"{game.POSITION_PREFIX}{person.id}")
    assert kept.startswith(f"{float(x)}|{float(y)}")
    game.set_entity_position(person.name, None, y + 16.0)
    assert (t.x, t.y) == (x, y + 16.0)
