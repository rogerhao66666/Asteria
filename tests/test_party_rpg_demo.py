"""The party RPG battle demo (reference_projects/party_rpg_demo), played through the battle
command menu the
player uses (BattleCommands: categories, cursor, boost, targets, ingredients) and, end to end, by
key presses.

Covers: travellers with a main and a secondary job and two weapon kinds; weaknesses revealed by
hitting them;
shields per enemy and Break; Boost repeating attacks and powering spells; divine skills that spend
several boost
points; a skill that needs two weapon kinds; skills of several hits and several damage types;
giving boost
points; calling a pet; concocting; poison that worsens, sleep, silence and attack up."""

import json
from pathlib import Path

import pytest

pygame = pytest.importorskip("pygame")

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "party_rpg_demo"
BP, SHIELD, HP = "bp", "shield", "vitality"
BOSS = "astral_tyrant:1"


def test_demo_manifest_opens_the_victory_aftermath_screen():
    manifest = json.loads((ROOT / "playable_test_manifest.json").read_text())
    assert manifest["battle"]["victory_aftermath"] is True


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
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT, width=960, height=540
    )
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


def _rows(commands, actor):
    """The menu rows now; at the root, every row of Attack, Skills and Items together."""
    if commands.mode == "root":
        return commands.attack_rows(actor) + commands.skill_rows(actor) + commands.item_rows()
    return commands.entries(actor)


def _choose(commands, actor, ability_id, *, category="Skills"):
    """Open the list that has ``ability_id`` (Attack / Skills / Items), move the cursor onto it and
    press Enter."""
    if commands.mode == "root":
        weapons = commands.weapon_ability_ids(actor)
        want = "Attack" if ability_id in weapons else category
        ids = [row.action_id for row in commands.entries(actor)]
        commands.cursor = ids.index(f"root:{want}")
        commands.press("confirm", actor)
    elif commands.category != category and commands.style != "root":
        while commands.category != category:
            commands.press("category", actor)
    ids = [row.action_id for row in _rows(commands, actor)]
    commands.cursor = 0
    for _ in range(ids.index(ability_id)):
        commands.press("down", actor)
    return commands.press("confirm", actor)


def _target(commands, actor, member_id):
    ids = [row.action_id for row in _rows(commands, actor)]
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
    assert {
        "attack_sword",
        "attack_spear",
        "level_slash",
        "twin_fang",
        "brand_of_valor",
        "donate_bp",
    } <= known
    assert {"attack_bow", "attack_dagger", "send_frost_lynx", "venom_strike"} <= set(
        game.battle.member("hero_02").ability_ids
    )
    assert (
        game.battle.battle_resources.current(BOSS, SHIELD) == 6
    )  # each enemy its own shield count
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
    row = next(r for r in _rows(commands, hero) if r.action_id == "brand_of_valor")
    assert (
        not row.enabled and row.disabled_reason == "Needs 3 bp (has 2)" and "3BP" in row.cost_text
    )
    assert (
        not _choose(commands, hero, "brand_of_valor") and commands.message == "Needs 3 bp (has 2)"
    )
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
    row = next(r for r in _rows(commands, hero) if r.action_id == "twin_fang")
    assert not row.enabled and row.disabled_reason == "Needs sword + spear"


def test_one_spell_of_three_elements_reveals_three_weaknesses(demo):
    _runtime, game, commands = demo
    hero = "hero_04"
    _choose(commands, hero, "elemental_barrage")
    _target(commands, hero, BOSS)
    revealed = {label for label, known in game.weaknesses(BOSS) if known}
    assert {"ice", "lightning"} <= revealed and "fire" not in {l for l, _ in game.weaknesses(BOSS)}
    assert (
        len(
            [
                e
                for e in game.battle_log
                if e.kind == "action" and e.ability_id == "elemental_barrage"
            ]
        )
        == 3
    )


