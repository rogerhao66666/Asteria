"""The Full Verification demo's armour, accessories and supplies (D61 G2).

* **Armour** (8) and **accessories** (8) in the two slots the party wears, Common to Mythic: the
  rarity sets the defence (or the accessory's bonus) and from Rare on a socket - a card socket in
  armour, a gem socket in an accessory (``TIERS``).
* **Potions**: HP in three grades, MP in two, an Elixir for both; **cures** for one state each
  (Antidote: Poison, Eye Drops: Blind, Echo Herb: Silence, Burn Salve: Burn, Clotting Draught:
  Bleed, Alarm Clock: Sleep) and a Remedy for all of them. Each is a battle item: its own
  ability on one ally (``apply_states`` with ``remove`` for the cures).
* **Throwing items**: a rock and an iron ball (physical, the ball stuns) and four bombs -
  thunder, wind, holy and dark - each with its element (``damage.<element>``) and a state.
* **Materials** (8) for the shops, crafting and disassembly.
* **Orbs** (7), one per element: socketed like gems (tags ``gem`` and ``orb``), each gives its
  element's attack and some magic - an orb in a weapon makes its blows carry that element.
* **Cards** (4) more, for card sockets (destroyed when taken out, like the foes' cards).

Pictures: 7Soul's CC0 icons (``asset_library/opengameart/7Soul_496_RPG_Icons``), copied into
``playable_assets/icons_7soul``. ``apply(project, root)`` adds what is missing and can run again;
``build_project.py`` runs it.
"""

from __future__ import annotations

import json

import trial_arsenal as arsenal

