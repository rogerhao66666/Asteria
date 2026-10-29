"""Durability, repair, nicknames, disassembly, job points and New Game Plus in a session."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.project import Project
from asteria.rpg import BattleAction
from asteria.rpg.disassembly import DisassemblyRecipe, DisassemblyYield
from asteria.rpg.durability import DurabilityRules, WearEvent
from asteria.rpg.job_points import JobPointRules
from asteria.rpg.new_game_plus import NewGamePlusRules
from asteria.rpg.progression_graph import ProgressionAllocationRuntime
from asteria.runtime.game_session import GameSessionError, GameSessionRuntime

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "party_rpg_demo"
HERO = "hero_01"
SWORD = "w_sword:hero_01"


def _session(**database):
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    for add, value in database.items():
        getattr(project.rpg_database, add)(value)
    return GameSessionRuntime(project, project.game_start.instantiate(project))


def _wear_rules(**extra):
    return DurabilityRules(
        "wear",
        default_max=3,
        wear=(WearEvent("attack", ["weapon"]), WearEvent("hit", ["accessory"])),
        **extra,
    )


def _sword(game):
    loadout = game.save.rpg_state.loadouts[HERO]
    return next(x for x in loadout.equipped() if x.instance_id == SWORD)


def test_battle_actions_wear_the_actors_weapons_through_the_hook():
    game = _session(add_durability_rules=_wear_rules())
    game.start_encounter(sorted(game.project.rpg_database.encounters)[0])
    foe = next(m for m, member in game.battle.members.items() if member.side == "enemies")
    game.battle.execute(BattleAction(HERO, "attack_sword", (foe,)))
    sword = _sword(game)
    assert sword.durability == 2 and sword.max_durability == 3


def test_a_broken_weapon_gives_nothing_and_the_player_is_told():
    game = _session(add_durability_rules=_wear_rules())
    before = game.resolve_actor_build(HERO)
    assert "attack_sword" in before.abilities
    for _ in range(3):
        game.wear_equipment(HERO, "attack")
    sword = _sword(game)
    assert sword.broken
    told = {n["text"] for n in game.drain_notices()}
    assert f"{sword.equipment.display_name} broke!" in told  # and the other weapon too
    after = game.resolve_actor_build(HERO)
    assert "attack_sword" not in after.abilities  # the broken sword grants nothing


def test_repair_charges_the_price_and_refuses_when_poor():
    rules = _wear_rules(repair_currency="gold", repair_cost_per_point=100)
    game = _session(add_durability_rules=rules)
    for _ in range(3):
        game.wear_equipment(HERO, "attack")
    gold = game.save.rpg_state.currencies["gold"]
    assert game.repair_equipment(HERO, SWORD, 1) == 1
    assert game.save.rpg_state.currencies["gold"] == gold - 100
    game.save.rpg_state.currencies["gold"] = 10.0
    with pytest.raises(GameSessionError, match="costs"):
        game.repair_equipment(HERO, SWORD)
    with pytest.raises(GameSessionError):
        game.repair_equipment(HERO, "nothing")
    with pytest.raises(GameSessionError):
        _session().repair_equipment(HERO, SWORD)


def test_rename_equipment_sets_the_nickname():
    game = _session()
    assert game.rename_equipment(HERO, SWORD, "  Dawn ") == "Dawn"
    assert _sword(game).nickname == "Dawn"
    with pytest.raises(ValueError):
        game.rename_equipment(HERO, SWORD, "x" * 40)


def test_disassemble_through_the_session_is_deterministic_and_atomic():
    recipe = DisassemblyRecipe("fire_bomb", (DisassemblyYield("alchemy_salt", 2, 2),))
    game = _session(add_disassembly_recipe=recipe)
    bag = game.save.rpg_state.inventory
    bag.add("fire_bomb", 1)
    salt = bag.count("alchemy_salt")
    result = game.disassemble("fire_bomb")
    assert result.gained == (("alchemy_salt", 2),) and bag.count("alchemy_salt") == salt + 2
    with pytest.raises(GameSessionError):
        game.disassemble("fire_bomb")  # none left
    with pytest.raises(GameSessionError):
        game.disassemble("ancient_thread")  # no recipe


def test_job_points_are_granted_per_class_after_victory():
    game = _session(add_job_point_rules=JobPointRules("jp", per_battle=5, per_enemy=1))
    state = game.save.rpg_state
    state.progression_allocations[HERO] = ProgressionAllocationRuntime()
    game.start_encounter(sorted(game.project.rpg_database.encounters)[0])
    for member_id in game.active_enemy_ids():
        game.battle.member(member_id).subject.resources.set_current("vitality", 0)
    defeated = len(game._enemy_ids)
    game.finish_victory()
    allocation = state.progression_allocations[HERO]
    classes = state.actor_progression[HERO].active_class_ids
    assert allocation.balance(f"jp.{classes[0]}") == 5 + defeated
    assert allocation.balance(f"jp.{classes[1]}") == (5 + defeated) * 0.5


def test_new_game_plus_returns_a_fresh_save_with_the_carried_parts():
    rules = NewGamePlusRules("ngp", carry=("levels", "currencies"), keep_currency_share=0.5)
    game = _session(add_new_game_plus_rules=rules)
    game.grant_actor_experience(HERO, 5000, level_threshold=1000)
    game.save.rpg_state.currencies["gold"] = 800.0
    game.save.event_context.set_switch("ending.good", True)
    fresh = game.new_game_plus()
    assert fresh.rpg_state.actor_progression[HERO].level >= 5
    start_gold = game.project.game_start.instantiate(game.project).rpg_state.currencies["gold"]
    assert fresh.rpg_state.currencies["gold"] == start_gold + 400.0
    assert not fresh.event_context.get_switch("ending.good")  # switches were not named
    assert game.save.rpg_state.currencies["gold"] == 800.0
    with pytest.raises(GameSessionError):
        _session().new_game_plus()


def test_a_weapon_that_breaks_mid_battle_blocks_its_ability_at_once():
    game = _session(add_durability_rules=_wear_rules())
    game.start_encounter(sorted(game.project.rpg_database.encounters)[0])
    foe = next(m for m, member in game.battle.members.items() if member.side == "enemies")
    assert "attack_sword" in game.battle.member(HERO).ability_ids
    for _ in range(3):
        game.wear_equipment(HERO, "attack")
    assert _sword(game).broken
    with pytest.raises(ValueError, match="source is broken"):
        game.battle.execute(BattleAction(HERO, "attack_sword", (foe,)))
    assert game.battle.blocked_abilities[HERO] >= {"attack_sword"}


def test_a_stat_giving_item_that_breaks_mid_battle_takes_its_bonus_off():
    from asteria.gameplay import ModifierOperation, StatModifier
    from asteria.rpg.items import EquipmentDefinition

    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    project.rpg_database.add_equipment(
        EquipmentDefinition(
            "w_power",
            "Power Blade",
            slot="weapon",
            modifiers=(StatModifier("pow", "power", ModifierOperation.ADD, 25),),
        )
    )
    project.rpg_database.add_durability_rules(_wear_rules())
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    game.equip_definition(HERO, "w_power", slot_id="weapon", replace=True)
    game.start_encounter(sorted(game.project.rpg_database.encounters)[0])
    stats = game.battle.member(HERO).subject.stats
    with_bonus = stats.get("power")
    for _ in range(3):
        game.wear_equipment(HERO, "attack")
    assert stats.get("power") == with_bonus - 25
