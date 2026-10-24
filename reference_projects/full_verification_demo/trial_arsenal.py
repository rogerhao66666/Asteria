"""The Full Verification demo's arsenal (D61 G1): every weapon kind in five rarities.

Nine kinds - sword, axe, spear, bow, dagger, staff, book, fist and throwing weapons - each with
at least five weapons from Common to Mythic. Books, fists and throwing weapons are new kinds:
each gets its own basic attack (``attack_book``, ``attack_fist``, ``attack_throw``, like the
other weapons' attacks: a weapon tag the foes' weaknesses and resistances read, the same hit
checks), so a hero who holds one fights with it.

What a weapon gives follows its rarity (``TIERS``): its kind's main stat (``power``, or
``magic`` for staves and books), from Rare on an element of its own and a critical bonus, and
sockets - Magic one gem socket, Rare and above two gem sockets and a card socket. Every weapon
carries the ``weapon`` tag, so the workshop refines it (``RefineRules`` "plus").

The pictures are 7Soul's "496 pixel art icons" (CC0, ``asset_library/opengameart/
7Soul_496_RPG_Icons``), copied into ``playable_assets/icons_7soul``. ``apply(project, root)``
adds what is missing and can run again on a built project; ``build_project.py`` runs it.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from pathlib import Path

LIBRARY = Path(__file__).resolve().parents[2] / "asset_library" / "opengameart"
ICONS = LIBRARY / "7Soul_496_RPG_Icons"
ICON_DIR = "playable_assets/icons_7soul"

# rarity: (main stat, element, crit, light weapons' speed, sockets: gems, card)
TIERS = {
    "common": (12, 0, 0, 0, 0, False),
    "magic": (20, 0, 3, 3, 1, False),
    "rare": (30, 10, 5, 4, 2, True),
    "legendary": (45, 15, 6, 6, 2, True),
    "mythic": (65, 25, 10, 8, 2, True),
}
MAGIC_KINDS = ("staff", "book")
LIGHT_KINDS = ("dagger", "fist", "throw", "bow")
# the new kinds' attacks: (copied from, display name)
ATTACKS = {
    "book": ("attack_staff", "Attack (book)"),
    "fist": ("attack_dagger", "Attack (fist)"),
    "throw": ("attack_bow", "Attack (throw)"),
}
# kind: [(id, name, rarity, element or "", 7Soul picture)]
WEAPONS = {
    "sword": [
        ("w_knights_blade", "Knight's Blade", "magic", "", "W_Sword009.png"),
        ("w_infernal_edge", "Infernal Edge", "mythic", "fire", "W_Sword016.png"),
    ],
    "axe": [
        ("w_battle_axe", "Battle Axe", "magic", "", "W_Axe005.png"),
        ("w_bloodreaver", "Bloodreaver", "rare", "dark", "W_Axe008.png"),
    ],
    "spear": [
        ("w_partisan", "Partisan", "magic", "", "W_Spear006.png"),
        ("w_tide_trident", "Tide Trident", "legendary", "ice", "W_Spear007.png"),
        ("w_skypiercer", "Skypiercer", "mythic", "lightning", "W_Spear011.png"),
    ],
    "bow": [
        ("w_recurve_bow", "Recurve Bow", "magic", "", "W_Bow04.png"),
        ("w_phoenix_bow", "Phoenix Bow", "legendary", "fire", "W_Bow08.png"),
        ("w_starfall_bow", "Starfall Bow", "mythic", "light", "W_Bow16.png"),
    ],
    "dagger": [
        ("w_main_gauche", "Main Gauche", "magic", "", "W_Dagger006.png"),
        ("w_frostfang", "Frostfang", "mythic", "ice", "W_Dagger017.png"),
    ],
    "staff": [
        ("w_jade_staff", "Jade Staff", "magic", "", "W_Staff02.png"),
        ("w_sun_staff", "Sun Staff", "legendary", "light", "W_Staff05.png"),
    ],
    "book": [
        ("w_primer", "Primer", "common", "", "W_Book05.png"),
        ("w_field_guide", "Field Guide", "magic", "", "W_Book02.png"),
        ("w_book_of_prayers", "Book of Prayers", "rare", "light", "W_Book03.png"),
        ("w_grimoire_of_flames", "Grimoire of Flames", "legendary", "fire", "W_Book06.png"),
        ("w_codex_of_frost", "Codex of Frost", "mythic", "ice", "W_Book07.png"),
    ],
    "fist": [
        ("w_leather_wraps", "Leather Wraps", "common", "", "W_Fist001.png"),
        ("w_brawler_gloves", "Brawler Gloves", "magic", "", "W_Fist002.png"),
        ("w_iron_knuckles", "Iron Knuckles", "rare", "earth", "W_Fist003.png"),
        ("w_storm_gauntlets", "Storm Gauntlets", "legendary", "lightning", "W_Fist004.png"),
        ("w_titan_fists", "Titan Fists", "mythic", "earth", "W_Fist005.png"),
    ],
    "throw": [
        ("w_throwing_axe", "Throwing Axe", "common", "", "W_Throw001.png"),
        ("w_harpoon", "Harpoon", "magic", "", "W_Throw002.png"),
        ("w_shuriken", "Shuriken", "rare", "wind", "W_Throw003.png"),
        ("w_shadow_star", "Shadow Star", "legendary", "dark", "W_Throw004.png"),
        ("w_void_star", "Void Star", "mythic", "dark", "W_Throw05.png"),
    ],
}


def credits_rows():
    cc0 = "[CC0 1.0](http://creativecommons.org/publicdomain/zero/1.0/)"
    return [
        "| `icons_7soul/*.png` (the added weapons, armour, accessories and supplies, D61) | "
        '"496 pixel art icons for '
        'medieval/fantasy RPG" (https://opengameart.org/content/496-pixel-art-icons-for-'
        "medievalfantasy-rpg), copied unmodified from `asset_library/opengameart/"
        f"7Soul_496_RPG_Icons` | Henrique Lazarini (7Soul1) | {cc0} |"
    ]


def weapon_ids():
    return [w[0] for weapons in WEAPONS.values() for w in weapons]


def _stats(kind, rarity, element):
    main, elemental, crit, speed, _gems, _card = TIERS[rarity]
    stats = {("magic" if kind in MAGIC_KINDS else "power"): main}
    if element and elemental:
        stats[f"{element}_attack"] = elemental
    if crit:
        stats["crit"] = crit
    if speed and kind in LIGHT_KINDS:
        stats["speed"] = speed
    return stats


def _sockets(rarity):
    from asteria.rpg import SocketDefinition

    _main, _elemental, _crit, _speed, gems, card = TIERS[rarity]
    sockets = [SocketDefinition(f"g{n}", accepted_tags=("gem",)) for n in range(1, gems + 1)]
    if card:
        sockets.append(SocketDefinition("c1", accepted_tags=("card",)))
    return tuple(sockets)


def _icon(root, file):
    target = Path(root) / ICON_DIR / file
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(ICONS / file, target)
    return f"{ICON_DIR}/{file}"


def _attack(project, kind, icon_id):
    """``attack_<kind>``: a copy of an existing weapon attack with the new kind's tag."""
    from asteria.gameplay.abilities import AbilityDefinition

    library = project.gameplay_library.abilities
    ability_id = f"attack_{kind}"
    source, name = ATTACKS[kind]
    text = json.dumps(library.require(source).to_data())
    data = json.loads(text.replace(f'"{source}', f'"{ability_id}'))  # ids follow the ability
    data["tags"] = [t for t in data["tags"] if not t.startswith("weapon.")] + [f"weapon.{kind}"]
    data["display_name"], data["icon_id"] = name, icon_id
    library._definitions[ability_id] = AbilityDefinition.from_data(data)
    targeting = project.rpg_database.battle_targeting
    targeting[ability_id] = dataclasses.replace(targeting[source], ability_id=ability_id)
    return ability_id


