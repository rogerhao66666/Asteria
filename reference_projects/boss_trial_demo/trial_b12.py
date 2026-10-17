"""Third wave of the Boss Trial: the systems a fight leaves behind or builds on - rolled gear
drops (rarity and affixes), stealing, use limits and mastery, boost points earned in a fight, a
capturable pet that fights as a unit and evolves, quests, achievements, enemy levels.

All of it is project data: Database > Game Data (Drop Tables, Rarities, Affixes, Pets, Quests,
Achievements) and Database > Game Systems > Battle Extras / Enemy Levels.
"""

from __future__ import annotations

import dataclasses

import trial_content as tc

from asteria.gameplay.states import StateDefinition
from asteria.rpg import BattleStatePolicy, EquipmentDefinition
from asteria.rpg.ability_build import AbilityEvolutionRule
from asteria.rpg.battle_extensions import ResourceGain, StealEntry, StealTable
from asteria.rpg.capture import CaptureRule
from asteria.rpg.drop_tables import DropEntry, DropTable
from asteria.rpg.enemies import RewardDefinition
from asteria.rpg.enemy_levels import DifficultyLevel, EnemyLevelRules
from asteria.rpg.interactions import InteractionRule
from asteria.rpg.loot import AffixDefinition, AffixModifier, RarityDefinition
from asteria.rpg.pets import PetEvolution, PetMove, PetSpeciesDefinition
from asteria.rpg.progression import ProgressionMilestone, ProgressionTrackDefinition
from asteria.rpg.quests import QuestDefinition, QuestObjective
from asteria.rpg.world_record import AchievementDefinition

HP, BP = tc.HP, tc.BP
ability, op, damage, healing = tc.ability, tc.op, tc.damage, tc.healing
_hits, _state = tc._hits, tc._state
WEAPON_GEAR = tuple(f"w_{k}" for k in tc.WEAPONS)


def loot(c):
    """Gear that drops is rolled: a rarity by weight and random affixes by item level."""
    db = c.db
    for rarity in (
        RarityDefinition("common", "Common", "#d8d8d8", 0, 0, 55.0, 0),
        RarityDefinition("magic", "Magic", "#6c8cff", 1, 2, 30.0, 1, 1, 1),
        RarityDefinition("rare", "Rare", "#ffe066", 3, 4, 12.0, 2, 2, 2),
        RarityDefinition("legendary", "Legendary", "#ff8a30", 5, 6, 2.5, 3, 3, 3),
    ):
        db.add_rarity(rarity)
    for affix_id, name, kind, stat, low, high in (
        ("keen_edge", "Keen", "prefix", "power", 3, 8),
        ("arcane", "Arcane", "prefix", "magic", 3, 8),
        ("sturdy", "Sturdy", "prefix", "defense", 3, 8),
        ("swift", "Swift", "prefix", "speed", 2, 5),
        ("of_the_hawk", "of the Hawk", "suffix", "crit", 1, 4),
        ("of_the_fox", "of the Fox", "suffix", "evade", 1, 4),
    ):
        db.add_affix(
            AffixDefinition(
                affix_id,
                name,
                kind,
                [AffixModifier(stat, "add", low, high, integer=True, per_level=0.3)],
                group=stat,
            )
        )
    db.add_drop_table(
        DropTable(
            "warlord_spoils",
            entries=[DropEntry(g, weight=1.0) for g in WEAPON_GEAR],
            rolls=2,
            nothing_weight=1.0,
            guaranteed=[DropEntry("healing_herb", minimum=1, maximum=3)],
        )
    )
    db.add_drop_table(
        DropTable(
            "wisp_drops",
            entries=[DropEntry("ether_leaf", weight=3.0), DropEntry("healing_herb", weight=3.0)],
            nothing_weight=4.0,
        )
    )
    for enemy_id, table in ((c.boss_id, "warlord_spoils"), ("mender_wisp", "wisp_drops")):
        enemy = db.enemies[enemy_id]
        db.enemies[enemy_id] = dataclasses.replace(
            enemy, reward=dataclasses.replace(enemy.reward, drop_table_id=table)
        )


