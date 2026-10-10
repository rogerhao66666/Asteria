from asteria.gameplay import (
    Effect,
    EffectOperation,
    EffectOperationKind,
    ModifierOperation,
    StatModifier,
)

from .actors import ActorDefinition, ClassDefinition, RpgDatabase
from .enemies import (
    EncounterDefinition,
    EncounterMember,
    EnemyDefinition,
    LootEntry,
    RewardDefinition,
)
from .items import (
    AttachmentDefinition,
    EquipmentDefinition,
    ItemDefinition,
    SocketDefinition,
)
from .progression import ProgressionMilestone, ProgressionTrackDefinition


def simple_rpg_database():
    """Beginner-ready reference RPG data; editable template content."""
    db = RpgDatabase()
    db.add_class(
        ClassDefinition(
            "adventurer",
            "Adventurer",
            stat_bonuses={"attack": 2, "defense": 2, "speed": 1},
            granted_tags=["class.adventurer"],
            granted_abilities=["basic_attack"],
        )
    )
    db.add_actor(
        ActorDefinition(
            "hero",
            "Hero",
            class_id="adventurer",
            base_stats={
                "attack": 10,
                "defense": 10,
                "magic": 10,
                "resistance": 10,
                "speed": 10,
            },
            base_resources={"hp": 100, "mp": 30},
            tags=["actor.player"],
        )
    )
    db.add_item(
        ItemDefinition(
            "potion",
            "Potion",
            tags=["item.consumable"],
            use_effects=[
                Effect(
                    "potion.heal",
                    [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", 30)],
                )
            ],
        )
    )
    db.add_equipment(
        EquipmentDefinition(
            "iron_sword",
            "Iron Sword",
            slot="weapon",
            tags=["equipment.weapon"],
            modifiers=[StatModifier("iron_sword.attack", "attack", ModifierOperation.ADD, 10)],
            sockets=[SocketDefinition("socket_1", accepted_tags=["attachment.weapon"])],
        )
    )
    db.add_attachment(
        AttachmentDefinition(
            "ruby",
            "Ruby",
            tags=["attachment.gem", "attachment.weapon"],
            modifiers=[StatModifier("ruby.attack", "attack", ModifierOperation.ADD, 5)],
        )
    )
    db.add_enemy(
        EnemyDefinition(
            "slime",
            "Slime",
            stats={"attack": 5, "defense": 2},
            resources={"hp": 30},
            tags=["enemy.slime"],
            abilities=["basic_attack"],
            reward=RewardDefinition(
                currencies={"gold": 5},
                experience={"level": 8},
                loot=[LootEntry("potion", chance=0.25)],
            ),
        )
    )
    db.add_encounter(
        EncounterDefinition(
            "field_slimes",
            members=[EncounterMember("slime", count=2)],
            tags=["encounter.field"],
        )
    )
    db.add_progression_track(
        ProgressionTrackDefinition(
            "level",
            "Level",
            milestones=[
                ProgressionMilestone(1, 0),
                ProgressionMilestone(2, 20, stat_bonuses={"attack": 1, "defense": 1}),
                ProgressionMilestone(
                    3,
                    50,
                    stat_bonuses={"attack": 1},
                    granted_abilities=["power_strike"],
                ),
                ProgressionMilestone(4, 100, stat_bonuses={"defense": 2}),
                ProgressionMilestone(5, 180, granted_tags=["rank.veteran"]),
            ],
        )
    )
    return db
