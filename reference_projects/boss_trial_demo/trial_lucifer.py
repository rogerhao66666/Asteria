"""Battle art of the Boss Trial demo, cut from Foozle's Lucifer packs (all CC0).

Every Lucifer character ships one strip per animation (``<Name>Right<Anim>.png``, square frames
whose side is the strip's height, drawn facing right). ``character_sheet`` lays the strips of one
character onto a single sheet with one cell size, trims the empty margin, and names the clips the
battle presentation asks for: idle, three attacks (attack, attack2, attack3), cast, hit, guard, ko,
revive, status and transform.
"""

from __future__ import annotations

import os
from pathlib import Path

FREE_ASSETS = Path(
    os.environ.get("ASTERIA_FREE_ASSETS", Path.home() / "Downloads" / "free_assets")
)
SOURCE = (("license", "CC0 1.0"), ("source", "Foozle Lucifer packs"))
PACKS = {
    "warrior": "Foozle_2DC0009_Lucifer_Warrior_Pixel_Art",
    "necromancer": "Foozle_2DC0010_Lucifer_Necromancer_Pixel_Art",
    "sorceress": "Foozle_2DC0011_Lucifer_Sorceress_Pixel_Art",
    "cultist": "Foozle_2DC0013_Lucifer_Cultist_Pixel_Art",
    "goblin_slinger": "Foozle_2DC0014_Lucifer_Goblin_Slinger_Pixel_Art",
    "goblin_berserker": "Foozle_2DC0015_Lucifer_Goblin_Berserker_Pixel_Art",
    "goblin_beast": "Foozle_2DC0016_Lucifer_Goblin_Beast_Pixel_Art",
    "goblin_rider": "Foozle_2DC0017_Lucifer_Goblin_Rider_Pixel_Art",
    "skeleton_grunt": "Foozle_2DC0018_Lucifer_Skeleton_Grunt_Pixel_Art",
    "skeleton_hunter": "Foozle_2DC0019_Lucifer_Skeleton_Hunter_Pixel_Art",
    "skeleton_ancient": "Foozle_2DC0020_Lucifer_Skeleton_Ancient_Pixel_Art",
    "skeleton_king": "Foozle_2DC0021_Lucifer_Skeleton_King_Pixel_Art",
}
UI_PACK = "Foozle_UI_0002_Lucifer_RPG_UI_Pixel_Art"
EXTRA_STATES = ("attack2", "attack3")  # the second and third attack animations


def available():
    return FREE_ASSETS.is_dir()


def pack_dir(key):
    return FREE_ASSETS / PACKS[key]


