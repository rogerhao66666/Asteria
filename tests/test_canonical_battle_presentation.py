"""CB2 / D14 #1: the canonical battle presentation draws animated combatants, plays authored
VFX / audio / camera choreography in sync with Battle Core results, and stays a pure
presentation layer (no second set of battle rules).

Uses the reference project's committed CC0 battle sheets and its canonical
combatant_visuals / motion_sequences data.
"""

import pytest

pygame = pytest.importorskip("pygame")

from test_playable_battle_loop import _boss_runtime  # noqa: E402

from asteria.runtime.battle_presentation_adapters import CanonicalBattleAdapter  # noqa: E402


@pytest.fixture
def battle(resource_root, monkeypatch):  # noqa: F811
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    runtime = _boss_runtime(resource_root)
    runtime._battle_presentation = adapter = CanonicalBattleAdapter(runtime)
    runtime.game.start_encounter("boss_room")
    adapter.begin()
    runtime._advance_to_hero_turn()
    runtime._present_battle(0.016)
    _settle(runtime)
    yield runtime, adapter
    runtime.close()


def _settle(runtime, limit=400):
    for _ in range(limit):
        if not runtime._battle_presentation.busy():
            return
        runtime._present_battle(0.02)
    raise AssertionError("presentation never became idle")


def _role(animator):
    return str(getattr(animator.role, "value", animator.role))


def _use(runtime, ability_id):
    skills = [s for s, _ in runtime._skills_for_actor(runtime._battle_actor())]
    runtime._use_skill(skills.index(ability_id))


def test_every_combatant_has_an_animated_sprite_with_default_staging(battle):
    runtime, adapter = battle
    assert adapter.visuals_enabled and adapter.fallback_reason == ""
    visuals = {v.member_id: v for v in adapter.screen.scene.combatants}
    assert set(visuals) == set(runtime.game.battle.members)
    width = adapter.screen.composer.layout.virtual_width
    heroes = [v for k, v in visuals.items() if k.startswith("hero")]
    enemies = [v for k, v in visuals.items() if not k.startswith("hero")]
    assert all(
        v.anchor.x > width / 2 and v.anchor.facing == "left" for v in heroes
    )  # party on the right
    assert all(
        v.anchor.x < width / 2 and v.anchor.facing == "right" for v in enemies
    )  # enemies on the left
    adapter.textures.draw_count = 0
    runtime._present_battle(0.016)
    assert adapter.textures.draw_count >= len(visuals)  # real texture blits, not a data mock
    idle = adapter.screen.animation.combatant("astral_tyrant:1")
    frames = set()
    for _ in range(40):
        runtime._present_battle(0.03)
        frames.add(idle.frame_index)
    assert len(frames) > 1  # idle animation actually advances


def test_skill_choreography_plays_animation_vfx_audio_camera_in_order(battle):
    runtime, adapter = battle
    screen = adapter.screen
    hero = runtime._battle_actor()
    target = "astral_tyrant:1"
    adapter.audio_cues.clear()
    _use(runtime, "fire_arc")
    runtime._present_battle(0.0)  # the frame that consumes the action
    assert adapter.busy()
    seen = {"attack": None, "vfx": None, "hit": None, "shake": None, "audio": None, "value": None}
    clock = 0.0
    while adapter.busy() and clock < 2.0:
        runtime._present_battle(0.02)
        clock += 0.02
        if seen["attack"] is None and _role(screen.animation.combatant(hero)).startswith("attack"):
            seen["attack"] = clock
        if seen["vfx"] is None and any(
            v.payload.get("asset_id") == "battle.fx.flame" for v in screen.feedback.vfx
        ):
            seen["vfx"] = clock
            assert adapter.particle_count() >= 1
        if seen["hit"] is None and _role(screen.animation.combatant(target)) == "hit":
            seen["hit"] = clock
        if seen["shake"] is None and screen.camera_feedback.camera_offset() != (0.0, 0.0):
            seen["shake"] = clock
        if seen["audio"] is None and any(
            dict(c.payload).get("asset_id") == "hit" for c in adapter.audio_cues
        ):
            seen["audio"] = clock
        if seen["value"] is None and any(v.target_id == target for v in screen.feedback.values):
            seen["value"] = clock
    assert all(v is not None for v in seen.values()), seen
    # Authored order: swing -> effect -> impact (hit pose, damage number, sound and shake
    # together).
    assert seen["attack"] < seen["vfx"] < seen["hit"]
    assert seen["hit"] == seen["value"] == seen["audio"] == seen["shake"]


