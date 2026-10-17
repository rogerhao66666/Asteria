"""Loot of the ARPG demo: base items per slot, rarities, affixes, sets, uniques and the drop table
of every monster.

An item drops with a rarity (common, magic, rare, legendary; set and unique pieces are fixed). The
rarity decides how many affixes it rolls; each affix is a prefix or a suffix with a value range
that grows with the monster's loot level, limited to the item tags / slots / rarities it names.
"""

from __future__ import annotations

from asteria.gameplay.modifiers import StatModifier
from asteria.rpg import EquipmentDefinition, EquipmentSetBonus, EquipmentSetDefinition
from asteria.rpg.drop_tables import DropEntry, DropTable
from asteria.rpg.loot import AffixDefinition, AffixModifier, RarityDefinition

SLOTS = ("weapon", "helm", "armor", "gloves", "boots", "amulet", "ring")

# id: (name, slot, tags, stats)
BASES = {
    # weapons: melee (blade / axe / mace), ranged (bow / crossbow), caster (staff / wand)
    "short_sword": ("Short Sword", "weapon", ("blade", "melee"), {"power": 4}),
    "long_sword": ("Long Sword", "weapon", ("blade", "melee"), {"power": 7, "dexterity": 1}),
    "war_axe": ("War Axe", "weapon", ("axe", "melee"), {"power": 7, "dexterity": -1}),
    "battle_axe": ("Battle Axe", "weapon", ("axe", "melee"), {"power": 11, "dexterity": -2}),
    "iron_mace": ("Iron Mace", "weapon", ("mace", "melee"), {"power": 6, "defense": 2}),
    "spiked_maul": ("Spiked Maul", "weapon", ("mace", "melee"), {"power": 10, "defense": 1}),
    "hunting_bow": ("Hunting Bow", "weapon", ("bow", "ranged"), {"dexterity": 5}),
    "long_bow": ("Long Bow", "weapon", ("bow", "ranged"), {"dexterity": 9, "power": 1}),
    "hand_crossbow": (
        "Hand Crossbow",
        "weapon",
        ("crossbow", "ranged"),
        {"dexterity": 6, "power": 3},
    ),
    "oak_staff": ("Oak Staff", "weapon", ("staff", "caster"), {"magic": 6}),
    "yew_staff": ("Yew Staff", "weapon", ("staff", "caster"), {"magic": 10}),
    "crystal_wand": ("Crystal Wand", "weapon", ("wand", "caster"), {"magic": 5, "crit": 3}),
    # armour: light (leather), heavy (mail, plate), cloth
    "leather_vest": ("Leather Vest", "armor", ("armor", "light"), {"defense": 4}),
    "studded_leather": (
        "Studded Leather",
        "armor",
        ("armor", "light"),
        {"defense": 7, "dexterity": 1},
    ),
    "chain_mail": ("Chain Mail", "armor", ("armor", "heavy"), {"defense": 8, "dexterity": -1}),
    "plate_armor": ("Plate Armor", "armor", ("armor", "heavy"), {"defense": 14, "dexterity": -2}),
    "cloth_robe": ("Cloth Robe", "armor", ("armor", "cloth"), {"defense": 2, "magic": 3}),
    "mage_robe": ("Mage Robe", "armor", ("armor", "cloth"), {"defense": 4, "magic": 6}),
    "iron_helm": ("Iron Helm", "helm", ("helm", "heavy"), {"defense": 3}),
    "great_helm": ("Great Helm", "helm", ("helm", "heavy"), {"defense": 6}),
    "leather_cap": ("Leather Cap", "helm", ("helm", "light"), {"defense": 2, "dexterity": 1}),
    "wizard_hat": ("Wizard Hat", "helm", ("helm", "cloth"), {"defense": 1, "magic": 4}),
    "leather_gloves": (
        "Leather Gloves",
        "gloves",
        ("gloves", "light"),
        {"defense": 1, "dexterity": 2},
    ),
    "gauntlets": ("Gauntlets", "gloves", ("gloves", "heavy"), {"defense": 3, "power": 2}),
    "silk_gloves": ("Silk Gloves", "gloves", ("gloves", "cloth"), {"magic": 3}),
    "leather_boots": (
        "Leather Boots",
        "boots",
        ("boots", "light"),
        {"defense": 2, "dexterity": 1},
    ),
    "iron_boots": ("Iron Boots", "boots", ("boots", "heavy"), {"defense": 4}),
    "silk_shoes": ("Silk Shoes", "boots", ("boots", "cloth"), {"defense": 1, "magic": 3}),
    "bone_amulet": ("Bone Amulet", "amulet", ("amulet", "jewelry"), {"power": 2, "magic": 2}),
    "silver_amulet": ("Silver Amulet", "amulet", ("amulet", "jewelry"), {"defense": 2, "crit": 2}),
    "copper_ring": ("Copper Ring", "ring", ("ring", "jewelry"), {}),
    "silver_ring": ("Silver Ring", "ring", ("ring", "jewelry"), {"dexterity": 2}),
}