def _strip_frames(path, mirror=False):
    from PIL import Image, ImageOps

    image = Image.open(path).convert("RGBA")
    side = image.height
    frames = [image.crop((i * side, 0, (i + 1) * side, side)) for i in range(image.width // side)]
    return [ImageOps.mirror(f) for f in frames] if mirror else frames


def _source_facing(facing):
    """``(pack folder, mirror)`` for a facing: every direction has its own strips in the pack
    (Left, Right, Up - the back view - and Down), so each is used as drawn, never turned round."""
    return facing, False


def _find(key, anim, facing="Right"):
    folder = pack_dir(key) / facing / "Png"
    hits = sorted(folder.glob(f"*{anim}.png"))
    return hits[0] if hits else None


def character_sheet(key, *, scale=2, cast="Attack02", transform="Jump", facing="Right"):
    """One sheet for a Lucifer character: ``(image, (frame w, frame h), clips, body_height)``.

    ``facing`` picks the pack's Right or Left strips: they are drawn separately (the swing, the
    weapon hand), not mirrors of each other, so a side that fights facing left uses ``"Left"`` art
    (the sheet is then marked ``facing: left`` and is not turned round)."""
    from PIL import Image

    wanted = {
        "idle": "Idle",
        "attack": "Attack01",
        "attack2": "Attack02",
        "attack3": "Attack03",
        "cast": cast,
        "hit": "Hurt",
        "ko": "Death",
        "transform": transform,
    }
    source, mirror = _source_facing(facing)
    strips = {}
    for role, anim in wanted.items():
        path = _find(key, anim, source) or _find(
            key, "Attack01" if role.startswith("attack") else "Idle", source
        )
        strips[role] = _strip_frames(path, mirror)
    cell = max(f.width for frames in strips.values() for f in frames)

    def placed(frame):
        out = Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
        out.alpha_composite(frame, ((cell - frame.width) // 2, cell - frame.height))
        return out

    cells = {role: [placed(f) for f in frames] for role, frames in strips.items()}
    boxes = [f.getchannel("A").getbbox() for frames in cells.values() for f in frames]
    boxes = [b for b in boxes if b]
    left, right = min(b[0] for b in boxes), max(b[2] for b in boxes)
    top, bottom = min(b[1] for b in boxes), max(b[3] for b in boxes)
    half = max(cell // 2 - left, right - cell // 2)
    box = (cell // 2 - half, top, cell // 2 + half, bottom)
    cells = {role: [f.crop(box) for f in frames] for role, frames in cells.items()}
    order, clips, frames = [], {}, []

    def add(role, source_role, *, duration, loop, reverse=False, hold=False, hit=None):
        source = cells[source_role]
        if reverse:
            source = source[::-1]
        start = len(frames)
        frames.extend(source)
        indices = list(range(start, start + len(source)))
        clip = {"frames": indices, "frame_duration": duration, "loop": loop}
        if hit is not None:
            clip["events"] = {str(hit): ["hit"]}
        clips[role] = clip
        order.append(role)

    def hit_frame(role):  # the strike lands a little past the middle of the swing
        return max(1, round(len(cells[role]) * 0.55))

    add("idle", "idle", duration=0.18, loop=True)
    add("attack", "attack", duration=0.085, loop=False, hit=hit_frame("attack"))
    add("attack2", "attack2", duration=0.085, loop=False, hit=hit_frame("attack2"))
    add("attack3", "attack3", duration=0.08, loop=False, hit=hit_frame("attack3"))
    add("cast", "cast", duration=0.1, loop=False)
    add("hit", "hit", duration=0.08, loop=False)
    add("ko", "ko", duration=0.12, loop=False)
    add("revive", "ko", duration=0.1, loop=False, reverse=True)
    add("transform", "transform", duration=0.1, loop=False)
    for role in ("attack", "attack2", "attack3", "cast", "hit", "transform"):
        # a swing or a jump ends mid-air or mid-blow: the last frame is the standing pose, so
        # the figure is back on its feet however long the rest of the action lasts
        clips[role]["frames"] = [*clips[role]["frames"], clips["idle"]["frames"][0]]
    clips["guard"] = {"frames": [clips["idle"]["frames"][0]], "frame_duration": 0.3, "loop": True}
    clips["status"] = dict(clips["idle"])
    width, height = box[2] - box[0], box[3] - box[1]
    sheet = Image.new("RGBA", (width * len(frames), height), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        sheet.paste(frame, (index * width, 0))
    sheet = sheet.resize((sheet.width * scale, sheet.height * scale), Image.NEAREST)
    idle_box = cells["idle"][0].getchannel("A").getbbox()
    body = (idle_box[3] - idle_box[1]) * scale
    return sheet, (width * scale, height * scale), clips, body


def feet_pivot(image, frame):
    """The vertical pivot (0..1 from the top) of the standing figure: the sheet's frames reach
    below the idle pose (other animations lie lower), so bars and names placed from the feet
    would sit on the figure; pivoting at the idle feet puts the anchor where the feet are."""
    cell = image.crop((0, 0, frame[0], frame[1]))
    box = cell.getchannel("A").getbbox()
    return round(box[3] / frame[1], 4) if box else 1.0


def credits_rows(keys):
    return [
        f"| `battle/*.png` ({', '.join(sorted(keys))}) | Foozle Lucifer character packs "
        f"({', '.join(PACKS[k] for k in sorted(keys))}), strips arranged on one sheet per "
        "character and scaled (built by `trial_lucifer.py`) | Foozle (Baldur) | "
        "[CC0 1.0](http://creativecommons.org/publicdomain/zero/1.0/) |"
    ]


def _facing_strip(key, facing, anim):
    source, mirror = _source_facing(facing)
    folder = pack_dir(key) / source / "Png"
    hits = sorted(folder.glob(f"*{anim}.png"))
    return _strip_frames(hits[0], mirror) if hits else []


def field_sheet(key, *, frame=64):
    """The walk cycle in the engine's 3 x 4 field sheet (rows down / left / right / up)."""
    from PIL import Image

    out = Image.new("RGBA", (3 * frame, 4 * frame), (0, 0, 0, 0))
    for row, facing in enumerate(("Down", "Left", "Right", "Up")):
        walk = _facing_strip(key, facing, "Walk") or _facing_strip(key, facing, "Run")
        picks = [walk[0], walk[len(walk) // 3], walk[2 * len(walk) // 3]]
        for column, cell in enumerate(picks):
            cell = cell.crop(cell.getchannel("A").getbbox() or (0, 0, *cell.size))
            x = column * frame + (frame - cell.width) // 2
            out.alpha_composite(cell, (x, row * frame + frame - cell.height - 2))
    return out


def npc_picture(key, *, size=48):
    """The front (facing down) idle pose of a character, for NPCs standing in the field."""
    from PIL import Image

    cell = villager(_facing_strip(key, "Down", "Idle")[0])
    box = cell.getchannel("A").getbbox() or (0, 0, *cell.size)
    cell = cell.crop(box)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(cell, ((size - cell.width) // 2, size - cell.height))
    return out


def villager(image):
    """The same figure in plain townsfolk colours (a sepia duotone), so a person in town never
    looks like one of the party's characters."""
    from PIL import ImageOps

    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    tone = ImageOps.colorize(
        ImageOps.grayscale(rgba), black=(38, 30, 26), white=(222, 204, 168), mid=(128, 104, 80)
    ).convert("RGBA")
    tone.putalpha(alpha)
    return tone


NPC_CAST = {  # who stands where in the field
    "Smith": "warrior",
    "Awakener": "cultist",
    "Jeweler": "sorceress",
    "Card Dealer": "necromancer",
    "Mystic Teacher": "sorceress",
    "Duelist Teacher": "warrior",
    "Weapon Master Dojo": "warrior",
    "Sage's Tower": "necromancer",
    "Hero's Shrine": "warrior",
    "Forgemaster's Smithy": "warrior",
    "Rogue Guild": "cultist",
    "Guardian Post": "warrior",
    "Shrine": "cultist",
    "Alchemist": "necromancer",
    "Merchant": "cultist",
    "Breaker": "sorceress",
    "Armory (Bow)": "sorceress",
    "Armory (Dagger)": "cultist",
}


# -- icons, UI skin and font --------------------------------------------------------------------
EQUIPMENT = FREE_ASSETS / "Foozle_2DS0005_Lucifer_Equipment_Pixel_Art" / "Equipment"
PICKUPS = FREE_ASSETS / "Foozle_2DS0006_Lucifer_Pickups_Pixel_Art" / "Pickups"
EQUIPMENT_ICONS = {  # equipment id: file under Equipment
    "w_sword": "Weapons/Png/Common Arming Sword.png",
    "w_axe": "Weapons/Png/Common Bearded Axe.png",
    "w_spear": "Weapons/Png/Common Spear.png",
    "w_dagger": "Weapons/Png/Legendary Rapier .png",
    "w_staff": "Weapons/Png/Wizards Pole.png",
    "w_sunbrand": "Weapons/Png/Rare Greatsword.png",
    "w_sunbrand_ex": "Weapons/Png/Mythic Godhammer.png",
    "a_warden_plate": "Chest/Png/Rare Plate Chestpiece.png",
    "a_warden_ring": "Misc/Png/Golden Enchanted Ring.png",
    "a_warden_charm": "Misc/Png/Rare Golden Gem Amulet.png",
    "f_normal": "Misc/Png/Rare Explorers Gloves.png",  # bare-handed fighting
    "f_dragon": "Misc/Png/Wizards Sparkle Ring.png",
}
ITEM_ICONS = {  # item id: file under Pickups
    "ruby_item": "Gems/Png/OrangeGem.png",
    "sapphire_item": "Gems/Png/BlueGem.png",
    "topaz_item": "Gems/Png/PinkGem.png",
    "onyx_item": "Gems/Png/PinkGem.png",
    "healing_salve": "Potions/Health/Png/SmallHealthPotion.png",
    "phoenix_tonic": "Potions/Health/Png/BigHealthPotion.png",
    "ether_draught": "Potions/Mana/Png/BigManaPotion.png",
    "storm_flask": "Potions/Stamina/Png/BigStaminaPotion.png",
    "fire_bomb": "Potions/Stamina/Png/SmallStaminaPotion.png",
    "frost_bomb": "Potions/Mana/Png/SmallManaPotion.png",
    "card_golem_item": "Gold/Png/PileOfGold.png",  # a monster card: shown as a pile of coins
    "card_slayer_item": "Gold/Png/PileOfGold.png",
    "card_vampire_item": "Gold/Png/PileOfGold.png",
    "card_wolf_item": "Gold/Png/PileOfGold.png",
}
SKILL_ICON_GROUPS = {  # which Lucifer class icon set a skill draws from
    "warrior": (
        "Warrior Icons",
        ("Warrior Red Skills", "Warrior Green Skills", "Warrior Purple Skills"),
    ),
    "sorceress": (
        "Sorceress Icons",
        ("Sorceress Red Icons", "Sorceress Green Skills", "Sorceress Purple Skills"),
    ),
    "necromancer": (
        "Necromancer Icons",
        ("Necromancer Red Skills", "Necromancer Green Skills", "Necromancer Purple Skills"),
    ),
}


def _skill_group(definition):
    tags = set(definition.tags)
    if tags & {"damage.dark"} or any(t.startswith("status.") for t in tags):
        return "necromancer"
    if "magic" in tags or tags & {f"damage.{e}" for e in ("fire", "ice", "lightning", "light")}:
        return "sorceress"
    return "warrior"


def _skill_pool(group):
    base = FREE_ASSETS / UI_PACK / "Skill Icons" / SKILL_ICON_GROUPS[group][0]
    files = []
    for folder in SKILL_ICON_GROUPS[group][1]:
        files.extend(sorted((base / folder / "Png").glob("*.png")))
    return files


def apply_icons(context):
    """Lucifer icons for gear, gems and skills (a skill takes the next picture of its class's
    set, in alphabetical order of skills, so the assignment is stable). Returns the ability ids
    that now carry a Lucifer icon."""
    import dataclasses
    import shutil

    folder = context.root / "playable_assets" / "lucifer" / "icons"
    folder.mkdir(parents=True, exist_ok=True)
    db = context.db

    def copy(source, name):
        shutil.copyfile(source, folder / name)
        return f"playable_assets/lucifer/icons/{name}"

    for equipment_id, rel in EQUIPMENT_ICONS.items():
        if equipment_id in db.equipment:
            icon = copy(EQUIPMENT / rel, f"{equipment_id}.png")
            db.equipment[equipment_id] = dataclasses.replace(
                db.equipment[equipment_id], icon_id=icon
            )
    for item_id, rel in ITEM_ICONS.items():
        if item_id in db.items:
            icon = copy(PICKUPS / rel, f"{item_id}.png")
            db.items[item_id] = dataclasses.replace(db.items[item_id], icon_id=icon)
    pools = {g: _skill_pool(g) for g in SKILL_ICON_GROUPS}
    cursor = dict.fromkeys(pools, 0)
    kept = []
    for ability_id in sorted(context.abilities.ids()):
        definition = context.abilities.get(ability_id)
        if definition.icon_id and ability_id.startswith("attack_"):
            continue  # a weapon's attack shows the weapon
        group = _skill_group(definition)
        pool = pools[group]
        source = pool[cursor[group] % len(pool)]
        cursor[group] += 1
        icon = copy(source, f"skill_{ability_id}.png")
        context.abilities._definitions[ability_id] = dataclasses.replace(definition, icon_id=icon)
        kept.append(ability_id)
    _node_icons(db, pools, copy)
    return tuple(kept)


def _node_icons(db, pools, copy):
    """Tree nodes that grant no ability (training, keystones, masteries) get a class icon of
    their own so every node of a skill tree has a picture."""
    import dataclasses

    groups = tuple(pools)
    for index, (graph_id, graph) in enumerate(sorted(db.progression_graphs.items())):
        pool = pools[groups[index % len(groups)]]
        nodes = []
        for number, node in enumerate(graph.nodes):
            if not node.icon_id and not any(r.granted_abilities for r in node.rewards):
                source = pool[(number * 5 + 3) % len(pool)]
                node = dataclasses.replace(node, icon_id=copy(source, f"node_{node.node_id}.png"))
            nodes.append(node)
        db.progression_graphs[graph_id] = dataclasses.replace(graph, nodes=tuple(nodes))


def apply_ui(context):
    """Skin the battle UI and the host's menus with the Lucifer RPG UI: stone panels, stone
    row buttons, wood for results, the pack's pixel font."""
    import dataclasses
    import shutil

    from asteria.presentation.ui_skin import NinePatch

    folder = context.root / "playable_assets" / "lucifer" / "ui"
    folder.mkdir(parents=True, exist_ok=True)
    ui = FREE_ASSETS / UI_PACK
    files = {
        "panel_stone.png": ui / "Panels" / "Panels" / "SimplePanel01.png",
        "panel_wood.png": ui / "Panels" / "Panels" / "SimplePanel03.png",
        "font.ttf": ui / "Font" / "PixelRpgFont-Regular.ttf",
    }
    for name, source in files.items():
        shutil.copyfile(source, folder / name)
    path = lambda name: f"playable_assets/lucifer/ui/{name}"  # noqa: E731
    library = context.project.battle_presentation_library
    for key in library.ids("ui_theme"):
        theme = library.require("ui_theme", key)
        library.set(
            "ui_theme",
            key,
            dataclasses.replace(
                theme,
                panel_skins=(
                    # the command menu beside a character stays see-through: no skin for
                    # "interaction:*" and the rows (their selected row is a soft highlight)
                    ("result", NinePatch(path("panel_wood.png"), 3, 3, 3, 3, 1.0)),
                    ("host:panel", NinePatch(path("panel_stone.png"), 3, 3, 3, 3, 2.0)),
                    ("hud:*", NinePatch(path("panel_stone.png"), 3, 3, 3, 3, 1.0)),
                ),
                font_asset_id=path("font.ttf"),
                font_scale=0.62,
            ),
        )
    for key in library.ids("ui_layout"):
        library.set(
            "ui_layout",
            key,
            dataclasses.replace(library.require("ui_layout", key), row_buttons=True),
        )


def credits_extra():
    cc0 = "[CC0 1.0](http://creativecommons.org/publicdomain/zero/1.0/)"
    return [
        "| `lucifer/icons/*.png` | Foozle Lucifer Equipment (`Foozle_2DS0005`), Lucifer Pickups "
        "(`Foozle_2DS0006`) and Lucifer RPG UI skill icons (`Foozle_UI_0002`), copied unmodified "
        f"| Foozle (Baldur) | {cc0} |",
        "| `lucifer/ui/*` | Foozle Lucifer RPG UI (`Foozle_UI_0002`): SimplePanel01 and 03, "
        "PixelRpgFont-Regular.ttf, copied unmodified "
        f"| Foozle (Baldur) | {cc0} |",
    ]


MUSIC = {  # manifest name: file of the CC0 Foozle music packs
    "town_theme": "Foozle_M0002_Explorer_Chiptunes/foozlecc - Theme #1 (30s).ogg",
    "woods_theme": "Foozle_M0002_Explorer_Chiptunes/foozlecc - Theme #2 (30s).ogg",
    "crypt_theme": "Foozle_M0001_Eerie_Space_Music/track 2.ogg",
    "battle_theme": "Foozle_M0002_Explorer_Chiptunes/foozlecc - Under Pressure Theme.ogg",
    "throne_theme": "Foozle_M0002_Explorer_Chiptunes/foozlecc - Under Pressure Theme 2.ogg",
}


def apply_music(context):
    """Copy the music into the project; the manifest names them (``context.audio``)."""
    import shutil

    folder = context.root / "playable_assets" / "audio"
    folder.mkdir(parents=True, exist_ok=True)
    context.audio = {}
    for name, rel in MUSIC.items():
        shutil.copyfile(FREE_ASSETS / rel, folder / f"{name}.ogg")
        context.audio[name] = f"playable_assets/audio/{name}.ogg"


def credits_music():
    cc0 = "[CC0 1.0](http://creativecommons.org/publicdomain/zero/1.0/)"
    return [
        "| `audio/town_theme.ogg`, `woods_theme.ogg`, `battle_theme.ogg`, `throne_theme.ogg` | "
        "Foozle Explorer Chiptunes (`Foozle_M0002`: Theme #1 / #2 (30s), Under Pressure 1-2),"
        f" copied unmodified, renamed | Foozle | {cc0} |",
        "| `audio/crypt_theme.ogg` | Foozle Eerie Space Music (`Foozle_M0001`: track 2), copied "
        f"unmodified, renamed | Foozle | {cc0} |",
    ]


EFFECTS_PACK = FREE_ASSETS / "Foozle_2DE0001_Pixel_Magic_Effects"


def effect_frames(folder, tint=None):
    """The frames of one Pixel Magic Effects strip; a ``tint`` is ``(dark, bright)`` colours the
    picture is recoloured with (its alpha stays)."""
    from PIL import Image, ImageOps

    frames = []
    for path in sorted((EFFECTS_PACK / folder).glob("*.png")):
        image = Image.open(path).convert("RGBA")
        if tint is not None:
            alpha = image.getchannel("A")
            image = ImageOps.colorize(ImageOps.grayscale(image), tint[0], tint[1]).convert("RGBA")
            image.putalpha(alpha)
        frames.append(image)
    return frames
