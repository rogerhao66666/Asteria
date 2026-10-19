"""An icon on every record that can carry one (phase 3): gear, items, gems, cards, jobs,
passives and states, all from the Lucifer packs.

A picture used twice is tinted, so no two records look alike: a ruby ring is the golden ring in
red, a flawless gem is its gem brightened with a white rim. Monster cards show the monster
itself (its Lucifer idle frame) on a card; bows and the Blessed Scroll are drawn here in the
packs' outlined style. Jobs, passives and states take pictures from the Lucifer skill icons
(warrior / sorceress / necromancer sets), each one a picture of its own.
"""

from __future__ import annotations

import dataclasses
import shutil

import trial_lucifer as lucifer

EQ = lucifer.EQUIPMENT
PICK = lucifer.PICKUPS

TINTS = {  # name: RGB multiplied into the picture
    "red": (1.25, 0.55, 0.5),
    "gold": (1.25, 1.05, 0.55),
    "green": (0.6, 1.2, 0.65),
    "purple": (0.95, 0.6, 1.3),
    "grey": (0.75, 0.75, 0.8),
    "white": (1.35, 1.35, 1.4),
    "dark": (0.55, 0.5, 0.6),
    "blue": (0.6, 0.85, 1.35),
}
GEAR = {  # equipment id: (file under Equipment, tint or None) / ("library_bow", rarity)
    "w_bow": ("library_bow", "common"),  # HomoHikka's CC0 bow (OpenGameArt), Lucifer outline
    "w_longbow": ("library_bow", "rare"),
    "w_steel_sword": ("Weapons/Png/Common Greatsword.png", None),
    "w_dragoon_lance": ("Weapons/Png/Common Spear.png", "gold"),
    "w_kris": ("Weapons/Png/Legendary Rapier .png", None),
    "w_war_axe": ("Weapons/Png/Legendary Dane Axe.png", None),
    "w_titan_cleaver": ("Weapons/Png/Mythic Battleaxe.png", None),
    "w_ash_staff": ("Weapons/Png/Mages Spire.png", None),
    "w_saint_staff": ("Weapons/Png/Wizards Pole.png", "gold"),
    "w_bone_scepter": ("Weapons/Png/Mythic Godhammer.png", None),
    "w_ritual_kris": ("Weapons/Png/Rare Explorers Hook.png", None),
    "a_leather_vest": ("Chest/Png/Rare Explorers Top.png", None),
    "a_shadow_garb": ("Chest/Png/Common Gambeson.png", "dark"),
    "a_chain_mail": ("Chest/Png/Common ChainMail Chestpiece.png", None),
    "a_knight_plate": ("Chest/Png/Legendary Royal Chestpiece.png", None),
    "a_linen_robe": ("Chest/Png/Magic Wizards Tunic Chestpiece.png", None),
    "a_silk_robe": ("Chest/Png/Magic Sorceress Gambeson.png", None),
    "a_dawn_robe": ("Chest/Png/Magic Sorceress Gambeson.png", "gold"),
    "a_grave_shroud": ("Chest/Png/Common Ragged shirt.png", "dark"),
    "a_zealot_mail": ("Chest/Png/Rare Plate Chestpiece.png", "red"),
    "a_iron_ring": ("Misc/Png/Silver Enchanted Ring.png", None),
    "a_ruby_ring": ("Misc/Png/Golden Enchanted Ring.png", "red"),
    "a_moon_pendant": ("Misc/Png/Common SIlver Amulet.png", None),
    "a_feather_charm": ("Misc/Png/Wizards Amulet.png", None),
    "a_hawk_eye": ("Misc/Png/Wizards Sparkle Ring.png", "blue"),
    "a_life_amulet": ("Misc/Png/Rare Golden Gem Amulet.png", "green"),
    "a_holy_symbol": ("Misc/Png/Wizards Amulet.png", "gold"),
    "a_phylactery": ("Misc/Png/Common SIlver Amulet.png", "purple"),
    "a_blood_amulet": ("Misc/Png/Rare Golden Gem Amulet.png", "red"),
}
GEMS = {  # gem: (Pickups gem file, tint or None)
    "ruby": ("OrangeGem.png", None),
    "sapphire": ("BlueGem.png", None),
    "topaz": ("PinkGem.png", "gold"),
    "onyx": ("PinkGem.png", "dark"),
    "emerald": ("BlueGem.png", "green"),
    "amethyst": ("PinkGem.png", "purple"),
    "diamond": ("BlueGem.png", "white"),
}
CARDS = {  # card: the Lucifer character drawn on it
    "card_slinger": "goblin_slinger",
    "card_beast": "goblin_beast",
    "card_hunter": "skeleton_hunter",
    "card_ancient": "skeleton_ancient",
    "card_acolyte": "skeleton_grunt",
    "card_vaelor": "skeleton_king",
    "card_wolf": "goblin_rider",
    "card_golem": "skeleton_grunt",
    "card_vampire": "necromancer",
    "card_slayer": "goblin_berserker",
}
POTIONS = {  # item: (Pickups potion file, tint)
    "poison_vial": ("Potions/Stamina/Png/SmallStaminaPotion.png", "green"),
    "smoke_bomb": ("Potions/Mana/Png/SmallManaPotion.png", "grey"),
    "holy_water": ("Potions/Mana/Png/BigManaPotion.png", "white"),
}