# set pieces: always "set" rarity
SETS = {
    "wanderer": (
        "The Wanderer's Path",
        {
            "wanderer_hood": ("Wanderer's Hood", "helm", {"defense": 3, "dexterity": 3}),
            "wanderer_coat": ("Wanderer's Coat", "armor", {"defense": 6, "power": 3}),
            "wanderer_band": ("Wanderer's Band", "ring", {"magic": 3, "power": 3}),
        },
        ((2, {"power": 6}), (3, {"dexterity": 8, "magic": 8})),
    ),
    "stormweaver": (
        "Stormweaver's Regalia",
        {
            "storm_cowl": ("Stormweaver's Cowl", "helm", {"magic": 6, "shock_dmg": 4}),
            "storm_robe": ("Stormweaver's Robe", "armor", {"defense": 6, "magic": 8}),
            "storm_gloves": ("Stormweaver's Gloves", "gloves", {"magic": 4, "crit": 3}),
        },
        ((2, {"shock_dmg": 8}), (3, {"magic": 14, "crit": 6})),
    ),
    "ironbound": (
        "Ironbound Bulwark",
        {
            "ironbound_helm": ("Ironbound Helm", "helm", {"defense": 8, "power": 2}),
            "ironbound_plate": ("Ironbound Plate", "armor", {"defense": 16}),
            "ironbound_boots": ("Ironbound Boots", "boots", {"defense": 6, "power": 2}),
        },
        ((2, {"defense": 10}), (3, {"defense": 14, "power": 8})),
    ),
}

# uniques: fixed powers, always "unique" rarity - each one defines a build
UNIQUES = {
    "cyclops_eye": (
        "The Cyclops' Eye",
        "ring",
        ("ring",),
        {"power": 6, "magic": 6, "dexterity": 6},
    ),
    "gelatin_aegis": ("Gelatin Aegis", "armor", ("armor", "heavy"), {"defense": 14, "power": 4}),
    "golem_heart": ("Golem Heart", "weapon", ("staff", "caster"), {"magic": 16, "defense": 4}),
    "bloodreaver": ("Bloodreaver", "weapon", ("axe", "melee"), {"power": 16, "crit": 10}),
    "viper_fang": (
        "Viper's Fang",
        "weapon",
        ("bow", "ranged"),
        {"dexterity": 12, "poison_dmg": 18},
    ),
    "tempest_staff": ("Tempest", "weapon", ("staff", "caster"), {"magic": 12, "shock_dmg": 18}),
    "phoenix_circlet": (
        "Phoenix Circlet",
        "helm",
        ("helm", "cloth"),
        {"magic": 8, "fire_dmg": 16},
    ),
    "glacier_ring": ("Glacier Ring", "ring", ("ring",), {"cold_dmg": 14, "defense": 4}),
    "windrunner_boots": (
        "Windrunners",
        "boots",
        ("boots", "light"),
        {"dexterity": 10, "multishot": 1},
    ),
    "wyrm_amulet": (
        "Wyrmheart Amulet",
        "amulet",
        ("amulet",),
        {"power": 8, "magic": 8, "crit": 8},
    ),
}

