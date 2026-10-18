"""Gear and crafting of the Full Verification (phase 3), Ragnarok / MapleStory / Diablo style.

* **More gear**: a second tier of every weapon (two gem sockets and a card socket), heavy /
  light / cloth armour in two tiers (a card socket) and six accessories (a gem socket).
* **Companion sets** with their own weapons that **grow** (enchant paths, MapleStory star
  force style): Vestments of Dawn (Mira), Regalia of the Grave (Vesper), Raiment of the Zealot
  (Cael); two and three pieces give bonuses. The Outfitter dresses each companion.
* **Gems** in seven kinds, each **fused** into a flawless one at the alchemy station (two of the
  same); **monster cards** (one per foe) drop rarely from minions and always from bosses.
* **Refining** +N for weapons and armour: ores used up per attempt, failures drop a level, a
  Blessed Scroll keeps it (engine: ``RefineRules.materials`` / ``protect_item``).
* More **affixes** on rolled drops, more **concoctions** in battle, more **alchemy** recipes and
  **disassembly** back into materials.
"""

from __future__ import annotations

import dataclasses

import trial_content as tc

from asteria.rpg import (
    AttachmentDefinition,
    EquipmentDefinition,
    EquipmentSetBonus,
    EquipmentSetDefinition,
    ItemDefinition,
    SocketDefinition,
)
from asteria.rpg.composition import (
    CompositionOutput,
    CompositionRecipeDefinition,
    CompositionSelection,
)
from asteria.rpg.disassembly import DisassemblyRecipe, DisassemblyYield
from asteria.rpg.drop_tables import DropEntry
from asteria.rpg.economy import ShopEntry
from asteria.rpg.equipment_growth import (
    EquipmentGrowthDefinition,
    EquipmentGrowthNodeDefinition,
    EquipmentGrowthReward,
)
from asteria.rpg.loot import AffixDefinition, AffixModifier
from asteria.rpg.refine import RefineRules

HP, SP = tc.HP, tc.SP
mod = tc._modifier