def _tint(image, name):
    from PIL import Image

    if not name:
        return image
    r, g, b = TINTS[name]
    bands = image.convert("RGBA").split()
    scaled = [
        band.point(lambda v, f=f: max(0, min(255, int(v * f))))
        for band, f in zip(bands, (r, g, b))
    ]
    return Image.merge("RGBA", (*scaled, bands[3]))


def _outline(image, color=(24, 16, 28, 255)):
    from PIL import Image

    mask = image.getchannel("A")
    out = Image.new("RGBA", image.size, (0, 0, 0, 0))
    solid = Image.new("RGBA", image.size, color)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        shifted = Image.new("L", image.size, 0)
        shifted.paste(mask, (dx, dy))
        out.paste(solid, (0, 0), shifted)
    out.alpha_composite(image)
    return out


OUTLINE = {"common": (183, 183, 183), "rare": (209, 202, 128)}  # the Lucifer rarity outlines
BOW = lucifer.FREE_ASSETS.parent / "opengameart" / "CC0_Ranged_Icons_HomoHikka" / "32x32"


def _library_bow(rarity):
    """HomoHikka's CC0 bow (asset library) wearing the Lucifer outline of ``rarity``: every
    transparent pixel touching the bow becomes the rarity colour."""
    from PIL import Image

    bow = Image.open(BOW / "bow.png").convert("RGBA")
    out = Image.new("RGBA", (bow.width + 2, bow.height + 2), (0, 0, 0, 0))
    out.alpha_composite(bow, (1, 1))
    src, px = out.copy().load(), out.load()
    for y in range(out.height):
        for x in range(out.width):
            if src[x, y][3]:
                continue
            near = (
                0 <= x + dx < out.width and 0 <= y + dy < out.height and src[x + dx, y + dy][3]
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )
            if any(near):
                px[x, y] = (*OUTLINE[rarity], 255)
    return out


def _scroll():
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((3, 3, 12, 12), fill=(232, 214, 168, 255))
    draw.rectangle((2, 2, 13, 4), fill=(198, 170, 120, 255))
    draw.rectangle((2, 11, 13, 13), fill=(198, 170, 120, 255))
    draw.line((5, 6, 10, 6), fill=(150, 110, 70, 255))
    draw.line((5, 8, 10, 8), fill=(150, 110, 70, 255))
    draw.point((7, 10), fill=(214, 60, 60, 255))  # the blessing's seal
    draw.point((8, 10), fill=(214, 60, 60, 255))
    return _outline(image)


def _flawless(image):
    from PIL import ImageEnhance

    bright = ImageEnhance.Brightness(image).enhance(1.35)
    return _outline(bright, (255, 255, 255, 255))


