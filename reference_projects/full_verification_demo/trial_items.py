"""Items of the Full Verification: concoctions in battle, an alchemy station, disassembly, a shop,
counter stances (reactions) and weapon swaps in the middle of a fight."""

from __future__ import annotations

import dataclasses

import trial_content as tc

from asteria.gameplay.states import StateDefinition
from asteria.rpg import BattleStatePolicy, ItemDefinition
from asteria.rpg.composition import (
    CompositionOutput,
    CompositionRecipeDefinition,
    CompositionSelection,
)
from asteria.rpg.disassembly import DisassemblyRecipe, DisassemblyYield
from asteria.rpg.economy import ShopDefinition, ShopEntry
from asteria.rpg.reactions import ReactionDefinition

HP, SP = tc.HP, tc.SP
ability, op, damage, healing = tc.ability, tc.op, tc.damage, tc.healing

# in battle: pick a base and a catalyst, the product acts at once
CONCOCTIONS = {
    "healing_salve": ("Healing Salve", ("healing_herb", "healing_herb"), "salve_heal", "self"),
    "fire_bomb": ("Fire Bomb", ("healing_herb", "fire_dust"), "bomb_fire", "enemy"),
    "frost_bomb": ("Frost Bomb", ("healing_herb", "ice_crystal"), "bomb_ice", "enemy"),
    "storm_flask": ("Storm Flask", ("fire_dust", "ice_crystal"), "flask_storm", "enemy"),
    "ether_draught": ("Ether Draught", ("ether_leaf", "healing_herb"), "draught_ether", "self"),
    "phoenix_tonic": ("Phoenix Tonic", ("phoenix_seed", "healing_herb"), "tonic_phoenix", "self"),
}

# at the alchemy station: materials become gems and cards
ALCHEMY = {
    "ruby_item": (("iron_ore",), ("fire_dust",)),
    "sapphire_item": (("silver_ore",), ("ice_crystal",)),
    "topaz_item": (("moon_shard",), ("ether_leaf",)),
    "onyx_item": (("alchemy_salt",), ("guardian_scale",)),
    "card_wolf_item": (("ancient_thread",), ("focus_stone",)),
    "card_golem_item": (("guardian_scale",), ("iron_ore",)),
}

DISASSEMBLY = {  # gems and cards go back to what they were made of
    "ruby_item": (("iron_ore", 1), ("fire_dust", 1)),
    "sapphire_item": (("silver_ore", 1), ("ice_crystal", 1)),
    "onyx_item": (("alchemy_salt", 1), ("guardian_scale", 1)),
    "card_wolf_item": (("ancient_thread", 1), ("focus_stone", 1)),
}

SHOP = (  # item: buy price
    ("healing_herb", 30),
    ("ether_leaf", 60),
    ("fire_dust", 40),
    ("ice_crystal", 40),
    ("iron_ore", 50),
    ("silver_ore", 80),
    ("ancient_thread", 120),
    ("ruby_item", 450),
    ("sapphire_item", 450),
    ("card_wolf_item", 1200),
)


def items_and_alchemy(c):
    db = c.db
    products = {
        "salve_heal": ability("salve_heal", effect=op(healing(35)), mode="self"),
        "bomb_fire": ability(
            "bomb_fire",
            tags=("damage.fire", "magic"),
            effect=op(damage("magic", 12)),
            apply_states=[{"state": "burn"}],
        ),
        "bomb_ice": ability(
            "bomb_ice",
            tags=("damage.ice", "magic"),
            effect=op(damage("magic", 12)),
            apply_states=[{"state": "freeze"}],
        ),
        "flask_storm": ability(
            "flask_storm",
            tags=("damage.lightning", "magic"),
            effect=op(damage("magic", 24)),
            apply_states=[{"state": "defense_down"}],
        ),
        "draught_ether": ability(
            "draught_ether",
            mode="self",
            effect=tc.EffectOperation(tc.EffectOperationKind.RESOURCE_DELTA, SP, 90),
        ),
        "tonic_phoenix": ability(
            "tonic_phoenix",
            mode="self",
            effect=op(healing(60)),
            apply_states=[{"state": "regen", "to": "self"}],
        ),
    }
    db.composition_recipes.clear()
    for recipe_id, (name, (base, catalyst), ability_id, target) in CONCOCTIONS.items():
        c.add(products[ability_id], target)
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
    c.add(ability("concoct", concoct_station="concoct"), "self")
    c.skill_names["concoct"] = "Concoct"
    for item_id, (bases, catalysts) in ALCHEMY.items():
        db.composition_recipes[f"craft_{item_id}"] = CompositionRecipeDefinition(
            f"craft_{item_id}",
            f"Craft {item_id}",
            station="alchemy",
            selections=(
                CompositionSelection("base", bases),
                CompositionSelection("catalyst", catalysts),
            ),
            outputs=(CompositionOutput(item_id),),
        )
    for item_id, yields in DISASSEMBLY.items():
        db.add_disassembly_recipe(
            DisassemblyRecipe(item_id, tuple(DisassemblyYield(i, n, n, 1.0) for i, n in yields))
        )
    db.shops["trial_shop"] = ShopDefinition(
        "trial_shop",
        "Gear & Goods",
        entries=tuple(
            ShopEntry(i, buy_prices={"gold": p}, sell_prices={"gold": p // 4}) for i, p in SHOP
        ),
    )
    actor = db.actors[c.hero_id]
    db.actors[c.hero_id] = dataclasses.replace(actor, abilities=("concoct", "counter_strike"))


def counters(c):
    """A counter stance (hero) and a punishing bulwark (boss), both through reactions."""
    db, library = c.db, c.library
    library.states._definitions["counter_stance"] = StateDefinition(
        "counter_stance", 4, contributed_tags=("state.counter",)
    )
    db.battle_state_policies["counter_stance"] = BattleStatePolicy(
        "counter_stance", tick_trigger="rpg.battle.turn_ended"
    )
    c.add(
        ability(
            "counter_strike",
            tags=("weapon.sword",),
            effect=op(damage("power", 14)),
            hits=tc._hits(1.0, tags=("weapon.sword",)),
        ),
        "enemy",
    )
    c.skill_names["counter_strike"] = "Counter Strike"
    c.add(
        ability(
            "w_counter",
            tags=("weapon.axe",),
            effect=op(damage("power", 7)),
            hits=tc._hits(1.0, tags=("weapon.axe",), checks=["land"]),
        ),
        "enemy",
    )
    db.reactions.clear()
    db.add_reaction(
        ReactionDefinition(
            "hero_counter",
            "rpg.battle.after_action",
            "event_targets",
            target_selector="event_source",
            ability_id="counter_strike",
            reactor_tags=("state.counter",),
        )
    )
    db.add_reaction(
        ReactionDefinition(
            "boss_bulwark_counter",
            "rpg.battle.after_action",
            "event_targets",
            target_selector="event_source",
            ability_id="w_counter",
            reactor_tags=("stance.bulwark",),
        )
    )
    tc.FX_BY_ABILITY.update({"counter_strike": ("slash",), "w_counter": ("circ",)})
    boss = db.enemies[c.boss_id]
    db.enemies[c.boss_id] = dataclasses.replace(boss, abilities=(*boss.abilities, "w_counter"))
