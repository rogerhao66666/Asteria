"""The results screen in the playable runtime: opt-in through the manifest, paged with Enter."""

from pathlib import Path

import pytest

pygame = pytest.importorskip("pygame")

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "party_rpg_demo"


def _runtime(monkeypatch, aftermath):
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT, width=960, height=540
    )
    runtime.open()
    runtime.manifest.setdefault("battle", {})["victory_aftermath"] = aftermath
    runtime._ui_mode = "field"
    game = runtime.game
    game.start_encounter(sorted(game.project.rpg_database.encounters)[0])
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    return runtime


def _win(runtime):
    game = runtime.game
    for member_id in game.active_enemy_ids():
        game.battle.member(member_id).subject.resources.set_current("vitality", 0)
    runtime._after_hero_action()


def _enter(runtime):
    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    runtime._battle_input([event])


def test_without_the_flag_one_enter_ends_the_victory(monkeypatch):
    runtime = _runtime(monkeypatch, False)
    try:
        _win(runtime)
        assert runtime._victory and runtime._victory_screen is None
        runtime._battle_presentation.busy = lambda: False
        _enter(runtime)
        assert not runtime._victory and runtime.game.mode == "field"
    finally:
        runtime.close()


def test_with_the_flag_enter_pages_through_the_results(monkeypatch):
    runtime = _runtime(monkeypatch, True)
    try:
        _win(runtime)
        screen = runtime._victory_screen
        assert runtime._victory and screen is not None and len(screen.pages) >= 2
        runtime._battle_presentation.busy = lambda: False
        for _ in range(len(screen.pages) - 1):
            _enter(runtime)
            assert runtime._victory  # still on the results
        _enter(runtime)
        assert not runtime._victory and runtime._victory_screen is None
        assert runtime.game.mode == "field"
    finally:
        runtime.close()


def test_the_results_screen_draws_into_the_frame(monkeypatch):
    runtime = _runtime(monkeypatch, True)
    try:
        _win(runtime)
        runtime._battle_presentation.busy = lambda: False
        before = runtime.screen.copy()
        runtime._victory_screen.draw(runtime)
        assert pygame.image.tobytes(before, "RGB") != pygame.image.tobytes(runtime.screen, "RGB")
    finally:
        runtime.close()