def test_battle_input_waits_for_the_choreography(battle):
    runtime, adapter = battle
    hero = runtime._battle_actor()
    _use(runtime, "strike")
    runtime._present_battle(0.0)
    acted = runtime._battle_actor()
    key = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1)
    log_before = len(runtime.game.battle_log)
    runtime._battle_input([key])  # ignored while the strike plays
    assert len(runtime.game.battle_log) == log_before and runtime._battle_actor() == acted
    _settle(runtime)
    assert hero is not None


def test_knockout_pose_waits_for_the_killing_blow(battle):
    runtime, adapter = battle
    game = runtime.game
    wisp = next(m for m in game.active_enemy_ids() if m.startswith("mender_wisp"))
    game.battle.member(wisp).subject.resources.set_current(game.rules.knockout_resource_id, 1)
    hero = runtime._battle_actor()
    runtime.game.use_ability(hero, "strike", (wisp,))
    runtime._after_hero_action()
    state = adapter.screen.animation.combatant(wisp)
    runtime._present_battle(0.016)
    assert not state.defeated  # Battle Core already knocked it out...
    _settle(runtime)
    assert state.defeated  # ...the KO pose follows the impact


def test_capture_prompt_appears_in_the_canonical_action_menu(battle):
    from asteria.rpg import CaptureRule

    runtime, adapter = battle
    db = runtime.game.project.rpg_database
    db.add_capture_rule(CaptureRule("mender_wisp", "hero_01", base_chance=0.25))
    runtime._present_battle(0.016)
    labels = [
        e.label for e in adapter.screen.action_menu._source
    ]  # every page of the command menu
    assert any(label.startswith("X  Capture (") for label in labels)


def test_missing_visual_profile_gets_a_generated_combatant_not_the_legacy_screen(
    battle, monkeypatch
):
    runtime, adapter = battle
    runtime.game.project.battle_presentation_library.remove("combatant_visuals", "astral_tyrant")
    monkeypatch.setattr(
        runtime,
        "_draw_battle_world",
        lambda *a, **k: pytest.fail("legacy drawing used"),
        raising=False,
    )
    fresh = CanonicalBattleAdapter(runtime)
    fresh.begin()
    assert fresh.visuals_enabled and not fresh.fallback_reason
    boss = next(
        v for v in fresh.screen.scene.combatants if v.member_id.startswith("astral_tyrant")
    )
    assert boss.sprite_sheet_asset_id == "generated.combatant.astral_tyrant"
    assert fresh.resolver.generated_image(boss.sprite_sheet_asset_id) is not None
    assert set(fresh.resolver.clip_set(boss.sprite_sheet_asset_id).clips) == {
        "weak",
        "idle",
        "attack",
        "hit",
        "ko",
    }
    runtime._battle_presentation = fresh
    runtime._present_battle(0.016)  # draws through the canonical screen


def test_using_a_skill_never_blocks_the_frame_loop(battle):
    """Real-machine finding (D15): the retired legacy effect loop blocked ~430 ms per skill."""
    import time

    runtime, adapter = battle
    start = time.perf_counter()
    _use(runtime, "fire_arc")
    assert time.perf_counter() - start < 0.2  # choreography plays on later frames
    runtime._present_battle(0.016)
    assert adapter.busy()
    _settle(runtime)


# --- D15: side-view staging requested after the first demo -------------------


def _frame(adapter):
    from asteria.runtime.camera import Camera2D

    layout = adapter.screen.composer.layout
    return layout, adapter.screen.build_frame(
        Camera2D(width=layout.virtual_width, height=layout.virtual_height)
    )


def test_combatants_stand_on_the_ground_below_the_backdrop(battle):
    _, adapter = battle
    layout = adapter.screen.composer.layout
    assert layout.party_hud == "bottom_row" and layout.stage_top > 0
    hud_top = layout.virtual_height - layout.margin - 24.0
    for visual in adapter.screen.scene.combatants:
        assert layout.virtual_height * layout.stage_top <= visual.anchor.y <= hud_top


