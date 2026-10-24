"""Hearthfold's Alchemy Table and Forge (U4): two workstations, their tabs and recipes.

* **Alchemy Table** (``alchemy``, below the Duelist Teacher, beside Apothecary Sela): Potions
  (new brews of the G2 materials: potions, cures, a Hi-Potion whose quality can give two or a
  Mega Potion, an Elixir that can fail and waits to be discovered), Gems, Fusion and Cards (the
  recipes the workshop's Alchemist already made, now tagged), and a Disassembly tab for gems
  and cards.
* **Forge** (``forge``, below Weaponsmith Brann): Ingots (mithril; gold can fail), Throwing
  (iron balls and bombs) and Orbs (fire and ice orbs from gems and mithril, both undiscovered at
  first), up to ten at once.

The two stations are objects on the plaza: a pot and an anvil (Ninja Adventure, CC0, as the
other townsfolk). The success picture is the demo's heal effect; the sounds are its own heal
and hit. ``apply(project, root)`` adds what is missing and can run again; ``build_project.py``
runs it after ``trial_shops``.
"""

from __future__ import annotations

from dataclasses import replace

# recipe id: (name, (base items), (catalyst items), (output, amount), options)
POTIONS = {
    "brew_potion": ("Brew Potion", ("healing_herb",), ("bat_wing",), ("potion", 2), {}),
    "brew_hi_potion": (
        "Brew Hi-Potion",
        ("potion", "potion"),
        ("ether_leaf",),
        ("hi_potion", 1),
        {
            "quality_tiers": (
                ("Fine", 0.6, (("hi_potion", 2),)),
                ("Masterwork", 0.9, (("mega_potion", 1),)),
            )
        },
    ),  # fmt: skip
    "brew_antidote": ("Brew Antidote", ("scorpion_claw",), ("healing_herb",), ("antidote", 2), {}),
    "brew_eye_drops": ("Brew Eye Drops", ("bat_wing",), ("ether_leaf",), ("eye_drops", 2), {}),
    "brew_elixir": (
        "Brew Elixir",
        ("phoenix_seed", "gold_ingot"),
        ("mithril_ingot",),
        ("elixir", 1),
        {"success_chance": 0.7, "failure_outputs": (("potion", 1),), "requires_discovery": True},
    ),
}
FORGE = {
    "smelt_mithril": ("Smelt Mithril Ingot", ("silver_ore", "silver_ore"), ("coal",),
                      ("mithril_ingot", 1), {"tags": ("smelt",)}),
    "smelt_gold": ("Smelt Gold Ingot", ("iron_ore", "fire_dust"), ("coal",), ("gold_ingot", 1),
                   {"tags": ("smelt",), "success_chance": 0.8, "failure_outputs": (("coal", 1),)}),
    "forge_iron_ball": ("Forge Iron Ball", ("iron_ore",), ("coal",), ("iron_ball", 3),
                        {"tags": ("bomb",)}),
    "forge_thunder_bomb": ("Forge Thunder Bomb", ("iron_ball",), ("scorpion_claw",),
                           ("thunder_bomb", 1), {"tags": ("bomb",)}),
    "forge_wind_bomb": ("Forge Wind Bomb", ("iron_ball",), ("bat_wing",), ("wind_bomb", 1),
                        {"tags": ("bomb",)}),
    "forge_fire_orb": ("Forge Fire Orb", ("ruby_item",), ("mithril_ingot",), ("fire_orb_item", 1),
                       {"tags": ("orb",), "requires_discovery": True}),
    "forge_ice_orb": ("Forge Ice Orb", ("sapphire_item",), ("mithril_ingot",),
                      ("ice_orb_item", 1), {"tags": ("orb",), "requires_discovery": True}),
}  # fmt: skip
ICONS = "playable_assets/icons_7soul"
# station: (object name, (x, y) in Hearthfold, Ninja Adventure picture)
OBJECTS = {
    "alchemy": ("Alchemy Table", (440.0, 200.0), ("item", "Items/Potion/LifePot.png")),
    "forge": ("Forge", (312.0, 200.0), ("item", "Items/Tool/Anvil.png")),
}