def test_donate_boost_then_concoct(demo):
    _runtime, game, commands = demo
    _bp(game, "hero_02", 0)
    _choose(commands, "hero_01", "donate_bp")
    _target(commands, "hero_01", "hero_02")
    assert _bp(game, "hero_02") == 1
    inventory = game.save.rpg_state.inventory
    herbs, dust = inventory.count("healing_herb"), inventory.count("fire_dust")
    hp = {e: game.battle.member(e).subject.resources.current(HP) for e in game.active_enemy_ids()}
    assert not _choose(commands, "hero_03", "concoct") and commands.mode == "ingredients"
    base = [r.action_id for r in _rows(commands, "hero_03")]
    assert base == ["fire_dust", "healing_herb"]  # what a base can be, from the bag
    commands.cursor = base.index("healing_herb")
    commands.press("confirm", "hero_03")
    catalyst = [r.action_id for r in _rows(commands, "hero_03")]
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
        battle.battle_states.apply_trigger(
            "rpg.battle.turn_ended", (battle.member("mender_wisp:2"),)
        )
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
    # the menu is Attack / Skills / Items: open Attack, pick the first weapon, pick the target
    keys = (pygame.K_RETURN, pygame.K_RETURN, pygame.K_RETURN)
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


# -- the other kinds of enemy: each one asks for a different answer -------------------------------


@pytest.fixture
def encounter(monkeypatch):
    import real_window

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    if not real_window.enabled():
        monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
        monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    opened = []

    def start(encounter_id):
        project = Project.load_json(
            ROOT / "project.asteria.json", EditorDocument().component_registry
        )
        runtime = PlayableTestRuntime(
            project, project.game_start.instantiate(project), ROOT, width=960, height=540
        )
        runtime.open()
        if real_window.enabled():
            real_window.set_stage(runtime)
        opened.append(runtime)
        runtime._ui_mode = "field"
        if encounter_id is not None:  # None: stay in the field
            runtime.game.start_encounter(encounter_id)
            runtime._battle_presentation.begin()
            runtime._advance_to_hero_turn()
        return runtime, runtime.game, runtime.battle_commands

    yield start
    for runtime in opened:
        runtime.close()


def _hp(game, member_id, value=None):
    pool = game.battle.member(member_id).subject.resources
    if value is not None:
        pool.set_current(HP, value)
    return pool.current(HP)


def test_every_new_encounter_has_battle_art_shields_and_weaknesses(encounter):
    for encounter_id in ("slime_pit", "old_crypt", "gazer_nest", "samurai_duel"):
        runtime, game, _commands = encounter(encounter_id)
        adapter = runtime._battle_presentation
        runtime._present_battle(0.016)
        assert adapter.visuals_enabled, adapter.fallback_reason
        for enemy in game.active_enemy_ids():
            kind = enemy.split(":", 1)[0]
            assert (
                adapter.screen.scene.visual_for(enemy).sprite_sheet_asset_id
                == f"battle.combatant.{kind}"
            )
            assert game.battle.battle_resources.current(enemy, SHIELD) >= 2 and game.weaknesses(
                enemy
            )


def test_fire_heals_the_gel_slime_and_lightning_breaks_it(encounter):
    _runtime, game, commands = encounter("slime_pit")
    slime = "gel_slime:1"
    _hp(game, slime, 1000)
    _choose(commands, "hero_04", "fireball")  # every enemy: no target to pick
    assert _hp_of(game, slime) > 1000  # absorbed
    shields = game.battle.battle_resources.current(slime, SHIELD)
    _choose(commands, "hero_04", "lightning_bolt")
    _target(commands, "hero_04", slime)
    assert game.battle.battle_resources.current(slime, SHIELD) == shields - 1 and (
        "lightning",
        True,
    ) in game.weaknesses(slime)


def test_the_gel_slime_splits_into_another_slime(encounter):
    _runtime, game, _commands = encounter("slime_pit")
    before = [e for e in game.active_enemy_ids() if e.startswith("gel_slime")]
    game.use_ability("gel_slime:1", "split", ("gel_slime:1",))
    after = [e for e in game.active_enemy_ids() if e.startswith("gel_slime")]
    assert len(after) == len(before) + 1


