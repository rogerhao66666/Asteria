"""Turn-based loot and stealing: a drop table that names equipment rolls its rarity and affixes
into the equipment bag; a skill can steal (a tag on the ability, not a menu special case)."""

import dataclasses

from test_battle_extensions_session import _first_encounter, _session

from asteria.rpg import BattleExtensionRules, StealEntry, StealTable
from asteria.rpg.drop_tables import DropEntry, DropTable
from asteria.rpg.loot import AffixDefinition, AffixModifier, RarityDefinition


def _win(game, encounter):
    game.start_encounter(encounter)
    for member_id in tuple(game.active_enemy_ids()):
        game.battle.member(member_id).subject.resources.set_current(
            game.rules.knockout_resource_id, 0
        )
    return game.finish_victory()


def test_a_drop_of_equipment_is_rolled_into_the_equipment_bag():
    game = _session()
    db = game.project.rpg_database
    sword = next(iter(db.equipment))
    db.add_rarity(RarityDefinition("fine", "Fine", "#ffffff", 1, 1, 1.0, 1))
    db.add_affix(
        AffixDefinition("sharp", "Sharp", "prefix", [AffixModifier("power", "add", 3, 3)])
    )
    db.add_drop_table(DropTable("loot", guaranteed=(DropEntry(sword),), rolls=0))
    encounter = _first_encounter(game)
    enemy_id = db.encounters[encounter].members[0].enemy_id
    enemy = db.enemies[enemy_id]
    db.enemies[enemy_id] = dataclasses.replace(
        enemy, reward=dataclasses.replace(enemy.reward, drop_table_id="loot")
    )
    state = game.save.rpg_state
    bag, held = len(state.equipment_bag), state.inventory.count(sword)
    _win(game, encounter)
    assert len(state.equipment_bag) > bag  # a rolled instance, not a count
    dropped = state.equipment_bag[-1]
    assert dropped.equipment.equipment_id == sword and dropped.rarity == "fine"
    assert state.inventory.count(sword) == held  # not also a plain item


def test_a_skill_tagged_steal_robs_its_target():
    probe = _session()
    probe.start_encounter(_first_encounter(probe))
    foe = next(m for m, member in probe.battle.members.items() if member.side == "enemies")
    table = StealTable(foe.split(":")[0], (StealEntry("potion", 1.0, 2),))
    game = _session(BattleExtensionRules("ext", steal_tables=(table,)))
    abilities = game.project.gameplay_library.abilities
    base = abilities.get("attack_axe")
    abilities._definitions["pilfer"] = dataclasses.replace(
        base, ability_id="pilfer", effects=(), tags=(*base.tags, "action.steal")
    )
    db = game.project.rpg_database
    db.battle_targeting["pilfer"] = dataclasses.replace(
        db.battle_targeting["attack_axe"], ability_id="pilfer"
    )
    game.start_encounter(_first_encounter(game))
    hero = game.save.rpg_state.party_active_actor_ids[0]
    member = game.battle.member(hero)
    game.battle.set_member_abilities(hero, (*member.ability_ids, "pilfer"))
    before = game.save.rpg_state.inventory.count("potion")
    game.use_ability(hero, "pilfer", (foe,))
    assert game.save.rpg_state.inventory.count("potion") == before + 2
