"""Headless tests of the playable battle loop (canonical battle screen) driven by session rules."""

import json
from pathlib import Path

import pytest

pygame = pytest.importorskip("pygame")


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
    create_battle_presentation_adapter,
    entry_semantics,
)
from asteria.runtime.game_save import GameRuntimeSave  # noqa: E402


def _boss_runtime(resource_root):
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    save = GameRuntimeSave.load_json(ROOT / "saves" / "boss_stress.asteria-save.json", project)
    import real_window

    if (
        real_window.enabled()
    ):  # real-window replay (tests/real_window.py): no dummy driver for this window
        import os

        os.environ.pop("SDL_VIDEODRIVER", None)
        os.environ.pop("SDL_AUDIODRIVER", None)
    runtime = PlayableTestRuntime(project, save, resource_root, width=960, height=540)
    runtime.open()
    if real_window.enabled():
        real_window.set_stage(runtime)
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


def test_canonical_adapter_understands_every_battle_fact_in_order(resource_root, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    runtime = _boss_runtime(resource_root)
    try:
        canonical = CanonicalBattleAdapter(runtime)
        runtime.game.start_encounter("boss_room")
        canonical.begin()  # canonical subscribes to this battle's hooks
        log = list(runtime.game.drain_battle_log())
        runtime._advance_to_hero_turn()
        for _ in range(40):
            log.extend(runtime.game.drain_battle_log())
            if runtime._victory or runtime._defeat:
                break
            runtime._use_skill(0)
        log.extend(runtime.game.drain_battle_log())
        canonical.consume(log)
        # The canonical screen replays the actions on its presentation clock.
        for _ in range(2000):
            if not canonical.busy():
                break
            canonical.update(0.05)
        assert not canonical.busy()
    finally:
        runtime.close()
    assert canonical.trace == [
        entry_semantics(e) for e in log
    ]  # the parity contract the legacy screen met
    assert canonical.trace[-1] == ("battle_finished", ("heroes",))
    assert sum(1 for t in canonical.trace if t[0] == "action") >= 5


def test_canonical_adapter_drives_hud_menu_feedback_and_renders(resource_root, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    runtime = _boss_runtime(resource_root)
    try:
        runtime._battle_presentation = CanonicalBattleAdapter(runtime)
        runtime.game.start_encounter("boss_room")
        runtime._battle_presentation.begin()
        runtime._advance_to_hero_turn()
        runtime._present_battle(0.016)
        for _ in range(400):  # commands appear once the enemy turns have played
            if not runtime._battle_presentation.busy():
                break
            runtime._present_battle(0.05)
        runtime._present_battle(0.016)
        screen = runtime._battle_presentation.screen
        assert screen.hud.members
        actor = runtime._battle_actor()
        ids = [e.action_id for e in screen.action_menu._source]  # every page of the command menu
        skills = [a for a, _ in runtime._skills_for_actor(actor)]
        assert (
            ids[: len(skills)] == skills
        )  # the authored skills first (keys 1-4), then every other one
        if runtime.game.max_boost_level(actor) > 0:
            assert "boost" in ids

        runtime.screen.fill((0, 0, 0))
        blank = pygame.image.tobytes(runtime.screen, "RGB")
        runtime._battle_presentation.draw()
        assert pygame.image.tobytes(runtime.screen, "RGB") != blank  # the canonical screen drew

        runtime._use_skill(0)
        for _ in range(400):
            runtime._present_battle(0.05)
            if not runtime._battle_presentation.busy():
                break
        runtime._battle_presentation.finalize_trace()
        assert runtime._battle_presentation.trace.count(("battle_started",)) == 1
        assert any(t[0] == "action" for t in runtime._battle_presentation.trace)
    finally:
        runtime.close()


def test_the_canonical_screen_is_the_only_battle_presentation(resource_root, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    runtime = _boss_runtime(resource_root)
    try:
        runtime.manifest["battle"].pop("presentation", None)  # no manifest choice -> canonical
        default = create_battle_presentation_adapter(runtime)
        assert isinstance(default, CanonicalBattleAdapter) and not default.legacy_requested
        runtime.manifest["battle"]["presentation"] = {"adapter": "legacy"}  # retired (CB15 A9)
        retired = create_battle_presentation_adapter(runtime)
        assert isinstance(retired, CanonicalBattleAdapter) and retired.legacy_requested
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
    key = lambda k: pygame.event.Event(pygame.KEYDOWN, key=k)  # noqa: E731
    try:
        assert isinstance(runtime._battle_presentation, CanonicalBattleAdapter)
        runtime._ui_mode = "field"
        runtime._frame([key(pygame.K_e)], 0.016)
        runtime._frame([key(pygame.K_RETURN)], 0.016)
        assert runtime.game.mode == "battle"
        # Each action now plays its choreography before the next command is accepted.
        for _ in range(3000):
            if runtime._victory or runtime._defeat:
                break
            runtime._frame([key(pygame.K_1)], 0.05)
        assert runtime._victory
        for _ in range(200):  # let the final choreography and result play out
            if not runtime._battle_presentation.busy():
                break
            runtime._frame([], 0.05)
        result = runtime._battle_presentation.screen.result.view
        assert result.finished and result.headline
        runtime._frame([key(pygame.K_RETURN)], 0.016)
        assert runtime.game.mode == "field" and not runtime._victory
        runtime._frame([], 0.016)
    finally:
        runtime.close()


def test_pygame_battle_ui_backend_scales_virtual_coordinates(monkeypatch):
    from types import SimpleNamespace

    from asteria.platform.pygame_battle_ui import PygameBattleUiBackend

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    surface = pygame.Surface((300, 150))
    backend = PygameBattleUiBackend(surface, scale=3)
    panel = SimpleNamespace(x=10, y=5, width=20, height=10)
    backend.draw_panel(panel, fill=(255, 0, 0), border=(0, 0, 0), radius=0, border_width=0)
    assert surface.get_at((30, 15))[:3] == (255, 0, 0)  # (10, 5) * 3
    assert surface.get_at((89, 44))[:3] == (255, 0, 0)  # far corner of 60x30 rect
    assert surface.get_at((91, 46))[:3] == (0, 0, 0)
    assert backend._font(10).get_height() > PygameBattleUiBackend(surface)._font(10).get_height()
    with pytest.raises(ValueError):
        PygameBattleUiBackend(surface, scale=0)


# --- CB2 follow-up: canonical battle UI layout (F-2) -----------------------


def _canonical_frame(resource_root, monkeypatch):
    from asteria.runtime.camera import Camera2D

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    runtime = _boss_runtime(resource_root)
    runtime._battle_presentation = CanonicalBattleAdapter(runtime)
    runtime.game.start_encounter("boss_room")
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    runtime._present_battle(0.016)
    for _ in range(400):  # let the opening enemy turns play out
        if not runtime._battle_presentation.busy():
            break
        runtime._present_battle(0.05)
    screen = runtime._battle_presentation.screen
    layout = screen.composer.layout
    frame = screen.build_frame(Camera2D(width=layout.virtual_width, height=layout.virtual_height))
    return runtime, layout, frame


def _overlaps(a, b):
    return (
        a.x < b.x + b.width
        and b.x < a.x + a.width
        and a.y < b.y + b.height
        and b.y < a.y + a.height
    )


def test_canonical_hud_panels_do_not_overlap(resource_root, monkeypatch):
    runtime, layout, frame = _canonical_frame(resource_root, monkeypatch)
    try:
        # Octopath staging: one HUD panel per hero down the right edge, enemies show overhead bars.
        hud = [p for p in frame.panels if p.panel_id.startswith("hud:")]
        heroes = list(runtime.game.battle.parties["heroes"].ids())
        assert sorted(p.member_id for p in hud) == sorted(heroes)
        assert not any(_overlaps(a, b) for i, a in enumerate(hud) for b in hud[i + 1 :])
        assert all(p.y >= 0 and p.y + p.height <= layout.virtual_height for p in hud)
        assert len({p.x for p in hud}) == 1  # one column
        overhead = {t.member_id for t in frame.texts if t.role == "overhead_name"}
        assert overhead == set(runtime.game.battle.parties["enemies"].ids())
        # the command menu stands by whoever acts and may cover a HUD panel (it is drawn last)
    finally:
        runtime.close()


def test_canonical_ui_uses_display_names_and_fits_the_timeline(resource_root, monkeypatch):
    runtime, layout, frame = _canonical_frame(resource_root, monkeypatch)
    try:
        texts = [t.text for t in frame.texts]
        assert "Hero 06" in texts and "Astral Tyrant" in texts
        assert not any(t.startswith("hero_") or ":" in t for t in texts if t)
        timeline = next(p for p in frame.panels if p.panel_id == "timeline")
        assert timeline.x >= 0 and timeline.x + timeline.width <= layout.virtual_width
        labels = [t.text for t in frame.texts if t.role in {"timeline_entry", "timeline_current"}]
        assert labels and all(len(x) <= 6 for x in labels)
        assert len(set(labels[:5])) == 5  # heroes stay distinguishable ("H06", "H04", ...)
    finally:
        runtime.close()


def test_pygame_backend_replaces_glyphs_the_font_cannot_draw(monkeypatch):
    from asteria.platform.pygame_battle_ui import PygameBattleUiBackend

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    backend = PygameBattleUiBackend(pygame.Surface((10, 10)))
    font = backend._font(20)
    assert backend._renderable(font, "▶ Strike") == "> Strike"
    assert backend._renderable(font, "Plain text 123") == "Plain text 123"


def test_victory_panel_keeps_rendering_after_the_battle_ends(resource_root, monkeypatch):
    """Regression: the frame after victory drew the HUD against a finished (None) battle."""
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    runtime = _boss_runtime(resource_root)
    key = lambda k: pygame.event.Event(pygame.KEYDOWN, key=k)  # noqa: E731
    try:
        runtime._ui_mode = "field"
        runtime._frame([key(pygame.K_e)], 0.016)
        runtime._frame([key(pygame.K_RETURN)], 0.016)
        for _ in range(
            3000
        ):  # one command whenever the canonical screen is idle and waiting for a hero
            if runtime._victory:
                break
            waiting = not runtime._battle_presentation.busy()
            runtime._frame([key(pygame.K_1)] if waiting else [], 0.05)
        assert runtime._victory and runtime.game.battle is None
        runtime._frame([], 0.016)
        for _ in range(400):  # the result screen and victory jingle play out first
            if not runtime._battle_presentation.busy():
                break
            runtime._frame([], 0.05)
        runtime._frame([key(pygame.K_RETURN)], 0.016)
        assert runtime.game.mode == "field" and not runtime._victory
    finally:
        runtime.close()
