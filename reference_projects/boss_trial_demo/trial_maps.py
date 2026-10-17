"""Maps of the Boss Trial: tile scenes built from Foozle's Lucifer tilesets (CC0).

Each map is a tile scene: ground, decoration and object layers plus a hidden collision layer, with
the player, NPCs, enemies in view and doors as entities. Everything here is ordinary project data
(assets, tile maps, scenes, event programs), so the editor opens and edits it like any other.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import trial_lucifer as lucifer

from asteria.assets.types import AssetRecord, AssetRef
from asteria.core import Entity, Scene, Transform
from asteria.events import EventProgram
from asteria.events.binding import EventBinding, SceneEventBindings
from asteria.events.program import EventInstruction
from asteria.graphics import EMPTY_TILE, TileChunk, TileLayer, TileMap
from asteria.graphics.serialization import tilemap_to_data

CHUNK = 16
ORDERS = {"ground": 0, "decor": 10, "objects": 50, "above": 150, "collision": 500}
DIRECTIONS = ("down", "up", "left", "right")
OUT = "playable_assets/lucifer/world"


def asset_id(*parts):
    return str(uuid5(NAMESPACE_URL, "asteria-boss-trial:" + ":".join(map(str, parts))))


class Assets:
    """Writes images and JSON under ``playable_assets/lucifer/world`` and registers records."""

    def __init__(self, project, root):
        self.project, self.root = project, Path(root)

    def _add(self, key, kind, relative, name):
        record = AssetRecord(
            asset_id(key, kind),
            kind,
            f"{OUT}/{relative}",
            name,
            "boss_trial_demo",
            1,
            {},
            {"source": "reference_projects/boss_trial_demo/trial_maps.py", "license": "CC0 1.0"},
        )
        self.project.assets.add(record)
        return record.id

    def _json(self, relative, data):
        path = self.root / OUT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def texture(self, key, image, name):
        path = self.root / OUT / f"{key}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
        return self._add(key, "texture", f"{key}.png", name)

    def sheet(self, key, image, frames, name, pivot=(0.5, 1.0)):
        texture = self.texture(key, image, name)
        self._json(
            f"{key}_sheet.json",
            {
                "texture_asset_id": texture,
                "frames": [
                    {
                        "x": x,
                        "y": y,
                        "width": w,
                        "height": h,
                        "pivot_x": pivot[0],
                        "pivot_y": pivot[1],
                    }
                    for x, y, w, h in frames
                ],
            },
        )
        return self._add(key, "sprite_sheet", f"{key}_sheet.json", f"{name} Sheet")

    def clips(self, key, clips, name):
        self._json(
            f"{key}_clips.json",
            {
                "clips": {
                    clip: {
                        "keyframes": [{"frame_index": f, "duration": step} for f in frames],
                        "loop": loop,
                    }
                    for clip, (frames, step, loop) in clips.items()
                }
            },
        )
        return self._add(key, "animation", f"{key}_clips.json", f"{name} Animations")

    def tileset(self, key, image, size, name, solid=()):
        columns = image.width // size
        count = columns * (image.height // size)
        frames = [((i % columns) * size, (i // columns) * size, size, size) for i in range(count)]
        sheet = self.sheet(key, image, frames, name, pivot=(0.0, 0.0))
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
        return self._add(key, "tileset", f"{key}_tileset.json", f"{name} Tileset"), columns

    def tilemap(self, key, data, name):
        self._json(f"{key}_map.json", data)
        return self._add(key, "tilemap", f"{key}_map.json", f"{name} Map")


class Grid:
    """Layers of tile ids being painted; ``data`` gives the TileMap data."""

    def __init__(self, columns, width, height, seed):
        self.columns, self.width, self.height = columns, width, height
        self.rng = random.Random(seed)
        self.layers = {name: {} for name in ORDERS}

    def tile(self, col, row):
        return row * self.columns + col

    def put(self, layer, x, y, tile):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.layers[layer][(x, y)] = tile

    def fill(self, layer, x0, y0, x1, y1, tiles, weights=None):
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.put(layer, x, y, self.rng.choices(tiles, weights)[0])

    def block(self, x0, y0, x1, y1):
        """Walls: tiles that stop the player (the hidden collision layer)."""
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.put("collision", x, y, 1)

    def stamp(self, layer, x, y, col, row, w, h, *, solid_rows=()):
        """Copy a w x h block of tileset tiles whose top-left is (col, row) to (x, y)."""
        for dy in range(h):
            for dx in range(w):
                self.put(layer, x + dx, y + dy, self.tile(col + dx, row + dy))
                if dy in solid_rows:
                    self.put("collision", x + dx, y + dy, 1)

    def data(self, tileset_id, size):
        layers = []
        for name, order in ORDERS.items():
            layer = TileLayer(
                name.capitalize(), order, name != "collision", 1.0, name == "collision"
            )
            for (x, y), tile_id in self.layers[name].items():
                if tile_id == EMPTY_TILE:
                    continue
                key = (x // CHUNK, y // CHUNK)
                chunk = layer.chunks.get(key)
                if chunk is None:
                    chunk = layer.chunks[key] = TileChunk.empty(key[0], key[1], CHUNK, CHUNK)
                chunk.set(x % CHUNK, y % CHUNK, tile_id)
            layers.append(layer)
        tilemap = TileMap(AssetRef(tileset_id, "tileset"), size, size, CHUNK, CHUNK, layers)
        tilemap.validate()
        return tilemap_to_data(tilemap)


def character(assets, key, lucifer_key, name):
    """A Lucifer character for the field: idle and walk clips for the four facings."""
    from PIL import Image

    strips = {}
    for facing, folder in (("down", "Down"), ("up", "Up"), ("left", "Left"), ("right", "Right")):
        idle = lucifer._facing_strip(lucifer_key, folder, "Idle")
        walk = lucifer._facing_strip(lucifer_key, folder, "Walk") or lucifer._facing_strip(
            lucifer_key, folder, "Run"
        )
        strips[facing] = (idle, walk or idle)
    cell = max(f.width for pair in strips.values() for frames in pair for f in frames)
    frames, clips, images = [], {}, []
    for facing in DIRECTIONS:
        idle, walk = strips[facing]
        start = len(images)
        images.extend(idle)
        clips[f"idle_{facing}"] = (list(range(start, start + len(idle))), 0.2, True)
        start = len(images)
        images.extend(walk)
        clips[f"walk_{facing}"] = (list(range(start, start + len(walk))), 0.1, True)
    sheet = Image.new("RGBA", (cell * len(images), cell), (0, 0, 0, 0))
    for index, image in enumerate(images):
        sheet.paste(image, (index * cell + (cell - image.width) // 2, cell - image.height))
        frames.append((index * cell, 0, cell, cell))
    return assets.sheet(key, sheet, frames, name), assets.clips(key, clips, name)


# -- scenes ---------------------------------------------------------------------------------------
from asteria.runtime.collision import Collider2DComponent  # noqa: E402
from asteria.runtime.components2d import (  # noqa: E402
    Animator2DComponent,
    Camera2DComponent,
    Interaction2DComponent,
    SpriteRenderer2D,
    TileMap2DComponent,
)
from asteria.runtime.field_ai import VisibleEncounterComponent  # noqa: E402


def _set(component, **fields):
    for key, value in fields.items():
        current = getattr(component, key, None)
        if isinstance(current, float) and isinstance(value, int) and not isinstance(value, bool):
            value = float(value)
        setattr(component, key, value)
    return component


def say(speaker, text):
    return EventInstruction("DIALOGUE", {"speaker": speaker, "text": text})


def world(command, **args):
    return EventInstruction("WORLD", {"command": command, "args": args})


class SceneBuilder:
    def __init__(self, project, key, name):
        self.project, self.key = project, key
        self.scene = Scene(name, scene_id=asset_id("scene", key))
        self.programs = SceneEventBindings()
        project.add_scene(self.scene)

    def entity(self, name, x, y):
        entity = Entity(name, entity_id=asset_id("entity", self.key, name))
        entity.add_component(Transform(x, y))
        return self.scene.add_entity(entity)

    def look(self, entity, sheet, clips):
        entity.add_component(_set(SpriteRenderer2D(), sprite_sheet_asset_id=sheet))
        entity.add_component(_set(Animator2DComponent(), clip_set_id=clips))

    def setup(self, tilemap, zoom=3.0):
        holder = self.entity("Map", -40, -8)
        holder.add_component(_set(TileMap2DComponent(), tilemap_asset_id=tilemap))
        camera = self.entity("Camera", -40, 24)
        camera.add_component(_set(Camera2DComponent(), width=320, height=180, zoom=zoom))

    def program(self, entity, program_id, instructions, *, trigger="action", radius=24.0):
        self.project.event_programs.register(
            program_id, EventProgram((*instructions, EventInstruction("END")), name=program_id)
        )
        self.programs.add(
            EventBinding(f"{program_id}.binding", entity.id, program_id, local_scope_id=program_id)
        )
        entity.add_component(
            _set(
                Interaction2DComponent(),
                event_binding_id=f"{program_id}.binding",
                event_program_id=program_id,
                local_scope_id=program_id,
                range=radius,
                require_facing=trigger == "action",
                trigger=trigger,
            )
        )

    def npc(self, name, xy, look, *, solid=True):
        entity = self.entity(name, *xy)
        self.look(entity, *look)
        if solid:
            entity.add_component(_set(Collider2DComponent(), width=10, height=8))
        return entity

    def door(self, name, xy, to_scene, to_xy, facing, weather=None, music=None):
        entity = self.entity(name, *xy)
        arrive = [] if weather is None else [world("SET_BATTLE_WEATHER", kind=weather)]
        if music:
            arrive.append(world("PLAY_BGM", asset_id=music, fade=0.6))
        self.program(
            entity,
            f"door.{self.key}.{name.lower().replace(' ', '_')}",
            [*arrive, world("TRANSFER", scene_id=to_scene, x=to_xy[0], y=to_xy[1], facing=facing)],
            trigger="touch",
            radius=14.0,
        )
        return entity

    def foe(self, name, xy, look, encounter_id, radius=14.0):
        entity = self.entity(name, *xy)
        self.look(entity, *look)
        entity.add_component(
            _set(VisibleEncounterComponent(), encounter_id=encounter_id, touch_radius=radius)
        )
        return entity

    def find_entity(self, name):
        return next(e for e in self.scene.entities() if e.name == name)

    def finish(self):
        self.project.scene_event_bindings[self.scene.id] = self.programs


# -- the tilesets: which tile of a Lucifer sheet is what ----------------------------------------
def _with_block_row(image, size=16):
    """The tileset sheet plus one empty row whose first tile is the invisible wall tile."""
    from PIL import Image

    out = Image.new("RGBA", (image.width, image.height + size), (0, 0, 0, 0))
    out.alpha_composite(image, (0, 0))
    return out, (image.height // size) * (image.width // size)


EXTERIOR = {
    "grass": [(5, 5), (11, 13), (13, 3), (13, 15), (45, 5)],
    "path": [(57, 0), (41, 4), (43, 4), (53, 0)],
    "rock": [(2, 3), (2, 1), (0, 15)],
}


def exterior(assets):
    """The exterior tileset: returns (tileset id, columns, wall tile id)."""
    from PIL import Image

    sheet = Image.open(
        lucifer.FREE_ASSETS
        / "Foozle_2DT0002_Lucifer_Exterior_Tileset_Pixel_Art"
        / "Png"
        / "OuterTileset.png"
    ).convert("RGBA")
    image, block = _with_block_row(sheet)
    columns = sheet.width // 16
    tileset, _ = assets.tileset("exterior", image, 16, "Exterior", solid=(block,))
    return tileset, columns, block


def paint_ground(grid, kinds, x0, y0, x1, y1, weights=None):
    tiles = [grid.tile(c, r) for c, r in kinds]
    grid.fill("ground", x0, y0, x1, y1, tiles, weights)


# -- stamps: props cut from tileset blocks (column, row, width, height in tiles) ---------------
EXTERIOR_PROPS = {
    "tree": (76, 2, 4, 4, (3,)),
    "grave": (58, 0, 2, 2, (1,)),
    "grave_cross": (62, 0, 2, 3, (2,)),
    "crypt": (66, 0, 4, 4, (3,)),
    "rocks": (70, 2, 6, 2, (1,)),
    "rock": (70, 0, 2, 2, (1,)),
    "bush": (70, 3, 2, 3, (2,)),
    "fence": (60, 6, 6, 2, (1,)),
}


def prop(grid, name, tx, ty, table=EXTERIOR_PROPS):
    col, row, w, h, solid = table[name]
    grid.stamp("objects", tx, ty, col, row, w, h, solid_rows=solid)


def scatter(grid, rng, names, count, x0, y0, x1, y1, keep_clear=(), table=EXTERIOR_PROPS):
    """Put ``count`` props at random free spots of the rectangle (never on a cleared box)."""
    placed = 0
    for _ in range(count * 20):
        if placed >= count:
            break
        name = rng.choice(names)
        w, h = table[name][2], table[name][3]
        tx, ty = rng.randrange(x0, x1 - w), rng.randrange(y0, y1 - h)
        spots = {(tx + dx, ty + dy) for dx in range(w) for dy in range(h)}
        if any(spots & set(box) for box in keep_clear) or any(
            s in grid.layers["objects"] or s in grid.layers["collision"] for s in spots
        ):
            continue
        prop(grid, name, tx, ty, table)
        placed += 1


def box(x0, y0, x1, y1):
    return {(x, y) for x in range(x0, x1) for y in range(y0, y1)}


def world_xy(tx, ty):
    """The world position of the middle of a tile."""
    return (tx * 16.0 + 8.0, ty * 16.0 + 8.0)


def hearthfold(grid):
    """The town: a plaza on crossing roads, walled by rock, shrines and graves at the edges."""
    w, h = grid.width, grid.height
    paint_ground(grid, EXTERIOR["grass"], 0, 0, w, h, [6, 1, 1, 1, 1])
    paint_ground(grid, EXTERIOR["path"], 2, 11, w - 1, 15)
    paint_ground(grid, EXTERIOR["path"], 20, 2, 25, h - 2)
    paint_ground(grid, EXTERIOR["path"], 12, 7, 33, 20)
    rock = [grid.tile(*EXTERIOR["rock"][0])]
    for x in range(w):
        for y in (0, h - 1):
            grid.put("ground", x, y, rock[0])
    for y in range(h):
        for x in (0, w - 1):
            grid.put("ground", x, y, rock[0])
    grid.block(0, 0, w, 1)
    grid.block(0, h - 1, w, h)
    grid.block(0, 0, 1, 12)
    grid.block(0, 15, 1, h)
    grid.block(w - 1, 0, w, 11)
    grid.block(w - 1, 16, w, h)
    clear = [box(2, 10, w - 1, 16), box(19, 1, 26, h - 1), box(11, 6, 34, 21)]
    scatter(grid, grid.rng, ("tree",), 14, 2, 2, w - 2, h - 2, clear)
    scatter(
        grid, grid.rng, ("grave", "grave_cross", "rock", "bush"), 10, 2, 2, w - 2, h - 2, clear
    )
    return {
        "start": world_xy(22, 13),
        "to_woods": world_xy(w - 3, 13),
        "plaza": [world_xy(x, y) for y in (8, 10, 16, 18) for x in (13, 15, 17, 27, 29, 31)],
    }


def _tileset(assets, key, folder, file, name):
    from PIL import Image

    sheet = Image.open(lucifer.FREE_ASSETS / folder / file).convert("RGBA")
    image, block = _with_block_row(sheet)
    tileset, _ = assets.tileset(key, image, 16, name, solid=(block,))
    return tileset, sheet.width // 16, block


DUNGEON = {
    "floor": [(1, 11), (2, 11), (3, 10), (1, 12), (4, 12)],
    "wall": [(9, 1), (10, 1), (11, 2), (9, 2)],
    "carpet": [(17, 12), (18, 12), (17, 13)],
    "void": [(6, 0)],
}
LAVA = {
    "floor": [(16, 25), (17, 26), (18, 25), (16, 27)],
    "wall": [(5, 5), (6, 6), (7, 7), (8, 5), (6, 8)],
    "lava": [(32, 28), (33, 28), (32, 29), (33, 29)],
}


def dungeon(assets):
    return _tileset(
        assets,
        "dungeon",
        "Foozle_2DT0003_Lucifer_Dungeon_Tileset_Pixel_Art/Png",
        "DungeonTileset.png",
        "Dungeon",
    )


def lava(assets):
    return _tileset(
        assets,
        "lava",
        "Foozle_2DT0011_Lucifer_Lava_Tileset_Pixel_Art",
        "LavaDungeonTileset.png",
        "Lava Dungeon",
    )


def carve(grid, kinds, x0, y0, x1, y1, layer="ground"):
    """A room of floor: its tiles are painted and its collision cleared."""
    tiles = [grid.tile(c, r) for c, r in kinds]
    grid.fill(layer, x0, y0, x1, y1, tiles)
    for y in range(y0, y1):
        for x in range(x0, x1):
            grid.layers["collision"].pop((x, y), None)


def walled(grid, kinds_wall, kinds_floor, rooms):
    """Fill the whole map with wall, then carve the rooms and corridors out of it."""
    w, h = grid.width, grid.height
    grid.fill("ground", 0, 0, w, h, [grid.tile(c, r) for c, r in kinds_wall])
    grid.block(0, 0, w, h)
    for x0, y0, x1, y1 in rooms:
        carve(grid, kinds_floor, x0, y0, x1, y1)


def whispering_woods(grid):
    """The woods: a long road through trees, goblin camps, a crypt door at the far end."""
    w, h = grid.width, grid.height
    paint_ground(grid, EXTERIOR["grass"], 0, 0, w, h, [6, 1, 1, 1, 1])
    road = [(2, 13, 22, 17), (20, 8, 28, 17), (26, 8, 44, 12), (40, 10, 54, 20), (30, 17, 36, 27)]
    for x0, y0, x1, y1 in road:
        paint_ground(grid, EXTERIOR["path"], x0, y0, x1, y1)
    rock = grid.tile(*EXTERIOR["rock"][0])
    for x in range(w):
        for y in (0, h - 1):
            grid.put("ground", x, y, rock)
    for y in range(h):
        for x in (0, w - 1):
            grid.put("ground", x, y, rock)
    grid.block(0, 0, w, 1)
    grid.block(0, h - 1, w, h)
    grid.block(0, 0, 1, 14)
    grid.block(0, 17, 1, h)
    grid.block(w - 1, 0, w, h)
    clear = [box(x0 - 1, y0 - 1, x1 + 1, y1 + 1) for x0, y0, x1, y1 in road]
    scatter(grid, grid.rng, ("tree",), 46, 2, 2, w - 2, h - 2, clear)
    scatter(grid, grid.rng, ("bush", "rock", "rocks", "grave"), 18, 2, 2, w - 2, h - 2, clear)
    prop(grid, "crypt", w - 7, 5)
    return {
        "from_town": world_xy(3, 15),
        "to_town": world_xy(1, 15),
        "to_crypt": world_xy(w - 5, 10),
        "from_crypt": world_xy(w - 5, 11),
        "foes": [
            world_xy(x, y) for x, y in ((10, 15), (18, 14), (24, 10), (32, 10), (37, 14), (44, 14))
        ],
        "boss": world_xy(48, 15),
        "healer": world_xy(8, 14),
        "camp": world_xy(33, 24),
    }


def catacombs(grid):
    """The catacombs: rooms joined by corridors, a red carpet to the Ancient's hall."""
    rooms = [
        (2, 12, 9, 18),
        (9, 14, 16, 16),
        (16, 10, 24, 20),
        (24, 14, 31, 16),
        (31, 8, 39, 22),
        (20, 20, 22, 26),
        (16, 26, 28, 30),
        (39, 14, 44, 16),
        (44, 8, 56, 24),
    ]
    walled(grid, DUNGEON["wall"], DUNGEON["floor"], rooms)
    carve(grid, DUNGEON["carpet"], 46, 12, 55, 20)
    return {
        "from_woods": world_xy(3, 15),
        "to_woods": world_xy(2, 15),
        "to_throne": world_xy(54, 16),
        "from_throne": world_xy(53, 16),
        "foes": [
            world_xy(x, y) for x, y in ((12, 15), (20, 13), (20, 17), (27, 15), (35, 12), (35, 18))
        ],
        "boss": world_xy(50, 16),
        "camp": world_xy(22, 28),
    }


