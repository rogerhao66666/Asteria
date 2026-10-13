"""Build the golden asset suite (ASTERIA_ASSET_SPEC §34) under tests/golden/assets.

    python scripts/build_golden_assets.py

Deterministic and self-contained: images are cropped from CC0 sheets already
committed in reference_projects/complex_reference_rpg/playable_assets (Ninja
Adventure, Kenney) or drawn procedurally here. Asset documents are produced
by the engine's own codecs, so they always match the canonical format.
See tests/golden/README.md for when and how to rebuild.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from asteria.assets.canonical import AssetSource, CanonicalAsset  # noqa: E402
from asteria.assets.icon import IconVariant, icon_asset  # noqa: E402
from asteria.assets.monster import MonsterAnimation, MonsterAsset  # noqa: E402
from asteria.assets.prop import (  # noqa: E402
    CollisionShape,
    InteractionPoint,
    PropVisual,
    prop_asset,
)
from asteria.assets.sprite_kinds import (  # noqa: E402
    CharacterAsset,
    NpcAsset,
    ProjectileAsset,
    SceneAsset,
    ScenePlacement,
    SkillAsset,
    SkillBeat,
    SpriteClipData,
    SpriteData,
    UiAsset,
    standard_asset_codecs,
)
from asteria.assets.tileset import TileCollision, TileDef, tileset_asset  # noqa: E402
from asteria.assets.vfx import VFXAnchor, VFXAsset, VFXVariant  # noqa: E402
from asteria.presentation.fidelity import FrameTiming, HighFidelityClip  # noqa: E402

PLAYABLE = REPO / "reference_projects" / "complex_reference_rpg" / "playable_assets"
OUT = REPO / "tests" / "golden" / "assets"
CODECS = standard_asset_codecs()


def canonical(asset_id, kind, source):
    return CanonicalAsset(asset_id, kind, AssetSource(source))


def write(asset, *, dependencies=(), tags=()):
    c = asset.canonical
    document = {
        "schema_version": 1,
        "asset_id": c.asset_id,
        "kind": c.kind,
        "source": c.source.uri,
        "tags": sorted(tags),
        "dependencies": list(dependencies),
        "payload": CODECS.encode_asset(c.kind, asset),
    }
    path = OUT / c.asset_id / f"{c.asset_id}.asset.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def save(image, relative):
    path = OUT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return relative


def hifi(name, frame_size, frames, ms, loop):
    return HighFidelityClip(
        name, frame_size, tuple(str(f) for f in frames), (FrameTiming(ms),), loop=loop
    )


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # golden_character — the field player walk sheet (3 x 4 frames of 64 px; rows
    # down/left/right/up).
    image = save(
        Image.open(PLAYABLE / "player_field_sheet.png").convert("RGBA"),
        "golden_character/walk.png",
    )
    clips = []
    for row, facing in enumerate(("down", "left", "right", "up")):
        base = row * 3
        clips.append(
            SpriteClipData(
                f"walk_{facing}",
                (base, base + 1, base + 2, base + 1),
                0.15,
                True,
                ((0, ("footstep",)), (2, ("footstep",))),
            )
        )
        clips.append(SpriteClipData(f"idle_{facing}", (base + 1,), 0.5, True))
    write(
        CharacterAsset(
            canonical("golden_character", "character", image),
            SpriteData(image, (64, 64), (0.5, 1.0), tuple(clips)),
            "idle_down",
        )
    )

    # golden_npc — that character placed as a patrolling villager with a talk event.
    write(
        NpcAsset(
            canonical("golden_npc", "npc", image),
            "golden_character",
            "Golden Villager",
            "golden.talk",
            "Talk",
            "patrol",
            ((0.0, 0.0), (32.0, 0.0)),
        ),
        dependencies=("golden_character",),
    )

    # golden_monster — Ninja Adventure flame monster (idle loop + hit).
    image = save(
        Image.open(PLAYABLE / "battle" / "mender_wisp.png").convert("RGBA"),
        "golden_monster/monster.png",
    )
    write(
        MonsterAsset(
            canonical("golden_monster", "monster", image),
            (
                MonsterAnimation(
                    "idle", hifi("idle", (64, 64), (0, 1, 2, 3), 160, True), ("right",)
                ),
                MonsterAnimation(
                    "hit", hifi("hit", (64, 64), (4, 0, 4, 0), 70, False), ("right",)
                ),
            ),
            "idle",
            (8.0, 8.0, 48.0, 56.0),
            (32.0, 64.0),
        )
    )

    # golden_tileset — 4 x 2 procedural tiles of 16 px.
    colors = [
        (92, 168, 72),
        (196, 160, 104),
        (64, 120, 200),
        (110, 110, 120),
        (80, 150, 64),
        (180, 140, 90),
        (52, 100, 180),
        (90, 90, 100),
    ]
    sheet = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    for i, color in enumerate(colors):
        x, y = (i % 4) * 16, (i // 4) * 16
        draw.rectangle((x, y, x + 15, y + 15), fill=color + (255,))
        draw.rectangle(
            (x, y, x + 15, y + 15), outline=tuple(max(0, c - 40) for c in color) + (255,)
        )
    tiles_uri = save(sheet, "golden_tileset/tiles.png")
    solid = TileCollision("rect", ((0, 0), (16, 0), (16, 16), (0, 16)))
    write(
        tileset_asset(
            "golden_tileset",
            tiles_uri,
            (64, 32),
            (16, 16),
            4,
            2,
            tiles=(
                TileDef(0, "grass"),
                TileDef(1, "path"),
                TileDef(2, "water", solid, animation=(2, 6), frame_ms=400),
                TileDef(3, "wall", solid),
            ),
        )
    )

    # golden_prop — the house from the reference field map.
    house = Image.open(PLAYABLE / "field_map.png").convert("RGBA").crop((96, 96, 240, 288))
    house_uri = save(house, "golden_prop/house.png")
    write(
        prop_asset(
            "golden_prop",
            house_uri,
            (PropVisual(house_uri, house.size, (0.5, 1.0)),),
            collisions=(CollisionShape("rect", size=(144.0, 96.0), offset=(0.0, 96.0)),),
            interactions=(InteractionPoint("door", (104.0, 176.0), frozenset({"enter"})),),
        )
    )

    # golden_icon — the party leader's portrait frame.
    icon = Image.open(PLAYABLE / "battle" / "hero_01.png").convert("RGBA").crop((0, 0, 64, 64))
    icon_uri = save(icon, "golden_icon/icon.png")
    write(
        icon_asset(
            "golden_icon",
            icon_uri,
            (IconVariant("default", icon_uri, size=(64, 64)),),
            usages=frozenset({"skill"}),
        )
    )

    # golden_vfx — Ninja Adventure flame burst (8 frames).
    flame = Image.open(PLAYABLE / "battle" / "flame.png").convert("RGBA")
    flame_uri = save(flame, "golden_vfx/flame.png")
    fw = flame.width // 8
    write(
        VFXAsset(
            canonical("golden_vfx", "vfx", flame_uri),
            (
                VFXVariant(
                    "burst",
                    hifi("burst", (fw, flame.height), range(8), 60, False),
                    VFXAnchor("target", (0.0, -24.0)),
                ),
            ),
            "burst",
            frozenset({"fire", "impact"}),
        )
    )

    # golden_projectile — procedural 4-frame orb (24 px).
    orb = Image.new("RGBA", (96, 24), (0, 0, 0, 0))
    draw = ImageDraw.Draw(orb)
    for i in range(4):
        r = 7 + (i % 2) * 2
        cx = i * 24 + 12
        draw.ellipse((cx - r, 12 - r, cx + r, 12 + r), fill=(255, 150 + i * 20, 60, 255))
        draw.ellipse((cx - 3, 9, cx + 3, 15), fill=(255, 245, 210, 255))
    orb_uri = save(orb, "golden_projectile/orb.png")
    write(
        ProjectileAsset(
            canonical("golden_projectile", "projectile", orb_uri),
            SpriteData(
                orb_uri,
                (24, 24),
                (0.5, 0.5),
                (SpriteClipData("fly", (0, 1, 2, 3), 0.05, True, ((0, ("trail",)),)),),
            ),
            240.0,
            1.5,
            8.0,
            "golden_vfx",
        ),
        dependencies=("golden_vfx",),
    )

    # golden_skill — a fire projectile skill: swing, launch, impact.
    write(
        SkillAsset(
            canonical("golden_skill", "skill", icon_uri),
            "fire_arc",
            "golden_icon",
            0.9,
            (
                SkillBeat(0.0, "animation", "attack"),
                SkillBeat(0.1, "projectile", "golden_projectile"),
                SkillBeat(0.32, "vfx", "golden_vfx"),
                SkillBeat(0.32, "audio", "hit"),
                SkillBeat(0.32, "camera", "shake"),
            ),
        ),
        dependencies=("golden_icon", "golden_projectile", "golden_vfx"),
    )

    # golden_ui — procedural nine-slice panel with three states stacked vertically.
    panel = Image.new("RGBA", (48, 144), (0, 0, 0, 0))
    draw = ImageDraw.Draw(panel)
    for i, (fill, border) in enumerate(
        (
            ((20, 26, 40), (124, 145, 190)),
            ((30, 38, 58), (200, 180, 110)),
            ((14, 18, 28), (90, 105, 140)),
        )
    ):
        y = i * 48
        draw.rounded_rectangle(
            (0, y, 47, y + 47), radius=6, fill=fill + (235,), outline=border + (255,), width=2
        )
    panel_uri = save(panel, "golden_ui/panel.png")
    write(
        UiAsset(
            canonical("golden_ui", "ui", panel_uri),
            panel_uri,
            (48, 144),
            (8, 8, 8, 8),
            (("hover", (0, 48, 48, 48)), ("normal", (0, 0, 48, 48)), ("pressed", (0, 96, 48, 48))),
        )
    )

    # golden_scene — a 12 x 8 tile clearing with the house, the villager and a monster.
    tiles = []
    for y in range(8):
        for x in range(12):
            tiles.append(3 if y == 0 else 1 if y == 5 else 2 if (x, y) in ((9, 6), (10, 6)) else 0)
    write(
        SceneAsset(
            canonical("golden_scene", "scene", tiles_uri),
            "golden_tileset",
            (12, 8),
            tuple(tiles),
            (
                ScenePlacement("golden_prop", 40.0, 72.0, 1),
                ScenePlacement("golden_npc", 96.0, 88.0, 2),
                ScenePlacement("golden_monster", 152.0, 96.0, 2),
            ),
            (64.0, 96.0),
        ),
        dependencies=("golden_tileset", "golden_prop", "golden_npc", "golden_monster"),
    )
    print(f"wrote {len(list(OUT.rglob('*.asset.json')))} golden assets to {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
