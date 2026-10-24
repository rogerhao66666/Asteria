"""The Full Verification demo's paper doll: three more slots, their gear, two screen layouts (U3).

* **Slots**: every hero gets ``head``, ``legs`` and ``feet`` (one piece each) beside the weapon,
  armour, accessory and form slots. The Lucifer doll picture has a place for each; the second
  weapon (Roger holds two) and the second accessory have places too.
* **Gear** (14): helmets, leggings and boots, Common to Legendary, in four styles - chain, plate
  (more defence), wizard (magic defence and magic) and explorer (speed and evasion). Rare and
  better have a gem socket; the armour refine rules take them (tag ``armor``). Pictures:
  Foozle's Lucifer Equipment icons (CC0), copied into ``playable_assets/lucifer/icons``.
  Hilde's Armoury sells them.
* **Layouts** (``menu_layout``): the equipment screen draws Lucifer UI's Inventory picture
  (CC0, ``playable_assets/lucifer/ui/inventory_doll.png``) four times its size with every slot
  placed on it, what fits on its lower half, the stone panels for the piece and the stats; the
  enhance screen uses the stone panels; both stand on the doll picture's brown.

``apply(project, root)`` adds what is missing and can run again; ``build_project.py`` runs it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EQUIPMENT_ART = REPO / "asset_library/foozle/Foozle_2DS0005_Lucifer_Equipment_Pixel_Art/Equipment"
DOLL_ART = REPO / (
    "asset_library/foozle/Foozle_UI_0002_Lucifer_RPG_UI_Pixel_Art/HUD/Inventory/Png/"
    "InventoryEmptyFields.png"
)
ICON_DIR = "playable_assets/lucifer/icons"
DOLL = "playable_assets/lucifer/ui/inventory_doll.png"
STONE = "playable_assets/lucifer/ui/panel_stone.png"
SLOTS = ("head", "legs", "feet")
# rarity: (defence, magic defence, style bonus, gem socket)
TIERS = {
    "common": (4, 2, 2, False),
    "magic": (7, 4, 3, False),
    "rare": (10, 7, 5, True),
    "legendary": (15, 10, 7, True),
}
# style: (defence ×, magic defence ×, {stat: weight of the style bonus})
STYLES = {
    "chain": (1.0, 1.0, {}),
    "plate": (1.5, 0.5, {}),
    "wizard": (0.5, 1.5, {"magic": 1}),
    "explorer": (0.8, 0.8, {"speed": 1, "evade": 1}),
}
# id: (name, slot, rarity, style, picture under EQUIPMENT_ART)
GEAR = {
    "hd_chain_helmet": ("Chainmail Helmet", "head", "common", "chain",
                        "Head/Png/Common Chainmail Helmet.png"),
    "hd_wizard_hat": ("Wizard's Hat", "head", "magic", "wizard", "Head/Png/Wizards Hat.png"),
    "hd_explorer_ushanka": ("Explorer's Ushanka", "head", "rare", "explorer",
                            "Head/Png/Rare Explorers Ushanka.png"),
    "hd_plate_helmet": ("Plate Helmet", "head", "rare", "plate",
                        "Head/Png/Rare Plate Helmet.png"),
    "hd_royal_helmet": ("Royal Helmet", "head", "legendary", "plate",
                        "Head/Png/Legendary Royal Helmet.png"),
    "lg_leggings": ("Leggings", "legs", "common", "explorer", "Bottom/Png/Common Leggings.png"),
    "lg_chain_leggings": ("Chainmail Leggings", "legs", "magic", "chain",
                          "Bottom/Png/Common Chainmail Leggings.png"),
    "lg_wizard_leggings": ("Wizard's Leggings", "legs", "magic", "wizard",
                           "Bottom/Png/Wizards Leggings.png"),
    "lg_explorer_leggings": ("Explorer's Leggings", "legs", "rare", "explorer",
                             "Bottom/Png/Rare Explorers Leggings.png"),
    "lg_plate_leggings": ("Plate Leggings", "legs", "rare", "plate",
                          "Bottom/Png/Rare Plate Leggings.png"),
    "ft_chain_boots": ("Chainmail Boots", "feet", "common", "chain",
                       "Feet/Png/Common Chainmail Boots.png"),
    "ft_wizard_shoes": ("Wizard's Shoes", "feet", "magic", "wizard",
                        "Feet/Png/Wizards Shoes.png"),
    "ft_explorer_boots": ("Explorer's Boots", "feet", "rare", "explorer",
                          "Feet/Png/Rare Explorers Boots.png"),
    "ft_plate_boots": ("Plate Boots", "feet", "rare", "plate", "Feet/Png/Rare Plate Boots.png"),
}  # fmt: skip
# the doll picture is 98 x 131; drawn 4x at (40, 96). Places are in screen pixels from there.
DOLL_RECT = (40, 96, 392, 524)
PLACES = (
    ("head", (56, 28, 64, 64)),
    ("armor", (272, 28, 64, 64)),
    ("legs", (56, 104, 64, 64)),
    ("feet", (272, 104, 64, 64)),
    ("accessory", (56, 180, 64, 64)),
    ("weapon", (132, 180, 128, 64)),
    ("weapon", (272, 180, 64, 64)),  # a second weapon (Roger holds two)
    ("accessory", (12, 204, 32, 32)),  # the little box on the left
    ("form", (348, 204, 32, 32)),  # and on the right
)


def equipment_ids():
    return list(GEAR)


def _icon(root, picture, equipment_id):
    target = Path(root) / ICON_DIR / f"{equipment_id}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(EQUIPMENT_ART / picture, target)
    return f"{ICON_DIR}/{equipment_id}.png"


def _stats(rarity, style):
    defence, magic_defence, bonus, _socket = TIERS[rarity]
    times, magic_times, weights = STYLES[style]
    stats = {
        "defense": round(defence * times),
        "magic_defense": round(magic_defence * magic_times),
    }
    for stat, weight in weights.items():
        stats[stat] = bonus * weight
    return {k: v for k, v in stats.items() if v}


def add_gear(project, root):
    from asteria.gameplay.modifiers import StatModifier
    from asteria.rpg import EquipmentDefinition, SocketDefinition

    db = project.rpg_database
    for eid, (name, slot, rarity, style, picture) in GEAR.items():
        modifiers = tuple(
            StatModifier(f"{eid}.{stat}", stat, "add", float(value))
            for stat, value in _stats(rarity, style).items()
        )
        socket = TIERS[rarity][3]
        db.equipment[eid] = EquipmentDefinition(
            eid,
            name,
            slot=slot,
            tags=(slot, "armor", f"{slot}.{style}"),  # "armor": the armour refine rules take it
            modifiers=modifiers,
            sockets=(SocketDefinition("g1", accepted_tags=("gem",)),) if socket else (),
            icon_id=_icon(root, picture, eid),
            rarity=rarity,
        )


def add_slots(project):
    """``head``, ``legs`` and ``feet`` on every hero's loadout in the game start."""
    data = project.game_start.rpg_state_data
    for loadout in data["loadouts"].values():
        have = {s["slot_id"] for s in loadout["slots"]}
        for slot_id in SLOTS:
            if slot_id not in have:
                loadout["slots"].append({"slot_id": slot_id, "capacity": 1, "accepted_tags": []})
            loadout["equipped"].setdefault(slot_id, [])


