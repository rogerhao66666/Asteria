"""CB4a: input actions, gamepad bindings, rebinding and persistence (ASTERIA_SPEC §8)."""

from types import SimpleNamespace

import pytest

from asteria.core import Scene
from asteria.editor import EditorDocument
from asteria.project import Project
from asteria.runtime.input_map import InputActionMap, InputActionTracker, InputBinding, RawInputState


def test_default_map_reads_keyboard_stick_dpad_and_buttons():
    m = InputActionMap.default()
    assert m.evaluate(RawInputState(keys={"left"})).movement_vector() == (-1.0, 0.0)
    assert m.evaluate(RawInputState(keys={"w"})).movement_vector() == (0.0, -1.0)
    stick = m.evaluate(RawInputState(axes={"0": 0.8, "1": -0.2}))
    assert stick.movement_vector() == (0.8, 0.0)  # below the 0.5 threshold on the y axis
    assert m.evaluate(RawInputState(hats={"y:0": 1})).movement_vector() == (0.0, -1.0)
    assert m.evaluate(RawInputState(buttons={"0"})).actions["confirm"] == 1.0
    assert m.evaluate(RawInputState()).actions["interact"] == 0.0


def test_rebinding_replaces_adds_and_optionally_steals_inputs():
    m = InputActionMap.default()
    old, new = InputBinding("key", "e"), InputBinding("key", "f")
    m.rebind("interact", old, new)
    assert new in m.bindings("interact") and old not in m.bindings("interact")
    m.rebind("interact", None, InputBinding("gamepad_button", "2"))
    assert InputBinding("gamepad_button", "2") in m.bindings("interact")
    m.rebind("cancel", None, InputBinding("key", "return"), exclusive=True)
    assert InputBinding("key", "return") not in m.bindings("confirm")
    with pytest.raises(KeyError):
        m.rebind("nope", None, new)
    with pytest.raises(ValueError):
        InputBinding("mouse", "1")


def test_input_map_persists_with_the_project_and_old_projects_get_the_default():
    project = Project("Game")
    project.add_scene(Scene("Map"))
    project.input_map.rebind("interact", None, InputBinding("key", "f"))
    registry = EditorDocument().component_registry
    data = project.to_data()
    assert data["version"] == 10
    restored = Project.from_data(data, registry)
    assert InputBinding("key", "f") in restored.input_map.bindings("interact")

    data["version"] = 8
    data.pop("input_map")
    data.pop("prefabs")
    assert Project.from_data(data, registry).input_map.to_data() == InputActionMap.default().to_data()


def test_tracker_reports_edges():
    tracker = InputActionTracker(InputActionMap.default())
    tracker.update(RawInputState(keys={"e"}))
    assert tracker.just_pressed("interact") and tracker.held("interact")
    tracker.update(RawInputState(keys={"e"}))
    assert not tracker.just_pressed("interact") and tracker.held("interact")
    tracker.update(RawInputState())
    assert tracker.just_released("interact")


def test_pygame_input_source_tracks_keys_and_reads_joysticks(monkeypatch):
    pygame = pytest.importorskip("pygame")
    from asteria.platform.pygame_input import PygameInputSource

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    source = PygameInputSource(pygame)
    source.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    source.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    source.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_a))
    assert source.raw_state().keys == {"return"}

    pad = SimpleNamespace(
        get_numbuttons=lambda: 2, get_button=lambda i: i == 1,
        get_numaxes=lambda: 2, get_axis=lambda i: (-0.9, 0.1)[i],
        get_numhats=lambda: 1, get_hat=lambda i: (0, -1),
    )
    source._joysticks[99] = pad
    raw = source.raw_state()
    assert raw.buttons == {"1"} and raw.axes["0"] == -0.9 and raw.hats == {"y:0": -1}
    snapshot = InputActionMap.default().evaluate(raw)
    assert snapshot.actions["cancel"] == 1.0 and snapshot.movement_vector() == (-0.9, 1.0)


def test_gamepad_stick_moves_the_player_in_the_playable_runtime(monkeypatch, tmp_path):
    pytest.importorskip("pygame")
    import shutil
    from pathlib import Path

    from asteria.core import Transform
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    root = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"
    shutil.copy(root / "playable_test_manifest.json", tmp_path / "playable_test_manifest.json")
    shutil.copytree(root / "playable_assets", tmp_path / "playable_assets")
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(project, project.game_start.instantiate(project), tmp_path)
    runtime.open()
    try:
        runtime._ui_mode = "field"
        start = runtime.game.player.get(Transform).x
        monkeypatch.setattr(runtime.input_source, "raw_state", lambda: RawInputState(axes={"0": 1.0}))
        for _ in range(10):
            runtime._frame([], 0.05)
        assert runtime.game.player.get(Transform).x > start
        assert runtime.game.facing == "right"
    finally:
        runtime.close()