def test_the_mirror_gazer_reflects_spells_and_cannot_be_put_to_sleep(encounter):
    _runtime, game, commands = encounter("gazer_nest")
    gazer, caster = "mirror_gazer:1", "hero_04"
    _hp(game, caster, 1500)
    gazer_hp = _hp_of(game, gazer)
    _choose(commands, caster, "lightning_bolt")
    _target(commands, caster, gazer)
    assert (
        _hp_of(game, gazer) == gazer_hp and _hp_of(game, caster) < 1500
    )  # it came back to the caster
    game.battle.apply_state("sleep", caster, gazer)
    assert game.turn_prevented(gazer) == ()  # immune.sleep
    spear = _hp_of(game, gazer)
    _choose(commands, "hero_01", "attack_spear")  # weapons get through
    _target(commands, "hero_01", gazer)
    assert _hp_of(game, gazer) < spear


def test_the_bone_wraith_shrugs_off_poison_and_fears_light(encounter):
    _runtime, game, commands = encounter("old_crypt")
    wraith = "bone_wraith:1"
    result = game.battle.apply_state("poison", "hero_02", wraith)
    assert not result.applied and result.immune
    shields = game.battle.battle_resources.current(wraith, SHIELD)
    _choose(commands, "hero_03", "holy_light")
    _target(commands, "hero_03", wraith)
    assert game.battle.battle_resources.current(wraith, SHIELD) == shields - 1


def test_the_iron_samurai_resists_swords_and_needs_a_spear(encounter):
    _runtime, game, commands = encounter("samurai_duel")
    samurai = "iron_samurai:1"
    shields = game.battle.battle_resources.current(samurai, SHIELD)
    assert shields == 8
    _hp(game, samurai, 14000)
    _choose(commands, "hero_01", "attack_sword")
    _target(commands, "hero_01", samurai)
    sword = 14000 - _hp_of(game, samurai)
    _hp(game, samurai, 14000)
    _choose(commands, "hero_01", "attack_spear")
    _target(commands, "hero_01", samurai)
    spear = 14000 - _hp_of(game, samurai)
    assert spear == pytest.approx(sword / 0.5 * 1.3)  # resisted x0.5 against weak x1.3
    assert (
        game.battle.battle_resources.current(samurai, SHIELD) == shields - 1
    )  # only the spear broke a shield


def test_field_enemies_wander_and_touching_one_starts_its_battle(encounter):
    from asteria.core import Transform
    from asteria.runtime.field_ai import VisibleEncounterComponent

    runtime, game, _commands = encounter(None)
    foes = {e.name: e for e in game.scene.entities() if e.has(VisibleEncounterComponent)}
    assert set(foes) == {"Gel Slime", "Bone Wraith", "Mirror Gazer", "Iron Samurai"}
    slime = foes["Gel Slime"].get(Transform)
    start = (slime.x, slime.y)
    for _ in range(40):  # it wanders
        runtime._frame([], 0.05)
    assert game.mode == "field" and (slime.x, slime.y) != start
    game.set_player_position(slime.x, slime.y)
    for _ in range(5):
        runtime._frame([], 0.05)
        if game.mode == "battle":
            break
    assert game.mode == "battle"
    assert {e.split(":", 1)[0] for e in game.active_enemy_ids()} == {"gel_slime", "web_spinner"}


@pytest.mark.parametrize("encounter_id", ["slime_pit", "old_crypt", "gazer_nest", "samurai_duel"])
def test_each_new_battle_is_won_with_the_keyboard_and_every_enemy_move_works(
    encounter, encounter_id
):
    runtime, game, _commands = encounter(encounter_id)
    failures = []
    run = game.run_enemy_turns

    def watched(*args, **kwargs):
        hero, log = run(*args, **kwargs)
        failures.extend(
            f"{member}: {outcome}" for member, outcome in log if isinstance(outcome, Exception)
        )
        return hero, log

    game.run_enemy_turns = watched
    keys = (pygame.K_RETURN, pygame.K_RETURN, pygame.K_RETURN)
    for step in range(6000):
        if runtime._victory or runtime._defeat:
            break
        if step > 600:  # let the enemies act for a while first, then finish
            for enemy in game.active_enemy_ids():
                _hp(game, enemy, min(_hp_of(game, enemy), 300))
        for (
            hero
        ) in game.active_hero_ids():  # keep the party standing so every enemy move gets used
            pool = game.battle.member(hero).subject.resources
            pool.set_current(HP, max(pool.current(HP), pool.maximum(HP) * 0.5))
        waiting = not runtime._battle_presentation.busy() and game.mode == "battle"
        runtime._frame(
            [pygame.event.Event(pygame.KEYDOWN, key=keys[step % 3])] if waiting else [], 0.05
        )
    assert runtime._victory, runtime._last_action_name
    assert failures == []