WEAPONS_T2 = {  # kind: (id, name, stat bonuses)
    "sword": ("w_steel_sword", "Steel Sword", {"power": 30}),
    "spear": ("w_dragoon_lance", "Dragoon Lance", {"power": 34, "crit": 4}),
    "dagger": ("w_kris", "Kris", {"power": 22, "speed": 8, "crit": 6}),
    "axe": ("w_war_axe", "War Axe", {"power": 40}),
    "bow": ("w_longbow", "Longbow", {"power": 28, "crit": 8}),
    "staff": ("w_ash_staff", "Ash Staff", {"magic": 32}),
}
ARMOR = {  # id: (name, weight class, stat bonuses)
    "a_leather_vest": ("Leather Vest", "light", {"defense": 10, "evade": 4}),
    "a_shadow_garb": ("Shadow Garb", "light", {"defense": 18, "evade": 10, "speed": 4}),
    "a_chain_mail": ("Chain Mail", "heavy", {"defense": 20}),
    "a_knight_plate": ("Knight's Plate", "heavy", {"defense": 34, "power": 6}),
    "a_linen_robe": ("Linen Robe", "cloth", {"defense": 6, "magic": 8}),
    "a_silk_robe": ("Silk Robe", "cloth", {"defense": 12, "magic": 16}),
}
ACCESSORIES = {
    "a_iron_ring": ("Iron Ring", {"defense": 6}),
    "a_ruby_ring": ("Ruby Ring", {"power": 8}),
    "a_moon_pendant": ("Moon Pendant", {"magic": 10}),
    "a_feather_charm": ("Feather Charm", {"speed": 6, "evade": 4}),
    "a_hawk_eye": ("Hawk Eye", {"crit": 8}),
    "a_life_amulet": ("Life Amulet", {"defense": 4, "magic": 4}),
}
SETS = {  # set id: (name, actor, (weapon, armour, accessory) as (id, name, kind, stats), bonuses)
    "dawn": (
        "Vestments of Dawn",
        "hero_02",
        (
            ("w_saint_staff", "Saint's Staff", "staff", {"magic": 36}),
            ("a_dawn_robe", "Dawn Robe", "cloth", {"defense": 14, "magic": 18}),
            ("a_holy_symbol", "Holy Symbol", "", {"magic": 12, "defense": 6}),
        ),
        ({"magic": 20}, {"magic": 30, "defense": 20}),
    ),
    "grave": (
        "Regalia of the Grave",
        "hero_03",
        (
            ("w_bone_scepter", "Bone Scepter", "staff", {"magic": 40}),
            ("a_grave_shroud", "Grave Shroud", "cloth", {"defense": 16, "magic": 14}),
            ("a_phylactery", "Phylactery", "", {"magic": 14, "crit": 4}),
        ),
        ({"magic": 24}, {"magic": 34, "crit": 8}),
    ),
    "zealot": (
        "Raiment of the Zealot",
        "hero_04",
        (
            ("w_ritual_kris", "Ritual Kris", "dagger", {"power": 30, "crit": 8}),
            ("a_zealot_mail", "Zealot Mail", "light", {"defense": 20, "speed": 6}),
            ("a_blood_amulet", "Blood Amulet", "", {"power": 10, "crit": 6}),
        ),
        ({"power": 20}, {"power": 30, "speed": 10}),
    ),
}
GEMS = {  # gem: (name, stat bonuses) - ruby, sapphire, topaz, onyx exist; three more here
    "emerald": ("Emerald", {"speed": 6, "evade": 6}),
    "amethyst": ("Amethyst", {"magic": 7, "crit": 4}),
    "diamond": ("Diamond", {"defense": 12}),
}
GEM_RECIPES = {  # new gem item: (base, catalyst)
    "emerald_item": ("silver_ore", "ether_leaf"),
    "amethyst_item": ("moon_shard", "ice_crystal"),
    "diamond_item": ("guardian_scale", "silver_ore"),
}
CARDS = {  # card: (name, foe, stat bonuses, extra tags)
    "card_slinger": ("Slinger Card", "goblin_slinger", {"speed": 8, "crit": 6}, ()),
    "card_beast": ("Beast Card", "goblin_beast", {"power": 20}, ()),
    "card_hunter": ("Hunter Card", "skeleton_hunter", {"crit": 12}, ()),
    "card_ancient": ("Ancient Card", "skeleton_ancient", {"magic": 22}, ("absorb.dark",)),
    "card_acolyte": ("Acolyte Card", "mender_wisp", {"magic": 8, "defense": 8}, ()),
    "card_vaelor": ("Vaelor Card", "crimson_warlord", {"power": 18, "defense": 18}, ()),
}
BOSSES = ("goblin_beast", "skeleton_ancient", "crimson_warlord")
CONCOCTIONS = {  # product: (name, base, catalyst, ability id, targeting, ability builder key)
    "poison_vial": ("Poison Vial", "healing_herb", "alchemy_salt", "vial_poison", "enemy"),
    "smoke_bomb": ("Smoke Bomb", "fire_dust", "alchemy_salt", "bomb_smoke", "enemy"),
    "holy_water": ("Holy Water", "ether_leaf", "moon_shard", "water_holy", "self"),
}
AFFIXES = (  # id, name, position, stat, low, high
    ("vampiric", "Vampiric", "prefix", "lifesteal", 0.02, 0.05),
    ("blazing", "Blazing", "prefix", "power", 5, 12),
    ("of_the_bear", "of the Bear", "suffix", "defense", 4, 10),
    ("of_wisdom", "of Wisdom", "suffix", "magic", 4, 10),
    ("deadly", "Deadly", "prefix", "crit", 2, 6),
    ("of_haste", "of Haste", "suffix", "speed", 2, 6),
)


def _mods(stats, source):
    return tuple(mod(stat, value, f"{source}.{stat}") for stat, value in stats.items())


def _attack(kind):
    return f"attack_{kind}"