# rarity: (armour defence, magic defence, resist, accessory bonus, socket)
TIERS = {
    "common": (10, 6, 0, 4, False),
    "magic": (16, 10, 5, 6, False),
    "rare": (24, 16, 10, 9, True),
    "legendary": (34, 24, 15, 12, True),
    "mythic": (48, 34, 20, 16, True),
}
# id: (name, rarity, weight, resist element, picture)
ARMOUR = {
    "a_padded_jerkin": ("Padded Jerkin", "common", "light", "", "A_Clothing02.png"),
    "a_scale_mail": ("Scale Mail", "magic", "heavy", "earth", "A_Armour02.png"),
    "a_mage_robe": ("Mage Robe", "magic", "cloth", "fire", "A_Clothing01.png"),
    "a_ranger_coat": ("Ranger Coat", "rare", "light", "wind", "A_Armour01.png"),
    "a_mithril_mail": ("Mithril Mail", "rare", "heavy", "lightning", "A_Armor04.png"),
    "a_bone_mail": ("Bone Mail", "legendary", "heavy", "dark", "E_Bones02.png"),
    "a_archon_robe": ("Archon Robe", "legendary", "cloth", "light", "A_Armor05.png"),
    "a_celestial_plate": ("Celestial Plate", "mythic", "heavy", "ice", "A_Armour03.png"),
}
# id: (name, rarity, {stat: weight of the tier's bonus}, picture)
ACCESSORIES = {
    "a_copper_ring": ("Copper Ring", "common", {"power": 1}, "Ac_Ring01.png"),
    "a_silver_ring": ("Silver Ring", "magic", {"magic": 1}, "Ac_Ring02.png"),
    "a_swift_medal": ("Swift Medal", "magic", {"speed": 1}, "Ac_Medal02.png"),
    "a_hunters_charm": ("Hunter's Charm", "rare", {"crit": 1, "power": 1}, "Ac_Necklace02.png"),
    "a_sages_pendant": (
        "Sage's Pendant",
        "rare",
        {"magic": 1, "magic_defense": 1},
        "Ac_Necklace03.png",
    ),
    "a_guardian_medal": (
        "Guardian Medal",
        "legendary",
        {"defense": 1, "evade": 1},
        "Ac_Medal01.png",
    ),
    "a_moonstone_necklace": (
        "Moonstone Necklace",
        "legendary",
        {"magic": 1, "speed": 1},
        "Ac_Necklace07.png",
    ),
    "a_royal_medal": (
        "Royal Medal",
        "mythic",
        {"power": 1, "magic": 1, "crit": 1},
        "Ac_Medal04.png",
    ),
}
STATES = {  # the cures: state id -> its word in a description
    "poison": "Poison",
    "blind": "Blind",
    "silence": "Silence",
    "burn": "Burn",
    "bleed": "Bleed",
    "sleep": "Sleep",
}
# id: (name, hp, mp, removes, picture)
POTIONS = {
    "potion": ("Potion", 500, 0, (), "P_Red01.png"),
    "hi_potion": ("Hi-Potion", 1500, 0, (), "P_Red05.png"),
    "mega_potion": ("Mega Potion", 4000, 0, (), "P_Red07.png"),
    "ether": ("Ether", 0, 60, (), "P_Blue01.png"),
    "hi_ether": ("Hi-Ether", 0, 180, (), "P_Blue05.png"),
    "elixir": ("Elixir", 9999, 999, (), "P_Yellow05.png"),
    "antidote": ("Antidote", 0, 0, ("poison",), "I_Antidote.png"),
    "eye_drops": ("Eye Drops", 0, 0, ("blind",), "P_White02.png"),
    "echo_herb": ("Echo Herb", 0, 0, ("silence",), "I_Leaf.png"),
    "burn_salve": ("Burn Salve", 0, 0, ("burn",), "P_Orange02.png"),
    "clotting_draught": ("Clotting Draught", 0, 0, ("bleed",), "P_Medicine08.png"),
    "alarm_clock": ("Alarm Clock", 0, 0, ("sleep",), "I_Clock.png"),
    "remedy": ("Remedy", 0, 0, tuple(STATES), "P_Pink05.png"),
}
# id: (name, element ("" physical), stat, coefficient, state, picture)
THROWN = {
    "throwing_rock": ("Throwing Rock", "", "power", 8, "", "I_Rock01.png"),
    "iron_ball": ("Iron Ball", "", "power", 12, "stun", "I_IronBall.png"),
    "thunder_bomb": ("Thunder Bomb", "lightning", "magic", 12, "stun", "I_Bottle01.png"),
    "wind_bomb": ("Wind Bomb", "wind", "magic", 12, "slow", "I_Bottle02.png"),
    "holy_bomb": ("Holy Bomb", "light", "magic", 12, "blind", "I_Bottle03.png"),
    "dark_bomb": ("Dark Bomb", "dark", "magic", 12, "silence", "I_Bottle04.png"),
}
MATERIALS = {
    "wolf_fur": ("Wolf Fur", "I_WolfFur.png"),
    "sharp_fang": ("Sharp Fang", "I_Fang.png"),
    "fine_fabric": ("Fine Fabric", "I_Fabric.png"),
    "coal": ("Coal", "I_Coal.png"),
    "mithril_ingot": ("Mithril Ingot", "I_SilverBar.png"),
    "gold_ingot": ("Gold Ingot", "I_GoldBar.png"),
    "bat_wing": ("Bat Wing", "I_BatWing.png"),
    "scorpion_claw": ("Scorpion Claw", "I_ScorpionClaw.png"),
}
ORBS = {  # element: (name, picture)
    "fire": ("Fire Orb", "I_Ruby.png"),
    "ice": ("Ice Orb", "I_Sapphire.png"),
    "lightning": ("Thunder Orb", "I_Crystal01.png"),
    "wind": ("Wind Orb", "I_Jade.png"),
    "earth": ("Earth Orb", "I_Agate.png"),
    "light": ("Light Orb", "I_Opal.png"),
    "dark": ("Dark Orb", "I_Amethist.png"),
}
CARDS = {  # card id: (name, stats, picture)
    "card_knight": ("Knight Card", {"defense": 12, "magic_defense": 6}, "I_Scroll.png"),
    "card_sage": ("Sage Card", {"magic": 12, "magic_defense": 8}, "I_Scroll02.png"),
    "card_wanderer": ("Wanderer Card", {"speed": 8, "evade": 8}, "I_Map.png"),
    "card_scholar": ("Scholar Card", {"accuracy": 10, "crit": 6}, "I_Book.png"),
}


