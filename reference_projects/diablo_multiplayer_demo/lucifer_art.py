"""Foozle Lucifer art (CC0) for the ARPG demo: four-facing characters, the overworld and the
dungeon tiles. Same shapes as ``art.py`` (sheets, clips named ``idle_/walk_/attack_<facing>``,
tile atlases with the same cell names), so the maps and the content do not change.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _path in (REPO / "scripts", REPO / "reference_projects" / "full_verification_demo"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import art  # noqa: E402
import trial_lucifer as lucifer  # noqa: E402

FOLDERS = {"down": "Down", "up": "Up", "left": "Left", "right": "Right"}
EXTERIOR = (
    lucifer.FREE_ASSETS
    / "Foozle_2DT0002_Lucifer_Exterior_Tileset_Pixel_Art"
    / "Png"
    / "OuterTileset.png"
)
DUNGEON = (
    lucifer.FREE_ASSETS
    / "Foozle_2DT0003_Lucifer_Dungeon_Tileset_Pixel_Art"
    / "Png"
    / "DungeonTileset.png"
)


def _surface(image):
    """A pygame surface from a PIL image."""
    image = image.convert("RGBA")
    return art.pygame.image.frombytes(image.tobytes(), image.size, "RGBA")


def _strip(key, facing, names):
    for name in names:
        frames = lucifer._facing_strip(key, facing, name)
        if frames:
            return frames
    return []


ACTIONS = {  # clip role: the Lucifer strips it may come from (first that exists), seconds total
    "attack": (("Attack01", "Attack02", "Idle"), 0.3),
    "attack2": (("Attack02", "Attack01", "Idle"), 0.4),
    "attack3": (("Attack03", "Attack02", "Attack01", "Idle"), 0.5),
    "jump": (("Jump", "Attack03", "Attack01", "Idle"), 0.5),
}


def character(assets, key, lucifer_key, name, *, height=26):
    """A Lucifer character as one sheet: per facing the idle and walk strips and the whole of the
    attack strips (``attack``, ``attack2``, ``attack3``) and the jump, every frame kept at its
    own size on one common cell (a strip's cell may be larger: arcs, a long weapon) and scaled so
    the standing figure is ``height`` px tall; the pivot stands at the feet."""
    from PIL import Image

    strips = {}
    for facing in FOLDERS.values():
        roles = {
            "idle": _strip(lucifer_key, facing, ("Idle",)),
            "walk": lucifer.walk_strip(lucifer_key, facing),
        }
        for role, (names, _seconds) in ACTIONS.items():
            roles[role] = _strip(lucifer_key, facing, names)
        strips[facing] = roles
    stand = strips["Down"]["idle"][0]
    body = stand.getchannel("A").getbbox()
    scale = height / float(body[3] - body[1])
    cell = max(f.width for roles in strips.values() for frames in roles.values() for f in frames)
    side = max(1, round(cell * scale))

    def placed(frame):  # centred, standing on the cell's bottom edge, at its own size
        out = Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
        out.alpha_composite(frame, ((cell - frame.width) // 2, cell - frame.height))
        return out.resize((side, side), Image.NEAREST)

    frames, order = [], {}
    for direction, facing in FOLDERS.items():
        for role in ("idle", "walk", *ACTIONS):
            indices = []
            for frame in strips[facing][role]:
                indices.append(len(frames))
                frames.append(placed(frame))
            order[(role, direction)] = indices
    sheet = Image.new("RGBA", (side * len(frames), side), (0, 0, 0, 0))
    for index, image in enumerate(frames):
        sheet.paste(image, (index * side, 0))
    rects = [(i * side, 0, side, side) for i in range(len(frames))]
    feet = frames[0].getchannel("A").getbbox()[3] / side  # where the standing figure's feet are
    sheet_id = assets.sheet(key, _surface(sheet), rects, name, pivot=(0.5, feet))
    clips = {}
    for (role, direction), indices in order.items():
        if role == "idle":
            clips[f"idle_{direction}"] = (indices, 0.18, True)
        elif role == "walk":
            clips[f"walk_{direction}"] = (indices, 0.1, True)
        else:
            clips[f"{role}_{direction}"] = (indices, ACTIONS[role][1] / len(indices), False)
    return sheet_id, assets.clips(key, clips, name)


# -- tiles --------------------------------------------------------------------------------------
def _crop(sheet, col, row, w=1, h=1, size=16):
    return sheet.crop((col * size, row * size, (col + w) * size, (row + h) * size))


def _scaled(image, cells, size=16):
    """``image`` resized to ``cells`` x ``cells`` tiles, as a list of ``size`` px cell images."""
    from PIL import Image

    image = image.resize((cells * size, cells * size), Image.LANCZOS)
    return {(dx, dy): _surface(_crop(image, dx, dy)) for dy in range(cells) for dx in range(cells)}


def _tinted(image, rgb):
    from PIL import Image

    tint = Image.new("RGBA", image.size, (*rgb, 255))
    out = Image.new("RGBA", image.size, (0, 0, 0, 0))
    out.alpha_composite(image)
    shade = Image.blend(out, Image.composite(tint, out, out.getchannel("A")), 0.35)
    return shade


def _put(atlas, name, surface, *, solid=False):
    atlas.ids[name] = len(atlas.cells)
    atlas.cells.append(surface)
    if solid:
        atlas.solid.add(atlas.ids[name])


def _house(kind):
    """A 3 x 3 tile building from the Lucifer dungeon set: a red (or blue, or slate) roof, brick
    walls, a door, lit windows; the shop has an awning, the forge a glowing furnace window."""
    from PIL import Image, ImageDraw

    sheet = Image.open(DUNGEON).convert("RGBA")
    image = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    roof = _crop(sheet, 20, 12)
    if kind == "house2":
        roof = _tinted(roof, (70, 100, 190))
    elif kind == "forge":
        roof = _crop(sheet, 30, 14)
    for x in range(3):
        image.alpha_composite(roof, (x * 16, 0))
        for y in (1, 2):
            image.alpha_composite(_crop(sheet, 9 + x, y), (x * 16, y * 16))
    draw = ImageDraw.Draw(image)
    draw.line((0, 15, 47, 15), fill=(60, 14, 14, 255))  # the eaves' shadow
    draw.line((0, 0, 47, 0), fill=(150, 50, 50, 255) if kind != "forge" else (80, 70, 60, 255))
    draw.rectangle((19, 33, 28, 47), fill=(40, 24, 14, 255))  # the door
    draw.ellipse((19, 30, 28, 38), fill=(40, 24, 14, 255))
    draw.point((26, 41), fill=(222, 180, 70, 255))
    glow = (255, 150, 60, 255) if kind == "forge" else (255, 214, 120, 255)
    for x in (5, 36):  # windows
        draw.rectangle((x, 21, x + 6, 28), fill=glow, outline=(24, 16, 28, 255))
    if kind == "shop":
        for x in range(0, 48, 8):  # a striped awning over the wall
            draw.rectangle((x, 16, x + 3, 19), fill=(230, 220, 200, 255))
            draw.rectangle((x + 4, 16, x + 7, 19), fill=(170, 40, 40, 255))
    return {(dx, dy): _surface(_crop(image, dx, dy)) for dy in range(3) for dx in range(3)}


def overworld_atlas():
    """16 px tiles from the Lucifer exterior set: grass, cobbled paths, pines, rocks, crypts."""
    from PIL import Image

    sheet = Image.open(EXTERIOR).convert("RGBA")
    a = art.Atlas(16)

    def cell(col, row):
        return _surface(_crop(sheet, col, row))

    grass = [(5, 5), (11, 13), (13, 3), (13, 15)]
    for name, (c, r) in zip(("grass", "grass1", "grass2", "grass3"), grass, strict=True):
        _put(a, name, cell(c, r))
    for name, (c, r) in zip(
        ("grass_dark", "grass_dark1", "grass_dark2", "grass_dark3"), grass, strict=True
    ):
        _put(a, name, cell(c, r))
    path = [(57, 0), (41, 4), (43, 4), (53, 0)]
    for dy in range(3):  # a dirt patch: cobbles all over (no soft edge in the set)
        for dx in range(3):
            _put(a, f"dirt.{dx}.{dy}", cell(*path[(dx + dy * 3) % len(path)]))
    pine = sheet.crop((76 * 16, 2 * 16, 80 * 16, 6 * 16))
    for name in ("tree", "pine", "autumn"):
        shade = pine if name != "autumn" else _tinted(pine, (150, 90, 40))
        for (dx, dy), image in _scaled(shade, 2).items():
            _put(a, f"{name}.{dx}.{dy}", image)
    rocks = sheet.crop((70 * 16, 0, 72 * 16, 2 * 16))
    for (dx, dy), image in _scaled(rocks, 2).items():
        _put(a, f"boulder.{dx}.{dy}", image)
    for name, (c, r) in (
        ("bush", (70, 3)),
        ("bush2", (71, 3)),
        ("fern", (70, 4)),
        ("flower_y", (13, 3)),  # no flowers in the set: plain grass variants
        ("flower_s", (11, 13)),
        ("flower_r", (13, 15)),
        ("flower_w", (5, 5)),
        ("rock", (70, 2)),
        ("rock2", (71, 2)),
        ("stump", (58, 2)),
        ("log", (59, 2)),
    ):
        _put(a, name, cell(c, r))
    for name in ("house", "house2", "shop", "forge"):
        for (dx, dy), part in _house(name).items():
            _put(a, f"{name}.{dx}.{dy}", part)
    for dy in range(3):  # a tall grave cross
        for dx in range(2):
            _put(a, f"statue.{dx}.{dy}", cell(62 + dx, dy))
    for dy in range(2):  # a stretch of fence for the gate
        for dx in range(3):
            _put(a, f"torii.{dx}.{dy}", cell(60 + dx, 6 + dy))
    for name, (c, r) in (("barrel", (60, 2)), ("crate", (61, 2)), ("pot", (58, 3))):
        _put(a, name, cell(c, r))
    a.blocker()
    return a


def dungeon_atlas():
    """18 px tiles (Lucifer dungeon art enlarged from 16) for the side-view mine."""
    from PIL import Image

    sheet = Image.open(DUNGEON).convert("RGBA")
    a = art.Atlas(18)

    def cell(col, row):
        image = _crop(sheet, col, row).resize((18, 18), Image.NEAREST)
        return _surface(image)

    # the stone floor: left edge / middle / right edge of the light slabs, bricks below
    for name, (c, r) in (
        ("top_l", (0, 10)),
        ("top", (1, 10)),
        ("top_r", (3, 10)),
        ("dirt", (10, 1)),
        ("dirt2", (11, 1)),
        ("dirt3", (10, 2)),
        ("dirt4", (11, 2)),
        ("plank_l", (0, 9)),
        ("plank", (1, 9)),
        ("plank_r", (3, 9)),
        ("slab", (30, 14)),
        ("ladder", (18, 5)),
        ("ladder_top", (18, 4)),
        ("crate", (31, 14)),
        ("crate2", (32, 14)),
        ("spikes", (46, 8)),
        ("door_top", (6, 0)),
        ("door", (6, 1)),
        ("coin", (35, 4)),
        ("plant", (33, 4)),
        ("sprout", (34, 4)),
        ("mushroom", (36, 4)),
        ("sign", (40, 4)),
        ("key", (37, 4)),
    ):
        _put(a, name, cell(c, r))
    a.blocker()
    return a


def mine_backdrops(assets):
    """Two dark brick strips (Lucifer dungeon walls) for ``ParallaxBackground2D``."""
    from PIL import Image

    sheet = Image.open(DUNGEON).convert("RGBA")
    wall = _crop(sheet, 10, 1, 2, 2)

    def strip(key, tint, columns=8):
        image = Image.new("RGBA", (24 * columns, 48), (0, 0, 0, 255))
        tile = wall.resize((24, 24), Image.NEAREST)
        for i in range(columns):
            for r in range(2):
                image.alpha_composite(tile, (i * 24, r * 24))
        image = Image.blend(Image.new("RGBA", image.size, (*tint, 255)), image, 0.35)
        return assets.texture(key, _surface(image), key.replace("_", " ").title())

    return strip("mine_far", (30, 26, 44)), strip("mine_near", (18, 14, 28))


UI_SET_1 = lucifer.FREE_ASSETS / "Foozle_UI_0001_RPG_Set_1"


def gothic_ui(project, root):
    """Foozle's RPG UI Set 1 (CC0): the dark ornate panel frames the HUD and the host menus, and
    its coin, bag and chest paintings become item icons (shrunk to a pixel-friendly size)."""
    import dataclasses

    from PIL import Image

    from asteria.presentation.ui_skin import NinePatch

    folder = Path(root) / "playable_assets" / "lucifer" / "ui"
    folder.mkdir(parents=True, exist_ok=True)

    def shrink(name, out, divisor=None, side=None):
        image = Image.open(UI_SET_1 / name).convert("RGBA")
        if divisor:
            size = (max(1, image.width // divisor), max(1, image.height // divisor))
        else:
            size = (side, side)
        image.resize(size, Image.LANCZOS).save(folder / out)
        return f"playable_assets/lucifer/ui/{out}"

    panel = shrink("Panel_1.png", "panel_gothic.png", divisor=3)
    shrink("Panel_2.png", "panel_gothic_wide.png", divisor=4)
    icons = {
        "coin": shrink("Coin.png", "icon_coin.png", side=32),
        "coins": shrink("Coins.png", "icon_coins.png", side=32),
        "bag": shrink("bag.png", "icon_bag.png", side=32),
        "chest": shrink("Chest.png", "icon_chest.png", side=32),
    }
    library = project.battle_presentation_library
    for key in library.ids("ui_theme"):
        theme = library.require("ui_theme", key)
        skin = NinePatch(panel, 22, 22, 22, 22, 0.5)
        skins = tuple((role, patch) for role, patch in theme.panel_skins if role == "result")
        library.set(
            "ui_theme",
            key,
            dataclasses.replace(
                theme, panel_skins=(*skins, ("host:panel", skin), ("hud:*", skin))
            ),
        )
    return icons


def gear_icons(reskin, project, files):
    """One icon asset per piece of gear: a picture of the Lucifer equipment pack."""
    import dataclasses
    import shutil

    folder = Path(reskin.root) / reskin.icon_dir
    folder.mkdir(parents=True, exist_ok=True)
    db = project.rpg_database
    for item_id, source in files.items():
        if item_id not in db.equipment:
            continue
        if isinstance(source, tuple):  # drawn here: the Lucifer pack has no bow or wand
            weapon_icon(source[1]).save(folder / f"equip_{item_id}.png")
        else:
            shutil.copyfile(lucifer.EQUIPMENT / source, folder / f"equip_{item_id}.png")
        icon = reskin._icon_asset(f"icon.{item_id}", f"{reskin.icon_dir}/equip_{item_id}.png")
        db.equipment[item_id] = dataclasses.replace(db.equipment[item_id], icon_id=icon)


def weapon_icon(kind):
    """A 32 x 16 weapon picture in the pack's size, lying like its swords (blade to the right):
    ``bow``, ``longbow``, ``crossbow`` or ``wand``. Drawn here, outlined like the pack's own."""
    from PIL import Image, ImageDraw

    wood, light, steel = (116, 80, 48, 255), (176, 126, 74, 255), (196, 202, 212, 255)
    string, gold, gem = (214, 210, 190, 255), (222, 180, 70, 255), (150, 110, 255, 255)
    image = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if kind in ("bow", "longbow"):
        top, right = (0, 22) if kind == "longbow" else (1, 20)
        draw.arc((4, top, right + 6, 15 - top), -85, 85, fill=wood, width=2)
        draw.arc((5, top, right + 5, 15 - top), -80, 80, fill=light, width=1)
        draw.line((right - 4, top + 1, right - 4, 14 - top), fill=string)
        draw.line((6, 8, 29, 8), fill=wood)
        draw.polygon([(28, 6), (31, 8), (28, 10)], fill=steel)
    elif kind == "crossbow":
        draw.rectangle((3, 7, 24, 9), fill=wood)
        draw.line((3, 7, 24, 7), fill=light)
        draw.arc((16, 0, 30, 15), -90, 90, fill=wood, width=2)
        draw.line((23, 1, 23, 14), fill=string)
        draw.line((10, 8, 28, 8), fill=steel)
    else:  # wand
        draw.line((4, 12, 22, 5), fill=wood, width=2)
        draw.line((4, 11, 22, 4), fill=light)
        draw.ellipse((21, 1, 28, 8), fill=gem)
        draw.point((23, 3), fill=(255, 255, 255, 255))
        draw.point((27, 1), fill=gold)
    mask = image.getchannel("A")
    outline = Image.new("RGBA", image.size, (0, 0, 0, 0))
    dark = Image.new("RGBA", image.size, (24, 16, 28, 255))
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        shifted = Image.new("L", image.size, 0)
        shifted.paste(mask, (dx, dy))
        outline.paste(dark, (0, 0), shifted)
    outline.alpha_composite(image)
    return outline


def arrow(assets):
    """An arrow flying to the right (drawn here: shaft, steel head, red fletching)."""
    pg = art.pygame
    image = pg.Surface((16, 5), pg.SRCALPHA)
    pg.draw.line(image, (120, 84, 52), (2, 2), (12, 2))
    pg.draw.polygon(image, (190, 196, 205), [(11, 0), (15, 2), (11, 4)])
    pg.draw.polygon(image, (200, 50, 50), [(0, 0), (3, 2), (0, 4)])
    return assets.sheet("arrow", image, [(0, 0, 16, 5)], "Arrow")


def node_icons(reskin, project):
    """A class icon for every skill-tree node that grants no ability (passives, keystones)."""
    pools = {group: lucifer._skill_pool(group) for group in lucifer.SKILL_ICON_GROUPS}
    folder = Path(reskin.root) / reskin.icon_dir
    folder.mkdir(parents=True, exist_ok=True)

    def copy(source, name):
        import shutil

        shutil.copyfile(source, folder / name)
        return f"{reskin.icon_dir}/{name}"

    lucifer._node_icons(project.rpg_database, pools, copy)


# -- spell and strike effects (Foozle Pixel Magic Effects, CC0) ---------------------------------
EFFECTS_PACK = lucifer.FREE_ASSETS / "Foozle_2DE0001_Pixel_Magic_Effects"
# name: (folder, tint or None); a tint recolours the picture (white = bright, dark stays dark)
EFFECTS = {
    "fire_ball": ("Fire_Ball", None),
    "explosion": ("Explosion", None),
    "spear": ("Molten_Spear", None),
    "water": ("Water", None),
    "geyser": ("Water_Geyser", None),
    "wind": ("Wind", None),
    "tornado": ("Tornado", None),
    "spike": ("Earth_Spike", None),
    "rocks": ("Rocks", None),
    "portal": ("Portal", None),
    "ice_bolt": ("Water", ((20, 40, 90), (235, 250, 255))),
    "ice_burst": ("Explosion", ((10, 40, 100), (200, 240, 255))),
    "bolt_ball": ("Fire_Ball", ((40, 30, 110), (255, 250, 150))),
    "bolt_strike": ("Molten_Spear", ((60, 50, 120), (255, 255, 170))),
    "bolt_burst": ("Explosion", ((60, 50, 130), (255, 255, 180))),
    "spark_arc": ("Wind", ((90, 70, 10), (255, 245, 120))),
    "ember_arc": ("Wind", ((120, 30, 10), (255, 190, 90))),
    "poison_cloud": ("Tornado", ((10, 60, 20), (170, 255, 120))),
    "poison_burst": ("Explosion", ((10, 70, 20), (170, 255, 110))),
    "gold_burst": ("Explosion", ((110, 70, 0), (255, 235, 140))),
    "blood_arc": ("Wind", ((90, 0, 10), (255, 90, 90))),
    "shadow_portal": ("Portal", ((20, 10, 50), (190, 150, 255))),
}


def _effect_frames(folder, tint):
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


def effect_sheets(assets):
    """One sprite sheet per effect (a strip of its frames): ``{name: sheet id}``."""
    from PIL import Image

    sheets = {}
    for name, (folder, tint) in EFFECTS.items():
        frames = _effect_frames(folder, tint)
        side = frames[0].width
        strip = Image.new("RGBA", (side * len(frames), side), (0, 0, 0, 0))
        for index, frame in enumerate(frames):
            strip.paste(frame, (index * side, 0))
        rects = [(i * side, 0, side, side) for i in range(len(frames))]
        sheets[name] = assets.sheet(f"fx_{name}", _surface(strip), rects, name, pivot=(0.5, 0.5))
    return sheets
