"""Build the KayKit party art: 3D chibi characters (CC0) photographed into smooth 2D sheets.

    .venv/bin/python scripts/build_kaykit_art.py            # assemble sheets from kept frames
    .venv/bin/python scripts/build_kaykit_art.py --render   # photograph first (needs Blender)
    .venv/bin/python scripts/build_kaykit_art.py --keys knight,mage --render

Sources: ``asset_library/kaykit/`` (characters, props and animations by Kay Lousberg, CC0).
Frames: ``local_reference/free_assets/kaykit_render/raw/<key>/`` (git-ignored; ``--render``
writes them with Blender through ``scripts/kaykit_render_blender.py``). Output, read by the
demos: ``asset_library/kaykit/rendered/<key>_battle.png`` + ``.json`` (every battle clip on
one grid, drawn with ``scaling: smooth``) and ``<key>_field.png`` + ``.json`` (the 3 x 4
walking sheet: down, left, right, up). A demo build never needs Blender: only re-rendering
does. ``--list`` prints the cast.

``--style toon`` shoots with cartoon shading (a few flat light bands) into ``raw/<key>_toon/``
and assembles pixel-art sheets: frames shrunk to the Lucifer characters' pixel size, one shared
palette, a dark one-pixel outline, ``scaling: pixel`` (``--out`` picks the folder).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIBRARY = REPO / "asset_library" / "kaykit"  # three packs, each with its licence text
ADVENTURERS = LIBRARY / "KayKit_Adventurers_2.0"
ANIMATIONS = LIBRARY / "KayKit_Character_Animations_1.1"
RENDERED = LIBRARY / "KayKit_Rendered_Sheets"
RAW = REPO / "local_reference" / "free_assets" / "kaykit_render" / "raw"
BLENDER_SCRIPT = REPO / "scripts" / "kaykit_render_blender.py"
VIRTUAL_PIXEL = 3  # sheet pixels per battle layout unit (480 x 270): 1:1 in a 1440-wide window
BODY_UNITS = 44.0  # the standing figure's height in layout units (the Lucifer Warrior is 38)
FIELD_CELL = 48  # the engine's walking sheet: 3 columns x 4 rows (down, left, right, up)
FIELD_BODY = 32  # the walking figure's height in that cell (the Lucifer walker is 31)
PIXEL_BODY = 36  # toon style: the standing figure in sheet pixels (the Lucifer Warrior is 31)
PIXEL_SCALE = 1.24  # toon style: layout units per sheet pixel, as Lucifer's 2x sheets at 0.62
PIXEL_COLOURS = 40  # toon style: one palette for every frame of a character
OUTLINE = (26, 20, 32, 255)  # toon style: the outline colour (Lucifer's near-black)
TOON_BANDS = [[0.0, 0.62], [0.32, 0.82], [0.62, 1.0]]  # diffuse brightness -> light level

# every clip the battle asks of a party member -> (animation, frames, one-shot) per weapon style
STYLES = {
    "sword_shield": {
        "idle": ("Idle_A", 8, False),
        "attack": ("Melee_1H_Attack_Slice_Diagonal", 10, True),
        "attack2": ("Melee_1H_Attack_Chop", 10, True),
        "attack3": ("Melee_1H_Attack_Jump_Chop", 12, True),
        "cast": ("Ranged_Magic_Raise", 10, True),
        "guard": ("Melee_Blocking", 4, False),
        "hit": ("Hit_A", 6, True),
        "ko": ("Death_A", 10, True),
        "victory": ("Cheering", 10, False),
    },
    "caster": {
        "idle": ("Idle_A", 8, False),
        "attack": ("Ranged_Magic_Shoot", 10, True),
        "attack2": ("Ranged_Magic_Raise", 10, True),
        "attack3": ("Ranged_Magic_Summon", 12, True),
        "cast": ("Ranged_Magic_Spellcasting", 10, True),
        "guard": ("Melee_Blocking", 4, False),
        "hit": ("Hit_A", 6, True),
        "ko": ("Death_A", 10, True),
        "victory": ("Cheering", 10, False),
    },
    "dual": {
        "idle": ("Idle_A", 8, False),
        "attack": ("Melee_Dualwield_Attack_Slice", 10, True),
        "attack2": ("Melee_Dualwield_Attack_Chop", 10, True),
        "attack3": ("Melee_Dualwield_Attack_Stab", 12, True),
        "cast": ("Throw", 10, True),
        "guard": ("Dodge_Backward", 4, False),
        "hit": ("Hit_A", 6, True),
        "ko": ("Death_A", 10, True),
        "victory": ("Cheering", 10, False),
    },
}
FIELD_CLIPS = {"walk": ("Walking_A", 3, False)}
FIELD_VIEWS = (("down", 90.0), ("left", 0.0), ("right", 180.0), ("up", 270.0))
BATTLE_VIEW = {"name": "battle", "yaw": 30.0, "pitch": 12.0, "size": 512, "ortho": 4.2}
FIELD_PITCH = 30.0  # the walker seen a little from above, as RPG field sprites are

CAST = {  # key: character, props held (asset, bone), weapon style
    "knight": (
        "Knight",
        (("sword_1handed", "handslot.r"), ("shield_badge_color", "handslot.l")),
        "sword_shield",
    ),
    "mage": ("Mage", (("staff", "handslot.r"), ("spellbook_open", "handslot.l")), "caster"),
    "rogue_hooded": (
        "Rogue_Hooded",
        (("wand", "handslot.r"), ("spellbook_closed", "handslot.l")),
        "caster",
    ),
    "rogue": ("Rogue", (("dagger", "handslot.r"), ("dagger", "handslot.l")), "dual"),
}
ANIMATION_FILES = (
    "General",
    "CombatMelee",
    "CombatRanged",
    "MovementBasic",
    "MovementAdvanced",
    "Simulation",
)


# -- Blender -------------------------------------------------------------------------------------
def blender_path(explicit=None):
    candidates = [
        explicit,
        os.environ.get("ASTERIA_BLENDER"),
        shutil.which("blender"),
        "/Applications/Blender.app/Contents/MacOS/Blender",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise SystemExit(
        "Blender was not found. Install it from https://www.blender.org/download/ (macOS: drag "
        "Blender.app into Applications) or set ASTERIA_BLENDER to the executable. The demos "
        "build without Blender: only --render needs it."
    )


def job(key):
    character, props, style = CAST[key]
    clips = [
        {"name": name, "action": action, "frames": frames, "hold_last": one_shot}
        for name, (action, frames, one_shot) in STYLES[style].items()
    ]
    clips += [
        {"name": name, "action": action, "frames": frames, "hold_last": one_shot}
        for name, (action, frames, one_shot) in FIELD_CLIPS.items()
    ]
    views = [{**BATTLE_VIEW, "clips": list(STYLES[style])}] + [
        {
            "name": f"field_{facing}",
            "yaw": yaw,
            "pitch": FIELD_PITCH,
            "size": 384,
            "ortho": 4.0,
            "shift_y": 0.0,
            "clips": list(FIELD_CLIPS),
        }
        for facing, yaw in FIELD_VIEWS
    ]
    return {
        "character": str(ADVENTURERS / "characters" / f"{character}.glb"),
        "props": [
            {"asset": str(ADVENTURERS / "props" / f"{asset}.gltf"), "bone": bone}
            for asset, bone in props
        ],
        "animations": [
            str(ANIMATIONS / "animations" / f"Rig_Medium_{name}.glb") for name in ANIMATION_FILES
        ],
        "clips": clips,
        "views": views,
    }


def raw_folder(key, style="smooth"):
    return RAW / (key if style == "smooth" else f"{key}_{style}")


def render(key, blender, views=None, style="smooth"):
    """Photograph ``key``; ``views`` (a prefix such as ``field``) re-shoots only those views."""
    out = raw_folder(key, style)
    work = job(key)
    if style == "toon":
        work["style"], work["bands"] = "toon", TOON_BANDS
    if views:
        work["views"] = [v for v in work["views"] if v["name"].startswith(views)]
        for old in out.glob(f"{views}*.png") if out.is_dir() else ():
            old.unlink()
    elif out.is_dir():
        shutil.rmtree(out)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(work, handle)
        job_path = handle.name
    command = [
        blender,
        "-b",
        "--factory-startup",
        "-noaudio",
        "--python",
        str(BLENDER_SCRIPT),
        "--",
        job_path,
        str(out),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    os.unlink(job_path)
    done = [line for line in result.stdout.splitlines() if "KAYKIT RENDER DONE" in line]
    if result.returncode or not done:
        sys.stderr.write(result.stdout[-3000:] + result.stderr[-3000:])
        raise SystemExit(f"Blender failed rendering {key}")
    print(done[-1])


# -- sheets --------------------------------------------------------------------------------------
def _frames(folder, view, clip):
    from PIL import Image

    paths = sorted(folder.glob(f"{view}_{clip}_*.png"))
    if not paths:
        raise SystemExit(f"no frames for {view}/{clip} in {folder}: run with --render")
    return [Image.open(p).convert("RGBA") for p in paths]


def _box(image, cut):
    return image.getchannel("A").point(lambda a: 255 if a > cut else 0).getbbox()


def _union(boxes):
    boxes = [b for b in boxes if b]
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def battle_sheet(key, folder):
    """Every battle clip of ``key`` on one grid, the standing figure BODY_UNITS tall."""
    from PIL import Image

    style = STYLES[CAST[key][2]]
    clips = {name: _frames(folder, "battle", name) for name in style}
    box = _union(_box(f, 8) for frames in clips.values() for f in frames)
    stand = _box(clips["idle"][0], 128)
    factor = BODY_UNITS * VIRTUAL_PIXEL / (stand[3] - stand[1])
    width = max(1, round((box[2] - box[0]) * factor))
    height = max(1, round((box[3] - box[1]) * factor))
    order, index = [], {}
    for name, frames in clips.items():
        index[name] = list(range(len(order), len(order) + len(frames)))
        order.extend(frames)
    columns = 10
    rows = (len(order) + columns - 1) // columns
    sheet = Image.new("RGBA", (width * columns, height * rows), (0, 0, 0, 0))
    for n, frame in enumerate(order):
        cell = frame.crop(box).resize((width, height), Image.LANCZOS)
        sheet.alpha_composite(cell, ((n % columns) * width, (n // columns) * height))
    idle = index["idle"][0]
    first = sheet.crop((0, 0, width, height))
    feet = _box(first, 128)[3]

    def clip(name, duration, *, back=False, reverse=False, hit=None, loop=False):
        frames = index[name][::-1] if reverse else list(index[name])
        if back:
            frames.append(idle)  # the swing ends standing, however long the action lasts
        data = {"frames": frames, "frame_duration": duration, "loop": loop}
        if hit is not None:
            data["events"] = {str(hit): ["hit"]}
        return data

    meta = {
        "frame_size": [width, height],
        "pivot": [0.5, round(feet / height, 4)],
        "scaling": "smooth",
        "body_height": stand[3] - stand[1],
        "clips": {
            "idle": clip("idle", 0.13, loop=True),
            "attack": clip("attack", 0.1, back=True, hit=6),
            "attack2": clip("attack2", 0.1, back=True, hit=6),
            "attack3": clip("attack3", 0.11, back=True, hit=7),
            "cast": clip("cast", 0.1, back=True),
            "guard": clip("guard", 0.15, loop=True),
            "hit": clip("hit", 0.09, back=True),
            "ko": clip("ko", 0.08),
            "revive": clip("ko", 0.07, reverse=True),
            "transform": clip("victory", 0.1, back=True),
            "status": clip("idle", 0.13, loop=True),
            "victory": clip("victory", 0.1, loop=True),
        },
        "scale": round(1 / VIRTUAL_PIXEL, 6),  # the profile transform: layout units per pixel
        "source": "KayKit Adventurers 2.0 + Character Animations 1.1 (Kay Lousberg, CC0), "
        "rendered by scripts/build_kaykit_art.py",
    }
    meta["body_height"] = round(meta["body_height"] * factor)
    return sheet, meta


def field_sheet(key, folder):
    """The engine's 3 x 4 walking sheet: rows down / left / right / up, 3 steps each."""
    from PIL import Image

    cells = {facing: _frames(folder, f"field_{facing}", "walk") for facing, _ in FIELD_VIEWS}
    box = _union(_box(f, 8) for frames in cells.values() for f in frames)
    stand = _box(cells["down"][0], 128)
    factor = FIELD_BODY / (stand[3] - stand[1])
    sheet = Image.new("RGBA", (3 * FIELD_CELL, 4 * FIELD_CELL), (0, 0, 0, 0))
    for row, (facing, _) in enumerate(FIELD_VIEWS):
        for column, frame in enumerate(cells[facing][:3]):
            cell = frame.crop(box)
            cell = cell.resize(
                (max(1, round(cell.width * factor)), max(1, round(cell.height * factor))),
                Image.LANCZOS,
            )
            x = column * FIELD_CELL + (FIELD_CELL - cell.width) // 2
            y = row * FIELD_CELL + FIELD_CELL - cell.height - 2
            sheet.alpha_composite(cell, (x, y))
    return sheet, {
        "frame_size": [FIELD_CELL, FIELD_CELL],
        "scaling": "smooth",
        "rows": [facing for facing, _ in FIELD_VIEWS],
    }