RARITIES = (
    RarityDefinition("common", "Common", "#d8d8d8", 0, 0, 55.0, 0),
    RarityDefinition("magic", "Magic", "#6c8cff", 1, 2, 30.0, 1, 1, 1),
    RarityDefinition("rare", "Rare", "#ffe066", 3, 4, 12.0, 2, 2, 2),
    RarityDefinition("legendary", "Legendary", "#ff8a30", 5, 6, 2.5, 3, 3, 3),
    RarityDefinition("set", "Set", "#44dd66", 1, 1, 0.0, 4),  # only from set pieces
    RarityDefinition("unique", "Unique", "#c8a46e", 0, 0, 0.0, 5),  # fixed powers
)


def _affix(
    affix_id,
    name,
    position,
    stat,
    low,
    high,
    *,
    group,
    per_level=0.0,
    operation="add",
    integer=True,
    **limits,
):
    return AffixDefinition(
        affix_id,
        name,
        position,
        [AffixModifier(stat, operation, low, high, integer=integer, per_level=per_level)],
        group=group,
        **limits,
    )


MELEE = ["blade", "axe", "mace", "melee"]
RANGED = ["bow", "crossbow", "ranged"]
CASTER = ["staff", "wand", "caster"]
WEAPONS = [*MELEE, *RANGED, *CASTER]


