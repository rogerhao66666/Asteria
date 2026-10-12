"""The Octopath-style battle demo (reference_projects/octopath_demo), played through the battle command menu the
player uses (BattleCommands: categories, cursor, boost, targets, ingredients) and, end to end, by key presses.

Covers: travellers with a main and a secondary job and two weapon kinds; weaknesses revealed by hitting them;
shields per enemy and Break; Boost repeating attacks and powering spells; divine skills that spend several boost
points; a skill that needs two weapon kinds; skills of several hits and several damage types; giving boost
points; calling a pet; concocting; poison that worsens, sleep, silence and attack up."""

from pathlib import Path

import pytest

pygame = pytest.importorskip("pygame")

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "octopath_demo"
BP, SHIELD, HP = "bp", "shield", "vitality"
BOSS = "astral_tyrant:1"


@pytest.fixture
def demo(monkeypatch):
    import real_window

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    if not real_window.enabled():
        monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
        monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(project, project.game_start.instantiate(project), ROOT, width=960, height=540)
    runtime.open()
    if real_window.enabled():
        real_window.set_stage(runtime)
    runtime._ui_mode = "field"
    game = runtime.game
    game.start_encounter("boss_room")
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    yield runtime, game, runtime.battle_commands
    runtime.close()


def _choose(commands, actor, ability_id, *, category="Skills"):
    """Move the menu cursor onto ``ability_id`` (switching category if needed) and press Enter."""
    while commands.category != category:
        commands.press("category", actor)
    ids = [row.action_id for row in commands.entries(actor)]
    commands.cursor = 0
    for _ in range(ids.index(ability_id)):
        commands.press("down", actor)
    return commands.press("confirm", actor)


def _target(commands, actor, member_id):
    ids = [row.action_id for row in commands.entries(actor)]
    assert commands.mode == "target", commands.mode
    for _ in range(ids.index(member_id)):
        commands.press("down", actor)
    return commands.press("confirm", actor)


def _bp(game, member_id, value=None):
    pool = game.battle.battle_resources
    if value is not None:
        pool.change(member_id, BP, value - pool.current(member_id, BP))
    return pool.current(member_id, BP)


def test_travellers_have_two_jobs_two_weapons_and_their_skills(demo):
    _runtime, game, _commands = demo
    progression = game.save.rpg_state.actor_progression
    assert progression["hero_01"].active_class_ids == ("warrior", "merchant")
    known = set(game.battle.member("hero_01").ability_ids)
    assert {"attack_sword", "attack_spear", "level_slash", "twin_fang", "brand_of_valor", "donate_bp"} <= known
    assert {"attack_bow", "attack_dagger", "call_frost_lynx", "venom_strike"} <= set(
        game.battle.member("hero_02").ability_ids
    )
    assert game.battle.battle_resources.current(BOSS, SHIELD) == 6  # each enemy its own shield count
    assert game.battle.battle_resources.current("mender_wisp:2", SHIELD) == 3


def test_boosted_sword_attack_hits_three_times_breaks_shields_and_reveals_the_weakness(demo):
    _runtime, game, commands = demo
    hero = "hero_01"
    assert ("sword", False) in game.weaknesses(BOSS)  # unknown until hit
    _bp(game, hero, 3)
    for _ in range(2):
        commands.press("right", hero)  # boost x3
    assert commands.boost == 2
    assert not _choose(commands, hero, "attack_sword")
    assert _target(commands, hero, BOSS)
    attacks = [e for e in game.battle_log if e.kind == "action" and e.ability_id == "attack_sword"]
    assert len(attacks) == 3 and _bp(game, hero) == 1
    assert game.battle.battle_resources.current(BOSS, SHIELD) == 3
    assert ("sword", True) in game.weaknesses(BOSS)


def test_break_skips_the_enemy_turn_and_doubles_damage(demo):
    _runtime, game, commands = demo
    hero = "hero_01"
    pool = game.battle.member(BOSS).subject.resources
    pool.set_current(HP, 26000)
    game.battle.battle_resources.change(BOSS, SHIELD, -5)  # one shield left
    before = pool.current(HP)
    _choose(commands, hero, "attack_spear")  # not a weakness of the boss: no shield lost
    _target(commands, hero, BOSS)
    plain = before - pool.current(HP)
    assert game.battle.battle_resources.current(BOSS, SHIELD) == 1
    _choose(commands, hero, "attack_sword")
    _target(commands, hero, BOSS)
    assert game.turn_prevented(BOSS) == ("broken",)
    before = pool.current(HP)
    _choose(commands, hero, "attack_spear")
    _target(commands, hero, BOSS)
    assert before - pool.current(HP) == pytest.approx(plain * 2)
    assert game.battle.battle_resources.current(BOSS, SHIELD) == 6  # restored to its own maximum


