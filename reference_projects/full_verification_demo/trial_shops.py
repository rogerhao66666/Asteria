"""Three new shops in Hearthfold (D61 G3): arms, armour and remedies.

* **Brann's Arms** (Weaponsmith Brann): every weapon of the arsenal (``trial_arsenal``).
* **Hilde's Armoury** (Armorer Hilde): the added armour and accessories (``trial_supplies``).
* **Sela's Remedies** (Apothecary Sela): potions, cures, throwing items, materials, orbs and
  cards; the shop buys them back for a quarter.

Gear is sold straight into the equipment bag (``ShopRuntime.receive_equipment``, D61) and costs
by its rarity (``PRICE``); the shops do not buy gear back (their sell tab is for items). The
three keepers stand on either side of the plaza's north road, each a Ninja Adventure character
of their own (CC0, ``trial_people.look``), and say one line before their shop opens.

``apply(project, root)`` adds what is missing and can run again; ``build_project.py`` runs it
after ``trial_supplies``.
"""

from __future__ import annotations

import trial_arsenal as arsenal
import trial_supplies as supplies

PRICE = {"common": 120, "magic": 400, "rare": 1200, "legendary": 3500, "mythic": 9000}
ITEM_PRICE = {
    "potion": 40,
    "hi_potion": 150,
    "mega_potion": 500,
    "ether": 80,
    "hi_ether": 300,
    "elixir": 1500,
    "antidote": 30,
    "eye_drops": 30,
    "echo_herb": 40,
    "burn_salve": 40,
    "clotting_draught": 40,
    "alarm_clock": 50,
    "remedy": 250,
    "throwing_rock": 10,
    "iron_ball": 60,
    "thunder_bomb": 180,
    "wind_bomb": 180,
    "holy_bomb": 220,
    "dark_bomb": 220,
}
MATERIAL_PRICE, ORB_PRICE, CARD_PRICE = 60, 900, 2400
# shop id: (name, keeper, (x, y) in Hearthfold, Ninja Adventure look, line)
SHOPS = {
    "arms_shop": (
        "Brann's Arms",
        "Weaponsmith Brann",
        (312.0, 168.0),
        "FighterWhite",
        "Steel for every hand. Books and knuckles too.",
    ),
    "armour_shop": (
        "Hilde's Armoury",
        "Armorer Hilde",
        (408.0, 168.0),
        "ManGreen",
        "Mail, robes and rings. Try them on.",
    ),
    "remedy_shop": (
        "Sela's Remedies",
        "Apothecary Sela",
        (408.0, 200.0),
        "Cavegirl",
        "Potions, bombs and the odd orb.",
    ),
}


def entries(project):
    """``{shop id: (ShopEntry, ...)}``."""
    from asteria.rpg.economy import ShopEntry

    db = project.rpg_database

    def gear(ids):
        return tuple(
            ShopEntry(i, buy_prices={"gold": float(PRICE[db.equipment[i].rarity or "common"])})
            for i in ids
        )

    def item(item_id, price):
        return ShopEntry(
            item_id, buy_prices={"gold": float(price)}, sell_prices={"gold": price // 4}
        )

    remedies = [item(i, p) for i, p in ITEM_PRICE.items()]
    remedies += [item(i, MATERIAL_PRICE) for i in supplies.MATERIALS]
    remedies += [item(f"{e}_orb_item", ORB_PRICE) for e in supplies.ORBS]
    remedies += [item(f"{c}_item", CARD_PRICE) for c in supplies.CARDS]
    return {
        "arms_shop": gear(arsenal.weapon_ids()),
        "armour_shop": gear(supplies.all_equipment_ids()),
        "remedy_shop": tuple(remedies),
    }


def _town(project):
    """A ``trial_maps.SceneBuilder`` on the built Hearthfold (no new scene is made)."""
    import trial_maps as maps

    scene = project.scene(maps.asset_id("scene", "town"))
    builder = maps.SceneBuilder.__new__(maps.SceneBuilder)
    builder.project, builder.key, builder.scene = project, "town", scene
    builder.programs = project.scene_event_bindings[scene.id]
    return builder


def apply(project, root):
    """Add the shops, their keepers and the keepers' events; returns how many shops were
    added. A keeper already standing in Hearthfold is left as it is."""
    import trial_maps as maps
    import trial_people as people

    from asteria.rpg.economy import ShopDefinition

    db = project.rpg_database
    made = entries(project)
    added = 0
    town = _town(project)
    standing = {e.name for e in town.scene.entities()}
    for shop_id, (name, keeper, xy, who, line) in SHOPS.items():
        added += shop_id not in db.shops
        db.shops[shop_id] = ShopDefinition(shop_id, name, entries=made[shop_id])
        if keeper in standing:
            continue
        key = "look_npc_" + keeper.lower().replace(" ", "_")
        look = people.look(maps.Assets(project, root), key, who, keeper)
        entity = town.npc(keeper, xy, look)
        town.program(
            entity,
            f"town.{shop_id}",
            [maps.say(keeper, line), maps.world("OPEN_SHOP", shop_id=shop_id)],
        )
    return added