def test_enemy_ai_never_targets_a_knocked_out_hero(encounter):
    _runtime, game, _commands = encounter("samurai_duel")
    standing = "hero_04"
    for hero in game.active_hero_ids():
        if hero != standing:
            _hp(game, hero, 0)
    battle = game.battle
    for _ in range(30):
        decision = battle.enemy_ai.decide(battle, "iron_samurai_ai", "iron_samurai:1")
        if decision.payload["ability_id"] != "war_cry":
            assert set(decision.target_ids) == {standing}


# -- pets, weapons, multi-hit skills ------------------------------------------------------------
HIT_TAGS = (
    "weapon.sword",
    "weapon.spear",
    "weapon.bow",
    "weapon.axe",
    "weapon.dagger",
    "damage.fire",
    "damage.ice",
    "damage.lightning",
)


@pytest.fixture
def hit_log(demo):
    """Every single hit of every action as ``(ability id, the hit's weapon / damage tags)``."""
    _runtime, game, _commands = demo
    hits = []
    original = game._one_hit

    def spy(actor_id, ability_id, targets, offensive, results, **kwargs):
        tags = game.battle.member(actor_id).subject.tags
        hits.append((ability_id, tuple(t for t in HIT_TAGS if tags.contains(t))))
        return original(actor_id, ability_id, targets, offensive, results, **kwargs)

    game._one_hit = spy
    return hits


def test_the_pet_attack_needs_an_owned_pet_and_hits_harder_when_the_pet_is_stronger(demo, hit_log):
    _runtime, game, commands = demo
    hero = "hero_02"  # Sera, the hunter
    pet = game.active_pet()
    assert (pet.species_id, pet.nickname, pet.level) == ("frost_lynx", "Frosty", 3)
    units = set(game.active_hero_ids())
    row = next(r for r in _rows(commands, hero) if r.action_id == "send_frost_lynx")
    assert row.enabled
    state = game.save.rpg_state
    owned = list(state.pets)
    state.pets.clear()  # no pet: the skill cannot be used
    row = next(r for r in _rows(commands, hero) if r.action_id == "send_frost_lynx")
    assert not row.enabled and row.disabled_reason == "Needs Frost Lynx"
    assert not _choose(commands, hero, "send_frost_lynx")
    assert commands.message == "Needs Frost Lynx"
    state.pets.extend(owned)
    boss = game.battle.member(BOSS).subject.resources
    boss.set_current(HP, 26000)
    shields = game.battle.battle_resources.current(BOSS, SHIELD)
    before = boss.current(HP)
    _choose(commands, hero, "send_frost_lynx")
    assert _target(commands, hero, BOSS)
    assert [t for a, t in hit_log if a == "send_frost_lynx"] == [("damage.ice",)] * 3
    assert game.battle.battle_resources.current(BOSS, SHIELD) < shields  # ice is its weakness
    level3 = before - boss.current(HP)
    assert game.battle.member(hero).subject.stats.get("pet_power") == 40  # 30 + 5 x (3 - 1)
    # the same attack with the pet at level 10 hits harder
    pet.level = 10
    boss.set_current(HP, 26000)
    game.battle.battle_resources.change(BOSS, SHIELD, 6)
    _choose(commands, hero, "send_frost_lynx")
    _target(commands, hero, BOSS)
    assert 26000 - boss.current(HP) > level3
    assert game.battle.member(hero).subject.stats.get("pet_power") == 75
    assert set(game.active_hero_ids()) == units  # the pet never became a unit


