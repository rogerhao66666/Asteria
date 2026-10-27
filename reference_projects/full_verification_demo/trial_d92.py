"""D92: weapon slots - the main weapon in the middle, the sub weapon on the right, the special
item on the left, weapons the Brave carries and swaps in battle, two-handed weapons.

* **Slots** (Game Systems ▸ Equipment Slots): every slot of the doll is defined with its name
  and order. ``weapon`` is the main weapon; ``sub_weapon`` takes any piece tagged ``weapon``;
  ``special`` takes pieces tagged ``special`` (the rings); ``arsenal`` holds six carried
  weapons that give nothing until swapped in, and only a job granting
  ``capability.carry_weapons`` has it - the Brave.
* **Two-handed**: bows, staves, spears and axes also take the sub-weapon slot
  (``blocks_slots``); wearing one puts the sub weapon back in the bag (Inventory Rules ▸ When a
  Place Is Taken: take_off), or in the carried slot when swapped in battle.
* **Roger** starts with a sword, the Warden Ring in the special slot and a bow, an axe, a prayer
  book and brawler gloves carried; his sub-weapon hand stays free for the Demon Ring the
  campaign finds.
* **The doll**: main weapon in the middle, sub weapon right, special left, the six carried
  places in a row below on a green field cut from the doll picture (``slot_cell.png``, the
  place's back picture); what fits moves down a little.

The project's other numbers are unchanged. Run it once over ``project.asteria.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

# slot: (name, 繁中, order, capacity, accepted tags, carried, needs, what it is for)
SLOTS = {
    "head": ("Head", "頭部", 10, 1, (), False, (), "Helmets and hats."),
    "armor": ("Body", "身體", 20, 1, (), False, (), "Armour and robes."),
    "legs": ("Legs", "腿部", 30, 1, (), False, (), "Leggings."),
    "feet": ("Feet", "腳部", 40, 1, (), False, (), "Boots and shoes."),
    "special": (
        "Special", "特殊道具", 50, 1, ("special",), False, (),
        "The left of the weapons: one special piece, a ring of power.",
    ),
    "weapon": (
        "Main Weapon", "主武器", 60, 1, (), False, (),
        "The middle: the weapon the hero fights with. A two-handed one also takes the sub"
        " weapon slot.",
    ),
    "sub_weapon": (
        "Sub Weapon", "副武器", 70, 1, ("weapon",), False, (),
        "The right of the main weapon: any one-handed weapon, its stats and attacks count too.",
    ),
    "accessory": ("Accessory", "飾品", 80, 1, (), False, (), "Amulets, charms and medals."),
    "form": ("Form", "形態", 90, 1, (), False, (), "The shape the hero fights in."),
    "arsenal": (
        "Carried Weapons", "攜帶武器", 100, 6, ("weapon",), True,
        ("capability.carry_weapons",),
        "Weapons the hero carries without wearing them: they give nothing until the battle's"
        " Swap command takes one up. Only a job with capability.carry_weapons has it.",
    ),
}  # fmt: skip
TWO_HANDED = ("bow", "staff", "spear", "axe")
CARRIER = "brave"
# tag: (name, 繁中, meaning, 繁中 meaning) - for Game Systems ▸ Tags (D91)
TAGS = {
    "special": (
        "Special", "特殊道具",
        "Fits the special slot, left of the weapons: the rings.",
        "放得進武器左邊的特殊道具格：戒指。",
    ),
    "capability.carry_weapons": (
        "Carries Weapons", "攜帶武器",
        "The hero has the Carried Weapons slot and can swap a carried weapon in battle.",
        "英雄有攜帶武器格，戰鬥中可以換上攜帶的武器。",
    ),
}  # fmt: skip
ZH_MEANING = {
    "head": "頭盔和帽子。",
    "armor": "鎧甲和長袍。",
    "legs": "護腿。",
    "feet": "靴子和鞋子。",
    "special": "武器左邊：一件特殊道具，例如魔戒。",
    "weapon": "中間：英雄拿來戰鬥的武器。雙手武器會同時佔用副武器格。",
    "sub_weapon": "主武器右邊：任何單手武器，它的能力值和攻擊也算進去。",
    "accessory": "護身符、墜飾和勳章。",
    "form": "英雄戰鬥時的形態。",
    "arsenal": "英雄攜帶但沒有穿戴的武器：戰鬥中用「換武器」換上之前沒有任何效果。只有擁有"
    " capability.carry_weapons 的職業才有這一格。",
}
ROGER = "hero_01"
ROGER_START = {
    "special": ("a_warden_ring",),
    "accessory": ("a_warden_charm",),
    "arsenal": ("w_bow", "w_axe", "w_book_of_prayers", "w_brawler_gloves"),
}
# the doll: (slot, rect in the doll picture's pixels); the n-th place shows the n-th piece
PLACES = (
    ("head", (56, 28, 64, 64)),
    ("armor", (272, 28, 64, 64)),
    ("legs", (56, 104, 64, 64)),
    ("feet", (272, 104, 64, 64)),
    ("special", (56, 180, 64, 64)),  # left of the weapons
    ("weapon", (132, 180, 128, 64)),  # the middle
    ("sub_weapon", (272, 180, 64, 64)),  # right
    ("accessory", (12, 204, 32, 32)),  # the little box on the left
    ("form", (348, 204, 32, 32)),  # and on the right
    *(("arsenal", (40 + n * 54, 290, 46, 46)) for n in range(6)),  # carried, under the doll
)
CANDIDATES = (48, 440, 376, 172)
# the carried places' picture: one green field of the doll picture (Lucifer UI, CC0)
DOLL = HERE / "playable_assets/lucifer/ui/inventory_doll.png"
CELL = "playable_assets/lucifer/ui/slot_cell.png"
CELL_BOX = (67, 44, 85, 62)


def patch_slots(db):
    db["equipment_slots"] = [
        {
            "slot_id": slot,
            "display_name": name,
            "order": order,
            "capacity": capacity,
            "accepted_tags": list(tags),
            **({"stowed": True} if carried else {}),
            **({"required_capabilities": list(needs)} if needs else {}),
            "description": meaning,
        }
        for slot, (name, _zh, order, capacity, tags, carried, needs, meaning) in SLOTS.items()
    ]


def patch_gear(db):
    """Rings are special; bows, staves, spears and axes take both hands; the Brave carries."""
    for piece in db["equipment"]:
        tags = set(piece["tags"])
        ring = "equip.ring" in tags or (
            piece["slot"] == "accessory" and "ring" in piece["equipment_id"]
        )
        if ring:
            tags.add("special")
        piece["tags"] = sorted(tags)
        if piece["slot"] == "weapon" and any(f"equip.{k}" in tags for k in TWO_HANDED):
            piece["blocks_slots"] = ["sub_weapon"]
        else:
            piece.pop("blocks_slots", None)
    brave = next(c for c in db["classes"] if c["class_id"] == CARRIER)
    brave["granted_tags"] = sorted({*brave["granted_tags"], "capability.carry_weapons"})


def patch_loadouts(data):
    loadouts = data["game_start"]["rpg_state"]["loadouts"]
    for actor_id, loadout in loadouts.items():
        loadout["slots"] = [
            {"slot_id": s, "accepted_tags": list(v[4]), "capacity": v[3]}
            for s, v in sorted(SLOTS.items())
        ]
        equipped = loadout["equipped"]
        for slot in SLOTS:
            equipped.setdefault(slot, [])
        if actor_id != ROGER:
            continue
        equipped["weapon"] = equipped["weapon"][:1]
        for slot, pieces in ROGER_START.items():
            equipped[slot] = [
                {
                    "attachments": {},
                    "equipment_id": piece,
                    "growth": None,
                    "instance_id": f"{piece}:{actor_id}",
                    "schema": "asteria.rpg.equipment_instance",
                    "version": 2,
                }
                for piece in pieces
            ]
        loadout["equipped"] = dict(sorted(equipped.items()))


def patch_doll(data):
    from PIL import Image

    Image.open(DOLL).convert("RGBA").crop(CELL_BOX).save(HERE / CELL)
    layout = data["battle_presentation_library"]["categories"]["menu_layout"]["equipment"]
    for element in layout["elements"]:
        if element["element_id"] == "doll":
            element["slots"] = [
                {
                    "rect": list(rect),
                    "slot_id": slot,
                    "icon_trim": True,
                    **({"backdrop": CELL} if slot == "arsenal" else {}),
                }
                for slot, rect in PLACES
            ]
        elif element["element_id"] == "candidates":
            element["rect"] = list(CANDIDATES)


def patch_words(data):
    db = data["rpg_database"]
    tables = {t["locale"]: t["entries"] for t in db["locale_tables"]}
    for slot, (_name, zh, *_rest) in SLOTS.items():
        tables["zh-TW"][f"data.slot.{slot}.name"] = zh
        tables["zh-TW"][f"data.slot.{slot}.description"] = ZH_MEANING[slot]
    for tag, (name, zh, meaning, zh_meaning) in TAGS.items():
        tables["zh-TW"][f"data.tag.{tag}.name"] = zh
        tables["zh-TW"][f"data.tag.{tag}.description"] = zh_meaning
        defined = [t for t in db["tag_definitions"] if t["tag_id"] != tag]
        db["tag_definitions"] = defined + [
            {
                "schema": "asteria.rpg.tag_definition",
                "version": 1,
                "tag_id": tag,
                "display_name": name,
                "description": meaning,
            }
        ]
    from asteria.rpg.built_in_text import engine_translations

    for word, chinese in engine_translations("zh-TW").items():  # the engine's new words
        tables["zh-TW"].setdefault(word, chinese)


def main():
    path = HERE / "project.asteria.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    db = data["rpg_database"]
    patch_slots(db)
    patch_gear(db)
    patch_loadouts(data)
    patch_doll(data)
    patch_words(data)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("weapon slots defined, two-handed weapons marked, the Brave carries weapons")


if __name__ == "__main__":
    main()