def forge(c):
    db = c.db
    gear(c)
    sets(c)
    gems_and_cards(c)
    refine(c)
    crafting(c)
    for affix_id, name, position, stat, low, high in AFFIXES:
        db.add_affix(
            AffixDefinition(
                affix_id,
                name,
                position,
                [AffixModifier(stat, "add", low, high, integer=stat != "lifesteal")],
                group=f"{stat}.extra",
            )
        )


def gear(c):
    db = c.db
    for kind, (eid, name, stats) in WEAPONS_T2.items():
        db.add_equipment(
            EquipmentDefinition(
                eid,
                name,
                slot="weapon",
                tags=("weapon", f"equip.{kind}", "tier.2"),
                modifiers=_mods(stats, eid),
                granted_abilities=(_attack(kind),),
                sockets=(
                    SocketDefinition("g1", accepted_tags=("gem",)),
                    SocketDefinition("g2", accepted_tags=("gem",)),
                    SocketDefinition("c1", accepted_tags=("card",)),
                ),
            )
        )
    for eid, (name, weight, stats) in ARMOR.items():
        db.add_equipment(
            EquipmentDefinition(
                eid,
                name,
                slot="armor",
                tags=("armor", f"armor.{weight}"),
                modifiers=_mods(stats, eid),
                sockets=(SocketDefinition("c1", accepted_tags=("card",)),),
            )
        )
    for eid, (name, stats) in ACCESSORIES.items():
        db.add_equipment(
            EquipmentDefinition(
                eid,
                name,
                slot="accessory",
                tags=("accessory",),
                modifiers=_mods(stats, eid),
                sockets=(SocketDefinition("g1", accepted_tags=("gem",)),),
            )
        )


def _growth(set_id, weapon_id, stat):
    """An enchanting path for a set weapon: Kindle (a card socket), three Stars, then one of
    two exclusive Paths (an element), and a Masterwork that needs every star."""
    reward = EquipmentGrowthReward
    nodes = (
        EquipmentGrowthNodeDefinition(
            "kindle",
            "Kindle",
            auto_unlock=False,
            rewards=reward(unlocked_sockets=("c1",), modifiers=(mod(stat, 8, f"{set_id}.k"),)),
        ),
        EquipmentGrowthNodeDefinition(
            "star",
            "Star Force",
            max_rank=3,
            auto_unlock=False,
            prerequisites=("kindle",),
            rewards=[reward(modifiers=(mod(stat, 6, f"{set_id}.s{i}"),)) for i in (1, 2, 3)],
        ),
        EquipmentGrowthNodeDefinition(
            "light_path",
            "Path of Light",
            auto_unlock=False,
            prerequisites=("kindle",),
            exclusive_group="path",
            rewards=reward(granted_tags=("damage.light",)),
        ),
        EquipmentGrowthNodeDefinition(
            "shadow_path",
            "Path of Shadow",
            auto_unlock=False,
            prerequisites=("kindle",),
            exclusive_group="path",
            rewards=reward(granted_tags=("damage.dark",)),
        ),
        EquipmentGrowthNodeDefinition(
            "masterwork",
            "Masterwork",
            auto_unlock=False,
            prerequisites=(("star", 3),),
            rewards=reward(
                modifiers=(mod(stat, 20, f"{set_id}.m"), mod("crit", 6, f"{set_id}.mc"))
            ),
        ),
    )
    return EquipmentGrowthDefinition(f"{weapon_id}_growth", f"{weapon_id} Enchant", nodes=nodes)