def affixes():
    """About fifty affixes: raw stats, crit, the four elements, defence, and legendary-only."""
    return (
        # offence prefixes
        _affix(
            "sharp",
            "Sharp",
            "prefix",
            "power",
            2,
            5,
            group="power",
            per_level=0.5,
            allowed_tags=MELEE,
        ),
        _affix(
            "brutal",
            "Brutal",
            "prefix",
            "power",
            4,
            9,
            group="power",
            per_level=0.6,
            min_level=4,
            allowed_tags=MELEE,
        ),
        _affix(
            "savage",
            "Savage",
            "prefix",
            "power",
            7,
            13,
            group="power",
            per_level=0.7,
            min_level=8,
            rarities=["rare", "legendary"],
            allowed_tags=MELEE,
        ),
        _affix("keen", "Keen", "prefix", "dexterity", 2, 6, group="dexterity", per_level=0.5),
        _affix(
            "swift",
            "Swift",
            "prefix",
            "dexterity",
            5,
            10,
            group="dexterity",
            per_level=0.6,
            min_level=6,
            rarities=["rare", "legendary"],
        ),
        _affix("arcane", "Arcane", "prefix", "magic", 3, 7, group="magic", per_level=0.6),
        _affix(
            "mystic",
            "Mystic",
            "prefix",
            "magic",
            6,
            12,
            group="magic",
            per_level=0.7,
            min_level=6,
            rarities=["rare", "legendary"],
            allowed_tags=CASTER,
        ),
        _affix(
            "deadly", "Deadly", "prefix", "crit", 2, 5, group="crit", per_level=0.3, weight=0.8
        ),
        _affix(
            "ruthless",
            "Ruthless",
            "prefix",
            "crit",
            5,
            9,
            group="crit",
            per_level=0.4,
            min_level=7,
            rarities=["rare", "legendary"],
            weight=0.6,
        ),
        _affix(
            "searing",
            "Searing",
            "prefix",
            "fire_dmg",
            3,
            7,
            group="element",
            per_level=0.6,
            allowed_tags=[*CASTER, "ring", "amulet", "helm"],
            weight=0.8,
        ),
        _affix(
            "frigid",
            "Frigid",
            "prefix",
            "cold_dmg",
            3,
            7,
            group="element",
            per_level=0.6,
            allowed_tags=[*CASTER, "ring", "amulet", "helm"],
            weight=0.8,
        ),
        _affix(
            "shocking",
            "Shocking",
            "prefix",
            "shock_dmg",
            3,
            7,
            group="element",
            per_level=0.6,
            allowed_tags=[*CASTER, *MELEE, "gloves", "amulet"],
            weight=0.8,
        ),
        _affix(
            "venomous",
            "Venomous",
            "prefix",
            "poison_dmg",
            3,
            7,
            group="element",
            per_level=0.6,
            allowed_tags=[*RANGED, "gloves", "ring", "amulet"],
            weight=0.8,
        ),
        _affix(
            "infernal",
            "Infernal",
            "prefix",
            "fire_dmg",
            8,
            14,
            group="element",
            per_level=0.8,
            min_level=8,
            rarities=["legendary"],
            allowed_tags=[*CASTER, "ring", "amulet"],
        ),
        _affix(
            "glacial",
            "Glacial",
            "prefix",
            "cold_dmg",
            8,
            14,
            group="element",
            per_level=0.8,
            min_level=8,
            rarities=["legendary"],
            allowed_tags=[*CASTER, "ring", "amulet"],
        ),
        _affix(
            "thundering",
            "Thundering",
            "prefix",
            "shock_dmg",
            8,
            14,
            group="element",
            per_level=0.8,
            min_level=8,
            rarities=["legendary"],
            allowed_tags=[*CASTER, *MELEE, "amulet"],
        ),
        _affix(
            "toxic",
            "Toxic",
            "prefix",
            "poison_dmg",
            8,
            14,
            group="element",
            per_level=0.8,
            min_level=8,
            rarities=["legendary"],
            allowed_tags=[*RANGED, "ring", "amulet"],
        ),
        # defence prefixes
        _affix(
            "sturdy",
            "Sturdy",
            "prefix",
            "defense",
            2,
            5,
            group="defense",
            per_level=0.4,
            allowed_tags=["armor", "helm", "gloves", "boots"],
        ),
        _affix(
            "fortified",
            "Fortified",
            "prefix",
            "defense",
            5,
            10,
            group="defense",
            per_level=0.5,
            min_level=5,
            rarities=["rare", "legendary"],
            allowed_tags=["armor", "helm", "gloves", "boots", "heavy"],
        ),
        _affix(
            "warded",
            "Warded",
            "prefix",
            "defense",
            3,
            7,
            group="defense",
            per_level=0.4,
            allowed_tags=["cloth", "amulet", "ring"],
        ),
        # suffixes
        _affix("of_the_bear", "of the Bear", "suffix", "defense", 1, 4, group="defense2"),
        _affix("of_the_fox", "of the Fox", "suffix", "dexterity", 1, 4, group="dex2"),
        _affix("of_the_owl", "of the Owl", "suffix", "magic", 1, 4, group="magic2"),
        _affix("of_might", "of Might", "suffix", "power", 1, 4, group="power2"),
        _affix(
            "of_precision", "of Precision", "suffix", "crit", 1, 4, group="crit2", per_level=0.2
        ),
        _affix(
            "of_the_assassin",
            "of the Assassin",
            "suffix",
            "crit",
            4,
            8,
            group="crit2",
            per_level=0.3,
            min_level=7,
            rarities=["rare", "legendary"],
        ),
        _affix(
            "of_flame", "of Flame", "suffix", "fire_dmg", 2, 5, group="element2", per_level=0.4
        ),
        _affix(
            "of_frost", "of Frost", "suffix", "cold_dmg", 2, 5, group="element2", per_level=0.4
        ),
        _affix(
            "of_storms", "of Storms", "suffix", "shock_dmg", 2, 5, group="element2", per_level=0.4
        ),
        _affix(
            "of_venom", "of Venom", "suffix", "poison_dmg", 2, 5, group="element2", per_level=0.4
        ),
        _affix(
            "of_the_eagle",
            "of the Eagle",
            "suffix",
            "multishot",
            1,
            1,
            group="multi",
            min_level=6,
            rarities=["rare", "legendary"],
            allowed_tags=[*RANGED, "boots"],
            weight=0.4,
        ),
        _affix(
            "of_slaughter",
            "of Slaughter",
            "suffix",
            "power",
            1.05,
            1.15,
            group="power3",
            operation="multiply",
            integer=False,
            min_level=5,
            rarities=["rare", "legendary"],
        ),
        _affix(
            "of_sorcery",
            "of Sorcery",
            "suffix",
            "magic",
            1.05,
            1.15,
            group="magic3",
            operation="multiply",
            integer=False,
            min_level=5,
            rarities=["rare", "legendary"],
            allowed_tags=[*CASTER, "cloth", "amulet"],
        ),
        _affix(
            "of_annihilation",
            "of Annihilation",
            "suffix",
            "power",
            1.2,
            1.35,
            group="power3",
            operation="multiply",
            integer=False,
            min_level=9,
            rarities=["legendary"],
        ),
        _affix(
            "of_the_archmage",
            "of the Archmage",
            "suffix",
            "magic",
            1.2,
            1.35,
            group="magic3",
            operation="multiply",
            integer=False,
            min_level=9,
            rarities=["legendary"],
            allowed_tags=[*CASTER, "cloth", "amulet"],
        ),
        _affix(
            "of_the_titan",
            "of the Titan",
            "suffix",
            "defense",
            1.2,
            1.4,
            group="defense3",
            operation="multiply",
            integer=False,
            min_level=9,
            rarities=["legendary"],
            allowed_tags=["armor", "helm", "heavy"],
        ),
    )