def ember_throne(grid):
    """The Skeleton King's hall: a lava pool in front of the dais."""
    rooms = [(2, 6, 34, 20), (34, 11, 38, 15)]
    walled(grid, LAVA["wall"], LAVA["floor"], rooms)
    lava_tiles = [grid.tile(c, r) for c, r in LAVA["lava"]]
    grid.fill("ground", 10, 9, 22, 17, lava_tiles)
    grid.block(10, 9, 22, 17)
    for x in range(10, 22):  # a bridge over the pool
        for y in (12, 13):
            grid.put("ground", x, y, grid.tile(*LAVA["floor"][0]))
            grid.layers["collision"].pop((x, y), None)
    return {
        "from_crypt": world_xy(4, 13),
        "to_crypt": world_xy(3, 13),
        "boss": world_xy(30, 13),
    }


# -- the world: four maps, who stands where, what the doors and the people say ------------------
def menu(speaker, prompt, options):
    """A dialogue menu: ``options`` is ``[(label, [instructions])]``; each branch ends the event.
    Built from CHOICE (the pick goes to the ``menu`` variable) and JUMP_IF."""
    from asteria.events.conditions import EventCondition

    out = [
        EventInstruction(
            "CHOICE",
            {
                "prompt": f"{speaker}: {prompt}",
                "variable_name": "menu",
                "choices": [{"text": label, "value": i} for i, (label, _) in enumerate(options)],
            },
        )
    ]
    for index in range(len(options)):
        condition = EventCondition("variable", "menu", "==", index, None).to_data()
        out.append(EventInstruction("JUMP_IF", {"condition": condition, "label": f"opt{index}"}))
    out.append(EventInstruction("END"))
    for index, (_label, steps) in enumerate(options):
        out.append(EventInstruction("LABEL", {"name": f"opt{index}"}))
        out.extend(steps)
        out.append(EventInstruction("END"))
    return out