def extras(c):
    """Steal, use limits, mastery levels that strengthen a skill, boost points from the fight."""
    db = c.db
    rules = db.battle_extension_rules["trial"]
    db.battle_extension_rules["trial"] = dataclasses.replace(
        rules,
        use_limits={"twilight_judgment": 1, "word_of_doom": 1},
        mastery={"dawn_and_dusk": (3, 8), "arcane_tome": (3, 8)},
        steal_tables=(
            StealTable(
                c.boss_id, (StealEntry("ancient_thread", 1.0, 1), StealEntry("ruby_item", 0.5, 1))
            ),
            StealTable("mender_wisp", (StealEntry("ether_leaf", 0.8, 1),), once=False),
        ),
        gains=(
            ResourceGain("kill", BP, flat=1.0),
            ResourceGain("taken", BP, per_max_hp=3.0),
        ),
    )
    # a mastered skill hits harder: the user carries mastery.<skill>.<level> tags
    for skill in ("dawn_and_dusk", "arcane_tome"):
        for level in (1, 2):
            db.interaction_rules[f"mastery_{skill}_{level}"] = InteractionRule(
                f"mastery_{skill}_{level}",
                source_tags_all=(f"mastery.{skill}.{level}",),
                multiplier=1.1,
            )


def pets(c):
    """A wisp that can be captured, fights as its own unit, learns moves and evolves."""
    db = c.db
    for ability_id, label, target, definition in (
        (
            "wisp_bolt",
            "Wisp Bolt",
            "enemy",
            ability(
                "wisp_bolt",
                tags=("magic", "damage.light"),
                effect=op(damage("magic", 9)),
                hits=_hits(1.0, tags=("damage.light",)),
            ),
        ),
        (
            "wisp_mend",
            "Wisp Mend",
            "ally",
            ability("wisp_mend", effect=op(healing(25)), allies=True),
        ),
        (
            "wisp_nova",
            "Wisp Nova",
            "enemies",
            ability(
                "wisp_nova",
                tags=("magic", "damage.light"),
                effect=op(damage("magic", 14)),
                hits=_hits(1.0, tags=("damage.light",)),
                targets=9,
            ),
        ),
    ):
        c.add(definition, target)
        c.skill_names[ability_id] = label
        tc.FX_BY_ABILITY[ability_id] = ("boost", "spark")
    db.pet_species["wisp"] = PetSpeciesDefinition(
        "wisp",
        "Mender Wisp",
        stats={"power": 14, "magic": 30, "defense": 10, "speed": 110},
        growth={"magic": 5, "defense": 2, "speed": 1},
        exp_per_battle=60,
        affinity_per_battle=10,
        battle_unit=True,
        resources={HP: 700},
        battle_abilities=("wisp_bolt", "wisp_mend"),
        learnset=(PetMove("wisp_nova", level=3),),
        evolutions=(PetEvolution("greater_wisp", min_level=5),),
        tags=("light",),
    )
    db.pet_species["greater_wisp"] = PetSpeciesDefinition(
        "greater_wisp",
        "Greater Wisp",
        stats={"power": 20, "magic": 60, "defense": 20, "speed": 40},
        growth={"magic": 6, "defense": 2, "speed": 1},
        battle_unit=True,
        resources={HP: 1600},
        battle_abilities=("wisp_bolt", "wisp_mend", "wisp_nova"),
        tags=("light",),
    )
    db.capture_rules.clear()
    db.add_capture_rule(
        CaptureRule("mender_wisp", pet_species_id="wisp", pet_level=2, base_chance=0.6)
    )


