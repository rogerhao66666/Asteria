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


# --- CB2: battle presentation adapters -------------------------------------

from asteria.runtime.battle_presentation_adapters import (  # noqa: E402
    CanonicalBattleAdapter,
    LegacyPygameBattleAdapter,
    create_battle_presentation_adapter,
    entry_semantics,
)
from asteria.runtime.game_save import GameRuntimeSave  # noqa: E402


def _boss_runtime(resource_root):
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    save = GameRuntimeSave.load_json(ROOT / "saves" / "boss_stress.asteria-save.json", project)
    runtime = PlayableTestRuntime(project, save, resource_root, width=960, height=540)
    runtime.open()
    return runtime


def _scripted_battle(runtime, *, rounds=12):
    """Play hero turns with each hero's first menu skill; returns the full battle log."""
    game = runtime.game
    game.start_encounter("boss_room")
    log = list(game.drain_battle_log())
    runtime._advance_to_hero_turn()
    for _ in range(rounds):
        log.extend(game.drain_battle_log())
        if runtime._victory or runtime._defeat:
            break
        runtime._use_skill(0)
    log.extend(game.drain_battle_log())
    return tuple(log)


def test_session_battle_log_records_turns_actions_and_outcomes(resource_root, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    runtime = _boss_runtime(resource_root)
    monkeypatch.setattr(runtime, "_play_fx", lambda *a, **k: None)
    try:
        log = _scripted_battle(runtime)
    finally:
        runtime.close()
    kinds = [e.kind for e in log]
    assert kinds[0] == "battle_started"
    assert "turn" in kinds and "action" in kinds
    assert [e.sequence for e in log] == sorted(e.sequence for e in log)
    offensive = [e for e in log if e.kind == "action" and e.outcomes]
    assert offensive and all(len(e.outcomes) == len(e.target_ids) for e in offensive)
    # Values are the observed knockout-resource drop, not an interaction multiplier.
    knockout = runtime.game.rules.knockout_resource_id
    assert knockout
    assert any(outcome.value.resolved_value > 1.0 for e in offensive for _, outcome in e.outcomes)


def test_legacy_and_canonical_adapters_agree_on_battle_semantics(resource_root, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    runtime = _boss_runtime(resource_root)
    monkeypatch.setattr(runtime, "_play_fx", lambda *a, **k: None)
    try:
        legacy = LegacyPygameBattleAdapter(runtime)
        canonical = CanonicalBattleAdapter(runtime)
        runtime.game.start_encounter("boss_room")
        legacy.begin(); canonical.begin()  # canonical subscribes to this battle's hooks
        log = list(runtime.game.drain_battle_log())
        runtime._advance_to_hero_turn()
        for _ in range(40):
            log.extend(runtime.game.drain_battle_log())
            if runtime._victory or runtime._defeat:
                break
            runtime._use_skill(0)
        log.extend(runtime.game.drain_battle_log())
        legacy.consume(log); canonical.consume(log)
    finally:
        runtime.close()
    assert legacy.trace == [entry_semantics(e) for e in log]
    assert canonical.trace == legacy.trace
    assert legacy.trace[-1] == ("battle_finished", ("heroes",))
    assert sum(1 for t in legacy.trace if t[0] == "action") >= 5


def test_canonical_adapter_drives_hud_menu_feedback_and_renders(resource_root, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    runtime = _boss_runtime(resource_root)
    monkeypatch.setattr(runtime, "_play_fx", lambda *a, **k: None)
    try:
        runtime._battle_presentation = CanonicalBattleAdapter(runtime)
        runtime.game.start_encounter("boss_room")
        runtime._battle_presentation.begin()
        runtime._advance_to_hero_turn()
        runtime._present_battle(0.016)
        screen = runtime._battle_presentation.screen
        assert screen.hud.members
        assert screen.action_menu.view.total_count == len(runtime._skills_for_actor(runtime._battle_actor()))

        runtime._draw_battle_world(show_labels=False)
        world_only = pygame.image.tobytes(runtime.screen, "RGB")
        runtime._battle_presentation.draw()
        assert pygame.image.tobytes(runtime.screen, "RGB") != world_only  # UI layer drew something

        runtime._use_skill(0)
        for _ in range(5):
            runtime._present_battle(0.05)
        assert runtime._battle_presentation.trace.count(("battle_started",)) == 1
        assert any(t[0] == "action" for t in runtime._battle_presentation.trace)
    finally:
        runtime.close()


def test_manifest_selects_the_adapter_and_legacy_is_default(resource_root, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    runtime = _boss_runtime(resource_root)
    try:
        assert isinstance(runtime._battle_presentation, LegacyPygameBattleAdapter)
        runtime.manifest["battle"]["presentation"] = {"adapter": "canonical"}
        assert isinstance(create_battle_presentation_adapter(runtime), CanonicalBattleAdapter)
        runtime.manifest["battle"]["presentation"] = {"adapter": "nope"}
        with pytest.raises(ValueError):
            create_battle_presentation_adapter(runtime)
    finally:
        runtime.close()


def test_full_frame_loop_with_canonical_adapter_reaches_victory(resource_root, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    manifest_path = resource_root / "playable_test_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["battle"]["presentation"] = {"adapter": "canonical"}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    runtime = _boss_runtime(resource_root)
    monkeypatch.setattr(runtime, "_play_fx", lambda *a, **k: None)
    key = lambda k: pygame.event.Event(pygame.KEYDOWN, key=k)  # noqa: E731
    try:
        assert isinstance(runtime._battle_presentation, CanonicalBattleAdapter)
        runtime._ui_mode = "field"
        runtime._frame([key(pygame.K_e)], 0.016)
        runtime._frame([key(pygame.K_RETURN)], 0.016)
        assert runtime.game.mode == "battle"
        for _ in range(60):
            if runtime._victory or runtime._defeat:
                break
            runtime._frame([key(pygame.K_1)], 0.05)
        assert runtime._victory
        result = runtime._battle_presentation.screen.result.view
        assert result.finished and result.headline
        runtime._frame([key(pygame.K_RETURN)], 0.016)
        assert runtime.game.mode == "field" and not runtime._victory
        runtime._frame([], 0.016)
    finally:
        runtime.close()