def test_a_sent_pet_gains_experience_levels_up_can_be_renamed_and_chosen(demo):
    _runtime, game, commands = demo
    pet = game.active_pet()
    pet.experience = 115.0  # level 3 needs 40 x 3 = 120
    _choose(commands, "hero_02", "send_frost_lynx")
    _target(commands, "hero_02", BOSS)
    for enemy in list(game.active_enemy_ids()):  # win the fight
        member = game.battle.member(enemy)
        game.battle.remove_combatant(enemy, state_id="defeated", reason="test")
        assert member is not None
    game.finish_victory()
    assert pet.level == 4 and pet.experience == pytest.approx(115 + 40 - 120)
    game.rename_pet(pet.instance_id, "Snowball")
    assert pet.name(game.pet_species(pet)) == "Snowball"
    other = game.add_pet("ember_hound", level=2)
    assert game.active_pet() is pet  # the first pet stays chosen until another is picked
    game.set_active_pet(other.instance_id)
    assert game.active_pet() is other
    assert game.pet_stats()["pet_power"] == 34 + 6  # level 2


def test_capturing_an_enemy_gives_an_owned_pet_with_its_level_and_unlocks_its_attack(demo):
    _runtime, game, _commands = demo
    hero = "hero_02"
    hound = next(e for e in game.active_enemy_ids() if e.startswith("ember_hound"))
    assert game.ability_unavailable(hero, "send_ember_hound") == "Needs Ember Hound"
    game.set_active_pet(game.pets()[0].instance_id)
    assert game.ability_unavailable(hero, "send_ember_hound") == "Needs Ember Hound"

    class Always:
        def random(self):
            return 0.0

    assert game.attempt_capture(hero, hound, rng=Always())
    caught = [p for p in game.pets() if p.species_id == "ember_hound"]
    assert len(caught) == 1 and caught[0].level == 2
    assert hound not in game.active_enemy_ids()
    game.set_active_pet(caught[0].instance_id)
    assert game.ability_unavailable(hero, "send_ember_hound") == ""
    # the hound became a pet, not a party member
    assert set(game.save.rpg_state.party_actor_ids) == {"hero_01", "hero_02", "hero_03", "hero_04"}


def test_pets_are_saved_and_loaded(demo):
    from asteria.rpg.save_state import RpgRuntimeState

    _runtime, game, _commands = demo
    game.add_pet("ember_hound", level=5, nickname="Cinder")
    state = game.save.rpg_state
    again = RpgRuntimeState.from_data(state.to_data(), game.project.rpg_database)
    assert [(p.species_id, p.nickname, p.level) for p in again.pets] == [
        ("frost_lynx", "Frosty", 3),
        ("ember_hound", "Cinder", 5),
    ]
    assert again.active_pet_id == state.active_pet_id


def test_each_weapon_has_its_own_attack_and_each_attack_finds_its_own_weakness(demo, hit_log):
    _runtime, game, commands = demo
    # the boss is weak to swords and axes, not to spears or bows
    assert {"attack_sword", "attack_spear"} <= set(game.battle.member("hero_01").ability_ids)
    _choose(commands, "hero_01", "attack_spear")
    _target(commands, "hero_01", BOSS)
    assert ("spear", True) not in game.weaknesses(BOSS)
    assert game.battle.battle_resources.current(BOSS, SHIELD) == 6
    _choose(commands, "hero_03", "attack_axe")
    _target(commands, "hero_03", BOSS)
    assert ("axe", True) in game.weaknesses(BOSS)
    assert game.battle.battle_resources.current(BOSS, SHIELD) == 5
    assert [a for a, _tags in hit_log] == ["attack_spear", "attack_axe"]


def test_changing_the_equipped_weapon_changes_the_attacks_it_gives(demo):
    _runtime, game, _commands = demo
    hero = "hero_01"
    assert {"attack_sword", "attack_spear"} <= set(game.resolve_actor_build(hero).abilities)
    taken = game.unequip_to_bag(hero, "weapon")  # the sword leaves the hand
    assert taken.equipment.equipment_id == "w_sword"
    build = set(game.resolve_actor_build(hero).abilities)
    assert "attack_sword" not in build and "attack_spear" in build
    bag = game.save.rpg_state.equipment_bag
    game.equip_from_bag(hero, bag.index(taken))  # and comes back
    assert "attack_sword" in set(game.resolve_actor_build(hero).abilities)