# loot tables: what each monster drops (``common`` = every base item; weights favour gear that
# suits the place)
def _entries(ids, weight=1.0):
    return [DropEntry(i, weight=weight) for i in ids]


COMMON = [
    i for i in BASES if i not in ("hand_crossbow", "spiked_maul", "battle_axe", "plate_armor")
]
HEAVY_HITTERS = (
    "hand_crossbow",
    "spiked_maul",
    "battle_axe",
    "plate_armor",
    "yew_staff",
    "long_bow",
)
SET_PIECES = [i for _, pieces, _ in SETS.values() for i in pieces]


BUILD_UNIQUES = (
    "bloodreaver",
    "viper_fang",
    "tempest_staff",
    "phoenix_circlet",
    "glacier_ring",
    "windrunner_boots",
    "wyrm_amulet",
)


def drop_tables():
    common = _entries(COMMON)
    higher = _entries(HEAVY_HITTERS, 1.5)
    sets = [DropEntry(i, weight=0.25, rarity="set") for i in SET_PIECES]

    def uniques(weight):
        return [DropEntry(i, weight=weight, rarity="unique") for i in BUILD_UNIQUES]

    potions = DropEntry("potion", minimum=1, maximum=2)
    return (
        DropTable("slime", entries=[DropEntry("slime_gel", weight=6), *common], nothing_weight=8),
        DropTable("eye", entries=[DropEntry("eye_lens", weight=6), *common], nothing_weight=6),
        DropTable(
            "skull",
            entries=[DropEntry("bone_shard", weight=4), *common, *sets],
            rolls=2,
            nothing_weight=3,
        ),
        DropTable(
            "elite",
            entries=[*common, *higher, *sets, *uniques(0.05)],
            rolls=3,
            luck_weight_bonus=0.5,
            guaranteed=[potions],
        ),
        DropTable(
            "cyclops",
            entries=[*common, *higher, *sets, *uniques(0.4)],
            rolls=5,
            luck_weight_bonus=1.0,
            guaranteed=[DropEntry("cyclops_eye"), DropEntry("potion", minimum=2, maximum=3)],
        ),
        DropTable(
            "walker", entries=[DropEntry("gear_scrap", weight=5), *common], nothing_weight=6
        ),
        DropTable(
            "drone",
            entries=[DropEntry("gear_scrap", weight=5), *common, *higher, *sets],
            nothing_weight=4,
        ),
        DropTable(
            "golem",
            entries=[*common, *higher, *sets, *uniques(0.5)],
            rolls=5,
            luck_weight_bonus=1.0,
            guaranteed=[DropEntry("golem_heart"), DropEntry("gelatin_aegis")],
        ),
    )


def register(db, icons):
    """Add the equipment, sets, rarities, affixes and drop tables to ``db``."""

    def add(item_id, name, slot, tags, stats):
        db.add_equipment(
            EquipmentDefinition(
                item_id,
                name,
                slot=slot,
                icon_id=icons.get(item_id, ""),
                tags=tags,
                modifiers=[StatModifier(f"{item_id}.{s}", s, "add", v) for s, v in stats.items()],
            )
        )

    for item_id, (name, slot, tags, stats) in BASES.items():
        add(item_id, name, slot, tags, stats)
    for item_id, (name, slot, tags, stats) in UNIQUES.items():
        add(item_id, name, slot, (*tags, "rarity:unique"), stats)
    for set_id, (title, pieces, bonuses) in SETS.items():
        for item_id, (name, slot, stats) in pieces.items():
            add(item_id, name, slot, (slot, "rarity:set"), stats)
        db.add_equipment_set(
            EquipmentSetDefinition(
                set_id,
                title,
                equipment_ids=tuple(pieces),
                bonuses=tuple(
                    EquipmentSetBonus(
                        count,
                        modifiers=[
                            StatModifier(f"{set_id}.{count}.{s}", s, "add", v)
                            for s, v in stats.items()
                        ],
                    )
                    for count, stats in bonuses
                ),
            )
        )
    for rarity in RARITIES:
        db.add_rarity(rarity)
    for affix in affixes():
        db.add_affix(affix)
    for table in drop_tables():
        db.add_drop_table(table)