def all_item_ids():
    return [
        *POTIONS,
        *THROWN,
        *MATERIALS,
        *(f"{element}_orb_item" for element in ORBS),
        *(f"{card}_item" for card in CARDS),
    ]


def all_equipment_ids():
    return [*ARMOUR, *ACCESSORIES]


def _modifiers(prefix, stats):
    from asteria.gameplay.modifiers import StatModifier

    return tuple(
        StatModifier(f"{prefix}.{stat}", stat, "add", float(value))
        for stat, value in stats.items()
        if value
    )


def _ability(
    project,
    ability_id,
    template,
    name,
    description,
    operations,
    *,
    tags=None,
    states=(),
    icon_id="",
):
    """A battle ability made from an existing one's data: ``template``'s targeting and checks,
    its own operations, states, tags and words."""
    import dataclasses

    from asteria.gameplay.abilities import AbilityDefinition

    library = project.gameplay_library.abilities
    data = json.loads(json.dumps(library.require(template).to_data()))
    data["ability_id"] = ability_id
    effect = data["effects"][0]
    effect["mode"] = "selected"
    effect["effect"]["effect_id"] = f"{ability_id}.effect"
    effect["effect"]["operations"] = operations
    data["effects"] = [effect]
    if tags is not None:
        data["tags"] = list(tags)
    data["apply_states"] = list(states)
    data["display_name"], data["description"] = name, description
    data["icon_id"] = icon_id
    data["costs"] = []  # an item pays with itself
    library._definitions[ability_id] = AbilityDefinition.from_data(data)
    targeting = project.rpg_database.battle_targeting
    targeting[ability_id] = dataclasses.replace(targeting[template], ability_id=ability_id)
    return ability_id


def _restore(target, amount):
    return {"kind": "resource_delta", "target": target, "value": float(amount)}


def _damage(stat, coefficient, defence):
    return {
        "kind": "resource_delta",
        "target": "vitality",
        "value": {
            "schema": "asteria.value_formula",
            "version": 1,
            "terms": [
                {"source": "source_stat", "key": stat, "coefficient": -float(coefficient)},
                {"source": "target_stat", "key": defence, "coefficient": 6.0},
            ],
            "multipliers": [],
            "minimum": None,
            "maximum": -1.0,
        },
    }


def _potion_words(hp, mp, removes):
    if removes:
        return "Support: removes " + ", ".join(STATES[s] for s in removes)
    if hp and mp:
        return "Healing: restores MP"
    return "Healing" if hp else "Support: restores MP"


def _thrown_words(element, state):
    head = "Magic / " + element.title() if element else "Physical / Non-elemental"
    return f"{head}: inflicts {state.replace('_', ' ').title()}" if state else head


def _state_word(state_id):
    return "Defence Down" if state_id == "defense_down" else state_id.replace("_", " ").title()


def fix_removal_words(project):
    """A skill that takes states away said "user gains Poison..." (the description builder
    counted removed states as gained); it says "removes ..." now. Returns how many changed."""
    import dataclasses

    library = project.gameplay_library.abilities
    changed = 0
    for ability_id in list(library.ids()):
        definition = library.require(ability_id)
        removed = [s["state"] for s in definition.apply_states if s.get("remove")]
        if not removed or "removes " in definition.description:
            continue
        gone = {_state_word(s) for s in removed}
        head, _, tail = definition.description.partition(": ")
        kept, prefix = [], ""
        for phrase in tail.split(", ") if tail else ():
            for lead in ("user gains ", "inflicts "):
                if phrase.startswith(lead):
                    prefix, phrase = lead, phrase[len(lead) :]
                    break
            else:
                if not any(phrase == w for w in gone) and phrase not in gone:
                    prefix = prefix if phrase[:1].isupper() else ""
            if phrase in gone:
                continue  # a removed state: it is said below, after "removes"
            kept.append(prefix + phrase if prefix else phrase)
            prefix = ""
        kept.append("removes " + ", ".join(_state_word(s) for s in removed))
        library._definitions[ability_id] = dataclasses.replace(
            definition, description=f"{head}: " + ", ".join(kept)
        )
        changed += 1
    return changed


