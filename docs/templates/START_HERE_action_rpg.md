# Start here - Action RPG (real-time loot and skill trees)

A real-time action RPG made only from project data: a town, a top-down field and a side-view
mine, three classes with skill trees, and loot with rarities and affixes. Open it in the editor,
press **Run Project**, then change things one at a time.

## Play it

| Keys | Action |
| --- | --- |
| W A S D | move |
| J | attack (one binding per class: `w_slash\|r_shot\|m_bolt\|punch`) |
| K / Left Shift | dodge |
| 1 - 4 | skills (4 is the potion) |
| Space | jump (side view) |
| E | talk | F | pick up | L | lock on |
| B | bag (grid, compares with what you wear) | C | skill tree | Esc | pause |

Talk to a class trainer in Hollowbrook to choose Warrior, Ranger or Mage.

## Where each rule lives

The toolbar has Scene, Database, Battle, Presentation, Events, Code and Multiplayer. Database
has the tabs Game Data, Game Systems, Enemy AI, Behavior Trees, Real-Time Combat and Game Start.
Every record form ends with a **Note** for your own remarks (the game never shows it).

| You want to change | Open | Record |
| --- | --- | --- |
| An attack's damage, knockback, hit-stun | Database > Real-Time Combat > Attacks | attack records |
| A projectile (speed, pierce, sprite) | Database > Real-Time Combat > Projectiles | projectile records |
| Rarities and affixes | Database > Real-Time Combat > Loot Rarities / Loot Affixes | colours, weights, stat rolls |
| A skill's cooldown, cost, name, icon | Database > Game Data > Abilities | `cooldown_seconds`, `costs`, `display_name`, `icon_id` |
| Combos, dodges, what a skill does over time | Presentation > Ability Timelines | one timeline per ability |
| Enemy and boss behaviour | Database > Behavior Trees and Enemy AI | trees `melee_grunt`, `shooter`, `elite`, `cyclops`, `golem` |
| A status (burning, chilled...) | Database > Game Data > Status Definitions | `display_name`, `icon_id`, `modifiers`, `periodic` |
| What drops from what | Database > Game Systems > Drop Tables | tables `slime`, `eye`, `skull`... |
| Classes and skill trees | Database > Game Data > Classes / Jobs and Skill Trees | trees tagged `class:<id>` or `shared` |
| The shop and the smith's recipes | Database > Game Systems (shops) and Game Data > Crafting | shop `merchant`, station `smith` |
| Maps | Scene workspace (Tiles, Layers) | scenes `Hollowbrook`, `Greenvale Fields`, `Rustdeep Mine` |
| Keys | Presentation > Controls | the `attack`, `dodge`, `skill_1`... actions |
| The HUD | Presentation > Menu Screens > Action RPG HUD | where the orbs, bars and action bar sit; what they show comes from the project (keys, icons, resources, statuses) |

## Try these first

1. Make the Mage's firebolt free: Game Data > Abilities > `m_bolt` > `costs` (remove it).
2. Give a status another icon: Game Data > Status Definitions > `burning` > `icon_id`.
3. Change a boss: Behavior Trees > `cyclops`.
4. Make legendary drops more common: Real-Time Combat > Loot Rarities > Legendary.

The README next to this file lists every system the project shows and how it is tested.