def sets(c):
    db = c.db
    for set_id, (name, _actor, pieces, (two, three)) in SETS.items():
        for eid, piece_name, kind, stats in pieces:
            if eid.startswith("w_"):
                stat = next(iter(stats))
                db.add_equipment_growth(_growth(set_id, eid, stat))
                definition = EquipmentDefinition(
                    eid,
                    piece_name,
                    slot="weapon",
                    tags=("weapon", f"equip.{kind}", f"set.{set_id}", "unique"),
                    modifiers=_mods(stats, eid),
                    granted_abilities=(_attack(kind),),
                    sockets=(
                        SocketDefinition("g1", accepted_tags=("gem",)),
                        SocketDefinition("g2", accepted_tags=("gem",)),
                        SocketDefinition("c1", accepted_tags=("card",), locked=True),
                    ),
                    growth_id=f"{eid}_growth",
                )
            elif kind:
                definition = EquipmentDefinition(
                    eid,
                    piece_name,
                    slot="armor",
                    tags=("armor", f"armor.{kind}", f"set.{set_id}"),
                    modifiers=_mods(stats, eid),
                    sockets=(SocketDefinition("c1", accepted_tags=("card",)),),
                )
            else:
                definition = EquipmentDefinition(
                    eid,
                    piece_name,
                    slot="accessory",
                    tags=("accessory", f"set.{set_id}"),
                    modifiers=_mods(stats, eid),
                    sockets=(SocketDefinition("g1", accepted_tags=("gem",)),),
                )
            db.add_equipment(definition)
        db.add_equipment_set(
            EquipmentSetDefinition(
                set_id,
                name,
                equipment_ids=tuple(p[0] for p in pieces),
                bonuses=(
                    EquipmentSetBonus(2, modifiers=_mods(two, f"{set_id}.set2")),
                    EquipmentSetBonus(3, modifiers=_mods(three, f"{set_id}.set3")),
                ),
            )
        )


def _socketable(c, attachment_id, name, kind, stats, tags=()):
    c.db.add_attachment(
        AttachmentDefinition(
            attachment_id, name, tags=(kind, *tags), modifiers=_mods(stats, attachment_id)
        )
    )
    c.db.add_item(
        ItemDefinition(
            f"{attachment_id}_item",
            name,
            stack_limit=20,
            attachment_id=attachment_id,
            destroyed_on_removal=kind == "card",
        )
    )


def gems_and_cards(c):
    db = c.db
    base = {
        "ruby": ("Ruby", {"power": 9}),
        "sapphire": ("Sapphire", {"magic": 9}),
        "topaz": ("Topaz", {"speed": 6, "crit": 6}),
        "onyx": ("Onyx", {"lifesteal": 0.06}),
    }
    for gem, (name, stats) in GEMS.items():
        _socketable(c, gem, name, "gem", stats)
    for gem, (name, stats) in {**base, **GEMS}.items():
        flawless = f"flawless_{gem}"
        _socketable(c, flawless, f"Flawless {name}", "gem", {k: v * 2 for k, v in stats.items()})
        db.composition_recipes[f"fuse_{gem}"] = CompositionRecipeDefinition(
            f"fuse_{gem}",
            f"Fuse {name}",
            station="alchemy",
            selections=(
                CompositionSelection("base", (f"{gem}_item",)),
                CompositionSelection("catalyst", (f"{gem}_item",)),
            ),
            outputs=(CompositionOutput(f"{flawless}_item"),),
        )
    for item_id, (base_item, catalyst) in GEM_RECIPES.items():
        db.composition_recipes[f"craft_{item_id}"] = CompositionRecipeDefinition(
            f"craft_{item_id}",
            f"Craft {item_id}",
            station="alchemy",
            selections=(
                CompositionSelection("base", (base_item,)),
                CompositionSelection("catalyst", (catalyst,)),
            ),
            outputs=(CompositionOutput(item_id),),
        )
    for card, (name, foe, stats, tags) in CARDS.items():
        _socketable(c, card, name, "card", stats, tags)
        enemy = db.enemies[foe]
        table_id = enemy.reward.drop_table_id
        table = db.drop_tables[table_id]
        if foe in BOSSES:  # a boss always leaves its card
            table = dataclasses.replace(
                table, guaranteed=(*table.guaranteed, DropEntry(f"{card}_item"))
            )
        else:  # a minion rarely
            table = dataclasses.replace(
                table, entries=(*table.entries, DropEntry(f"{card}_item", weight=0.3))
            )
        db.drop_tables[table_id] = table