def test_divine_skill_needs_three_boost_points_and_spends_them(demo):
    _runtime, game, commands = demo
    hero = "hero_01"
    _bp(game, hero, 2)
    row = next(r for r in commands.entries(hero) if r.action_id == "brand_of_valor")
    assert not row.enabled and row.disabled_reason == "Needs 3 bp (has 2)" and "3 BP" in row.cost_text
    assert not _choose(commands, hero, "brand_of_valor") and commands.message == "Needs 3 bp (has 2)"
    _bp(game, hero, 3)
    _choose(commands, hero, "brand_of_valor")
    assert _target(commands, hero, BOSS)
    assert _bp(game, hero) == 0
    hits = [e for e in game.battle_log if e.kind == "action" and e.ability_id == "brand_of_valor"]
    assert len(hits) == 5  # sword, spear, sword, spear, lightning


def test_twin_fang_needs_a_sword_and_a_spear_equipped(demo):
    _runtime, game, commands = demo
    hero = "hero_01"
    assert game.ability_unavailable(hero, "twin_fang") == ""
    game.battle.member(hero).subject.tags.remove("equip.spear")
    row = next(r for r in commands.entries(hero) if r.action_id == "twin_fang")
    assert not row.enabled and row.disabled_reason == "Needs sword + spear"


def test_one_spell_of_three_elements_reveals_three_weaknesses(demo):
    _runtime, game, commands = demo
    hero = "hero_04"
    _choose(commands, hero, "elemental_barrage")
    _target(commands, hero, BOSS)
    revealed = {label for label, known in game.weaknesses(BOSS) if known}
    assert {"ice", "lightning"} <= revealed and "fire" not in {l for l, _ in game.weaknesses(BOSS)}
    assert len([e for e in game.battle_log if e.kind == "action" and e.ability_id == "elemental_barrage"]) == 3


def test_donate_boost_call_the_pet_and_concoct(demo):
    _runtime, game, commands = demo
    _bp(game, "hero_02", 0)
    _choose(commands, "hero_01", "donate_bp")
    _target(commands, "hero_01", "hero_02")
    assert _bp(game, "hero_02") == 1
    assert _choose(commands, "hero_02", "call_frost_lynx")  # self-targeted: acts at once
    assert "hero_07" in game.active_hero_ids()
    inventory = game.save.rpg_state.inventory
    herbs, dust = inventory.count("healing_herb"), inventory.count("fire_dust")
    hp = {e: game.battle.member(e).subject.resources.current(HP) for e in game.active_enemy_ids()}
    assert not _choose(commands, "hero_03", "concoct") and commands.mode == "ingredients"
    base = [r.action_id for r in commands.entries("hero_03")]
    assert base == ["fire_dust", "healing_herb"]  # what a base can be, from the bag
    commands.cursor = base.index("healing_herb")
    commands.press("confirm", "hero_03")
    catalyst = [r.action_id for r in commands.entries("hero_03")]
    commands.cursor = catalyst.index("fire_dust")
    assert commands.press("confirm", "hero_03")  # a fire bomb on every enemy: no target to pick
    assert (inventory.count("healing_herb"), inventory.count("fire_dust")) == (herbs - 1, dust - 1)
    assert all(game.battle.member(e).subject.resources.current(HP) < hp[e] for e in hp)


def test_poison_worsens_sleep_skips_turns_and_attack_up_raises_damage(demo):
    _runtime, game, commands = demo
    battle = game.battle
    battle.apply_state("poison", "hero_02", "mender_wisp:2")
    pool = battle.member("mender_wisp:2").subject.resources
    pool.set_current(HP, 3800)
    losses = []
    for _ in range(3):
        before = pool.current(HP)
        battle.battle_states.apply_trigger("rpg.battle.turn_ended", (battle.member("mender_wisp:2"),))
        losses.append(before - pool.current(HP))
    assert losses == [180, 360, 540]
    battle.battle_states.policies["sleep"] = battle.battle_states.policies["sleep"].__class__(
        "sleep", prevent_action=True, tick_trigger="rpg.battle.turn_ready"
    )
    battle.apply_state("sleep", "hero_04", "ember_hound:3")
    assert game.turn_prevented("ember_hound:3") == ("sleep",)
    boss = battle.member(BOSS).subject.resources
    boss.set_current(HP, 26000)
    before = boss.current(HP)
    _choose(commands, "hero_01", "attack_spear")
    _target(commands, "hero_01", BOSS)
    plain = before - boss.current(HP)
    _choose(commands, "hero_01", "abide")  # self: attack up
    assert battle.member("hero_01").subject.states.get("attack_up") is not None
    before = boss.current(HP)
    _choose(commands, "hero_01", "attack_spear")
    _target(commands, "hero_01", BOSS)
    assert before - boss.current(HP) > plain * 1.3


def test_the_demo_battle_is_won_with_the_keyboard(demo):
    runtime, game, _commands = demo
    keys = (pygame.K_DOWN, pygame.K_RETURN, pygame.K_RETURN)
    for step in range(6000):
        if runtime._victory or runtime._defeat:
            break
        for enemy in game.active_enemy_ids():  # keep it short: the boss is already worn down
            pool = game.battle.member(enemy).subject.resources
            pool.set_current(HP, min(pool.current(HP), 900))
        waiting = not runtime._battle_presentation.busy() and game.mode == "battle"
        events = [pygame.event.Event(pygame.KEYDOWN, key=keys[step % 3])] if waiting else []
        runtime._frame(events, 0.05)
    assert runtime._victory and game.battle is None  # every enemy beaten through the command menu