def add_to_shop(project):
    import trial_shops as shops

    from asteria.rpg.economy import ShopDefinition, ShopEntry

    db = project.rpg_database
    shop = db.shops.get("armour_shop")
    if shop is None:
        return
    have = {e.item_id for e in shop.entries}
    extra = tuple(
        ShopEntry(i, buy_prices={"gold": float(shops.PRICE[db.equipment[i].rarity])})
        for i in GEAR
        if i not in have
    )
    db.shops["armour_shop"] = ShopDefinition(
        shop.shop_id, shop.display_name, shop.entries + extra, icon_id=shop.icon_id
    )


def layouts(root):
    """The equipment and enhance screens' layouts (``MenuLayout``)."""
    from asteria.presentation.menu_layout import MenuElement, MenuLayout, MenuSlotPlace
    from asteria.presentation.ui_skin import NinePatch

    target = Path(root) / DOLL
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(DOLL_ART, target)
    stone = NinePatch(STONE, 3, 3, 3, 3, 2.0)
    dark, rim = (30, 24, 20, 244), (92, 72, 50)  # the doll picture's browns
    clear, brown = (0, 0, 0, 0), (40, 34, 31)
    gold = (255, 214, 120)
    equipment = MenuLayout(
        "equipment",
        elements=(
            MenuElement("frame", "panel", fill=dark, border=rim),
            MenuElement("title", "text", rect=(460, 30, 400, 40), color=gold, size=34),
            MenuElement("member", "text", rect=(460, 72, 780, 28)),
            MenuElement(
                "doll",
                "doll",
                rect=DOLL_RECT,
                image=DOLL,
                slots=tuple(MenuSlotPlace(s, r) for s, r in PLACES),
            ),
            # what fits: on the doll picture's empty lower half, no frame of its own
            MenuElement(
                "candidates",
                "list",
                rect=(48, 378, 376, 234),
                fill=clear,
                border=brown,
                row_height=42,
            ),
            MenuElement("detail", "detail", rect=(452, 112, 386, 508), skin=stone),
            MenuElement("stats", "list", rect=(852, 112, 388, 508), skin=stone, row_height=30),
            MenuElement("hint", "text", rect=(48, 640, 1180, 24)),
        ),
    )
    enhance = MenuLayout(
        "enhance",
        elements=(
            MenuElement("frame", "panel", fill=dark, border=rim),
            MenuElement("title", "text", color=gold, size=34),
            MenuElement("gear", "list", skin=stone),
            MenuElement("sockets", "list", skin=stone),
            MenuElement("choices", "list", skin=stone),
            MenuElement("detail", "detail", skin=stone),
        ),
    )
    return equipment, enhance


def add_layouts(project, root):
    library = project.battle_presentation_library
    for layout in layouts(root):
        library.set("menu_layout", layout.screen_id, layout)


def apply(project, root):
    """Everything above; returns how many equipment records were added."""
    before = len(project.rpg_database.equipment)
    add_gear(project, root)
    add_slots(project)
    add_to_shop(project)
    add_layouts(project, root)
    return len(project.rpg_database.equipment) - before
