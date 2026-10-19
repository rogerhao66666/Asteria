"""Dress a reference project in Foozle's Lucifer art (all CC0): combatants, field pictures,
backgrounds, UI skin and font, and the icons of skills, states, gear, items and pets.

    from lucifer_reskin import Reskin
    Reskin(project, root).run(heroes={...}, enemies={...}, field={...})

The engine stays generic: this is a repository tool that edits project data (assets, presentation
library records, icon ids, manifest pictures). The packs are read from the engine's asset library
``asset_library/foozle`` (or ``ASTERIA_FREE_ASSETS``); what the projects use is copied into
their ``playable_assets``.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "reference_projects" / "full_verification_demo"
for path in (REPO / "src", DEMO):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import trial_lucifer as lucifer  # noqa: E402
import trial_maps as world  # noqa: E402

from asteria.assets.canonical import AssetSource, CanonicalAsset  # noqa: E402
from asteria.presentation.battle_combatant_visuals import (  # noqa: E402
    BattleCombatantVisualProfile,
    BattleVisualAssetSet,
    BattleVisualStateDefinition,
    BattleVisualTransform,
    default_jrpg_visual_states,
)

HERO_ROLES = {"idle", "attack", "cast", "guard", "hit", "ko", "revive", "status", "transform"}
ENEMY_ROLES = ("idle", "attack", "cast", "hit", "ko")
SOURCE = (("license", "CC0 1.0"), ("source", "Foozle Lucifer packs"))
POTIONS = {
    "health": "Health/Png/{size}HealthPotion.png",
    "mana": "Mana/Png/{size}ManaPotion.png",
    "stamina": "Stamina/Png/{size}StaminaPotion.png",
}
WEAPON_ICON = {
    "sword": "Weapons/Png/Common Arming Sword.png",
    "axe": "Weapons/Png/Common Bearded Axe.png",
    "spear": "Weapons/Png/Common Spear.png",
    "dagger": "Weapons/Png/Legendary Rapier .png",
    "staff": "Weapons/Png/Wizards Pole.png",
    "bow": "Weapons/Png/Mages Spire.png",
    "hammer": "Weapons/Png/Mythic Godhammer.png",
}
SLOT_FOLDERS = {
    "armor": "Chest",
    "body": "Chest",
    "chest": "Chest",
    "helm": "Head",
    "head": "Head",
    "boots": "Feet",
    "feet": "Feet",
    "legs": "Bottom",
    "accessory": "Misc",
    "ring": "Misc",
    "charm": "Misc",
    "amulet": "Misc",
}


class Reskin:
    def __init__(self, project, root, *, icon_dir="playable_assets/lucifer/icons"):
        self.project, self.root = project, Path(root)
        self.db = project.rpg_database
        self.library = project.battle_presentation_library
        self.icon_dir = icon_dir
        self.states = tuple(s for s in default_jrpg_visual_states() if s.state_id in HERO_ROLES)
        self.extra = tuple(BattleVisualStateDefinition(r, r) for r in lucifer.EXTRA_STATES)

    # -- combatants ------------------------------------------------------------------------
    def combatant(self, name, key, *, hero, scale=None, large=False):
        scale = (0.52 if hero else 0.5) if scale is None else scale
        facing = "Left" if hero else "Right"  # the party fights facing left
        image, frame, clips, body = lucifer.character_sheet(key, facing=facing)
        folder = self.root / "playable_assets" / "battle"
        folder.mkdir(parents=True, exist_ok=True)
        image.save(folder / f"{name}.png")
        asset_id = f"battle.combatant.{name}"
        tags = {"battle", "combatant", "hero" if hero else "enemy"}
        metadata = [
            ("clips", clips),
            ("frame_size", list(frame)),
            ("pivot", [0.5, lucifer.feet_pivot(image, frame)]),
        ]
        metadata.append(("body_height", body))
        if hero:  # the Left strips already face left: the engine does not turn them round
            metadata.append(("facing", "left"))
        self.project.assets.register(
            CanonicalAsset(
                asset_id,
                "sprite_sheet",
                AssetSource(f"playable_assets/battle/{name}.png", "project", SOURCE),
                tags=frozenset(tags),
                metadata=tuple(metadata),
            ),
            replace=True,
        )
        states = (
            self.states if hero else tuple(BattleVisualStateDefinition(r, r) for r in ENEMY_ROLES)
        )
        self.library.set(
            "combatant_visuals",
            name,
            BattleCombatantVisualProfile(
                name,
                BattleVisualAssetSet(asset_id),
                (*states, *self.extra),
                BattleVisualTransform(scale_x=scale * (1.1 if large else 1.0), scale_y=scale),
                hud_visible=True,
            ),
        )

    def combatants(self, heroes, enemies):
        """A sheet and a visual profile for every actor / enemy of the project that has a
        character listed (a project without presentation data gets its profiles here)."""
        ids = (
            set(self.library.ids("combatant_visuals")) | set(self.db.actors) | set(self.db.enemies)
        )
        for name, key in heroes.items():
            if name in ids:
                self.combatant(name, key, hero=True)
        for name, key in enemies.items():
            if name in ids:
                self.combatant(name, key, hero=False, large="king" in key or "beast" in key)

    # -- the field and the legacy pictures --------------------------------------------------
    def pictures(self, manifest_path, *, player, enemies, legacy_heroes):
        """Field sprites (the player's walk sheet, foes in view) and the legacy battle pictures."""
        assets = self.root / "playable_assets"
        lucifer.field_sheet(player).save(assets / "player_field_sheet.png")
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        for record in manifest["field"]["entity_sprites"].values():
            rel = Path(record["sprite"])
            key = enemies.get(rel.stem.removeprefix("field_")) or enemies.get(
                "astral_tyrant" if rel.stem == "boss_field" else ""
            )
            if key:
                lucifer.npc_picture(key, size=record["size"][0]).save(self.root / rel)
        for enemy, rel in manifest["battle"].get("enemy_sprites", {}).items():
            key = enemies.get(enemy)
            if key:
                lucifer.npc_picture(key, size=96).save(self.root / rel)
        for rel, key in zip(manifest["battle"].get("heroes", ()), legacy_heroes, strict=False):
            lucifer.npc_picture(key, size=96).save(self.root / rel)

    def backdrops(self, *, field="exterior", battle="exterior"):
        assets = self.root / "playable_assets"
        paint_background(field, (960, 540), road=True).save(assets / "field_map.png")
        paint_background(battle, (960, 540), road=False, dim=0.45, wall_rows=1).save(
            assets / "battle_background.png"
        )

    # -- the UI -----------------------------------------------------------------------------
    def ui(self):
        """Stone panels and the pixel font for the battle UI and the host menus; the command menu
        keeps its own place."""
        context = _Context(self.project, self.root)
        lucifer.apply_ui(context)
        for key in self.library.ids("ui_theme"):  # the older menus are narrower: a smaller face
            theme = self.library.require("ui_theme", key)
            self.library.set("ui_theme", key, dataclasses.replace(theme, font_scale=0.5))
        for key in self.library.ids("ui_layout"):
            layout = self.library.require("ui_layout", key)
            self.library.set(  # feet stay on the grass: the backdrop's wall is the top 9%
                "ui_layout",
                key,
                dataclasses.replace(
                    layout,
                    party_hud="side_list",  # Octopath: a panel per hero down the right edge
                    action_menu_placement="actor_bottom_right",  # right by who acts
                    menu_over_stage=True,  # the command menu stands see-through beside the actor
                    overhead_zones=("left",),  # foes carry their name over the head
                    overhead_bars=False,  # their health stays hidden (the bestiary tells it)
                    hidden_zones=(),
                    row_buttons=True,
                    stage_top=0.12,
                    overhead_below=False,  # enemies stand in dense columns: bars float above
                ),
            )

    # -- icons ------------------------------------------------------------------------------
    def icons(self):
        folder = self.root / self.icon_dir
        folder.mkdir(parents=True, exist_ok=True)
        rel = lambda name: f"{self.icon_dir}/{name}"  # noqa: E731

        def copy(source, name):
            shutil.copyfile(source, folder / name)
            return rel(name)

        self._gear_icons(copy)
        self._item_icons(copy)
        self._skill_icons(copy)

    def _icon_asset(self, asset_id, uri):
        """A named icon asset (the editor's pickers list these) for one copied picture."""
        self.project.assets.register(
            CanonicalAsset(
                asset_id,
                "icon",
                AssetSource(uri, "project", SOURCE),
                tags=frozenset({"icon"}),
            ),
            replace=True,
        )
        return asset_id

    def _gear_icons(self, copy):
        cycles = {}
        for equipment_id in sorted(self.db.equipment):
            record = self.db.equipment[equipment_id]
            blob = f"{equipment_id} {record.slot} {' '.join(record.tags)}".lower()
            kind = next((k for k in WEAPON_ICON if k in blob), None)
            if record.slot == "weapon" or kind:
                source = lucifer.EQUIPMENT / WEAPON_ICON[kind or "sword"]
                if kind is None:  # weapon_01 ...: the weapons of the sheet in turn
                    names = sorted(WEAPON_ICON)
                    source = lucifer.EQUIPMENT / WEAPON_ICON[names[len(cycles) % len(names)]]
                    cycles["w"] = cycles.get("w", 0) + 1
            else:
                folder = next((v for k, v in SLOT_FOLDERS.items() if k in blob), "Misc")
                files = sorted((lucifer.EQUIPMENT / folder / "Png").glob("*.png"))
                index = cycles[folder] = cycles.get(folder, -1) + 1
                source = files[index % len(files)]
            icon = self._icon_asset(
                f"icon.{equipment_id}", copy(source, f"equip_{equipment_id}.png")
            )
            self.db.equipment[equipment_id] = dataclasses.replace(record, icon_id=icon)

    def _item_icons(self, copy):
        pick = {"gem": ["Gems/Png/OrangeGem.png", "Gems/Png/BlueGem.png", "Gems/Png/PinkGem.png"]}
        for index, item_id in enumerate(sorted(self.db.items)):
            record = self.db.items[item_id]
            blob = f"{item_id} {' '.join(record.tags)}".lower()
            size = "Big" if any(w in blob for w in ("big", "elixir", "phoenix")) else "Small"
            if any(w in blob for w in ("ether", "mana", "draught", "focus", "moon")):
                rel = "Potions/" + POTIONS["mana"].format(size=size)
            elif any(w in blob for w in ("heal", "herb", "salve", "tonic", "regen")):
                rel = "Potions/" + POTIONS["health"].format(size=size)
            elif any(w in blob for w in ("stamina", "flask", "bomb")):
                rel = "Potions/" + POTIONS["stamina"].format(size=size)
            elif any(w in blob for w in ("gold", "coin", "emblem")):
                rel = "Gold/Png/PileOfGold.png"
            else:
                rel = pick["gem"][index % 3]
            icon = self._icon_asset(
                f"icon.{item_id}", copy(lucifer.PICKUPS / rel, f"item_{item_id}.png")
            )
            self.db.items[item_id] = dataclasses.replace(record, icon_id=icon)

    def _skill_icons(self, copy):
        pools = {g: lucifer._skill_pool(g) for g in lucifer.SKILL_ICON_GROUPS}
        cursor = dict.fromkeys(pools, 0)
        abilities = self.project.gameplay_library.abilities
        for ability_id in sorted(abilities.ids()):
            definition = abilities.get(ability_id)
            group = lucifer._skill_group(definition)
            pool = pools[group]
            source = pool[cursor[group] % len(pool)]
            cursor[group] += 1
            icon = copy(source, f"skill_{ability_id}.png")
            abilities._definitions[ability_id] = dataclasses.replace(definition, icon_id=icon)
        states = self.project.gameplay_library.states
        for index, state_id in enumerate(sorted(states.ids())):
            definition = states.get(state_id)
            pool = pools[("warrior", "sorceress", "necromancer")[index % 3]]
            icon = copy(pool[(index * 7) % len(pool)], f"state_{state_id}.png")
            states._definitions[state_id] = dataclasses.replace(definition, icon_id=icon)
        for species_id, species in sorted(self.db.pet_species.items()):
            icon = copy(
                lucifer.FREE_ASSETS / lucifer.UI_PACK / "Character Icons" / "Warrior Icon.png",
                f"pet_{species_id}.png",
            )
            self.db.pet_species[species_id] = dataclasses.replace(species, icon_id=icon)

    HEAVY_WORDS = ("slam", "cleave", "crush", "hammer", "bash", "charge", "smash", "whirl")

    def animations(self):
        """Each skill's swing plays the strip that fits it: a plain blow the first attack strip,
        a spell or a buff the second (cast), a finisher or heavy blow the third."""
        abilities = self.project.gameplay_library.abilities
        for key in self.library.ids("motion_sequences"):
            if key not in abilities.ids():
                continue
            definition = abilities.get(key)
            tags = set(definition.tags)
            if "divine" in tags or len(definition.hits or ()) >= 3:
                clip = "attack3"
            elif any(word in key for word in self.HEAVY_WORDS):
                clip = "attack3"
            elif "magic" in tags or any(t.startswith("damage.") for t in tags):
                clip = "attack2"
            else:
                continue
            sequence = self.library.require("motion_sequences", key)
            beats = tuple(
                dataclasses.replace(b, cue=clip)
                if b.channel == "animation" and b.cue == "attack" and b.member_id == "@source"
                else b
                for b in sequence.beats
            )
            self.library.set("motion_sequences", key, dataclasses.replace(sequence, beats=beats))

    def effects(self):
        """Battle effect strips drawn from the Foozle Pixel Magic Effects instead of any older
        picture (same asset ids, so skills keep their effects)."""
        from PIL import Image

        folders = {"slash": "Wind", "flame": "Explosion", "explosion": "Explosion"}
        for asset in self.project.assets.query("sprite_sheet", tags={"vfx"}):
            key = asset.asset_id.rsplit(".", 1)[-1]
            if key not in folders or "effects_pack" in dict(asset.metadata):
                continue
            frames = lucifer.effect_frames(folders[key])
            count, side = len(frames), frames[0].width * 2
            strip = Image.new("RGBA", (side * count, side), (0, 0, 0, 0))
            for index, frame in enumerate(frames):
                strip.alpha_composite(frame.resize((side, side), Image.NEAREST), (index * side, 0))
            target = self.root / asset.source.uri
            strip.save(target)
            meta = dict(asset.metadata)
            clips = {
                name: {**clip, "frames": list(range(count))}
                for name, clip in meta.get("clips", {}).items()
            }
            meta.update(clips=clips, frame_size=[side, side], effects_pack="pixel_magic")
            if key == "slash":
                meta["face_attacker"] = True
            self.project.assets.register(
                CanonicalAsset(
                    asset.asset_id,
                    asset.kind,
                    AssetSource(asset.source.uri, "project", SOURCE),
                    tags=asset.tags,
                    metadata=tuple(meta.items()),
                ),
                replace=True,
            )

    def run(self, *, heroes, enemies, manifest_path, field_player="warrior", legacy=()):
        self.combatants(heroes, enemies)
        self.pictures(
            manifest_path,
            player=field_player,
            enemies=enemies,
            legacy_heroes=legacy or list(heroes.values()),
        )
        self.backdrops()
        self.ui()
        self.icons()
        self.effects()
        self.animations()


class _Context:
    """What ``trial_lucifer.apply_ui`` wants of a project."""

    def __init__(self, project, root):
        self.project, self.root = project, Path(root)


def paint_background(kind, size, *, road, dim=0.0, wall_rows=5):
    """A Lucifer-tile picture the size of a field map or a battle backdrop (drawn at 3x)."""
    import random

    from PIL import Image

    rng = random.Random(7)
    width, height = size[0] // 3, size[1] // 3
    sheets = {
        "exterior": (
            "Foozle_2DT0002_Lucifer_Exterior_Tileset_Pixel_Art/Png/OuterTileset.png",
            world.EXTERIOR["grass"],
            world.EXTERIOR["path"],
            world.EXTERIOR["rock"][0],
        ),
        "dungeon": (
            "Foozle_2DT0003_Lucifer_Dungeon_Tileset_Pixel_Art/Png/DungeonTileset.png",
            world.DUNGEON["floor"],
            world.DUNGEON["carpet"],
            world.DUNGEON["wall"][0],
        ),
        "lava": (
            "Foozle_2DT0011_Lucifer_Lava_Tileset_Pixel_Art/LavaDungeonTileset.png",
            world.LAVA["floor"],
            world.LAVA["lava"],
            world.LAVA["wall"][0],
        ),
    }
    rel, ground, path, wall = sheets[kind]
    sheet = Image.open(lucifer.FREE_ASSETS / rel).convert("RGBA")
    out = Image.new("RGBA", (width, height), (0, 0, 0, 255))

    def tile(col, row):
        return sheet.crop((col * 16, row * 16, col * 16 + 16, row * 16 + 16))

    horizon = wall_rows if not road else 0  # battle backdrops have a wall of trees / stone on top
    for y in range(0, height, 16):
        for x in range(0, width, 16):
            if y // 16 < horizon:
                out.alpha_composite(tile(*wall), (x, y))
            else:
                out.alpha_composite(tile(*rng.choice(ground)), (x, y))
    if road:
        for y in range(height // 2 - 24, height // 2 + 24, 16):
            for x in range(0, width, 16):
                out.alpha_composite(tile(*rng.choice(path)), (x, y))
    if kind == "exterior" and road:  # trees stand on the field map only, never behind a fight
        top = horizon * 16 - 40 if not road else 8
        for x in range(8, width - 40, 56):
            out.alpha_composite(sheet.crop((76 * 16, 2 * 16, 80 * 16, 6 * 16)), (x, max(0, top)))
    if dim:  # a darker, quieter ground: the fighters stand out against it
        out.alpha_composite(Image.new("RGBA", out.size, (8, 12, 20, round(255 * dim))))
    return out.resize((width * 3, height * 3), Image.NEAREST)
