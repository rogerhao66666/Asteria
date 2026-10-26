"""D88 on the built project: things block with their whole picture, people with their feet.

As in RPG Maker - a building's tiles cannot be walked on, a person stands on one tile - every
object of the demo (the house, the chests, the bed, the workbenches, the board, the plaque,
the banner, the cache, the vault, the graves and the bush) is set to "Blocks its whole
picture" (``Collider2D.fit = "picture"``, sized by ``editor.passability.picture_box``, as the
Inspector's Passability does); the people keep their feet box.

The equipment screen's doll places cut their icons' empty edges (``MenuSlotPlace.icon_trim``),
so a worn piece's picture fills its place.

The Items page shows the chosen item's details (Menu Pages ``item_details``): the items get a
description (English and Chinese), and the potions a use from the menu (their battle effect's
HP / MP, as in RPG Maker, where a potion works in the menu too).

Run: ``python reference_projects/full_verification_demo/trial_d88.py`` (safe to run again).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

OBJECTS = (
    "Roger's House",
    "Hall of Heroes",
    "Alchemy Table",
    "Forge",
    "Bounty Board",
    "Starfall Chest",
    "Old Cache",
    "Sealed Vault",
    "Victory Banner",
    "Family Chest",
    "Bed",
)
DOODAD = "doodad:"  # every placed doodad (graves, the bush) is a thing too


def _components(node):
    if isinstance(node, dict):
        if isinstance(node.get("components"), list):
            yield node
        for value in node.values():
            yield from _components(value)
    elif isinstance(node, list):
        for value in node:
            yield from _components(value)


def boxes():
    """Entity id -> picture box of every object, measured from the project as it stands."""
    from asteria.editor import EditorDocument
    from asteria.editor.passability import picture_box
    from asteria.project import Project

    project = Project.load_json(HERE / "project.asteria.json", EditorDocument().component_registry)
    found = {}
    for scene in project.scenes():
        for entity in scene.entities():
            if entity.name in OBJECTS or entity.name.startswith(DOODAD):
                box = picture_box(project, HERE, entity)
                if box is not None:
                    found[entity.id] = box
    return found


def patch(data, found):
    changed = 0
    for holder in _components(data["scenes"]):
        box = found.get(holder.get("id"))
        if box is None:
            continue
        for component in holder["components"]:
            if component.get("type") != "asteria.Collider2D":
                continue
            width, height, offset_x, offset_y = box
            fields = {
                **component["fields"],
                "fit": "picture",
                "shape": "box",
                "is_trigger": False,
                "width": width,
                "height": height,
                "offset_x": offset_x,
                "offset_y": offset_y,
            }
            fields = dict(sorted(fields.items()))
            if fields != component["fields"] or component["version"] != 4:
                component["fields"], component["version"] = fields, 4
                changed += 1
    return changed


def trim_icons(data):
    """Every doll place of the equipment layout cuts its icon's empty edges."""
    layouts = data["battle_presentation_library"]["categories"]["menu_layout"]
    for element in layouts["equipment"]["elements"]:
        for place in element.get("slots", ()):
            place["icon_trim"] = True


