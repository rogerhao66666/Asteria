"""Art for the ARPG demo: CC0 sprites and tiles cut from Ninja Adventure and Kenney Pixel
Platformer, written as ordinary project assets (texture, sprite sheet, animation set, tileset).

Nothing here is engine code. Every sheet becomes a canonical asset record, so the editor, the
runtime and any other game read them the same way.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

from asteria.assets.types import AssetRecord  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FREE = REPO / "local_reference" / "free_assets"
NINJA = FREE / "ninja_adventure" / "extracted" / "Ninja Adventure - Asset Pack"
KENNEY = FREE / "kenney_pixel-platformer" / "extracted"
OUT = "playable_assets"
DIRECTIONS = ("down", "up", "left", "right")  # Ninja Adventure sheet column order


def asset_id(*parts):
    return str(uuid5(NAMESPACE_URL, "asteria-arpg-demo:" + ":".join(map(str, parts))))


class Assets:
    """Writes images and JSON under ``playable_assets`` and registers their asset records."""

    def __init__(self, project, root=HERE):
        pygame.init()
        self.project = project
        self.root = Path(root)
        self.ids = {}

    def _add(self, key, kind, relative, name):
        record = AssetRecord(
            asset_id(key, kind),
            kind,
            f"{OUT}/{relative}",
            name,
            "arpg_demo",
            1,
            {},
            {"source": "reference_projects/arpg_demo/build_project.py"},
        )
        self.project.assets.add(record)
        self.ids[(key, kind)] = record.id
        return record.id

    def _json(self, relative, data):
        path = self.root / OUT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def texture(self, key, surface, name):
        relative = f"{key}.png"
        path = self.root / OUT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(surface, str(path))
        return self._add(key, "texture", relative, name)

    def sheet(self, key, surface, frames, name, pivot=(0.5, 0.5)):
        """``frames``: ``(x, y, w, h)`` rectangles; returns the sprite sheet id."""
        texture = self.texture(key, surface, name)
        data = {
            "texture_asset_id": texture,
            "frames": [
                {"x": x, "y": y, "width": w, "height": h, "pivot_x": pivot[0], "pivot_y": pivot[1]}
                for x, y, w, h in frames
            ],
        }
        self._json(f"{key}_sheet.json", data)
        return self._add(key, "sprite_sheet", f"{key}_sheet.json", f"{name} Sheet")

    def clips(self, key, clips, name):
        """``clips``: ``{name: ([frame, ...], seconds per frame, loop)}``; returns the set id."""
        data = {
            "clips": {
                clip: {
                    "keyframes": [{"frame_index": f, "duration": step} for f in frames],
                    "loop": loop,
                }
                for clip, (frames, step, loop) in clips.items()
            }
        }
        self._json(f"{key}_clips.json", data)
        return self._add(key, "animation", f"{key}_clips.json", f"{name} Animations")

    def tileset(self, key, surface, size, count, name, solid=()):
        """A tileset over a one-row-per-16-tiles atlas; ``solid`` tile ids block."""
        columns = surface.get_width() // size
        frames = [((i % columns) * size, (i // columns) * size, size, size) for i in range(count)]
        sheet = self.sheet(key, surface, frames, name, pivot=(0.0, 0.0))
        tiles = {
            str(i): {
                "frame_index": i,
                "collision": "solid" if i in solid else "none",
                "terrain": None,
                "tags": [],
            }
            for i in range(count)
        }
        self._json(
            f"{key}_tileset.json",
            {
                "sprite_sheet_asset_id": sheet,
                "tile_width": size,
                "tile_height": size,
                "tiles": tiles,
            },
        )
        return self._add(key, "tileset", f"{key}_tileset.json", f"{name} Tileset")

    def tilemap(self, key, data, name):
        self._json(f"{key}_map.json", data)
        return self._add(key, "tilemap", f"{key}_map.json", f"{name} Map")


def load(path):
    return pygame.image.load(str(path))


# -- characters -----------------------------------------------------------------------------------
def ninja_character(assets, key, folder, name):
    """A Ninja Adventure character (16 px, columns down/up/left/right; rows 0-3 walk, row 4
    attack): sheet + idle / walk / attack clips for the four facings."""
    image = load(NINJA / "Actor" / "Character" / folder / "SpriteSheet.png")
    frames = [(c * 16, r * 16, 16, 16) for r in range(7) for c in range(4)]
    sheet = assets.sheet(key, image, frames, name)
    clips = {}
    for col, d in enumerate(DIRECTIONS):
        clips[f"idle_{d}"] = ([col], 1.0, True)
        clips[f"walk_{d}"] = ([r * 4 + col for r in range(4)], 0.12, True)
        clips[f"attack_{d}"] = ([4 * 4 + col], 0.3, False)
    return sheet, assets.clips(key, clips, name)


def ninja_monster(assets, key, relative, name):
    """A Ninja Adventure monster (64 x 64: four 16 px columns of facings, four walk rows)."""
    image = load(NINJA / "Actor" / "Monster" / relative)
    frames = [(c * 16, r * 16, 16, 16) for r in range(4) for c in range(4)]
    sheet = assets.sheet(key, image, frames, name)
    clips = {}
    for col, d in enumerate(DIRECTIONS):
        clips[f"idle_{d}"] = ([col, 4 + col], 0.35, True)
        clips[f"walk_{d}"] = ([r * 4 + col for r in range(4)], 0.14, True)
    return sheet, assets.clips(key, clips, name)


def ninja_boss(assets, key, folder, name, size=50):
    """A front-facing Ninja Adventure boss strip (Walk.png + Idle.png): the same frames serve
    every facing."""
    walk = load(NINJA / "Actor" / "Boss" / folder / "Walk.png")
    idle = load(NINJA / "Actor" / "Boss" / folder / "Idle.png")
    nw, ni = walk.get_width() // size, idle.get_width() // size
    strip = pygame.Surface(((nw + ni) * size, size), pygame.SRCALPHA)
    strip.blit(walk, (0, 0))
    strip.blit(idle, (nw * size, 0))
    frames = [(i * size, 0, size, size) for i in range(nw + ni)]
    sheet = assets.sheet(key, strip, frames, name)
    clips = {}
    for d in DIRECTIONS:
        clips[f"walk_{d}"] = (list(range(nw)), 0.12, True)
        clips[f"idle_{d}"] = (list(range(nw, nw + ni)), 0.16, True)
    return sheet, assets.clips(key, clips, name)


def kenney_character(assets, key, cells, name, scale=1):
    """Kenney Pixel Platformer characters (24 px): ``cells`` are two (col, row) walk frames.
    The art faces left; flipped copies face right. ``scale`` enlarges it (a boss)."""
    source = load(KENNEY / "Tilemap" / "tilemap-characters_packed.png")
    size = 24 * scale
    strip = pygame.Surface((size * 4, size), pygame.SRCALPHA)
    for i, (c, r) in enumerate(cells):
        frame = source.subsurface((c * 24, r * 24, 24, 24))
        frame = pygame.transform.scale(frame, (size, size))
        strip.blit(frame, (i * size, 0))
        strip.blit(pygame.transform.flip(frame, True, False), ((2 + i) * size, 0))
    frames = [(i * size, 0, size, size) for i in range(4)]
    sheet = assets.sheet(key, strip, frames, name)
    left, right = [0, 1], [2, 3]
    clips = {}
    for d in DIRECTIONS:
        frames_d = right if d == "right" else left
        clips[f"walk_{d}"] = (frames_d, 0.16, True)
        clips[f"idle_{d}"] = (frames_d, 0.45, True)
    return sheet, assets.clips(key, clips, name)


def item_icon(assets, key, relative, name, size=None, scale=1):
    """The first ``size`` (w, h) frame of an image (a projectile, an effect), optionally enlarged,
    as a one-frame sheet. Projectiles are drawn pointing right."""
    image = load(NINJA / relative)
    w, h = size or image.get_size()
    frame = image.subsurface((0, 0, w, h))
    if scale != 1:
        frame = pygame.transform.scale(frame, (w * scale, h * scale))
    return assets.sheet(key, frame, [(0, 0, w * scale, h * scale)], name)


def title_image(root, layout, atlas, size=(960, 540), zoom=3):
    """A title backdrop: the middle of a map's visible layers, scaled up."""
    grid, tile = layout["grid"], layout["size"]
    w, h = size[0] // zoom, size[1] // zoom
    x0 = (grid.width * tile - w) // 2
    y0 = (grid.height * tile - h) // 2
    picture = pygame.Surface((w, h), pygame.SRCALPHA)
    for layer in ("ground", "decor", "objects", "above"):
        for (x, y), tile_id in grid.layers[layer].items():
            picture.blit(atlas.cells[tile_id], (x * tile - x0, y * tile - y0))
    path = Path(root) / OUT / "title.png"
    pygame.image.save(pygame.transform.scale(picture, size), str(path))
    return path