def test_enemy_hp_floats_over_enemies_and_party_hp_sits_in_a_bottom_row(battle):
    runtime, adapter = battle
    layout, frame = _frame(adapter)
    enemies = set(runtime.game.battle.parties["enemies"].ids())
    heroes = set(runtime.game.battle.parties["heroes"].ids())
    overhead = {t.member_id: t for t in frame.texts if t.role == "overhead_name"}
    assert set(overhead) == enemies
    bars = {(g.member_id, g.resource_id) for g in frame.gauges}
    assert all((enemy, "vitality") in bars for enemy in enemies)  # HP over each enemy
    assert all((hero, "vitality") in bars for hero in heroes)  # HP in each party cell
    for enemy in enemies:
        visual = adapter.screen.scene.visual_for(enemy)
        assert (
            overhead[enemy].y < visual.anchor.y - adapter.screen.member_heights[enemy]
        )  # above the head
    hud = [p for p in frame.panels if p.panel_id.startswith("hud:")]
    assert {p.member_id for p in hud} == heroes and len({p.y for p in hud}) == 1


def test_commands_show_only_on_a_heroes_turn_and_never_cover_the_party(battle):
    runtime, adapter = battle
    layout, frame = _frame(adapter)
    menu = next(p for p in frame.panels if p.panel_id == "action_menu")  # idle: hero waiting
    camera_x = [
        v.anchor.x
        for v in adapter.screen.scene.combatants
        if v.member_id in runtime.game.battle.parties["heroes"].ids()
    ]
    assert menu.x + menu.width <= min(camera_x) - 8  # left of the whole party
    _use(runtime, "strike")
    runtime._present_battle(0.016)
    assert adapter.busy()
    playing = _frame(adapter)[1]
    assert not any(p.panel_id == "action_menu" for p in playing.panels)  # hidden during the action
    _settle(runtime)
    runtime._present_battle(0.016)
    back = _frame(adapter)[1]
    assert any(p.panel_id == "action_menu" for p in back.panels)


# --- ENG-10: battle resources are released when play returns to the field ---------


def test_battle_images_are_released_after_the_battle(battle):
    runtime, adapter = battle
    runtime._present_battle(0.016)
    battle_images = [rel for rel, scope in runtime._image_scope.items() if scope == "battle"]
    assert any("battle/" in rel for rel in battle_images)
    battle_images = [rel for rel in battle_images if "/lucifer/ui/" not in rel]  # skin: shared
    game = runtime.game
    for enemy in game.active_enemy_ids():
        game.battle.member(enemy).subject.resources.set_current(game.rules.knockout_resource_id, 0)
    game.finish_victory()
    runtime._victory = False
    runtime._ui_mode = "field"
    runtime._frame([], 0.016)
    assert game.mode == "field"
    assert not any(scope == "battle" for scope in runtime._image_scope.values())
    assert all(rel not in runtime._loaded for rel in battle_images)
    assert runtime.released_images >= len(battle_images)


def test_repeated_battles_keep_the_image_cache_bounded(battle):
    runtime, adapter = battle
    game = runtime.game
    sizes = []
    for _ in range(3):
        if game.mode != "battle":
            game.start_encounter("boss_room")
        runtime._ui_mode = "field"
        runtime._frame([], 0.016)
        runtime._present_battle(0.016)
        for enemy in game.active_enemy_ids():
            game.battle.member(enemy).subject.resources.set_current(
                game.rules.knockout_resource_id, 0
            )
        game.finish_victory()
        runtime._frame([], 0.016)
        sizes.append(len(runtime._loaded))
    assert sizes[0] == sizes[-1]  # nothing accumulates across battles


def _impact_time(runtime, adapter, ability):
    screen = adapter.screen
    _use(runtime, ability)
    runtime._present_battle(0.0)
    clock = 0.0
    while adapter.busy() and clock < 3.0:
        runtime._present_battle(0.01)
        clock += 0.01
        if _role(screen.animation.combatant("astral_tyrant:1")) == "hit":
            return clock
    raise AssertionError("no impact")