def needs_quest(quest_id, status, steps, label="ready"):
    """``steps`` when the quest has that status (``inactive`` until it was started)."""
    from asteria.events.conditions import EventCondition

    condition = EventCondition("rpg", f"quest:{quest_id}", "==", status, None).to_data()
    return [
        EventInstruction("JUMP_IF", {"condition": condition, "label": label}),
        EventInstruction("END"),
        EventInstruction("LABEL", {"name": label}),
        *steps,
    ]


def when(name, steps_true, steps_false, *, source="switch"):
    """Run ``steps_true`` when the switch/variable ``name`` is on, else ``steps_false``."""
    from asteria.events.conditions import EventCondition

    condition = EventCondition(source, name, "==", True, None).to_data()
    return [
        EventInstruction("JUMP_IF", {"condition": condition, "label": "yes"}),
        *steps_false,
        EventInstruction("END"),
        EventInstruction("LABEL", {"name": "yes"}),
        *steps_true,
    ]


def set_switch(name, value=True):
    return EventInstruction("SET_SWITCH", {"name": name, "value": value})


FOE_LOOKS = {
    "goblin_slinger": "goblin_slinger",
    "goblin_berserker": "goblin_berserker",
    "goblin_beast": "goblin_beast",
    "skeleton_grunt": "skeleton_grunt",
    "skeleton_hunter": "skeleton_hunter",
    "skeleton_ancient": "skeleton_ancient",
    "skeleton_king": "skeleton_king",
}
NPC_FACES = ("warrior", "sorceress", "necromancer", "cultist")


