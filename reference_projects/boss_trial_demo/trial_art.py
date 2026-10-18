"""Battle art of the Boss Trial demo, all from Foozle's CC0 packs: the Lucifer characters (see
``trial_lucifer.py``), the Pixel Magic Effects strips for the skill effects, and the Lucifer
equipment pictures for the weapon attacks.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import trial_lucifer as lucifer

REPO = Path(__file__).resolve().parents[2]
SOURCE = lucifer.SOURCE


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
        left = "hero" in tags  # the party fights facing left: its Left strips, not turned round
        image.save(battle / f"{name}.png")
        pivot_y = lucifer.feet_pivot(image, frame)
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
                    ("pivot", [0.5, pivot_y]),
                    *((("facing", "left"),) if left else ()),
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
                hud_visible="summon" not in tags,  # foes carry a name and bar; summons no panel
            ),
        )

    roles = {"idle", "attack", "cast", "guard", "hit", "ko", "revive", "status", "transform"}
    hero_states = tuple(s for s in default_jrpg_visual_states() if s.state_id in roles)
    import trial_content

    extra = tuple(BattleVisualStateDefinition(r, r) for r in lucifer.EXTRA_STATES)
    hero_states = (*hero_states, *extra)
    enemy_states = (
        *(BattleVisualStateDefinition(r, r) for r in ("idle", "attack", "cast", "hit", "ko")),
        *extra,
    )
    for name, key, tags, scale, states in (
        (context.hero_id, "warrior", ("hero",), 0.62, hero_states),
        ("hero_02", "sorceress", ("hero",), 0.62, hero_states),
        ("spirit_knight", "goblin_rider", ("hero", "summon"), 0.62, hero_states),
        (context.boss_id, "skeleton_king", ("enemy",), 1.15, enemy_states),
        ("hero_03", "necromancer", ("hero",), 0.62, hero_states),
        ("hero_04", "cultist", ("hero",), 0.62, hero_states),
        ("mender_wisp", "skeleton_grunt", ("enemy",), 0.9, enemy_states),
        ("vigil_acolyte", "skeleton_grunt", ("enemy",), 0.9, enemy_states),
        ("goblin_slinger", "goblin_slinger", ("enemy",), 0.9, enemy_states),
        ("goblin_beast", "goblin_beast", ("enemy",), 1.1, enemy_states),
        ("skeleton_hunter", "skeleton_hunter", ("enemy",), 0.9, enemy_states),
        ("skeleton_ancient", "skeleton_ancient", ("enemy",), 1.1, enemy_states),
    ):
        image, frame, clips, body = lucifer.character_sheet(
            key, facing="Left" if "hero" in tags else "Right"
        )
        register(name, image, frame, clips, tags, scale, states, body if "enemy" in tags else None)
    lucifer.field_sheet("warrior").save(out_dir / "player_field_sheet.png")
    lucifer.npc_picture("skeleton_king", size=64).save(out_dir / "boss_field.png")
    for name in trial_content.SERVICES:
        lucifer.npc_picture(lucifer.NPC_CAST.get(name, "cultist")).save(
            out_dir / f"npc_{_slug(name)}.png"
        )


def _slug(name):
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")


EFFECTS = {  # key: (Pixel Magic Effects folder, tint or None, VFX scale)
    "fire": ("Explosion", None, 1.0),
    "ice": ("Water_Geyser", ((10, 40, 100), (200, 240, 255)), 0.9),
    "thunder": ("Molten_Spear", ((60, 50, 130), (255, 255, 170)), 1.0),
    "spark": ("Wind", ((90, 70, 10), (255, 245, 120)), 0.8),
    "spirit": ("Portal", ((20, 10, 50), (190, 150, 255)), 0.8),
    "shield": ("Portal", ((10, 30, 90), (180, 220, 255)), 0.9),
    "aura": ("Portal", ((110, 70, 0), (255, 235, 140)), 0.9),
    "boost": ("Tornado", ((110, 70, 0), (255, 235, 140)), 0.7),
    "explosion": ("Explosion", None, 1.0),
    "circle": ("Portal", None, 0.9),
    "smoke": ("Tornado", None, 0.9),
    "slash": ("Wind", None, 0.8),
    "slash2": ("Wind", ((90, 0, 10), (255, 90, 90)), 0.8),
    "cut": ("Wind", None, 0.8),
    "cutx": ("Wind", ((90, 70, 10), (255, 245, 120)), 0.8),
    "cutd": ("Wind", ((90, 0, 10), (255, 90, 90)), 0.8),
    "claw": ("Wind", ((120, 30, 10), (255, 190, 90)), 0.8),
    "clawd": ("Wind", ((90, 0, 10), (255, 90, 90)), 0.8),
    "circ": ("Wind", ((120, 30, 10), (255, 190, 90)), 0.8),
}
DIRECTIONAL = {"spark", "slash", "slash2", "cut", "cutx", "cutd", "claw", "clawd", "circ"}


def effect_assets(context):
    """One VFX sprite sheet per effect kind (Pixel Magic Effects strips, tinted, 2x)."""
    from PIL import Image

    from asteria.assets.canonical import AssetSource, CanonicalAsset

    out = context.root / "playable_assets" / "battle"
    out.mkdir(parents=True, exist_ok=True)
    for key, (folder, tint, vfx_scale) in EFFECTS.items():
        frames = lucifer.effect_frames(folder, tint)
        count, side = len(frames), frames[0].width * 2
        strip = Image.new("RGBA", (side * count, side), (0, 0, 0, 0))
        for i, frame in enumerate(frames):
            strip.alpha_composite(frame.resize((side, side), Image.NEAREST), (i * side, 0))
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
                    ("frame_size", [side, side]),
                    ("pivot", [0.5, 0.5]),
                    ("vfx", {"anchor": "center", "scale": 0.5 * vfx_scale}),
                    *((("face_attacker", True),) if key in DIRECTIONAL else ()),
                ),
            ),
            replace=True,
        )


def weapon_icons(context):
    """A weapon's attack shows the weapon: the Lucifer equipment picture of each weapon is set
    on its attack ability (the weapon's own icon comes with ``trial_lucifer.apply_icons``)."""
    import shutil

    folder = context.root / "playable_assets" / "icons"
    folder.mkdir(parents=True, exist_ok=True)
    kept = []
    for equipment_id, relative in lucifer.EQUIPMENT_ICONS.items():
        if not relative.startswith("Weapons/"):
            continue
        attack = "attack_" + equipment_id[2:]
        if attack not in context.abilities.ids():
            continue
        target = f"weapon_{equipment_id[2:]}.png"
        shutil.copyfile(lucifer.EQUIPMENT / relative, folder / target)
        definition = context.abilities.get(attack)
        context.abilities._definitions[attack] = dataclasses.replace(
            definition, icon_id=f"playable_assets/icons/{target}"
        )
        kept.append(attack)
    return tuple(kept)


def write_credits(root):
    """The credits of this demo: Lucifer art and music, and the sound effects the reference game
    ships."""
    credits = Path(root) / "playable_assets" / "CREDITS.md"
    old = credits.read_text(encoding="utf-8") if credits.exists() else ""
    cc0 = "[CC0 1.0](http://creativecommons.org/publicdomain/zero/1.0/)"
    sound = [
        line
        for line in old.split("\n")
        if line.startswith("| `audio/") and "theme" not in line.split("|")[1]
    ]
    rows = [
        *lucifer.credits_rows(tuple(lucifer.PACKS)),
        *lucifer.credits_extra(),
        *lucifer.credits_music(),
        "| `battle/fx_*.png` (19 skill effects) | Foozle Pixel Magic Effects "
        "(`Foozle_2DE0001`): Explosion, Water Geyser, Molten Spear, Wind, Tornado, Portal "
        f"strips, tinted and scaled | Foozle (lordfitoi) | {cc0} |",
        *sound,
    ]
    credits.write_text(
        "# Playable assets - credits and licenses\n\n"
        "| File(s) | Source | Author | License |\n|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n\n## Licensing\n\nEvery file here is CC0 1.0. No AI-generated art.\n",
        encoding="utf-8",
    )


def prune_unused_art(context):
    """The reference game's other heroes and monsters are not part of this demo: drop their
    visuals, sheets and files so the project only holds what it uses."""
    keep = {
        context.hero_id,
        "hero_02",
        "hero_03",
        "hero_04",
        "spirit_knight",
        context.boss_id,
        "mender_wisp",
        "vigil_acolyte",
        "pet",
        "goblin_slinger",
        "goblin_beast",
        "skeleton_hunter",
        "skeleton_ancient",
    }
    library = context.project.battle_presentation_library
    # a captured wisp fights on the hero side: every pet unit (member ids "pet:...") is drawn
    # with the "pet" profile, here the same sheet as the wild wisp; no side-list panel, that list
    # is for the party's characters
    wisp = library.require("combatant_visuals", "goblin_slinger")
    library.set(
        "combatant_visuals",
        "pet",
        dataclasses.replace(
            wisp,
            profile_id="pet",
            hud_visible=False,
            # about the size of a character; pets stand in their own column (see front_large_zones)
            transform=dataclasses.replace(wisp.transform, scale_x=0.62, scale_y=0.62),
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
