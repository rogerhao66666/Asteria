"""Art plumbing for the ARPG demo: writes sprites and tiles (cut from Foozle's Lucifer packs by
``lucifer_art.py``) as ordinary project assets (texture, sprite sheet, animation set, tileset).

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
OUT = "playable_assets"
DIRECTIONS = ("down", "up", "left", "right")


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

    def sheet(self, key, surface, frames, name, pivot=(0.5, 0.5), pivots=None):
        """``frames``: ``(x, y, w, h)`` rectangles; ``pivots``, when given, one ``(x, y)`` per
        frame in place of the one ``pivot``; returns the sprite sheet id."""
        texture = self.texture(key, surface, name)
        pivots = pivots or [pivot] * len(frames)
        data = {
            "texture_asset_id": texture,
            "frames": [
                {"x": x, "y": y, "width": w, "height": h, "pivot_x": px, "pivot_y": py}
                for (x, y, w, h), (px, py) in zip(frames, pivots)
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


# -- tiles ----------------------------------------------------------------------------------------
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


def write_credits(root=HERE):
    text = """# Art credits (all CC0 1.0 - public domain)

* **Lucifer packs** by Foozle (commissioned from Baldur) - every character, monster and boss
  (Warrior, Sorceress, Necromancer, Cultist, Goblins, Skeletons), the exterior and dungeon
  tiles, the equipment, pickup and skill icons, the RPG UI panels and pixel font.
* **Pixel Magic Effects** and **RPG UI Set 1** by Foozle - spell and strike effects, the
  ornate panels and the coin, bag and chest paintings. https://foozlecc.itch.io/

The arrow is drawn by `lucifer_art.py`. The other images in this folder are cut from those packs
by `build_project.py` (cropped, scaled, combined into sheets). No AI-generated art.
"""
    path = Path(root) / OUT / "CREDITS.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


__all__ = [
    "Assets",
    "Atlas",
    "title_image",
    "write_credits",
]