def test_a_skill_can_strike_once_with_every_weapon_or_five_times_or_three_with_one_spell(
    demo, hit_log
):
    _runtime, game, commands = demo
    # one hit with each weapon, then lightning: sword, spear, sword, spear, lightning
    _bp(game, "hero_01", 3)
    _choose(commands, "hero_01", "brand_of_valor")
    _target(commands, "hero_01", BOSS)
    assert [t for a, t in hit_log if a == "brand_of_valor"] == [
        ("weapon.sword",),
        ("weapon.spear",),
        ("weapon.sword",),
        ("weapon.spear",),
        ("damage.lightning",),
    ]
    # five arrows and an ice finisher
    hit_log.clear()
    _bp(game, "hero_02", 3)
    _choose(commands, "hero_02", "arrowstorm")
    _target(commands, "hero_02", BOSS)
    assert [t for a, t in hit_log if a == "arrowstorm"] == [("weapon.bow",)] * 5 + [
        ("damage.ice",)
    ]
    # one big fire spell lands three times
    hit_log.clear()
    _choose(commands, "hero_04", "grand_inferno")
    _target(commands, "hero_04", BOSS)
    assert [t for a, t in hit_log if a == "grand_inferno"] == [("damage.fire",)] * 3


def _concoct(commands, hero, base, catalyst, target=None):
    assert not _choose(commands, hero, "concoct") and commands.mode == "ingredients"
    for pick in (base, catalyst):
        ids = [r.action_id for r in _rows(commands, hero)]
        commands.cursor = ids.index(pick)
        commands.press("confirm", hero)
    if target is not None:
        assert commands.mode == "target"
        _target(commands, hero, target)


def _hp_of(game, member):
    return game.battle.member(member).subject.resources.current(HP)


@pytest.mark.parametrize(
    "base,catalyst,product",
    [
        ("healing_herb", "fire_dust", "fire_bomb"),
        ("healing_herb", "ice_crystal", "frost_bomb"),
        ("fire_dust", "ice_crystal", "storm_flask"),
        ("healing_herb", "healing_herb", "healing_salve"),
    ],
)
def test_every_concoction_recipe_works_in_battle(demo, base, catalyst, product):
    _runtime, game, commands = demo
    bag = game.save.rpg_state.inventory
    bag.add(base, 2)  # enough for the salve (two of the same)
    before_base, before_catalyst = bag.count(base), bag.count(catalyst)
    enemies = [e for e in game.active_enemy_ids()]
    hurt = {e: _hp_of(game, e) for e in enemies}
    game.battle.member("hero_01").subject.resources.set_current(HP, 100)
    if product == "healing_salve":
        _concoct(commands, "hero_03", base, catalyst, target="hero_01")
        assert _hp_of(game, "hero_01") > 100
    elif product == "storm_flask":
        _concoct(commands, "hero_03", base, catalyst, target="ember_hound:3")
        assert game.battle.member("ember_hound:3").subject.states.get("defense_down") is not None
        assert _hp_of(game, "ember_hound:3") < hurt["ember_hound:3"]
    else:  # a bomb on every enemy: no target to pick
        _concoct(commands, "hero_03", base, catalyst)
        assert all(_hp_of(game, e) < hurt[e] for e in enemies)
    spent = 2 if base == catalyst else 1
    assert bag.count(base) == before_base - spent
    if base != catalyst:
        assert bag.count(catalyst) == before_catalyst - 1
    assert bag.count(product) == 0  # made and used at once