def apply(project, root):
    """Add the armour, accessories and supplies; returns how many records were added."""
    from asteria.rpg import (
        AttachmentDefinition,
        EquipmentDefinition,
        ItemDefinition,
        SocketDefinition,
    )

    db = project.rpg_database
    before = len(db.equipment) + len(db.items) + len(db.attachments)
    icon = lambda picture: arsenal._icon(root, picture)  # noqa: E731
    for eid, (name, rarity, weight, element, picture) in ARMOUR.items():
        defence, magic_defence, resist, _bonus, socket = TIERS[rarity]
        stats = {"defense": defence, "magic_defense": magic_defence}
        if element and resist:
            stats[f"{element}_resist"] = resist
        db.equipment[eid] = EquipmentDefinition(
            eid,
            name,
            slot="armor",
            tags=("armor", f"armor.{weight}"),
            modifiers=_modifiers(eid, stats),
            sockets=(SocketDefinition("c1", accepted_tags=("card",)),) if socket else (),
            icon_id=icon(picture),
            rarity=rarity,
        )
    for eid, (name, rarity, weights, picture) in ACCESSORIES.items():
        bonus, socket = TIERS[rarity][3], TIERS[rarity][4]
        db.equipment[eid] = EquipmentDefinition(
            eid,
            name,
            slot="accessory",
            tags=("accessory",),
            modifiers=_modifiers(eid, {s: bonus * w for s, w in weights.items()}),
            sockets=(SocketDefinition("g1", accepted_tags=("gem",)),) if socket else (),
            icon_id=icon(picture),
            rarity=rarity,
        )
    for item_id, (name, hp, mp, removes, picture) in POTIONS.items():
        operations = [
            op
            for op in (
                _restore("vitality", hp) if hp else None,
                _restore("technique", mp) if mp else None,
            )
            if op
        ] or [_restore("vitality", 0.0)]
        ability = _ability(
            project,
            f"use_{item_id}",
            "heal",
            name,
            _potion_words(hp, mp, removes),
            operations,
            tags=("ability", "healing"),
            states=[{"state": s, "to": "targets", "remove": True} for s in removes],
            icon_id=icon(picture),
        )
        db.items[item_id] = ItemDefinition(
            item_id,
            name,
            tags=("consumable", "cure" if removes else "potion"),
            icon_id=icon(picture),
            battle_ability=ability,
        )
    for item_id, (name, element, stat, coefficient, state, picture) in THROWN.items():
        defence = "magic_defense" if stat == "magic" else "defense"
        tags = ("ability", f"damage.{element}", "magic") if element else ("ability", "physical")
        ability = _ability(
            project,
            f"throw_{item_id}",
            "bomb_fire",
            name,
            _thrown_words(element, state),
            [_damage(stat, coefficient, defence)],
            tags=tags,
            states=[{"state": state, "to": "targets", "remove": False}] if state else [],
            icon_id=icon(picture),
        )
        db.items[item_id] = ItemDefinition(
            item_id, name, tags=("throwable",), icon_id=icon(picture), battle_ability=ability
        )
    for item_id, (name, picture) in MATERIALS.items():
        db.items[item_id] = ItemDefinition(
            item_id, name, tags=("material",), icon_id=icon(picture)
        )
    for element, (name, picture) in ORBS.items():
        orb = f"{element}_orb"
        db.attachments[orb] = AttachmentDefinition(
            orb,
            name,
            tags=("gem", "orb"),
            modifiers=_modifiers(orb, {f"{element}_attack": 15, "magic": 6}),
            icon_id=icon(picture),
        )
        db.items[f"{orb}_item"] = ItemDefinition(
            f"{orb}_item", name, stack_limit=20, icon_id=icon(picture), attachment_id=orb
        )
    for card, (name, stats, picture) in CARDS.items():
        db.attachments[card] = AttachmentDefinition(
            card, name, tags=("card",), modifiers=_modifiers(card, stats), icon_id=icon(picture)
        )
        db.items[f"{card}_item"] = ItemDefinition(
            f"{card}_item",
            name,
            stack_limit=20,
            icon_id=icon(picture),
            attachment_id=card,
            destroyed_on_removal=True,
        )
    fix_removal_words(project)
    return len(db.equipment) + len(db.items) + len(db.attachments) - before