# (an item id, a start "card_" or an end "_bomb", English, Chinese): the first that matches
DESCRIPTIONS = (
    (
        "potion",
        "A red potion that closes wounds. Use it in the menu or in battle.",
        "紅色藥水，能讓傷口癒合。選單與戰鬥中都能使用。",
    ),
    ("hi_potion", "A stronger potion: restores a lot of HP.", "效果更強的藥水，大量恢復生命。"),
    (
        "mega_potion",
        "The strongest potion: restores almost all HP.",
        "最強的藥水，幾乎恢復全部生命。",
    ),
    ("ether", "A blue tonic that restores MP.", "藍色補劑，恢復魔力。"),
    ("hi_ether", "A strong blue tonic that restores a lot of MP.", "強效藍色補劑，大量恢復魔力。"),
    ("elixir", "Restores all HP and MP.", "完全恢復生命與魔力。"),
    ("antidote", "Cures Poison. Used in battle.", "解除中毒。戰鬥中使用。"),
    ("remedy", "Cures most bad states. Used in battle.", "解除大部分異常狀態。戰鬥中使用。"),
    (
        "healing_herb",
        "A bitter herb for brewing salves at the Alchemy Table.",
        "苦味的藥草，可在煉金桌調製藥膏。",
    ),
    ("_bomb", "Thrown at the foes in battle.", "戰鬥中投向敵人。"),
    (
        "card_",
        "A monster card. Put it into a piece of gear at the Forge (Cards).",
        "魔物卡片。可在鍛造台（卡片）插入裝備。",
    ),
    (
        "charm_",
        "A charm. Put it into a piece of gear at the Forge (Cards).",
        "護符。可在鍛造台（卡片）插入裝備。",
    ),
    ("_orb_item", "An elemental orb for a gear socket.", "屬性寶珠，可鑲入裝備的插槽。"),
    (
        "flawless_",
        "A flawless gem for a gear socket: stronger than the plain one.",
        "無瑕寶石，可鑲入裝備的插槽，比一般寶石更強。",
    ),
    (
        "_item",
        "A gem for a gear socket (Forge, Sockets).",
        "寶石，可鑲入裝備的插槽（鍛造台・插槽）。",
    ),
)
MATERIAL = (
    "A crafting material for the Forge and the Alchemy Table.",
    "製作素材，用於鍛造台與煉金桌。",
)
OTHER = ("A throwing weapon for battle.", "戰鬥用的投擲武器。")
CURE = ("Cures a bad state. Used in battle.", "解除異常狀態。戰鬥中使用。")
CONCOCTION = ("Brewed at the Alchemy Table; used in battle.", "在煉金桌調製，戰鬥中使用。")


def chinese():
    """English -> Chinese of every item description (the demo's glossary reads it)."""
    texts = [(e, z) for _p, e, z in DESCRIPTIONS] + [MATERIAL, OTHER, CURE, CONCOCTION]
    return dict(texts)


def description(item):
    item_id = item["item_id"]
    for part, english, chinese in DESCRIPTIONS:
        prefix, suffix = part.endswith("_"), part.startswith("_")
        if (
            item_id == part
            or (prefix and item_id.startswith(part))
            or (suffix and item_id.endswith(part))
        ):
            return english, chinese
    if "material" in item.get("tags", ()):
        return MATERIAL
    if "throwable" in item.get("tags", ()):
        return OTHER
    if "cure" in item.get("tags", ()):
        return CURE
    if "concoction" in item.get("tags", ()):
        return CONCOCTION
    return None


def patch_items(data):
    """Descriptions for the items, and a menu use for the potions (their battle HP / MP)."""
    db = data["rpg_database"]
    abilities = {a["ability_id"]: a for a in data["gameplay_library"]["abilities"]}
    zh = next(t for t in db["locale_tables"] if t["locale"] == "zh-TW")["entries"]
    for item in db["items"]:
        text = description(item)
        key = f"data.item.{item['item_id']}.description"
        if text is None:
            item.pop("description", None)
            zh.pop(key, None)
        else:
            item["description"], zh[key] = text
        ability = abilities.get(item.get("battle_ability", ""))
        if "potion" not in item.get("tags", ()) or ability is None:
            continue
        effects = []
        for entry in ability["effects"]:
            effect = dict(entry["effect"])
            effect["operations"] = [
                op for op in effect["operations"] if op["kind"] == "resource_delta"
            ]
            effect["effect_id"] = f"{item['item_id']}.menu"
            effects.append(effect)
        item["use_effects"] = effects


def patch_words(data):
    """The engine's Chinese for the words the demo's table does not have yet (D88's new ones)."""
    from asteria.rpg.built_in_text import engine_translations

    tables = data["rpg_database"]["locale_tables"]
    entries = next(t for t in tables if t["locale"] == "zh-TW")["entries"]
    for key, word in engine_translations("zh-TW").items():
        entries.setdefault(key, word)


def main():
    path = HERE / "project.asteria.json"
    found = boxes()
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = patch(data, found)
    trim_icons(data)
    patch_items(data)
    patch_words(data)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"objects blocking with their whole picture: {len(found)} (changed {changed})")


if __name__ == "__main__":
    main()