def refine(c):
    db = c.db
    db.add_item(ItemDefinition("blessed_scroll", "Blessed Scroll", stack_limit=20))
    weapon = db.refine_rules["plus"]
    db.refine_rules["plus"] = dataclasses.replace(
        weapon, materials=(("iron_ore", 1),), protect_item="blessed_scroll"
    )
    db.add_refine_rules(
        RefineRules(
            "plus_armor",
            max_level=10,
            equipment_tags=("armor",),
            bonuses={"defense": 4.0},
            currency="gold",
            base_cost=150,
            cost_growth=120,
            success=[1, 1, 0.9, 0.7, 0.6, 0.5, 0.4, 0.3, 0.25, 0.2],
            on_fail="drop",
            safe_until=2,
            materials={"silver_ore": 1},
            protect_item="blessed_scroll",
        )
    )


def crafting(c):
    db = c.db
    products = {
        "vial_poison": tc.ability(
            "vial_poison",
            tags=("damage.dark", "magic"),
            effect=tc.op(tc.damage("magic", 8)),
            apply_states=[{"state": "poison"}, {"state": "power_down"}],
        ),
        "bomb_smoke": tc.ability(
            "bomb_smoke",
            tags=("magic",),
            effect=tc.op(tc.damage("magic", 4)),
            apply_states=[{"state": "blind"}],
        ),
        "water_holy": tc.ability(
            "water_holy",
            mode="self",
            effect=tc.op(tc.healing(30)),
            apply_states=[{"state": "ward", "to": "self"}],
        ),
    }
    for recipe_id, (name, base, catalyst, ability_id, target) in CONCOCTIONS.items():
        c.add(products[ability_id], target)
        c.skill_names[ability_id] = name
        db.add_item(
            ItemDefinition(recipe_id, name, tags=("concoction",), battle_ability=ability_id)
        )
        db.composition_recipes[recipe_id] = CompositionRecipeDefinition(
            recipe_id,
            name,
            station="concoct",
            selections=(
                CompositionSelection("base", (base,)),
                CompositionSelection("catalyst", (catalyst,)),
            ),
            outputs=(CompositionOutput(recipe_id),),
        )
    for gem in (*GEMS, "topaz"):  # gems break back into what they were made of
        item_id = f"{gem}_item"
        if item_id in db.disassembly_recipes:
            continue
        materials = GEM_RECIPES.get(item_id, ("moon_shard", "ether_leaf"))
        db.add_disassembly_recipe(
            DisassemblyRecipe(item_id, tuple(DisassemblyYield(i, 1, 1, 1.0) for i in materials))
        )
    shop = db.shops["trial_shop"]
    extra = (
        ("blessed_scroll", 300),
        ("emerald_item", 450),
        ("amethyst_item", 450),
        ("diamond_item", 450),
        ("alchemy_salt", 60),
        ("moon_shard", 90),
        ("guardian_scale", 120),
    )
    db.shops["trial_shop"] = dataclasses.replace(
        shop,
        entries=(
            *shop.entries,
            *(
                ShopEntry(i, buy_prices={"gold": p}, sell_prices={"gold": p // 4})
                for i, p in extra
            ),
        ),
    )


def outfitter_steps(say, world, menu):
    """The Outfitter dresses a companion in their set (weapon, armour, accessory)."""
    options = []
    for _set_id, (name, actor_id, pieces, _bonus) in SETS.items():
        who = {"hero_02": "Mira", "hero_03": "Vesper", "hero_04": "Cael"}[actor_id]
        steps = [
            world("EQUIP_ITEM", actor_id=actor_id, equipment_id=eid, index=0) for eid, *_ in pieces
        ]
        steps.append(say("Outfitter", f"{who} wears the {name}."))
        options.append((f"{who}: {name}", steps))
    options.append(("Leave", [say("Outfitter", "Come back in one piece.")]))
    return menu("Outfitter", "Whom shall I dress?", options)