def test_every_secondary_job_skill_works_in_battle(demo):
    _runtime, game, commands = demo
    battle = game.battle
    hound = "ember_hound:3"
    # Sera, thief: a dagger strike that poisons and one that lowers defence
    _choose(commands, "hero_02", "venom_strike")
    _target(commands, "hero_02", hound)
    assert battle.member(hound).subject.states.get("poison") is not None
    _choose(commands, "hero_02", "armor_corrosive")
    _target(commands, "hero_02", hound)
    assert battle.member(hound).subject.states.get("defense_down") is not None
    # Garrick, merchant: gives a boost point away (tested above)
    # Bram, cleric: heals, hurts, cleanses
    battle.member("hero_01").subject.resources.set_current(HP, 50)
    _choose(commands, "hero_03", "heal_wounds")
    assert _hp_of(game, "hero_01") > 50
    before = _hp_of(game, hound)
    _choose(commands, "hero_03", "holy_light")
    _target(commands, "hero_03", hound)
    assert _hp_of(game, hound) < before
    battle.apply_state("poison", hound, "hero_02")
    battle.apply_state("poison", "hero_01", hound)
    _choose(commands, "hero_03", "cleanse")
    _target(commands, "hero_03", "hero_01")
    assert battle.member("hero_01").subject.states.get("poison") is None
    # Ione, dancer: attack up for everyone, and a lullaby that puts one enemy to sleep
    _choose(commands, "hero_04", "peacock_strut")
    assert all(
        battle.member(h).subject.states.get("attack_up") is not None
        for h in game.active_hero_ids()
    )
    import dataclasses

    policies = battle.battle_states.policies  # sleep lands 80 % of the time: make it certain
    policies["sleep"] = dataclasses.replace(policies["sleep"], base_chance=1.0)
    _choose(commands, "hero_04", "sleepy_waltz")
    _target(commands, "hero_04", hound)
    assert battle.member(hound).subject.states.get("sleep") is not None


@pytest.mark.parametrize(
    "hero,ability,hits",
    [
        ("hero_01", "brand_of_valor", 5),
        ("hero_02", "arrowstorm", 6),
        ("hero_03", "last_stand", 1),
        ("hero_04", "elemental_storm", 3),
    ],
)
def test_all_four_divine_skills_wait_for_three_boost_points_then_spend_them(
    demo, hero, ability, hits
):
    _runtime, game, commands = demo
    _bp(game, hero, 2)
    row = next(r for r in _rows(commands, hero) if r.action_id == ability)
    assert not row.enabled and row.disabled_reason == "Needs 3 bp (has 2)"
    _bp(game, hero, 3)
    _choose(commands, hero, ability)
    if commands.mode == "target":  # single target, or an all-targets row that asks nobody
        _target(commands, hero, BOSS)
    assert _bp(game, hero) == 0
    log = [e for e in game.battle_log if e.kind == "action" and e.ability_id == ability]
    assert len(log) >= hits  # an all-targets skill logs once per hit
    if ability == "last_stand":
        assert all(
            game.battle.member(h).subject.states.get("attack_up") is not None
            for h in game.active_hero_ids()
        )


def test_the_pets_screen_lists_pets_chooses_the_active_one_and_renames(demo):
    from asteria.runtime.pets_screen import PetsScreen

    runtime, game, _commands = demo
    game.add_pet("ember_hound", level=4)
    screen = PetsScreen(runtime)
    pressed = set()
    runtime.input.just_pressed = lambda action: action in pressed
    pg = runtime.pg
    pressed.add("move_down")
    screen.handle(0.0, [])
    pressed.clear()
    assert screen.selected().species_id == "ember_hound"
    pressed.add("confirm")
    screen.handle(0.0, [])
    pressed.clear()
    assert game.active_pet().species_id == "ember_hound"
    typed = [pg.event.Event(pg.KEYDOWN, key=pg.K_r, unicode="r", mod=0)]
    screen.handle(0.0, typed)  # R starts renaming
    assert screen.renaming == ""
    letters = [pg.event.Event(pg.KEYDOWN, key=ord(c), unicode=c, mod=0) for c in "Ash"]
    screen.handle(0.0, letters)
    screen.draw()  # the half-typed name is on screen
    screen.handle(0.0, [pg.event.Event(pg.KEYDOWN, key=pg.K_RETURN, unicode="\r", mod=0)])
    assert screen.renaming is None
    assert game.active_pet().nickname == "Ash"
    pressed.add("cancel")
    screen.handle(0.0, [])
    assert screen.closed
    # a game with pets has the entry in its pause menu, a game without does not
    assert any(key == "pets" for key, _label in runtime._pause_menu.options)