def mine_backdrops(assets):
    """Two cave-silhouette strips from Kenney's background tiles, tinted dark: ``(far, near)``
    texture asset ids for ``ParallaxBackground2D``."""
    source = load(KENNEY / "Tilemap" / "tilemap-backgrounds_packed.png")

    def strip(key, tint, columns=8):
        # the hill row and the fill below it (the flat sky row is left out: the scene has its own)
        tiles = [source.subsurface((c * 24, r * 24, 24, 24)) for c in (4, 5) for r in (1, 2)]
        image = pygame.Surface((24 * columns, 48), pygame.SRCALPHA)
        for i in range(columns):
            col = i % 2
            for r in range(2):
                image.blit(tiles[col * 2 + r], (i * 24, r * 24))
        shade = pygame.Surface(image.get_size(), pygame.SRCALPHA)
        shade.fill((*tint, 255))
        image.blit(shade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return assets.texture(key, image, key.replace("_", " ").title())

    return strip("mine_far", (70, 60, 100)), strip("mine_near", (40, 34, 60))


# -- item icons -----------------------------------------------------------------------------------
TINY = FREE / "kenney_tiny-dungeon" / "extracted" / "Tilemap" / "tilemap_packed.png"
ICON_SOURCES = {  # equipment / item id -> ("tiny", col, row) | ("ninja", relative path)
    "short_sword": ("tiny", 8, 8),
    "war_axe": ("tiny", 10, 9),
    "hunting_bow": ("ninja", "Items/Weapons/Bow/Sprite.png"),
    "oak_staff": ("tiny", 10, 10),
    "leather_vest": ("tiny", 5, 8),
    "chain_mail": ("tiny", 6, 8),
    "cloth_robe": ("ninja", "Items/Scroll/ScrollIce.png"),
    "iron_helm": ("tiny", 0, 8),
    "copper_ring": ("ninja", "Items/Resource/GemYellow.png"),
    "wanderer_hood": ("tiny", 3, 8),
    "wanderer_coat": ("ninja", "Items/Scroll/ScrollPlant.png"),
    "wanderer_band": ("ninja", "Items/Resource/GemGreen.png"),
    "cyclops_eye": ("ninja", "Items/Resource/GemPurple.png"),
    "gelatin_aegis": ("ninja", "Items/Scroll/ScrollRock.png"),
    "golem_heart": ("ninja", "Items/Resource/GemRed.png"),
    "potion": ("tiny", 7, 9),
    "slime_gel": ("ninja", "Items/Resource/Water.png"),
    "bone_shard": ("ninja", "Items/Resource/Rock.png"),
    "eye_lens": ("ninja", "Items/Resource/GemGreen.png"),
    "gear_scrap": ("ninja", "Items/Resource/BarIron.png"),
    # abilities (action bar) and states (status row)
    "punch": ("ninja", "Items/Weapons/Club/Sprite.png"),
    "w_slash": ("tiny", 8, 8),
    "w_whirl": ("ninja", "Items/Weapons/Axe/Sprite.png"),
    "w_leap": ("ninja", "Items/Weapons/Lance/Sprite.png"),
    "w_shout": ("ninja", "Items/Scroll/ScrollRock.png"),
    "r_shot": ("ninja", "Items/Weapons/Bow/Sprite.png"),
    "r_volley": ("ninja", "Items/Weapons/Bow2/Sprite.png"),
    "r_pierce": ("ninja", "Items/Weapons/Rapier/Sprite.png"),
    "r_tumble": ("ninja", "Items/Resource/feather.png"),
    "m_bolt": ("ninja", "Items/Weapons/MagicWand/Sprite.png"),
    "m_nova": ("ninja", "Items/Scroll/ScrollIce.png"),
    "m_meteor": ("ninja", "Items/Scroll/ScrollFire.png"),
    "m_blink": ("ninja", "Items/Scroll/ScrollThunder.png"),
    "roll": ("ninja", "Items/Action/Interact.png"),
    "state_healing": ("ninja", "Items/Potion/Heart.png"),
    "state_war_cry": ("ninja", "Items/Weapons/Katana/Sprite.png"),
    "state_burning": ("ninja", "Items/Scroll/ScrollFire.png"),
    "state_bleeding": ("ninja", "Items/Resource/GemRed.png"),
    "state_chilled": ("ninja", "Items/Scroll/ScrollIce.png"),
}


def write_item_icons(root=HERE):
    """One 16 px PNG per item under ``playable_assets/icons`` (cut from CC0 sheets); returns
    ``{item id: relative path}`` for ``icon_id``."""
    folder = Path(root) / OUT / "icons"
    folder.mkdir(parents=True, exist_ok=True)
    tiny = load(TINY)
    paths = {}
    for item_id, source in ICON_SOURCES.items():
        if source[0] == "tiny":
            image = tiny.subsurface((source[1] * 16, source[2] * 16, 16, 16)).copy()
        else:
            image = load(NINJA / source[1]).copy()
        pygame.image.save(image, str(folder / f"{item_id}.png"))
        paths[item_id] = f"{OUT}/icons/{item_id}.png"
    return paths


# -- tiles ----------------------------------------------------------------------------------------
TILESETS = NINJA / "Backgrounds" / "Tilesets"


class Atlas:
    """Builds a tileset atlas from named source cells; ``ids[name]`` is the tile id."""

    def __init__(self, size, columns=16):
        self.size, self.columns = size, columns
        self.cells, self.ids, self.solid = [], {}, set()
        self._sources = {}

    def _source(self, path):
        if path not in self._sources:
            self._sources[path] = load(path)
        return self._sources[path]

    def add(self, name, path, col, row, *, solid=False, gap=0):
        step = self.size + gap
        image = self._source(path).subsurface((col * step, row * step, self.size, self.size))
        self.ids[name] = len(self.cells)
        self.cells.append(image)
        if solid:
            self.solid.add(self.ids[name])
        return self.ids[name]

    def block(self, name, path, col, row, w, h, *, solid=False):
        """A ``w`` x ``h`` group of cells named ``name.<dx>.<dy>``."""
        for dy in range(h):
            for dx in range(w):
                self.add(f"{name}.{dx}.{dy}", path, col + dx, row + dy, solid=solid)

    def blocker(self):
        """An invisible solid tile for collision layers."""
        self.ids["block"] = len(self.cells)
        self.cells.append(pygame.Surface((self.size, self.size), pygame.SRCALPHA))
        self.solid.add(self.ids["block"])
        return self.ids["block"]

    def surface(self):
        rows = -(-len(self.cells) // self.columns)
        atlas = pygame.Surface((self.columns * self.size, rows * self.size), pygame.SRCALPHA)
        for i, cell in enumerate(self.cells):
            atlas.blit(cell, ((i % self.columns) * self.size, (i // self.columns) * self.size))
        return atlas


def overworld_atlas():
    """16 px top-down tiles: grass, dirt paths, trees, rocks, flowers, houses."""
    floor, nature, house = (
        TILESETS / "TilesetFloor.png",
        TILESETS / "TilesetNature.png",
        TILESETS / "TilesetHouse.png",
    )
    a = Atlas(16)
    a.add("grass", floor, 0, 12)
    for i in (1, 2, 3):
        a.add(f"grass{i}", floor, i, 12)
    a.add("grass_dark", floor, 11, 12)
    for i in (12, 13, 14):
        a.add(f"grass_dark{i - 11}", floor, i, 12)
    a.block("dirt", floor, 0, 7, 3, 3)  # a dirt patch in grass: corners, edges, centre
    a.block("tree", nature, 0, 0, 2, 2)
    a.block("pine", nature, 2, 0, 2, 2)
    a.block("autumn", nature, 18, 0, 2, 2)
    a.block("boulder", nature, 16, 14, 2, 2)
    for name, col, row in (
        ("bush", 0, 10),
        ("bush2", 1, 10),
        ("fern", 4, 10),
        ("flower_y", 0, 11),
        ("flower_s", 1, 11),
        ("flower_r", 3, 11),
        ("flower_w", 6, 11),
        ("rock", 17, 17),
        ("rock2", 18, 17),
        ("stump", 4, 8),
        ("log", 5, 8),
    ):
        a.add(name, nature, col, row)
    a.block("house", house, 0, 0, 3, 3)
    a.block("house2", house, 8, 0, 3, 3)
    a.block("shop", house, 16, 0, 3, 3)
    a.block("forge", house, 19, 0, 3, 3)
    a.block("statue", house, 1, 15, 2, 3)
    a.block("torii", house, 1, 5, 3, 2)
    for name, col, row in (("barrel", 14, 15), ("crate", 16, 15), ("pot", 17, 15)):
        a.add(name, house, col, row)
    a.blocker()
    return a


def dungeon_atlas():
    """18 px Kenney Pixel Platformer tiles for the side-view dungeon."""
    sheet = KENNEY / "Tilemap" / "tilemap_packed.png"
    a = Atlas(18)
    # Kenney groups ground as left edge / middle / right edge columns (1, 2, 3); 0 is a lone block
    a.add("top_l", sheet, 1, 2)
    a.add("top", sheet, 2, 2)
    a.add("top_r", sheet, 3, 2)
    a.add("dirt", sheet, 4, 0)  # plain fill (no outline)
    a.add("dirt2", sheet, 5, 0)
    a.add("dirt3", sheet, 4, 1)
    a.add("dirt4", sheet, 5, 1)
    a.add("plank_l", sheet, 8, 2)
    a.add("plank", sheet, 9, 2)
    a.add("plank_r", sheet, 10, 2)
    a.add("slab", sheet, 6, 7)
    a.add("ladder", sheet, 11, 3)
    a.add("ladder_top", sheet, 11, 2)
    a.add("crate", sheet, 6, 0)
    a.add("crate2", sheet, 6, 1)
    a.add("spikes", sheet, 8, 3)
    a.add("door_top", sheet, 10, 6)
    a.add("door", sheet, 10, 7)
    a.add("coin", sheet, 11, 7)
    a.add("plant", sheet, 4, 6)
    a.add("sprout", sheet, 5, 6)
    a.add("mushroom", sheet, 8, 6)
    a.add("sign", sheet, 5, 4)
    a.add("key", sheet, 7, 1)
    a.blocker()
    return a


def write_credits(root=HERE):
    text = """# Art credits (all CC0 1.0 - public domain)

* **Ninja Adventure** by Pixel-boy and AAA - characters, monsters, bosses, top-down tiles,
  item icons. https://pixel-boy.itch.io/ninja-adventure-asset-pack
* **Pixel Platformer** by Kenney (www.kenney.nl) - side-view tiles and dungeon enemies.
  https://kenney.nl/assets/pixel-platformer
* **Tiny Dungeon** by Kenney (www.kenney.nl) - weapon, shield and potion icons.
  https://kenney.nl/assets/tiny-dungeon

The images in this folder are cut from those packs by `build_project.py` (cropped, recoloured
only by flipping, combined into sheets). No AI-generated art.
"""
    path = Path(root) / OUT / "CREDITS.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


__all__ = [
    "Assets",
    "Atlas",
    "dungeon_atlas",
    "item_icon",
    "kenney_character",
    "mine_backdrops",
    "ninja_boss",
    "ninja_character",
    "ninja_monster",
    "overworld_atlas",
    "title_image",
    "write_item_icons",
    "write_credits",
]
