"""Battle art of the Boss Trial demo, cut from the CC0 Ninja Adventure pack (local_reference).

The hero is the animated NinjaGreen (real idle, attack, hit, dead, item and roll strips) with the
pack's Katana layer drawn into the attack frames. The boss (GiantRedSamurai) has real idle,
attack, charge and hit strips. Both are drawn at the same pixel scale.
"""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACK = (
    REPO
    / "local_reference"
    / "free_assets"
    / "ninja_adventure"
    / "extracted"
    / "Ninja Adventure - Asset Pack"
    / "Actor"
)
RIGHT = 3  # Ninja Adventure columns: down, up, left, right (the engine flips for left-facing)
SOURCE = (("license", "CC0 1.0"), ("source", "Ninja Adventure Asset Pack"))


def _helpers():
    spec = importlib.util.spec_from_file_location(
        "reference_battle_art", REPO / "scripts" / "build_reference_battle_presentation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hue_shift(image, degrees):
    """The same picture with every colour turned round the colour wheel (alpha untouched)."""
    from PIL import Image

    r, g, b, a = image.split()
    h, sat, v = Image.merge("RGB", (r, g, b)).convert("HSV").split()
    h = h.point(lambda x: (x + round(degrees / 360 * 256)) % 256)
    out = Image.merge("HSV", (h, sat, v)).convert("RGB")
    out.putalpha(a)
    return out


def _ninja_cells(name="NinjaGreen", hue=0):
    """The animated ninja's strips as ``{strip: [frame per row]}`` of its right-facing column."""
    from PIL import Image

    base = PACK / "CharacterAnimated" / name / "Separate"
    out = {}
    for strip in ("Idle", "Attack", "Hit", "Dead", "Item", "Roll"):
        image = Image.open(base / f"{strip}.png").convert("RGBA")
        if hue:
            image = _hue_shift(image, hue)
        column = RIGHT if image.width >= 128 else 0
        out[strip] = [
            image.crop((column * 32, r * 32, column * 32 + 32, r * 32 + 32))
            for r in range(image.height // 32)
        ]
    return out


def ninja_sheet(scale=2, weapon="Katana", hue=0):
    """NinjaGreen on 64 px canvases (the character is 32 px, bottom-centred; the room above and
    to the sides holds the weapon swing). The pack's weapon sheet is 4 x 4 cells of 64 px - one
    column per facing, one row per attack frame - centred on the character, so the katana and
    its slash arc are drawn into the attack frames exactly as the pack intends.
    Frame order: idle(0-3) attack(4-7) hit(8-9) dead(10-11) item(12-13) roll(14-16)."""
    from PIL import Image

    h = _helpers()
    cells = _ninja_cells(hue=hue)
    weapon_sheet = Image.open(PACK / "CharacterAnimated" / "Weapon" / f"{weapon}.png").convert(
        "RGBA"
    )

    def canvas(frame, layer=None):
        out = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        out.alpha_composite(frame, (16, 32))
        if layer is not None:  # the weapon cell is centred on the character: (16, 16) in it
            out.alpha_composite(layer, (0, 16))
        return out

    attack = []
    for row, frame in enumerate(cells["Attack"]):
        layer = weapon_sheet.crop((RIGHT * 64, row * 64, RIGHT * 64 + 64, row * 64 + 64))
        attack.append(canvas(frame, layer))
    plain = {k: [canvas(f) for f in v] for k, v in cells.items() if k != "Attack"}
    frames = [*plain["Idle"], *attack, *plain["Hit"], *plain["Dead"], *plain["Item"]]
    frames += plain["Roll"]
    n_idle, n_att = len(plain["Idle"]), len(attack)
    a0 = n_idle
    h0 = a0 + n_att
    d0 = h0 + len(plain["Hit"])
    i0 = d0 + len(plain["Dead"])
    r0 = i0 + len(plain["Item"])
    clips = {
        "idle": {"frames": list(range(n_idle)), "frame_duration": 0.2, "loop": True},
        "attack": {
            "frames": list(range(a0, a0 + n_att)) + [0],
            "frame_duration": 0.1,
            "loop": False,
            "events": {"1": ["hit"]},
        },
        "cast": {"frames": [i0, i0 + 1, i0 + 1, i0], "frame_duration": 0.14, "loop": False},
        "guard": {"frames": [i0], "frame_duration": 0.3, "loop": True},
        "hit": {"frames": [h0, h0 + 1, h0], "frame_duration": 0.08, "loop": False},
        "ko": {"frames": [d0 + 1], "frame_duration": 0.5, "loop": False},
        "revive": {"frames": [d0 + 1, d0, 0], "frame_duration": 0.2, "loop": False},
        "status": {"frames": [0, 1], "frame_duration": 0.25, "loop": True},
        "transform": {
            "frames": list(range(r0, r0 + len(plain["Roll"]))) + [0],
            "frame_duration": 0.1,
            "loop": False,
        },
    }
    # trim the empty margin: the engine sizes a combatant by its frame, and menus, health bars
    # and the step toward a foe all follow that size. Symmetric around the character, feet at the
    # bottom edge, so the pivot stays under the character.
    boxes = [f.getchannel("A").getbbox() for f in frames]
    left = min(b[0] for b in boxes if b)
    right = max(b[2] for b in boxes if b)
    top = min(b[1] for b in boxes if b)
    bottom = max(b[3] for b in boxes if b)
    half = max(32 - left, right - 32)
    box = (32 - half, top, 32 + half, bottom)
    frames = [f.crop(box) for f in frames]
    width, height = box[2] - box[0], box[3] - box[1]
    return h._strip(frames, scale), (width * scale, height * scale), clips


def ninja_field_sheet(*, scale=2, frame=64):
    """NinjaGreen walk cycle -> the engine's 3 x 4 field sheet (rows down / left / right / up)."""
    from PIL import Image

    walk = Image.open(PACK / "CharacterAnimated" / "NinjaGreen" / "Separate" / "Walk.png")
    walk = walk.convert("RGBA")
    column = {"down": 0, "left": 2, "right": 3, "up": 1}
    out = Image.new("RGBA", (3 * frame, 4 * frame), (0, 0, 0, 0))
    size = 32 * scale
    for engine_row, facing in enumerate(("down", "left", "right", "up")):
        for pattern, source_row in enumerate((1, 0, 3)):
            cell = walk.crop(
                (
                    column[facing] * 32,
                    source_row * 32,
                    column[facing] * 32 + 32,
                    source_row * 32 + 32,
                )
            ).resize((size, size), Image.NEAREST)
            out.alpha_composite(
                cell,
                (pattern * frame + (frame - size) // 2, engine_row * frame + frame - size - 2),
            )
    return out


def samurai_sheet(name="GiantRedSamurai"):
    """The boss on 96 x 96 cells: idle(0-5) attack(6-9) charge(10-12) hit(13-15) ko(16)."""
    from PIL import Image

    h = _helpers()
    base = PACK / "Boss" / name
    load = lambda f: Image.open(base / f).convert("RGBA")  # noqa: E731

    def cells(image, width, height, count):
        out = []
        for c in range(min(count, image.width // width)):
            frame = image.crop((c * width, 0, c * width + width, height))
            canvas = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
            canvas.alpha_composite(frame, ((96 - width) // 2, 96 - height))
            out.append(canvas)
        return out

    idle = cells(load("Idle.png"), 96, 48, 6)
    attack = cells(load("AttackRight.png"), 96, 96, 4)
    charge = cells(load("ChargeRight.png"), 96, 96, 3)
    hit = cells(load("Hit.png"), 96, 48, 3)
    frames = idle + attack + charge + hit + [h._darken(hit[-1])]
    n_idle, n_attack, n_charge = len(idle), len(attack), len(charge)
    a0 = n_idle
    c0 = a0 + n_attack
    h0 = c0 + n_charge
    last = len(frames) - 1
    clips = {
        "idle": {"frames": list(range(n_idle)), "frame_duration": 0.14, "loop": True},
        "attack": {
            "frames": list(range(a0, a0 + n_attack)) + [0],
            "frame_duration": 0.09,
            "loop": False,
            "events": {"2": ["hit"]},
        },
        "cast": {
            "frames": list(range(c0, c0 + n_charge)) * 2,
            "frame_duration": 0.1,
            "loop": False,
        },
        "hit": {"frames": list(range(h0, last)), "frame_duration": 0.09, "loop": False},
        "ko": {"frames": [last], "frame_duration": 0.5, "loop": False},
    }
    return h._strip(frames, 2), (192, 192), clips, frames[0]


def hero_and_boss_art(context):
    from asteria.assets.canonical import AssetSource, CanonicalAsset
    from asteria.presentation.battle_combatant_visuals import (
        BattleCombatantVisualProfile,
        BattleVisualAssetSet,
        BattleVisualStateDefinition,
        BattleVisualTransform,
        default_jrpg_visual_states,
    )

    project, out_dir = context.project, context.root / "playable_assets"
    battle = out_dir / "battle"
    battle.mkdir(parents=True, exist_ok=True)
    library = project.battle_presentation_library

    def register(name, image, frame, clips, tags, scale, states, body_height=None):
        image.save(battle / f"{name}.png")
        asset_id = f"battle.combatant.{name}"
        project.assets.register(
            CanonicalAsset(
                asset_id,
                "sprite_sheet",
                AssetSource(f"playable_assets/battle/{name}.png", "project", SOURCE),
                tags=frozenset({"battle", "combatant", *tags}),
                metadata=(
                    ("clips", clips),
                    ("frame_size", list(frame)),
                    ("pivot", [0.5, 1.0]),
                    *((("body_height", body_height),) if body_height else ()),
                ),
            ),
            replace=True,
        )
        library.set(
            "combatant_visuals",
            name,
            BattleCombatantVisualProfile(
                name,
                BattleVisualAssetSet(asset_id),
                states,
                BattleVisualTransform(scale_x=scale, scale_y=scale),
                hud_visible="enemy" not in tags
                and "summon" not in tags,  # no panel for foes or summons
            ),
        )

    roles = {"idle", "attack", "cast", "guard", "hit", "ko", "revive", "status", "transform"}
    hero_states = tuple(s for s in default_jrpg_visual_states() if s.state_id in roles)
    import trial_content
    import trial_lucifer as lucifer

    if lucifer.available():
        extra = tuple(BattleVisualStateDefinition(r, r) for r in lucifer.EXTRA_STATES)
        hero_states = (*hero_states, *extra)
        enemy_states = (
            *(BattleVisualStateDefinition(r, r) for r in ("idle", "attack", "cast", "hit", "ko")),
            *extra,
        )
        for name, key, tags, scale, states in (
            (context.hero_id, "warrior", ("hero",), 0.9, hero_states),
            ("hero_02", "sorceress", ("hero",), 0.9, hero_states),
            ("spirit_knight", "skeleton_grunt", ("hero", "summon"), 0.9, hero_states),
            (context.boss_id, "skeleton_king", ("enemy",), 1.15, enemy_states),
            ("mender_wisp", "goblin_slinger", ("enemy",), 0.9, enemy_states),
        ):
            image, frame, clips, body = lucifer.character_sheet(key)
            register(
                name, image, frame, clips, tags, scale, states, body if "enemy" in tags else None
            )
        lucifer.field_sheet("warrior").save(out_dir / "player_field_sheet.png")
        lucifer.npc_picture("skeleton_king", size=64).save(out_dir / "boss_field.png")
        for name in trial_content.SERVICES:
            lucifer.npc_picture(lucifer.NPC_CAST.get(name, "cultist")).save(
                out_dir / f"npc_{_slug(name)}.png"
            )
        return
    image, frame, clips = ninja_sheet()
    register(context.hero_id, image, frame, clips, ("hero",), 0.9, hero_states)
    # Mira: the same animated ninja turned violet, same frame size so she stands in the same column
    image, frame, clips = ninja_sheet(hue=-70)
    register("hero_02", image, frame, clips, ("hero",), 0.9, hero_states)
    # the spirit Mira calls: the same ninja in blue, with no party panel (it is a summon)
    image, frame, clips = ninja_sheet(hue=150)
    register("spirit_knight", image, frame, clips, ("hero", "summon"), 0.9, hero_states)
    image, frame, clips, field_frame = samurai_sheet()
    boss_states = tuple(
        BattleVisualStateDefinition(r, r) for r in ("idle", "attack", "cast", "hit", "ko")
    )
    box = field_frame.getchannel("A").getbbox()  # the idle pose: where the head is
    body = (box[3] - box[1]) * 2  # the sheet is drawn at 2x
    register(context.boss_id, image, frame, clips, ("enemy",), 0.9, boss_states, body)
    side = 64 / max(field_frame.size)
    field_frame.resize(
        (round(field_frame.width * side), round(field_frame.height * side)), 0
    ).save(out_dir / "boss_field.png")
    npc_sprites(out_dir, trial_content.SERVICES)
    ninja_field_sheet().save(out_dir / "player_field_sheet.png")


NPC_LOOKS = {  # who stands where: a Ninja Adventure character per service
    "Smith": "Caveman",
    "Awakener": "Monk",
    "Jeweler": "Princess",
    "Card Dealer": "OldMan",
    "Mystic Teacher": "SorcererOrange",
    "Duelist Teacher": "NinjaRed",
    "Weapon Master Dojo": "Samurai",
    "Sage's Tower": "OldMan",
    "Hero's Shrine": "Knight",
    "Forgemaster's Smithy": "Caveman",
    "Rogue Guild": "NinjaBlue",
    "Guardian Post": "Knight",
    "Shrine": "Monk",
    "Alchemist": "SorcererOrange",
    "Merchant": "Villager",
    "Breaker": "Hunter",
    "Armory (Bow)": "Hunter",
    "Armory (Dagger)": "Samurai",
}


def npc_sprites(folder, names):
    """One field sprite per service: the front pose of its character, scaled."""
    from PIL import Image

    folder = Path(folder)
    for name in names:
        character = NPC_LOOKS.get(name, "Villager")
        base = PACK / "Character" / character / "SeparateAnim" / "Idle.png"
        frame = Image.open(base).convert("RGBA").crop((0, 0, 16, 16))
        frame.resize((48, 48), Image.NEAREST).save(folder / f"npc_{_slug(name)}.png")


def _slug(name):
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")


FX = Path(PACK).parents[0] / "FX"
EFFECTS = {  # key: (strip under FX, frames, frame width, VFX scale)
    "fire": ("Elemental/Flam/SpriteSheet.png", 8, 25, 1.0),
    "ice": ("Elemental/Ice/SpriteSheet.png", 10, 32, 1.0),
    "thunder": ("Elemental/Thunder/SpriteSheet.png", 8, 20, 1.3),
    "spark": ("Magic/Spark/SpriteSheet.png", 10, 27, 1.0),
    "spirit": ("Magic/Spirit/SpriteSheet.png", 5, 32, 1.0),
    "shield": ("Magic/Shield/SpriteSheetBlue.png", 6, 24, 1.1),
    "aura": ("Magic/Aura/SpriteSheet.png", 5, 25, 1.2),
    "boost": ("Magic/Boost/SpriteSheet.png", 8, 53, 0.8),
    "explosion": ("Elemental/Explosion/SpriteSheet.png", 9, 40, 1.3),
    "circle": ("Magic/Circle/SpriteSheetSpark.png", 6, 32, 1.2),
    "smoke": ("Smoke/Smoke/SpriteSheet.png", 6, 32, 1.2),
    "slash": ("Attack/SlashCurved/SpriteSheet.png", 4, 32, 1.3),
    "slash2": ("Attack/SlashDoubleCurved/SpriteSheet.png", 4, 32, 1.3),
    "cut": ("Attack/Cut/SpriteSheet.png", 4, 32, 1.3),
    "cutx": ("Attack/CutX/SpriteSheet.png", 4, 32, 1.3),
    "cutd": ("Attack/CutDouble/SpriteSheet.png", 5, 32, 1.3),
    "claw": ("Attack/Claw/SpriteSheet.png", 4, 32, 1.3),
    "clawd": ("Attack/ClawDouble/SpriteSheet.png", 4, 32, 1.3),
    "circ": ("Attack/CircularSlash/SpriteSheet.png", 4, 32, 1.4),
}


def effect_assets(context):
    """One VFX sprite sheet per effect kind from the CC0 pack (cropped, 4x)."""
    from PIL import Image

    from asteria.assets.canonical import AssetSource, CanonicalAsset

    out = context.root / "playable_assets" / "battle"
    out.mkdir(parents=True, exist_ok=True)
    for key, (relative, count, width, vfx_scale) in EFFECTS.items():
        image = Image.open(FX / relative).convert("RGBA")
        frames = [
            image.crop((i * width, 0, i * width + width, image.height)) for i in range(count)
        ]
        height = image.height
        strip = Image.new("RGBA", (width * count * 4, height * 4), (0, 0, 0, 0))
        for i, frame in enumerate(frames):
            strip.alpha_composite(
                frame.resize((width * 4, height * 4), Image.NEAREST), (i * width * 4, 0)
            )
        name = f"fx_{key}"
        strip.save(out / f"{name}.png")
        context.project.assets.register(
            CanonicalAsset(
                f"battle.fx.{key}",
                "sprite_sheet",
                AssetSource(f"playable_assets/battle/{name}.png", "project", SOURCE),
                tags=frozenset({"battle", "vfx"}),
                metadata=(
                    (
                        "clips",
                        {
                            "play": {
                                "frames": list(range(count)),
                                "frame_duration": 0.06,
                                "loop": False,
                            }
                        },
                    ),
                    ("frame_size", [width * 4, height * 4]),
                    ("pivot", [0.5, 0.5]),
                    ("vfx", {"anchor": "center", "scale": 0.5 * vfx_scale}),
                ),
            ),
            replace=True,
        )


IDYLWILD = REPO / "local_reference" / "free_assets" / "idylwilds_arsenal" / "extracted"
WEAPON_ICONS = {  # equipment id: Idylwild's Arsenal icon (CC0, 32 x 32)
    "w_sword": "sword1border",
    "w_spear": "spear1border",
    "w_dagger": "dagger2border",
    "w_axe": "axe3border",
    "w_bow": "bow2border",
    "w_staff": "staff1border",
    "w_sunbrand": "sword4border",
    "w_sunbrand_ex": "sword5border",
}


def weapon_icons(context):
    """Copy the weapon icons into the project and set them on the weapons and their attacks."""
    import shutil

    folder = context.root / "playable_assets" / "icons"
    folder.mkdir(parents=True, exist_ok=True)
    db = context.db
    kept = []
    for equipment_id, icon in WEAPON_ICONS.items():
        target = f"weapon_{equipment_id[2:]}.png"
        shutil.copyfile(IDYLWILD / f"{icon}.png", folder / target)
        path = f"playable_assets/icons/{target}"
        db.equipment[equipment_id] = dataclasses.replace(db.equipment[equipment_id], icon_id=path)
        attack = "attack_" + equipment_id[2:]
        if attack in context.abilities.ids():
            definition = context.abilities.get(attack)
            context.abilities._definitions[attack] = dataclasses.replace(definition, icon_id=path)
            kept.append(attack)
    return tuple(kept)


def write_credits(root):
    """Credit rows for what this demo adds to the copied reference assets."""
    credits = Path(root) / "playable_assets" / "CREDITS.md"
    text = credits.read_text(encoding="utf-8")
    cc0 = "[CC0 1.0](http://creativecommons.org/publicdomain/zero/1.0/)"
    ninja = "[Ninja Adventure Asset Pack](https://pixel-boy.itch.io/ninja-adventure-asset-pack)"
    rows = [
        "| `battle/hero_01.png`, `player_field_sheet.png` (Boss Trial hero) | "
        f"{ninja} - `Actor/CharacterAnimated/NinjaGreen` strips and the `Weapon/Katana` layer, "
        "frames arranged on 64 px canvases and scaled "
        f"(built by `reference_projects/boss_trial_demo/trial_art.py`) | Pixel-boy, AAA | {cc0} |",
        "| `battle/hero_02.png` (Mira, the companion) | "
        f"{ninja} - the same NinjaGreen strips with the hue turned and the `Weapon/Katana` layer "
        f"(`_hue_shift` in `trial_art.py`) | Pixel-boy, AAA | {cc0} |",
        "| `battle/crimson_warlord.png`, `boss_field.png` (Boss Trial boss) | "
        f"{ninja} - `Actor/Boss/GiantRedSamurai` Idle / AttackRight / ChargeRight / Hit strips, "
        f"hit / KO frames darkened | Pixel-boy, AAA | {cc0} |",
        "| `battle/fx_*.png` (19 skill effects) | "
        f"{ninja} - `FX/Elemental`, `FX/Magic`, `FX/Attack`, `FX/Smoke`, cropped and scaled | "
        f"Pixel-boy, AAA | {cc0} |",
        "| `npc_*.png` | "
        f"{ninja} - `Actor/Character/*` front poses (Caveman, Monk, Princess, OldMan, Samurai, "
        f"Knight, Hunter, NinjaRed, NinjaBlue, SorcererOrange, Villager), scaled | "
        f"Pixel-boy, AAA | {cc0} |",
        "| `icons/weapon_*.png` (8 weapon icons) | [Idylwild's Arsenal]"
        "(https://opengameart.org/node/171012) - copied unmodified, renamed | Idylwild | "
        f"{cc0} (author asks for no credit; none is required) |",
        "| `icons/skill_*.png` | Original: drawn by code in "
        "`src/asteria/graphics/forged_icons.py` | This repository | Same as the repository |",
    ]
    # rows of the reference game whose files this demo no longer carries
    stale = (
        "| `hero_01_battle.png` … `hero_06_battle.png`",
        "| `player_field_sheet.png` | [Ninja Adventure Asset Pack](https://pixel-boy.itch.io/ninja-adv",
        "| `battle/hero_01.png` … `battle/hero_12.png`",
    )
    text = "\n".join(x for x in text.split("\n") if not x.startswith(stale))
    import trial_lucifer

    if trial_lucifer.available():
        rows = [
            r
            for r in rows
            if not r.startswith("| `battle/hero_0") and not r.startswith("| `battle/crimson")
        ]
        rows += trial_lucifer.credits_rows(
            ("warrior", "sorceress", "skeleton_grunt", "skeleton_king", "goblin_slinger")
        )
        rows += trial_lucifer.credits_extra()
    rows.append(
        "| `battle/mender_wisp.png` (the boss's helper) | "
        f"{ninja} - `Actor/Monster/Flam`, cropped and scaled | Pixel-boy, AAA | {cc0} |"
    )
    rows.append(
        "| `hero_01_battle.png`, `mender_wisp_battle.png` (pictures for the legacy playtest "
        "fallback) | [Tiny Dungeon](https://kenney.nl/assets/tiny-dungeon) 1.0 tiles, scaled | "
        f"Kenney (kenney.nl) | {cc0} |"
    )
    marker = "\n## Licensing"
    new = [r for r in rows if r.split("|")[1].strip() not in text]
    if new:
        i = text.index(marker)
        credits.write_text(
            text[:i].rstrip("\n") + "\n" + "\n".join(new) + "\n" + text[i:], encoding="utf-8"
        )


def prune_unused_art(context):
    """The reference game's other heroes and monsters are not part of this demo: drop their
    visuals, sheets and files so the project only holds what it uses."""
    keep = {context.hero_id, "hero_02", "spirit_knight", context.boss_id, "mender_wisp", "pet"}
    library = context.project.battle_presentation_library
    # a captured wisp fights on the hero side: every pet unit (member ids "pet:...") is drawn
    # with the "pet" profile, here the same sheet as the wild wisp; no side-list panel, that list
    # is for the party's characters
    wisp = library.require("combatant_visuals", "mender_wisp")
    library.set(
        "combatant_visuals",
        "pet",
        dataclasses.replace(
            wisp,
            profile_id="pet",
            hud_visible=False,
            # about the size of a character; pets stand in their own column (see front_large_zones)
            transform=dataclasses.replace(wisp.transform, scale_x=0.9, scale_y=0.9),
        ),
    )
    root = context.root / "playable_assets"
    for profile_id in list(library.ids("combatant_visuals")):
        if profile_id in keep:
            continue
        library.remove("combatant_visuals", profile_id)
        try:
            context.project.assets.remove(f"battle.combatant.{profile_id}")
        except KeyError:
            pass
        for path in (root / "battle" / f"{profile_id}.png", root / f"{profile_id}_battle.png"):
            path.unlink(missing_ok=True)
    for index in range(2, 7):  # the reference game's other legacy hero pictures
        (root / f"hero_{index:02d}_battle.png").unlink(missing_ok=True)
