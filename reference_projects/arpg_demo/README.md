# Asteria ARPG Demo (D22 A10)

A small Diablo-like action RPG built **only from project data**. The engine knows nothing about
Diablo: the same systems build a soulslike, a twin-stick shooter or a platformer brawler. Diablo
is the example because it is the best-known ARPG.

```bash
python reference_projects/arpg_demo/build_project.py              # rebuild (idempotent)
python -m asteria.runtime.preview reference_projects/arpg_demo/project.asteria.json
python scripts/arpg_demo_live_check.py warrior OUT_DIR            # scripted real-window check
```

## What is in it

| Area | Where it lives in the data |
| --- | --- |
| **Hollowbrook** (town, top-down): merchant, smith, three class trainers, elder | scene `Hollowbrook`; NPC event programs `npc.*` |
| **Greenvale Fields** (top-down): slimes, watchers that shoot, an elite pack, the Cyclops boss | scene `Greenvale Fields`; behavior trees `melee_grunt`, `shooter`, `elite`, `cyclops` |
| **Rustdeep Mine** (side view): platforms, one-way ledges, a ladder, crawlers, bats, drones, the Rust Golem | scene `Rustdeep Mine`; `Ledge *` / `Ladder *` colliders; trees `walker`, `drone`, `golem` |
| Classes: Adventurer → Warrior / Ranger / Mage | `rpg_database.classes`; a trainer runs `SET_CLASSES` |
| Skill trees: one per class plus shared Attributes | `progression_graphs` tagged `class:<id>` or `shared`; 2 AP per level |
| One control scheme for every class | the player's `ActionCombat.bindings`: `attack=w_slash\|r_shot\|m_bolt\|punch` - the first known ability is used |
| Skills (combo, whirlwind, leap, war cry; shot, volley, pierce, tumble; firebolt, nova, meteor, blink) | `gameplay_library` timelines, abilities, attacks, projectiles |
| Loot: Common / Magic / Rare / Legendary with random affixes, a 3-piece set, uniques | `rarities`, `affixes`, `equipment_sets`; uniques and set pieces carry a `rarity:<id>` tag |
| Potions are items an ability spends | ability `potion` costs `item:potion`; the smith brews them, the merchant sells them |
| Crafting parts and gold | drop tables `slime`, `eye`, `skull`, ...; shop `merchant`; recipes `brew_*` at station `smith` |

Controls: WASD move, J attack, K dodge, 1-4 skills (4 = potion), Space jump (side view), E talk,
F pick up, B bag (a grid with a tooltip that compares stats with what you wear and shows set
bonuses), C skill tree, Esc pause. Beaten bosses stay dead after save and load
(`defeat_switch`); each class has its own look (`ClassAppearance`); the mine has parallax
backdrops (`ParallaxBackground2D`); the camera looks ahead (`camera_look_ahead`).

## Engine features this demo needed (all generic)

- Tile-map scenes in the playable runtime (`runtime/tile_scene_view.py`): layers below / above
  characters, directional `idle_* / walk_* / attack_*` clips, a camera that follows the player,
  tile walls that block controllers, AI and projectiles, projectile sprites.
- Binding alternatives (`a|b|c`), the `SET_CLASSES` world command, the skill tree screen,
  `item:<id>` ability costs, hitbox cues that reshape the hitbox (AoE swings), `apply_state` on
  gameplay-event cues (self buffs), fixed rarities by tag, short loot names.
- The grid bag screen, `ClassAppearance`, `ParallaxBackground2D`, `defeat_switch`, chunked tile
  rendering (a map of any size costs only what the camera sees).

## Art

All CC0: Ninja Adventure (characters, monsters, top-down tiles), Kenney Pixel Platformer
(side-view tiles and mine enemies) and Kenney Tiny Dungeon (weapon and potion icons). See `playable_assets/CREDITS.md`. No AI-generated art.