def test_hit_stop_beat_freezes_the_action_at_the_impact(battle):
    """BTL-04: a timing/hit_stop beat holds the presentation clock and animation for its
    duration."""
    from asteria.editor import EditorDocument
    from asteria.editor.action_timeline_authoring import ActionTimelineController

    runtime, adapter = battle
    baseline = _impact_time(runtime, adapter, "fire_arc")

    def to_fire_arc_caster():
        for _ in range(12):
            _settle(runtime)
            runtime._advance_to_hero_turn()
            _settle(runtime)
            skills = [s for s, _ in runtime._skills_for_actor(runtime._battle_actor())]
            if "fire_arc" in skills:
                return
            runtime._use_skill(0)
            runtime._present_battle(0.0)
        raise AssertionError("no hero with fire_arc came up")

    to_fire_arc_caster()
    document = EditorDocument()
    document.set_project(runtime.game.project)
    api = ActionTimelineController(document)
    flame_at = next(b.at for b in api.beats("fire_arc") if b.channel == "vfx")
    api.add_beat(
        "fire_arc", "freeze", flame_at, "timing", "hit_stop", member="@source", duration=0.2
    )
    assert api.problems(api.get("fire_arc")) == []
    frozen_clock = adapter._clock
    adapter._start_hit_stop(0.1)
    adapter.update(0.05)
    assert adapter._clock == frozen_clock  # held
    adapter.update(0.1)
    assert adapter._clock == pytest.approx(frozen_clock + 0.05)  # resumes after the hold
    delayed = _impact_time(runtime, adapter, "fire_arc")
    assert delayed == pytest.approx(baseline + 0.2, abs=0.03)


def test_an_authored_state_machine_chooses_the_battle_clips(resource_root, monkeypatch):
    """ANI-02: a sheet's state machine (Animation States editor) drives the battle animation:
    battle roles
    fire its triggers and it picks the clip - here "attack" deliberately plays the sheet's "hit"
    clip."""
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from asteria.editor import EditorDocument
    from asteria.editor.animation_state_machine_authoring import AnimationStateMachineAuthoring

    runtime = _boss_runtime(resource_root)
    try:
        project = runtime.game.project
        sheet = "battle.combatant.hero_01"
        document = EditorDocument(project)
        api = AnimationStateMachineAuthoring(document, resource_root=resource_root)
        clips = api.clips(sheet)
        assert {"idle", "hit"} <= set(clips)
        api.create(sheet, initial_clip="idle")
        api.add_state(sheet, "struck_pose", "hit")
        api.add_parameter(sheet, "attack", trigger=True)
        api.add_transition(
            sheet, "*", "struck_pose", conditions=(("attack", "==", True),), priority=5
        )
        api.add_transition(sheet, "struck_pose", api.definition(sheet).initial, when_finished=True)
        runtime._battle_presentation = adapter = CanonicalBattleAdapter(runtime)
        runtime.game.start_encounter("boss_room")
        adapter.begin()
        animator = adapter.screen.animation.combatant("hero_01")
        assert animator.machine is not None and animator.clip_name == "idle"
        animator.set_role("attack")
        assert (
            animator.machine.state == "struck_pose" and animator.clip_name == "hit"
        )  # the machine chose
        for _ in range(200):
            animator.update(0.05)
            if animator.machine.state == animator.machine.definition.initial:
                break
        assert (
            animator.clip_name == "idle" and animator.role.value == "idle"
        )  # back to rest when finished
    finally:
        runtime.close()


def test_hidden_zones_draw_no_hud_for_their_members(battle):
    """Like Octopath: only the party has a panel; enemies show neither a bar nor a name."""
    import dataclasses

    runtime, adapter = battle
    composer = adapter.screen.composer
    composer.layout = dataclasses.replace(composer.layout, hidden_zones=("left",))
    _, frame = _frame(adapter)
    enemies = set(runtime.game.battle.parties["enemies"].ids())
    heroes = set(runtime.game.battle.parties["heroes"].ids())
    assert not [
        t for t in frame.texts if t.member_id in enemies and not t.role.startswith("timeline")
    ]
    assert not [g for g in frame.gauges if g.member_id in enemies]
    assert not [
        p for p in frame.panels if p.member_id in enemies and not p.role.startswith("timeline")
    ]
    assert {g.member_id for g in frame.gauges} >= heroes  # the party keeps its HUD