def _card(character):
    """A card: parchment, a frame, the monster standing in it."""
    from PIL import Image, ImageDraw

    card = Image.new("RGBA", (24, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    draw.rectangle((0, 0, 23, 31), fill=(70, 52, 34, 255))
    draw.rectangle((1, 1, 22, 30), fill=(236, 220, 176, 255))
    draw.rectangle((3, 3, 20, 22), fill=(120, 150, 170, 255))
    draw.rectangle((3, 25, 20, 28), fill=(200, 178, 130, 255))
    figure = lucifer._facing_strip(character, "Down", "Idle")[0]
    box = figure.getchannel("A").getbbox() or (0, 0, *figure.size)
    figure = figure.crop(box)
    figure.thumbnail((17, 19), Image.NEAREST)
    card.alpha_composite(figure, (3 + (18 - figure.width) // 2, 3 + (20 - figure.height)))
    return card.resize((48, 64), Image.NEAREST)


WEAPON_RARITY = {  # a weapon's rarity: what its Lucifer picture is called (Common, Rare...)
    "w_sword": "common",
    "w_steel_sword": "common",
    "w_dagger": "common",
    "w_axe": "common",
    "w_spear": "common",
    "w_staff": "common",
    "w_bow": "common",
    "w_sunbrand": "rare",  # Aldric's sword: the Rare Greatsword
    "w_ritual_kris": "rare",
    "w_dragoon_lance": "rare",
    "w_ash_staff": "rare",
    "w_saint_staff": "rare",
    "w_longbow": "rare",
    "w_kris": "legendary",
    "w_war_axe": "legendary",
    "w_sunbrand_ex": "legendary",
    "w_bone_scepter": "mythic",
    "w_titan_cleaver": "mythic",
    "w_demon_ring": "mythic",
}


def weapon_rarities(context):
    """Every weapon wears the rarity its picture names; Mythic is added for the Godhammer and the
    Demon Ring (weight 0: authored only, never rolled as loot)."""
    from asteria.rpg.loot import RarityDefinition

    db = context.db
    if "mythic" not in db.rarities:
        db.add_rarity(RarityDefinition("mythic", "Mythic", "#ff4a4a", 6, 6, 0.0, 4, 3, 3))
    for equipment_id, rarity in WEAPON_RARITY.items():
        if equipment_id in db.equipment:
            weapon = db.equipment[equipment_id]
            db.equipment[equipment_id] = dataclasses.replace(weapon, rarity=rarity)


def apply_all(context):
    """Give every gear piece, item, attachment, job, passive and state without an icon one."""

    folder = context.root / "playable_assets" / "lucifer" / "icons"
    folder.mkdir(parents=True, exist_ok=True)
    db = context.db

    def save(image, name):
        image.save(folder / name)
        return f"playable_assets/lucifer/icons/{name}"

    def open_png(path):
        if path.is_relative_to(EQ):  # equipment pictures are whole (a weapon is 32 x 16)
            from PIL import Image

            return Image.open(path).convert("RGBA")
        return lucifer.first_frame(path)  # a strip (the pickups) gives its first frame

    for eid, (source, extra) in GEAR.items():
        if eid not in db.equipment:
            continue
        if source == "library_bow":
            image = _library_bow(extra)
        else:
            image = _tint(open_png(EQ / source), extra)
        db.equipment[eid] = dataclasses.replace(
            db.equipment[eid], icon_id=save(image, f"{eid}.png")
        )
        attack = context.abilities.get(f"attack_{eid[2:]}")
        if attack is not None:  # a weapon's attack shows the weapon (the bow's too)
            context.abilities._definitions[attack.ability_id] = dataclasses.replace(
                attack, icon_id=db.equipment[eid].icon_id
            )
    for gem, (file, tint) in GEMS.items():
        picture = _tint(open_png(PICK / "Gems" / "Png" / file), tint)
        for prefix, image in (("", picture), ("flawless_", _flawless(picture))):
            attachment = f"{prefix}{gem}"
            icon = save(image, f"{attachment}.png")
            if f"{attachment}_item" in db.items:
                item = db.items[f"{attachment}_item"]
                db.items[item.item_id] = dataclasses.replace(item, icon_id=icon)
            if attachment in db.attachments:
                record = db.attachments[attachment]
                db.attachments[attachment] = dataclasses.replace(record, icon_id=icon)
    for card, character in CARDS.items():
        icon = save(_card(character), f"{card}.png")
        if f"{card}_item" in db.items:
            item = db.items[f"{card}_item"]
            db.items[item.item_id] = dataclasses.replace(item, icon_id=icon)
        if card in db.attachments:
            db.attachments[card] = dataclasses.replace(db.attachments[card], icon_id=icon)
    for item_id, (file, tint) in POTIONS.items():
        if item_id in db.items:
            icon = save(_tint(open_png(PICK / file), tint), f"{item_id}.png")
            db.items[item_id] = dataclasses.replace(db.items[item_id], icon_id=icon)
    if "blessed_scroll" in db.items:
        icon = save(_scroll(), "blessed_scroll.png")
        db.items["blessed_scroll"] = dataclasses.replace(db.items["blessed_scroll"], icon_id=icon)
    _skill_pictures(context, folder)


def _skill_pictures(context, folder):
    """Jobs, passives and states: one Lucifer skill picture each, from the set that fits."""
    db = context.db
    pools = {group: lucifer._skill_pool(group) for group in lucifer.SKILL_ICON_GROUPS}
    used = set()
    for path in folder.glob("skill_*.png"):  # the skills' pictures are taken
        used.add(path.read_bytes())
    cursor = dict.fromkeys(pools, 0)

    def pick(group, name):
        pool = pools[group]
        for _ in range(len(pool)):
            source = pool[cursor[group] % len(pool)]
            cursor[group] += 1
            if source.read_bytes() not in used or len(used) >= sum(map(len, pools.values())):
                break
        used.add(source.read_bytes())
        shutil.copyfile(source, folder / name)
        return f"playable_assets/lucifer/icons/{name}"

    magic = {"mystic", "sage", "cleric", "priest", "bishop"}
    dark = {"necromancer", "lich", "death_lord", "cultist", "zealot", "heretic"}
    for class_id in sorted(db.classes):
        record = db.classes[class_id]
        if record.icon_id:
            continue
        group = (
            "sorceress" if class_id in magic else "necromancer" if class_id in dark else "warrior"
        )
        db.classes[class_id] = dataclasses.replace(
            record, icon_id=pick(group, f"job_{class_id}.png")
        )
    for passive_id in sorted(db.passives):
        record = db.passives[passive_id]
        if record.icon_id:
            continue
        stats = {m.stat for m in record.modifiers}
        group = "sorceress" if "magic" in stats else "warrior"
        if stats & {"crit", "evade", "lifesteal"}:
            group = "necromancer"
        db.passives[passive_id] = dataclasses.replace(
            record, icon_id=pick(group, f"passive_{passive_id}.png")
        )
    # a tree node that teaches a skill shows that skill's picture (the graph and the in-game
    # tree screen draw every node with its icon)
    abilities = context.abilities
    for graph_id in sorted(db.progression_graphs):
        graph = db.progression_graphs[graph_id]
        nodes = []
        for node in graph.nodes:
            skills = [a for r in node.rewards for a in r.granted_abilities]
            if not node.icon_id and skills:
                definition = abilities.get(skills[0])
                icon = getattr(definition, "icon_id", "") if definition is not None else ""
                if icon:
                    node = dataclasses.replace(node, icon_id=icon)
            nodes.append(node)
        db.progression_graphs[graph_id] = dataclasses.replace(graph, nodes=tuple(nodes))
    states = context.library.states._definitions
    for state_id in sorted(states):
        record = states[state_id]
        if not getattr(record, "icon_id", ""):
            states[state_id] = dataclasses.replace(
                record, icon_id=pick("necromancer", f"state_{state_id}.png")
            )
