"""Headless smoke test of the legacy pygame battle loop driven by session rules."""

import json
import shutil
from pathlib import Path

import pytest

pygame = pytest.importorskip("pygame")

from PIL import Image  # noqa: E402

from asteria.editor import EditorDocument  # noqa: E402
from asteria.project import Project  # noqa: E402
from asteria.runtime.playable_test_runtime import PlayableTestRuntime  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"


def _image_paths(value):
    if isinstance(value, str) and value.endswith(".png"):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _image_paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from _image_paths(item)


@pytest.fixture
def resource_root(tmp_path):
    """Reference manifest plus flat-colour placeholder images (no art is bundled)."""
    shutil.copy(ROOT / "playable_test_manifest.json", tmp_path / "playable_test_manifest.json")
    manifest = json.loads((tmp_path / "playable_test_manifest.json").read_text(encoding="utf-8"))
    for relative in set(_image_paths(manifest)):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (512, 512), (90, 120, 200, 255)).save(path)
    return tmp_path


@pytest.fixture
def runtime(resource_root, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    value = PlayableTestRuntime(project, project.game_start.instantiate(project), resource_root, width=960, height=540)
    value.open()
    monkeypatch.setattr(value, "_play_fx", lambda *args, **kwargs: None)
    yield value
    value.close()


def test_battle_loop_gives_turns_to_scheduled_heroes_and_uses_rules(runtime):
    game = runtime.game
    game.start_encounter("boss_room")
    runtime._advance_to_hero_turn()
    actor = runtime._battle_actor()
    assert actor in game.active_hero_ids()

    for _ in range(4):
        if runtime._victory or runtime._defeat:
            break
        before = runtime._battle_actor()
        runtime._use_skill(0)
        assert not runtime._last_action_name.startswith("Action failed"), runtime._last_action_name
        runtime._draw_battle()
        if not (runtime._victory or runtime._defeat):
            assert runtime._battle_actor() in game.active_hero_ids()
            assert before is not None


def test_boost_cycles_within_the_rules_limit(runtime):
    game = runtime.game
    game.start_encounter("boss_room")
    runtime._advance_to_hero_turn()
    actor = runtime._battle_actor()
    limit = game.max_boost_level(actor)
    seen = set()
    for _ in range(limit + 2):
        runtime._battle_input([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b)])
        seen.add(runtime._boost_level)
    assert seen == set(range(limit + 1))


def test_field_interaction_shows_dialogue_then_enters_battle(resource_root, monkeypatch):
    from asteria.runtime.game_save import GameRuntimeSave

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    save = GameRuntimeSave.load_json(ROOT / "saves" / "boss_stress.asteria-save.json", project)
    runtime = PlayableTestRuntime(project, save, resource_root, width=960, height=540)
    runtime.open()
    try:
        runtime._ui_mode = "field"
        key = lambda k: pygame.event.Event(pygame.KEYDOWN, key=k)  # noqa: E731
        runtime._frame([key(pygame.K_e)], 0.016)
        assert runtime.game.pending_dialogue.line.speaker == "Astral Tyrant"
        assert runtime.game.mode == "field"
        runtime._frame([], 0.016)  # dialogue keeps waiting
        assert runtime.game.pending_dialogue is not None
        runtime._frame([key(pygame.K_RETURN)], 0.016)
        assert runtime.game.mode == "battle"
        assert runtime._battle_actor() in runtime.game.active_hero_ids()
    finally:
        runtime.close()