def stations():
    """``{station id: WorkstationDefinition}``."""
    from asteria.rpg.workstations import WorkstationCategory as Tab
    from asteria.rpg.workstations import WorkstationDefinition

    return {
        "alchemy": WorkstationDefinition(
            "alchemy",
            "Alchemy Table",
            icon_id=f"{ICONS}/P_Red05.png",
            categories=(
                Tab("potions", "Potions", ("potion",), f"{ICONS}/P_Red01.png"),
                Tab("gems", "Gems", ("gem",), f"{ICONS}/I_Ruby.png"),
                Tab("fusion", "Fusion", ("fuse",), f"{ICONS}/I_Crystal01.png"),
                Tab("cards", "Cards", ("card",), f"{ICONS}/I_Scroll.png"),
            ),
            disassembly=True,
            craft_sound="heal",
            fail_sound="hit",
            success_image="playable_assets/fx_heal.png",
        ),
        "forge": WorkstationDefinition(
            "forge",
            "Forge",
            icon_id=f"{ICONS}/I_SilverBar.png",
            categories=(
                Tab("ingots", "Ingots", ("smelt",), f"{ICONS}/I_GoldBar.png"),
                Tab("throwing", "Throwing", ("bomb",), f"{ICONS}/I_IronBall.png"),
                Tab("orbs", "Orbs", ("orb",), f"{ICONS}/I_Sapphire.png"),
            ),
            max_quantity=10,
            craft_sound="heal",
            fail_sound="hit",
            success_image="playable_assets/fx_heal.png",
        ),
    }


def _recipe(recipe_id, station, name, base, catalyst, output, options):
    from asteria.rpg.composition import (
        CompositionOutput,
        CompositionQualityTier,
        CompositionRecipeDefinition,
        CompositionSelection,
    )

    options = dict(options)
    tiers = [
        CompositionQualityTier(q, t, [CompositionOutput(i, n) for i, n in outs])
        for q, t, outs in options.pop("quality_tiers", ())
    ]
    failure = [CompositionOutput(i, n) for i, n in options.pop("failure_outputs", ())]
    return CompositionRecipeDefinition(
        recipe_id,
        name,
        station=station,
        selections=(
            CompositionSelection("base", base),
            CompositionSelection("catalyst", catalyst),
        ),
        outputs=(CompositionOutput(*output),),
        quality_tiers=tiers,
        failure_outputs=failure,
        tags=options.pop("tags", ("potion",)),
        **options,
    )


def _tag(recipe_id):
    """The tab an Alchemist recipe goes to: gems, fused gems or cards."""
    if recipe_id.startswith("fuse_"):
        return "fuse"
    return "card" if recipe_id.startswith("craft_card_") else "gem"


def apply(project, root):
    """Add the stations, their recipes and their objects; returns how many stations were
    added. An object already on the plaza is left as it is."""
    import trial_maps as maps
    import trial_people as people
    import trial_shops as shops

    db = project.rpg_database
    added = 0
    for station_id, station in stations().items():
        added += station_id not in db.workstations
        db.workstations[station_id] = station
    for recipe_id, recipe in list(db.composition_recipes.items()):
        if recipe.station == "alchemy" and not recipe.tags:
            db.composition_recipes[recipe_id] = replace(recipe, tags=(_tag(recipe_id),))
    for recipe_id, (name, base, catalyst, output, options) in POTIONS.items():
        db.composition_recipes[recipe_id] = _recipe(
            recipe_id, "alchemy", name, base, catalyst, output, options
        )
    for recipe_id, (name, base, catalyst, output, options) in FORGE.items():
        db.composition_recipes[recipe_id] = _recipe(
            recipe_id, "forge", name, base, catalyst, output, options
        )
    town = shops._town(project)
    standing = {e.name for e in town.scene.entities()}
    for station_id, (name, xy, picture) in OBJECTS.items():
        if name in standing:
            continue
        key = "look_object_" + name.lower().replace(" ", "_")
        look = people.look(maps.Assets(project, root), key, picture, name)
        entity = town.npc(name, xy, look)
        town.program(
            entity, f"town.{station_id}", [maps.world("OPEN_CRAFTING", station=station_id)]
        )
    return added