# the picture of every piece of gear: a file of the Lucifer equipment pack, or ("ninja", file)
# where the pack has no such weapon (bows, wands)
W, C, H, F, M = "Weapons/Png/", "Chest/Png/", "Head/Png/", "Feet/Png/", "Misc/Png/"
ICON_FILES = {
    "short_sword": W + "Common Arming Sword.png",
    "long_sword": W + "Common Greatsword.png",
    "war_axe": W + "Common Bearded Axe.png",
    "battle_axe": W + "Mythic Battleaxe.png",
    "iron_mace": W + "Rare Explorers Hook.png",
    "spiked_maul": W + "Mythic Godhammer.png",
    "hunting_bow": ("ninja", "Items/Weapons/Bow/Sprite.png"),
    "long_bow": ("ninja", "Items/Weapons/Bow2/Sprite.png"),
    "hand_crossbow": ("ninja", "Items/Weapons/Bow2/Sprite.png"),
    "oak_staff": W + "Wizards Pole.png",
    "yew_staff": W + "Mages Spire.png",
    "crystal_wand": ("ninja", "Items/Weapons/MagicWand/Sprite.png"),
    "leather_vest": C + "Rare Explorers Top.png",
    "studded_leather": C + "Common Gambeson.png",
    "chain_mail": C + "Common ChainMail Chestpiece.png",
    "plate_armor": C + "Rare Plate Chestpiece.png",
    "cloth_robe": C + "Common Ragged shirt.png",
    "mage_robe": C + "Magic Wizards Tunic Chestpiece.png",
    "iron_helm": H + "Common Chainmail Helmet.png",
    "great_helm": H + "Rare Plate Helmet.png",
    "leather_cap": H + "Rare Explorers Ushanka.png",
    "wizard_hat": H + "Wizards Hat.png",
    "leather_gloves": M + "Rare Explorers Gloves.png",
    "gauntlets": M + "Rare Explorers Gloves.png",
    "silk_gloves": M + "Rare Explorers Gloves.png",
    "leather_boots": F + "Rare Explorers Boots.png",
    "iron_boots": F + "Rare Plate Boots.png",
    "silk_shoes": F + "Wizards Shoes.png",
    "bone_amulet": M + "Common SIlver Amulet.png",
    "silver_amulet": M + "Wizards Amulet.png",
    "copper_ring": M + "Golden Enchanted Ring.png",
    "silver_ring": M + "Silver Enchanted Ring.png",
    "wanderer_hood": H + "Rare Explorers Ushanka.png",
    "wanderer_coat": C + "Rare Explorers Top.png",
    "wanderer_band": M + "Silver Enchanted Ring.png",
    "storm_cowl": H + "Wizards Hat.png",
    "storm_robe": C + "Magic Sorceress Gambeson.png",
    "storm_gloves": M + "Rare Explorers Gloves.png",
    "ironbound_helm": H + "Rare Plate Helmet.png",
    "ironbound_plate": C + "Rare Plate Chestpiece.png",
    "ironbound_boots": F + "Rare Plate Boots.png",
    "cyclops_eye": M + "Wizards Sparkle Ring.png",
    "gelatin_aegis": C + "Legendary Royal Chestpiece.png",
    "golem_heart": W + "Mages Spire.png",
    "bloodreaver": W + "Legendary Dane Axe.png",
    "viper_fang": ("ninja", "Items/Weapons/Bow/Sprite.png"),
    "tempest_staff": W + "Wizards Pole.png",
    "phoenix_circlet": H + "Legendary Royal Helmet.png",
    "glacier_ring": M + "Silver Enchanted Ring.png",
    "windrunner_boots": F + "Rare Explorers Boots.png",
    "wyrm_amulet": M + "Rare Golden Gem Amulet.png",
}