# -- toon style: pixel-art sheets ----------------------------------------------------------------
def _palette(frames, factor):
    """One palette for a character, from a few of its frames at their final size."""
    from PIL import Image

    picks = frames[:: max(1, len(frames) // 12)]
    smalls = [
        f.resize((max(1, round(f.width * factor)), max(1, round(f.height * factor))), Image.BOX)
        for f in picks
    ]
    strip = Image.new("RGB", (sum(s.width for s in smalls), max(s.height for s in smalls)))
    x = 0
    for small in smalls:
        opaque = small.getchannel("A").point(lambda a: 255 if a > 110 else 0)
        strip.paste(small.convert("RGB"), (x, 0), opaque)
        x += small.width
    return strip.quantize(PIXEL_COLOURS, method=Image.Quantize.MEDIANCUT)


def _pixel(frame, size, palette):
    """``frame`` as pixel art of ``size``: hard alpha, the palette's colours, a 1-pixel outline
    round the figure (four-way, like hand-drawn sprites)."""
    from PIL import Image, ImageChops

    small = frame.resize(size, Image.BOX)
    alpha = small.getchannel("A").point(lambda a: 255 if a > 110 else 0)
    rgb = small.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB")
    body = rgb.convert("RGBA")
    body.putalpha(alpha)
    width, height = size
    padded = Image.new("L", (width + 2, height + 2), 0)
    padded.paste(alpha, (1, 1))
    grown = padded
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        grown = ImageChops.lighter(grown, ImageChops.offset(padded, dx, dy))
    out = Image.new("RGBA", (width + 2, height + 2), (0, 0, 0, 0))
    edge = Image.new("RGBA", out.size, OUTLINE)
    out.paste(edge, (0, 0), grown)
    out.alpha_composite(body, (1, 1))
    return out


def pixel_battle_sheet(key, folder):
    """The toon frames as a pixel-art battle sheet (same clips and layout as ``battle_sheet``)."""
    from PIL import Image

    style = STYLES[CAST[key][2]]
    clips = {name: _frames(folder, "battle", name) for name in style}
    box = _union(_box(f, 8) for frames in clips.values() for f in frames)
    stand = _box(clips["idle"][0], 128)
    factor = PIXEL_BODY / (stand[3] - stand[1])
    inner = (max(1, round((box[2] - box[0]) * factor)), max(1, round((box[3] - box[1]) * factor)))
    width, height = inner[0] + 2, inner[1] + 2
    order, index = [], {}
    for name, frames in clips.items():
        index[name] = list(range(len(order), len(order) + len(frames)))
        order.extend(f.crop(box) for f in frames)
    palette = _palette(order, factor)
    columns = 10
    rows = (len(order) + columns - 1) // columns
    sheet = Image.new("RGBA", (width * columns, height * rows), (0, 0, 0, 0))
    for n, frame in enumerate(order):
        cell = _pixel(frame, inner, palette)
        sheet.alpha_composite(cell, ((n % columns) * width, (n // columns) * height))
    smooth_sheet, meta = battle_sheet(key, folder)  # the clip table is the same
    feet = _box(sheet.crop((0, 0, width, height)), 128)[3]
    meta.update(
        frame_size=[width, height],
        pivot=[0.5, round(feet / height, 4)],
        scaling="pixel",
        body_height=PIXEL_BODY,
        scale=PIXEL_SCALE,
    )
    return sheet, meta


def pixel_field_sheet(key, folder):
    """The toon walking frames as a pixel-art 3 x 4 walking sheet."""
    from PIL import Image

    cells = {facing: _frames(folder, f"field_{facing}", "walk") for facing, _ in FIELD_VIEWS}
    box = _union(_box(f, 8) for frames in cells.values() for f in frames)
    stand = _box(cells["down"][0], 128)
    factor = FIELD_BODY / (stand[3] - stand[1])
    crops = {facing: [f.crop(box) for f in frames] for facing, frames in cells.items()}
    palette = _palette([f for frames in crops.values() for f in frames], factor)
    size = (max(1, round((box[2] - box[0]) * factor)), max(1, round((box[3] - box[1]) * factor)))
    sheet = Image.new("RGBA", (3 * FIELD_CELL, 4 * FIELD_CELL), (0, 0, 0, 0))
    for row, (facing, _) in enumerate(FIELD_VIEWS):
        for column, frame in enumerate(crops[facing][:3]):
            cell = _pixel(frame, size, palette)
            x = column * FIELD_CELL + (FIELD_CELL - cell.width) // 2
            y = row * FIELD_CELL + FIELD_CELL - cell.height - 1
            sheet.alpha_composite(cell, (x, y))
    return sheet, {
        "frame_size": [FIELD_CELL, FIELD_CELL],
        "scaling": "pixel",
        "rows": [facing for facing, _ in FIELD_VIEWS],
    }


def build(key, style="smooth", out=None):
    folder = raw_folder(key, style)
    out = Path(out) if out else RENDERED
    out.mkdir(parents=True, exist_ok=True)
    makers = (
        (("battle", battle_sheet), ("field", field_sheet))
        if style == "smooth"
        else (("battle", pixel_battle_sheet), ("field", pixel_field_sheet))
    )
    for kind, maker in makers:
        sheet, meta = maker(key, folder)
        sheet.save(out / f"{key}_{kind}.png")
        (out / f"{key}_{kind}.json").write_text(
            json.dumps(meta, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"{key}_{kind}: {sheet.size[0]}x{sheet.size[1]} frame {meta['frame_size']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--render", action="store_true", help="photograph with Blender first")
    parser.add_argument("--keys", default=",".join(CAST), help="comma-separated cast keys")
    parser.add_argument("--blender", help="the Blender executable (else ASTERIA_BLENDER)")
    parser.add_argument(
        "--views", help="with --render: re-shoot only the views whose name starts with this"
    )
    parser.add_argument(
        "--style", choices=("smooth", "toon"), default="smooth", help="toon: pixel-art sheets"
    )
    parser.add_argument("--out", help="the folder the sheets go to (else the rendered pack)")
    parser.add_argument("--list", action="store_true", help="print the cast and exit")
    args = parser.parse_args(argv)
    if args.list:
        for key, (character, props, style) in CAST.items():
            print(f"{key}: {character}, {style}, holding {[p[0] for p in props]}")
        return 0
    keys = [k.strip() for k in args.keys.split(",") if k.strip()]
    unknown = [k for k in keys if k not in CAST]
    if unknown:
        raise SystemExit(f"unknown cast keys {unknown}; --list shows them")
    blender = blender_path(args.blender) if args.render else None
    for key in keys:
        if args.render:
            render(key, blender, args.views, args.style)
        build(key, args.style, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