def progress(c):
    """Quests, achievements and enemy levels."""
    db = c.db
    db.add_quest(
        QuestDefinition(
            "slay_vaelor",
            "Slay Vaelor",
            description="Defeat the warlord, bring back herbs for the wounded.",
            objectives=(
                QuestObjective("warlord", "defeat_enemy", target=c.boss_id, required=1),
                QuestObjective("herbs", "item", target="healing_herb", required=3),
            ),
            reward=RewardDefinition(currencies={"gold": 3000}),
        )
    )
    db.add_quest(
        QuestDefinition(
            "wisp_hunt",
            "Wisp Hunt",
            description="Put down ten wisps.",
            objectives=(
                QuestObjective("wisps", "defeat_enemy", target="mender_wisp", required=10),
            ),
            reward=RewardDefinition(currencies={"gold": 1500}),
            prerequisites=("slay_vaelor",),
        )
    )
    for achievement in (
        AchievementDefinition(
            "warlord_slayer",
            "Warlord Slayer",
            description="Defeat Vaelor.",
            kind="defeated",
            target=c.boss_id,
            value=1,
        ),
        AchievementDefinition(
            "wisp_hunter",
            "Wisp Hunter",
            description="Defeat ten wisps.",
            kind="defeated",
            target="mender_wisp",
            value=10,
        ),
        AchievementDefinition(
            "quest_done",
            "Contract Complete",
            description="Complete Slay Vaelor.",
            kind="quest",
            target="slay_vaelor",
            hidden=True,
        ),
    ):
        db.add_achievement(achievement)
    db.add_enemy_level_rules(
        EnemyLevelRules(
            "trial_levels",
            resource_growth={HP: 0.03},
            stat_growth={"power": 0.02, "magic": 0.02},
            reward_growth=0.1,
            difficulties=(
                DifficultyLevel("normal"),
                DifficultyLevel("hard", 1.5, 1.5),
                DifficultyLevel("nightmare", 2.5, 3.0),
            ),
            default_difficulty="normal",
        )
    )


JOB_RULES = {  # job: (level, jobs it needs first)
    "weapon_master": (3, ("duelist",)),
    "sage": (4, ("mystic",)),
    "hero": (8, ("knight", "duelist")),
    "forgemaster": (3, ("knight",)),
    "rogue": (3, ("duelist",)),
    "guardian": (5, ("knight",)),
}


def curves_and_unlocks(c):
    """Levels cost more as they go (a drawn curve) and the advanced jobs ask for something."""
    db = c.db
    db.progression_tracks["level_curve"] = ProgressionTrackDefinition(
        "level_curve",
        "Level curve",
        milestones=tuple(
            ProgressionMilestone(level, 0 if level == 1 else 150 * (level - 1) ** 2)
            for level in range(1, 41)
        ),
    )
    for job, (level, needs) in JOB_RULES.items():
        db.classes[job] = dataclasses.replace(
            db.classes[job], unlock_level=level, unlock_classes=needs
        )


EVOLUTIONS = (  # (source skill, evolved id, label, rank of the battle-experience track, power x)
    ("brave_slash", "brave_slash_ii", "Brave Slash II", 2, 1.5),
    ("rally_cry", "rally_cry_ii", "Rally Cry II", 2, 1.0),
    ("arsenal_barrage", "arsenal_barrage_ii", "Arsenal Barrage II", 3, 1.6),
    ("fireball", "fireball_ii", "Fireball II", 2, 1.5),
)


