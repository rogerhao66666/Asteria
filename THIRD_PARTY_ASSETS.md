# Third-party assets

Downloaded packs live in the git-ignored `local_reference/free_assets/<pack>/`
(`download/` = original archive, `extracted/` = contents). Only files listed as
"In repo" below are committed. Verified 2026-10-09 from each pack's page and
bundled license file.

| Pack | Author | Source URL | License | Redistribution | Commercial use | Repository inclusion | Intended usage |
|---|---|---|---|---|---|---|---|
| Ninja Adventure – Asset Pack (89 MB) | Pixel-boy, AAA | https://pixel-boy.itch.io/ninja-adventure-asset-pack | CC0 1.0 (`LICENSE.txt`) | Allowed | Allowed | **In repo**: 6 audio files (`playable_assets/audio/`) and derived battle sheets (`playable_assets/battle/`: 15 combatant sheets from `Actor/Character`, `Actor/Monster`, `Actor/Boss/DemonCyclop` and 3 effect sheets from `FX/Slash`, `FX/Elemental`; cropped and scaled, hit/KO frames are flashed/darkened copies of source frames) built by `scripts/build_reference_battle_presentation.py`; rest local only | Asset Pipeline, animation, VFX, audio, battle presentation, runtime tests; minimal reference project |
| Kenney Roguelike/RPG Pack | Kenney | https://kenney.nl/assets/roguelike-rpg-pack | CC0 1.0 | Allowed | Allowed | Local only | Tilemap / pipeline tests |
| Kenney RPG Base | Kenney | https://kenney.nl/assets/rpg-base | CC0 1.0 | Allowed | Allowed | Local only | Tilemap / pipeline tests |
| Kenney UI Pack | Kenney | https://kenney.nl/assets/ui-pack | CC0 1.0 | Allowed | Allowed | Local only | Battle/runtime UI tests |
| Kenney UI Pack: RPG Expansion | Kenney | https://kenney.nl/assets/ui-pack-rpg-expansion | CC0 1.0 | Allowed | Allowed | Local only | Battle/runtime UI tests |
| Kenney Impact Sounds | Kenney | https://kenney.nl/assets/impact-sounds | CC0 1.0 | Allowed | Allowed | Local only | Audio runtime tests (CB6) |
| Kenney Interface Sounds | Kenney | https://kenney.nl/assets/interface-sounds | CC0 1.0 | Allowed | Allowed | Local only | Audio runtime tests (CB6) |
| Kenney UI Audio | Kenney | https://kenney.nl/assets/ui-audio | CC0 1.0 | Allowed | Allowed | Local only | Audio runtime tests (CB6) |
| Kenney RPG Audio | Kenney | https://kenney.nl/assets/rpg-audio | CC0 1.0 | Allowed | Allowed | Local only | Audio runtime tests (CB6) |
| Kenney Tiny Town | Kenney | https://kenney.nl/assets/tiny-town | CC0 1.0 | Allowed | Allowed | **In repo** (derived): `reference_projects/complex_reference_rpg/playable_assets/` | Reference project field/battle backgrounds |
| Kenney Tiny Dungeon | Kenney | https://kenney.nl/assets/tiny-dungeon | CC0 1.0 | Allowed | Allowed | **In repo** (derived): same folder | Reference project heroes/enemies |
| Idylwild's Arsenal (122.9 KB, 50 weapon icons 32x32) | Idylwild | https://opengameart.org/node/171012 (also https://idylwild.itch.io/idylwilds-arsenal) | CC0 1.0 (per the OpenGameArt page; the zip has no license file); author states no AI tools were used | Allowed | Allowed | **In repo** (copied unmodified, 8 icons): `reference_projects/boss_trial_demo/playable_assets/icons/weapon_*.png`; source pack at `local_reference/free_assets/idylwilds_arsenal/` | Weapon icons of the Boss Trial demo |
| Foozle Lucifer characters (Warrior, Sorceress, Skeleton Grunt, Skeleton King, Goblin Slinger; more downloaded: Necromancer, Cultist, Goblin Beast/Berserker/Rider, Skeleton Ancient/Hunter) | Foozle (commissioned from Baldur) | https://foozlecc.itch.io/ (`Foozle_2DC0009`-`2DC0021`) | CC0 1.0 (Readme.txt of every pack) | Allowed | Allowed | **In repo** (re-cut): `reference_projects/{boss_trial_demo,octopath_demo,complex_reference_rpg}/playable_assets/battle/*.png`, `player_field_sheet.png`, `npc_*.png`, and the packaged `party_rpg` / `basic_rpg` templates; source packs in `~/Downloads/free_assets` | Battle and field art of the Boss Trial demo |
| Foozle Lucifer Equipment, Pickups, RPG UI (panels, button, font, skill icons) | Foozle (commissioned from Baldur) | https://foozlecc.itch.io/ (`Foozle_2DS0005`, `Foozle_2DS0006`, `Foozle_UI_0002`) | CC0 1.0 (Readme.txt of every pack) | Allowed | Allowed | **In repo** (copied unmodified): `reference_projects/{boss_trial_demo,octopath_demo,complex_reference_rpg}/playable_assets/lucifer/` and the party templates | Icons, UI skin and font of those demos |
| LPC Base Assets | Liberated Pixel Cup contributors | https://opengameart.org/content/liberated-pixel-cup-lpc-base-assets-sprites-map-tiles | CC-BY-SA 3.0 / GPL 3.0 | Allowed with attribution + share-alike | Allowed with attribution + share-alike | **Not in repo** (the field player sheet derived from `soldier.png` was replaced with a CC0 Ninja Adventure character; the bald soldier is gone) | Local only |
| Free Pixel Art Asset Pack | Xiao Su Zao Shui (xiaosuzaoshui) | https://xiaosuzaoshui.itch.io/pixel-art | Royalty-free personal/commercial use, modification allowed; **"Redistribution is prohibited"** (no resale, no inclusion in competing products) | **Not allowed** — verification status: NOT CLEARED | Allowed (in a game) | **Local only — never commit or package** | Local battle-animation tests (idle/run/attack/hurt/death) |

Rules: copy only the minimum files a test or reference project needs, record
each committed file's source in a `CREDITS.md` next to it, and keep share-alike
(CC-BY-SA) files clearly separated. Using these packs does not change the
canonical SPEC or scope; the JRPG Demo remains deferred until SPEC closure.