def labels():
    """The battle menu's names of the new kinds' attacks (manifest ``battle.skills``)."""
    return {f"attack_{kind}": name for kind, (_source, name) in ATTACKS.items()}


def patch_manifest(root):
    """Add the new attacks' battle labels to a built demo's manifest; returns how many."""
    path = Path(root) / "playable_test_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    skills = manifest.setdefault("battle", {}).setdefault("skills", {})
    added = {k: {"label": v} for k, v in labels().items() if k not in skills}
    if added:
        skills.update(added)
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return len(added)


def apply(project, root, skill_names=None):
    """Add the arsenal to ``project`` (its pictures copied under ``root``); returns how many
    weapons were added. Weapons already there are written again the same way. ``skill_names``
    (the build's) gets the new attacks' battle names."""
    if skill_names is not None:
        skill_names.update(labels())
    from asteria.rpg import EquipmentDefinition

    db = project.rpg_database
    added = 0
    for kind, weapons in WEAPONS.items():
        attack = f"attack_{kind}"
        for weapon_id, name, rarity, element, picture in weapons:
            icon_id = _icon(root, picture)
            if kind in ATTACKS and attack not in project.gameplay_library.abilities.ids():
                _attack(project, kind, icon_id)  # the kind's first weapon pictures its attack
            stats = _stats(kind, rarity, element)
            added += weapon_id not in db.equipment
            db.equipment[weapon_id] = EquipmentDefinition(
                weapon_id,
                name,
                slot="weapon",
                tags=("weapon", f"equip.{kind}"),
                modifiers=_modifiers(weapon_id, stats),
                granted_abilities=(attack,),
                sockets=_sockets(rarity),
                icon_id=icon_id,
                rarity=rarity,
            )
    return added


def _modifiers(weapon_id, stats):
    from asteria.gameplay.modifiers import StatModifier

    return tuple(
        StatModifier(f"{weapon_id}.{stat}", stat, "add", float(value))
        for stat, value in stats.items()
    )
