"""Build the reference project's canonical battle presentation fixture (CB2, D14 #1).

Usage:
    python scripts/build_reference_battle_presentation.py [FREE_ASSETS_DIR]

Writes animated combatant and effect sheets derived from the CC0 Ninja
Adventure pack to ``playable_assets/battle/`` and records them in
``project.asteria.json`` as canonical data:

* ``sprite_sheet`` canonical assets with frame size, pivot and clip metadata;
* ``combatant_visuals`` profiles (one per actor / enemy id);
* ``motion_sequences`` (one per ability id plus ``default_action``).

The project file's format version is left unchanged (only these sections are
rewritten through the canonical encoders). Output is deterministic. The only
image processing is cropping, nearest-neighbour scaling and, for hit/KO
frames without source art, a white flash / darkened copy of a source frame.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageEnhance

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from asteria.assets.canonical import AssetSource, CanonicalAsset  # noqa: E402
from asteria.assets.serialization import deserialize_asset_registry, serialize_asset_registry  # noqa: E402
from asteria.presentation.battle_combatant_visuals import (  # noqa: E402
    BattleCombatantVisualProfile, BattleVisualAssetSet, BattleVisualStateDefinition, BattleVisualTransform,
)
from asteria.presentation.battle_motion_sequence import BattleMotionBeat, BattleMotionSequence  # noqa: E402
from asteria.presentation.library import BattlePresentationLibrary  # noqa: E402
from asteria.presentation.battle_hud import BattleHudProfile, BattleHudResourceStyle  # noqa: E402

PROJECT_DIR = REPO / "reference_projects" / "complex_reference_rpg"
OUT = PROJECT_DIR / "playable_assets" / "battle"
NINJA = "ninja_adventure/extracted/Ninja Adventure - Asset Pack"
RIGHT = 3  # Ninja Adventure walk sheets: columns are down, up, left, right
SCALE = 4

HEROES = {
    "hero_01": "Hunter", "hero_02": "NinjaRed", "hero_03": "Knight", "hero_04": "SorcererOrange",
    "hero_05": "Monk", "hero_06": "NinjaBlue", "hero_07": "Samurai", "hero_08": "Princess",
    "hero_09": "NinjaGreen", "hero_10": "Caveman", "hero_11": "Villager", "hero_12": "OldMan",
}
MONSTERS = {"mender_wisp": "Monster/Flam/SpriteSheet.png", "ember_hound": "Monster/Beast/Beast.png"}
CHARACTER_ENEMIES = {"iron_guard": "Skeleton"}
BOSS = ("astral_tyrant", "Boss/DemonCyclop")
PLAYER_CHARACTER = HEROES["hero_01"]  # the party leader also walks the field
EFFECTS = {  # asset id -> (source, frame width, frame height, scale)
    "battle.fx.slash": ("FX/Slash/SpriteSheetArc.png", 38, 34, 3),
    "battle.fx.flame": ("FX/Elemental/Flam/SpriteSheet.png", 25, 30, 3),
    "battle.fx.explosion": ("FX/Elemental/Explosion/SpriteSheet.png", 40, 40, 3),
}


def _crop(image, column, row, size):
    return image.crop((column * size[0], row * size[1], (column + 1) * size[0], (row + 1) * size[1]))


def _strip(frames, scale):
    w, h = frames[0].size
    sheet = Image.new("RGBA", (w * scale * len(frames), h * scale), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        sheet.alpha_composite(frame.resize((w * scale, h * scale), Image.NEAREST), (i * w * scale, 0))
    return sheet


def _flash(frame):
    white = Image.new("RGBA", frame.size, (255, 255, 255, 255))
    mixed = Image.blend(frame, white, 0.55)
    mixed.putalpha(frame.getchannel("A"))
    return mixed


def _darken(frame):
    dark = ImageEnhance.Brightness(frame).enhance(0.45)
    dark.putalpha(frame.getchannel("A").point(lambda a: a * 3 // 4))
    return dark


def character_sheet(root, name):
    base = root / NINJA / "Actor" / "Character" / name / "SeparateAnim"
    load = lambda f: Image.open(base / f).convert("RGBA")  # noqa: E731
    cell = (16, 16)
    idle, walk, attack, dead = load("Idle.png"), load("Walk.png"), load("Attack.png"), load("Dead.png")
    frames = [_crop(idle, RIGHT, 0, cell)] + [_crop(walk, RIGHT, r, cell) for r in range(4)]
    frames += [_crop(attack, RIGHT, 0, cell), _flash(_crop(idle, RIGHT, 0, cell)), _crop(dead, 0, 0, cell)]
    clips = {
        "idle": {"frames": [0, 0, 2, 0], "frame_duration": 0.22, "loop": True},
        "attack": {"frames": [1, 3, 5, 5, 0], "frame_duration": 0.08, "loop": False, "events": {"2": ["hit"]}},
        "hit": {"frames": [6, 0, 6, 0], "frame_duration": 0.07, "loop": False},
        "ko": {"frames": [7], "frame_duration": 0.5, "loop": False},
    }
    return _strip(frames, SCALE), (16 * SCALE, 16 * SCALE), clips


def field_player_sheet(root, name, *, scale=3, frame=64):
    """Ninja Adventure walk cycle -> engine 3x4 sheet (rows down/left/right/up; stride, stand, stride)."""
    walk = Image.open(root / NINJA / "Actor" / "Character" / name / "SeparateAnim" / "Walk.png").convert("RGBA")
    source_column = {"down": 0, "left": 2, "right": 3, "up": 1}   # Walk.png columns: down, up, left, right
    pattern_row = (1, 0, 3)                                       # stride, standing, other stride
    out = Image.new("RGBA", (3 * frame, 4 * frame), (0, 0, 0, 0))
    size = 16 * scale
    for engine_row, facing in enumerate(("down", "left", "right", "up")):
        for pattern, source_row in enumerate(pattern_row):
            cell = _crop(walk, source_column[facing], source_row, (16, 16)).resize((size, size), Image.NEAREST)
            out.alpha_composite(cell, (pattern * frame + (frame - size) // 2, engine_row * frame + frame - size - 2))
    return out


def monster_sheet(root, relative):
    sheet = Image.open(root / NINJA / "Actor" / relative).convert("RGBA")
    cell = (16, 16)
    walk = [_crop(sheet, RIGHT, r, cell) for r in range(4)]
    frames = walk + [_flash(walk[0]), _darken(walk[0])]
    clips = {
        "idle": {"frames": [0, 1, 2, 3], "frame_duration": 0.16, "loop": True},
        "attack": {"frames": [0, 1, 2, 3, 0], "frame_duration": 0.07, "loop": False, "events": {"2": ["hit"]}},
        "hit": {"frames": [4, 0, 4, 0], "frame_duration": 0.07, "loop": False},
        "ko": {"frames": [5], "frame_duration": 0.5, "loop": False},
    }
    return _strip(frames, SCALE), (16 * SCALE, 16 * SCALE), clips


def boss_sheet(root, relative):
    base = root / NINJA / "Actor" / relative
    cell = (50, 50)
    idle = Image.open(base / "Idle.png").convert("RGBA")
    hit = Image.open(base / "Hit.png").convert("RGBA")
    frames = [_crop(idle, c, 0, cell) for c in range(5)] + [_crop(hit, c, 0, cell) for c in range(3)]
    frames.append(_darken(frames[-1]))
    clips = {
        "idle": {"frames": [0, 1, 2, 3, 4], "frame_duration": 0.14, "loop": True},
        "attack": {"frames": [0, 2, 4, 4, 2, 0], "frame_duration": 0.07, "loop": False, "events": {"2": ["hit"]}},
        "hit": {"frames": [5, 6, 7], "frame_duration": 0.09, "loop": False},
        "ko": {"frames": [8], "frame_duration": 0.5, "loop": False},
    }
    return _strip(frames, 2), (100, 100), clips


def effect_sheet(root, relative, fw, fh, scale):
    sheet = Image.open(root / NINJA / relative).convert("RGBA")
    count = sheet.width // fw
    frames = [_crop(sheet, c, 0, (fw, fh)) for c in range(count)]
    clips = {"play": {"frames": list(range(count)), "frame_duration": 0.06, "loop": False}}
    return _strip(frames, scale), (fw * scale, fh * scale), clips


def _asset(asset_id, path, frame_size, clips, tags, pivot=(0.5, 1.0)):
    return CanonicalAsset(
        asset_id, "sprite_sheet", AssetSource(str(path.relative_to(PROJECT_DIR)), "project",
                                               (("license", "CC0 1.0"), ("source", "Ninja Adventure Asset Pack"))),
        tags=frozenset(tags), metadata=(("clips", clips), ("frame_size", list(frame_size)), ("pivot", list(pivot))),
    )


def _profile(member_key, asset_id, scale=1.0):
    states = tuple(BattleVisualStateDefinition(role, role) for role in ("idle", "attack", "hit", "ko"))
    return BattleCombatantVisualProfile(member_key, BattleVisualAssetSet(asset_id), states,
                                        BattleVisualTransform(scale_x=scale, scale_y=scale))


def _beat(beat_id, at, channel, cue, member, **payload):
    return BattleMotionBeat(beat_id, at, channel, cue, member_id=member, payload=payload or None)


def motion_sequences():
    def offensive(sequence_id, fx, hit_at, duration, shake, flash=None):
        beats = [
            _beat("swing", 0.0, "animation", "attack", "@source"),
            _beat("fx", round(hit_at - 0.12, 3), "vfx", fx, "@target"),
            _beat("impact", hit_at, "animation", "hit", "@target"),
            _beat("sound", hit_at, "audio", "hit", "@target"),
            _beat("shake", hit_at, "camera", "shake", "@target", amplitude=shake, duration=0.18),
        ]
        if flash:
            beats.append(_beat("flash", hit_at, "screen_fx", "flash", "@target", alpha=flash, duration=0.08))
        return BattleMotionSequence(sequence_id, duration, beats)

    return (
        offensive("default_action", "battle.fx.slash", 0.24, 0.7, 4),
        offensive("strike", "battle.fx.slash", 0.24, 0.7, 4),
        offensive("fire_arc", "battle.fx.flame", 0.32, 0.9, 5, flash=40),
        offensive("meteor", "battle.fx.explosion", 0.45, 1.1, 9, flash=80),
        BattleMotionSequence("heal", 0.8, (
            _beat("raise", 0.0, "animation", "attack", "@source"),
            _beat("fx", 0.12, "vfx", "battle.fx.heal", "@target"),
            _beat("sound", 0.12, "audio", "heal", "@target"),
        )),
    )


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(argv[0]) if argv else REPO / "local_reference" / "free_assets"
    if not (root / NINJA).is_dir():
        raise SystemExit(f"Ninja Adventure pack not found under {root}")
    OUT.mkdir(parents=True, exist_ok=True)
    field_player_sheet(root, PLAYER_CHARACTER).save(PROJECT_DIR / "playable_assets" / "player_field_sheet.png")
    assets = []
    profiles = []

    def write(name, built, member_keys, tags, scale=0.5):
        image, frame_size, clips = built
        path = OUT / f"{name}.png"
        image.save(path)
        asset_id = f"battle.combatant.{name}"
        assets.append(_asset(asset_id, path, frame_size, clips, tags))
        for key in member_keys:
            profiles.append(_profile(key, asset_id, scale))

    for actor_id, name in HEROES.items():
        write(actor_id, character_sheet(root, name), [actor_id], {"battle", "combatant", "hero"})
    for enemy_id, relative in MONSTERS.items():
        write(enemy_id, monster_sheet(root, relative), [enemy_id], {"battle", "combatant", "enemy"})
    for enemy_id, name in CHARACTER_ENEMIES.items():
        write(enemy_id, character_sheet(root, name), [enemy_id], {"battle", "combatant", "enemy"})
    write(BOSS[0], boss_sheet(root, BOSS[1]), [BOSS[0]], {"battle", "combatant", "enemy", "boss"}, scale=0.8)
    for asset_id, (relative, fw, fh, scale) in EFFECTS.items():
        image, frame_size, clips = effect_sheet(root, relative, fw, fh, scale)
        path = OUT / f"{asset_id.rsplit('.', 1)[-1]}.png"
        image.save(path)
        assets.append(_asset(asset_id, path, frame_size, clips, {"battle", "vfx"}, pivot=(0.5, 0.5)))
    # The procedural heal sheet (4 x 4 frames of 64 px) already ships with the project.
    heal = PROJECT_DIR / "playable_assets" / "fx_heal.png"
    assets.append(CanonicalAsset(
        "battle.fx.heal", "sprite_sheet", AssetSource(str(heal.relative_to(PROJECT_DIR)), "project",
                                                       (("license", "repository"),)),
        tags=frozenset({"battle", "vfx"}),
        metadata=(("clips", {"play": {"frames": list(range(16)), "frame_duration": 0.04, "loop": False}}),
                  ("frame_size", [64, 64]), ("pivot", [0.5, 0.5])),
    ))

    project_path = PROJECT_DIR / "project.asteria.json"
    data = json.loads(project_path.read_text(encoding="utf-8"))
    registry = deserialize_asset_registry(data["assets"])
    for asset in assets:
        registry.register(asset, replace=asset.asset_id in {a.asset_id for a in registry.snapshot()})
    data["assets"] = serialize_asset_registry(registry)
    library = BattlePresentationLibrary.from_data(data["battle_presentation_library"])
    for profile in profiles:
        library.set("combatant_visuals", profile.profile_id, profile)
    for sequence in motion_sequences():
        library.set("motion_sequences", sequence.sequence_id, sequence)
    # Side-view staging: party HUD as a bottom row, enemy bars over their heads,
    # commands beside the acting hero, combatants on the ground below the horizon.
    from dataclasses import replace
    layout = library.require("ui_layout", "adaptive")
    library.set("ui_layout", "adaptive", replace(layout, party_hud="bottom_row", overhead_zones=("left",),
                                                 action_menu_placement="actor", stage_top=0.44))
    library.set("hud", "adaptive", BattleHudProfile(
        resources=[BattleHudResourceStyle("vitality", "HP", order=0, priority=10),
                   BattleHudResourceStyle("technique", "SP", order=1, priority=5)],
        show_unmapped_resources=True,
    ))
    data["battle_presentation_library"] = library.to_data()
    project_path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(assets)} sprite sheet assets, {len(profiles)} combatant profiles to {project_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