def evolutions(c):
    """Skills that turn into stronger ones as the party fights: a track of battle experience,
    its ranks, and an evolution rule per skill (Database > Game Data > Ability Evolutions)."""
    db = c.db
    db.progression_tracks["battle_experience"] = ProgressionTrackDefinition(
        "battle_experience",
        "Battle experience",
        milestones=(
            ProgressionMilestone(1, 0),
            ProgressionMilestone(2, 100),
            ProgressionMilestone(3, 300),
        ),
    )
    for enemy_id, amount in ((c.boss_id, 150), ("mender_wisp", 25)):
        enemy = db.enemies[enemy_id]
        reward = enemy.reward
        db.enemies[enemy_id] = dataclasses.replace(
            enemy,
            reward=dataclasses.replace(
                reward, experience={**reward.experience, "battle_experience": float(amount)}
            ),
        )
    abilities = c.abilities._definitions
    for source, result, label, rank, factor in EVOLUTIONS:
        base = abilities.get(source)
        if base is None:
            continue
        hits = [{**h, "power": h.get("power", 1.0) * factor} for h in base.hits]
        evolved = dataclasses.replace(
            base, ability_id=result, hits=hits, display_name=label, tags=base.tags
        )
        abilities[result] = evolved
        db.battle_targeting[result] = dataclasses.replace(
            db.battle_targeting[source], ability_id=result
        )
        c.skill_names[result] = label
        if source in tc.FX_BY_ABILITY:
            tc.FX_BY_ABILITY[result] = tc.FX_BY_ABILITY[source]
        if source in tc.SELF_TARGETED:
            tc.SELF_TARGETED.add(result)
        db.add_ability_evolution(
            AbilityEvolutionRule(
                f"evolve_{source}",
                source,
                result,
                progression_track_id="battle_experience",
                minimum_rank=rank,
            )
        )


def transform(c):
    """A transformation is a piece of equipment in its own slot: it adds stats, tags and skills
    while worn, and wearing the plain one turns the hero back. Both are plain data."""
    db = c.db
    for ability_id, label, target, definition in (
        (
            "dragon_claw",
            "Dragon Claw",
            "enemy",
            ability(
                "dragon_claw",
                tags=("damage.fire", "form.dragon"),
                effect=op(damage("power", 18)),
                hits=_hits(1.0, 1.0, 1.3, tags=("damage.fire",)),
            ),
        ),
        (
            "dragon_breath",
            "Dragon Breath",
            "enemies",
            ability(
                "dragon_breath",
                tags=("magic", "damage.fire", "form.dragon"),
                effect=op(damage("magic", 14)),
                sp=30,
                hits=_hits(1.0, tags=("damage.fire",)),
                targets=9,
                apply_states=[_state("burn")],
            ),
        ),
        (
            "dragon_revert",
            "Revert",
            "self",
            ability(
                "dragon_revert",
                apply_states=[_state("dragon_form", "self", remove=True)],
                commands=[
                    {
                        "command": "EQUIP_ITEM",
                        "args": {
                            "actor_id": "hero_01",
                            "equipment_id": "f_normal",
                            "slot_id": "form",
                            "index": 0,
                        },
                    }
                ],
            ),
        ),
    ):
        c.add(definition, target)
        c.skill_names[ability_id] = label
    # the form's stats and tag are a state: they change at once, in the middle of the fight
    c.library.states._definitions["dragon_form"] = StateDefinition(
        "dragon_form",
        99,
        modifiers=(
            tc._modifier("power", 80, "dragon.power"),
            tc._modifier("magic", 60, "dragon.magic"),
            tc._modifier("defense", 60, "dragon.defense"),
        ),
        contributed_tags=("form.dragon",),
    )
    db.battle_state_policies["dragon_form"] = BattleStatePolicy("dragon_form")
    db.add_equipment(EquipmentDefinition("f_normal", "Human Form", slot="form", tags=("form",)))
    db.add_equipment(
        EquipmentDefinition(
            "f_dragon",
            "Dragon Form",
            slot="form",
            tags=("form", "form.dragon"),
            granted_abilities=("dragon_claw", "dragon_breath", "dragon_revert"),
        )
    )


def escape(c):
    """The swarm can be run from (the escape rule: speed helps); the warlord's hall cannot."""
    db = c.db
    for encounter_id, encounter in db.encounters.items():
        if encounter_id == "boss_room":
            db.encounters[encounter_id] = dataclasses.replace(
                encounter, tags=(*encounter.tags, "no_escape")
            )


def systems(c):
    loot(c)
    extras(c)
    pets(c)
    progress(c)
    curves_and_unlocks(c)
    evolutions(c)
    transform(c)
    escape(c)