def build_world(c, story):
    """Replace the reference field with the four Lucifer maps; ``story(c, builders, looks,
    places)`` adds the people, programs and rules of the game."""
    from asteria.runtime.game_start import GameStartDefinition

    project, root = c.project, c.root
    for old in project.scenes():  # the reference field is not part of this game
        project._scenes.pop(old.id)
        project.scene_event_bindings.pop(old.id, None)
    assets = Assets(project, root)
    ext, ext_cols, _ = exterior(assets)
    dun, dun_cols, _ = dungeon(assets)
    lav, lav_cols, _ = lava(assets)
    town_grid, woods_grid = Grid(ext_cols, 44, 26, 11), Grid(ext_cols, 60, 32, 12)
    crypt_grid, throne_grid = Grid(dun_cols, 56, 32, 13), Grid(lav_cols, 40, 26, 14)
    places = {
        "town": hearthfold(town_grid),
        "woods": whispering_woods(woods_grid),
        "crypt": catacombs(crypt_grid),
        "throne": ember_throne(throne_grid),
    }
    maps = {
        "town": assets.tilemap("town", town_grid.data(ext, 16), "Hearthfold"),
        "woods": assets.tilemap("woods", woods_grid.data(ext, 16), "Whispering Woods"),
        "crypt": assets.tilemap("crypt", crypt_grid.data(dun, 16), "Catacombs"),
        "throne": assets.tilemap("throne", throne_grid.data(lav, 16), "Ember Throne"),
    }
    looks = {
        key: character(assets, f"look_{key}", key, key.replace("_", " ").title())
        for key in (*NPC_FACES, *FOE_LOOKS.values())
    }
    builders = {
        "town": SceneBuilder(project, "town", "Hearthfold"),
        "woods": SceneBuilder(project, "woods", "Whispering Woods"),
        "crypt": SceneBuilder(project, "crypt", "Catacombs"),
        "throne": SceneBuilder(project, "throne", "Ember Throne"),
    }
    for key, builder in builders.items():
        builder.setup(maps[key])
    town, woods, crypt, throne = (builders[k] for k in ("town", "woods", "crypt", "throne"))
    hero = town.entity("Player", *places["town"]["start"])
    town.look(hero, *looks["warrior"])
    town.door(
        "Road East",
        places["town"]["to_woods"],
        woods.scene.id,
        places["woods"]["from_town"],
        "right",
        "rain",
        "woods_theme",
    )
    woods.door(
        "Road West",
        places["woods"]["to_town"],
        town.scene.id,
        places["town"]["to_woods"],
        "left",
        "none",
        "town_theme",
    )
    woods.door(
        "Crypt Door",
        places["woods"]["to_crypt"],
        crypt.scene.id,
        places["crypt"]["from_woods"],
        "right",
        "none",
        "crypt_theme",
    )
    crypt.door(
        "Stairs Up",
        places["crypt"]["to_woods"],
        woods.scene.id,
        places["woods"]["from_crypt"],
        "left",
        "rain",
        "woods_theme",
    )
    crypt.door(
        "Throne Door",
        places["crypt"]["to_throne"],
        throne.scene.id,
        places["throne"]["from_crypt"],
        "right",
        "dust",
        "throne_theme",
    )
    throne.door(
        "Stairs Down",
        places["throne"]["to_crypt"],
        crypt.scene.id,
        places["crypt"]["from_throne"],
        "left",
        "none",
        "crypt_theme",
    )
    patrols = {
        "woods": (
            woods,
            "woods",
            ("goblin_slinger", "goblin_berserker"),
            ("woods_patrol", "woods_ambush"),
        ),
        "crypt": (
            crypt,
            "crypt",
            ("skeleton_grunt", "skeleton_hunter"),
            ("crypt_patrol", "crypt_guard"),
        ),
    }
    for key, (builder, _area, kinds, encounters) in patrols.items():
        for index, xy in enumerate(places[key]["foes"]):
            kind = kinds[index % len(kinds)]
            builder.foe(
                f"{kind.replace('_', ' ').title()} {index + 1}",
                xy,
                looks[kind],
                encounters[index % 2],
            )
    woods.foe(
        "Goblin Beast", places["woods"]["boss"], looks["goblin_beast"], "woods_boss", radius=22.0
    )
    crypt.foe(
        "Skeleton Ancient",
        places["crypt"]["boss"],
        looks["skeleton_ancient"],
        "crypt_boss",
        radius=22.0,
    )
    throne.foe(
        "Vaelor", places["throne"]["boss"], looks["skeleton_king"], "boss_room", radius=24.0
    )
    from asteria.core.prefab import prefab_from_entity

    for prefab_id, face in (("spirit_lantern", "necromancer"), ("bone_pile", "skeleton_grunt")):
        template = Entity(
            prefab_id.replace("_", " ").title(), entity_id=asset_id("prefab", prefab_id)
        )
        template.add_component(Transform(0, 0))
        template.add_component(_set(SpriteRenderer2D(), sprite_sheet_asset_id=looks[face][0]))
        template.add_component(_set(Animator2DComponent(), clip_set_id=looks[face][1]))
        project.prefabs.add(prefab_from_entity(template, prefab_id))
    from PIL import Image

    banner = Image.open(
        lucifer.FREE_ASSETS / lucifer.UI_PACK / "Panels" / "Panels" / "SimplePanel02.png"
    ).convert("RGBA")
    places["pictures"] = {
        "banner": assets.texture("banner", banner.resize((256, 256), 0), "Banner")
    }
    places["scenes"] = {key: builder.scene.id for key, builder in builders.items()}
    story(c, builders, looks, places)
    for builder in builders.values():
        builder.finish()
    project.startup_scene_id = town.scene.id
    data = project.game_start.to_data()
    data.update(
        scene_id=town.scene.id,
        player_entity_id=hero.id,
        player_position=list(places["town"]["start"]),
        player_facing="down",
    )
    project.game_start = GameStartDefinition.from_data(data)
    return places