# -- the battle screen's layout: dense information must not overlap -----------------------------
def _overlaps(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _screen_rects(runtime):
    """Pixel rects of the party panels, the turn bar, the command menu, every combatant (sprite
    with its name and life bar above) and the shield / weakness blocks under the enemies."""
    adapter = runtime._battle_presentation
    result = adapter.draw()
    frame = result.frame
    runtime._draw_battle_extras()
    scale = runtime.width / adapter.screen.composer.layout.virtual_width
    panels = {}
    for panel in frame.panels:
        if panel.panel_id.startswith("turn:"):
            continue  # tiles inside the turn bar
        panels[panel.panel_id] = (
            panel.x * scale,
            panel.y * scale,
            panel.width * scale,
            panel.height * scale,
        )
    members = {}
    for member in runtime.game.battle.members.values():
        if not runtime.game.battle.is_active(member):
            continue
        where = adapter.member_screen_box(member.member_id)
        if where is None:
            continue
        x, top, feet = where
        members[member.member_id] = (x - 22, top - 34, 44, feet - top + 34)
    blocks = {b.member_id: b.rect() for b in runtime.battle_extras_blocks if b.rect()}
    return panels, members, blocks


@pytest.mark.parametrize("encounter_id", ["boss_room", "slime_pit", "old_crypt", "gazer_nest"])
def test_no_information_covers_other_information_on_the_battle_screen(encounter, encounter_id):
    runtime, game, commands = encounter(encounter_id)
    hero = runtime._turn_actor
    for _ in range(240):  # the boss intro camera settles
        runtime._frame([], 1 / 60)
    for step in ("", "confirm", "cancel", "down", "confirm"):  # root, Attack, root, Skills
        if step:
            commands.press(step, hero)
        for _ in range(10):
            runtime._frame([], 1 / 60)
        panels, members, blocks = _screen_rects(runtime)
        assert any(k.startswith("hud:") for k in panels) and "timeline" in panels
        names = list(panels)
        for i, a in enumerate(names):  # the party list and the turn bar are apart
            for b in names[i + 1 :]:
                if {a, b} & {"action_menu"} or (a + b).count("button:"):
                    continue  # the command menu is the top layer by the acting member
                assert not _overlaps(panels[a], panels[b]), (encounter_id, step, a, b)
        for member_id, rect in members.items():
            for name, panel in panels.items():
                if name == "action_menu":  # the menu may cover others; never the one who acts
                    if member_id == hero:
                        assert not _overlaps(rect, panel), (encounter_id, step, member_id, name)
                    continue
                if name == "timeline" or name.startswith("hud:"):
                    assert not _overlaps(rect, panel), (encounter_id, step, member_id, name)
        for member_id, block in blocks.items():
            for other_id, rect in members.items():
                if other_id != member_id:  # a block under its own sprite is where it belongs
                    assert not _overlaps(block, rect), (encounter_id, step, member_id, other_id)
            for name, panel in panels.items():
                if name != "action_menu" and not name.startswith("button:"):
                    assert not _overlaps(block, panel), (encounter_id, step, member_id, name)
            for other_id, other in blocks.items():
                if other_id != member_id:
                    assert not _overlaps(block, other), (encounter_id, step, member_id, other_id)
        assert (
            0 <= panels["action_menu"][0]
            and panels["action_menu"][0] + panels["action_menu"][2] <= runtime.width
            if "action_menu" in panels
            else True
        )


def test_the_menu_stays_clear_of_every_enemy_name_and_bar_while_the_camera_moves(encounter):
    runtime, game, commands = encounter("boss_room")
    hero = runtime._turn_actor
    for frame in range(150):
        runtime._frame([], 1 / 60)
        if frame == 20:
            commands.press("confirm", hero)
        adapter = runtime._battle_presentation
        frame_view = adapter.draw().frame
        scale = runtime.width / adapter.screen.composer.layout.virtual_width
        menu = [p for p in frame_view.panels if p.panel_id == "action_menu"]
        if not menu:
            continue
        m = (menu[0].x * scale, menu[0].y * scale, menu[0].width * scale, menu[0].height * scale)
        for text in frame_view.texts:
            if text.role == "overhead_name":
                half = 3.0 * len(text.text) * scale / 2 + 4
                rect = (text.x * scale - half, text.y * scale, 2 * half, 8 * scale)
                assert not _overlaps(m, rect), (frame, text.text)
    assert menu
