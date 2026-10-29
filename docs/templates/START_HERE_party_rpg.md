# Start here - Party RPG (break and boost battles)

This project is a finished turn-based battle game made only from project data. Open it in the
editor, press **Run Project**, then change things one at a time. Everything below is a record you
can edit; nothing is hard-coded in the engine.

## Play it

| Keys | Action |
| --- | --- |
| Up / Down | choose a command or target |
| Tab | switch Skills / Items |
| Left / Right | raise / lower the boost level (a boost point is gained every turn) |
| Enter / Esc | confirm / go back |
| Esc (field) | pause menu (its entries and their order: Database > Game Systems > Pause Menu) |

## Where each rule lives

The toolbar has Scene, Database, Battle, Presentation, Events, Code and Multiplayer. Database
has the tabs Game Data, Game Systems, Enemy AI, Behavior Trees, Real-Time Combat and Game Start.
Every record form ends with a **Note** for your own remarks (the game never shows it).

| You want to change | Open | Record |
| --- | --- | --- |
| Weaknesses, resistances, absorb, reflect, Break x2 | Battle > Damage Interactions | the interaction rules |
| An enemy's shields, weaknesses, immunities | Database > Game Data > Enemies / Bosses | `resources.shield` and its `weak.*` / `resist.*` / `immune.*` tags |
| What enemies do | Database > Enemy AI | one set of moves per enemy |
| Poison, sleep, silence rules (chance, immunity) | Battle > Status Effects | the battle policies |
| A status itself (duration, effect, name, icon) | Database > Game Data > Status Definitions | `display_name`, `icon_id`, `modifiers`, `periodic` |
| A skill: cost, hits, states, summons, pet | Database > Game Data > Abilities | `battle_costs`, `hits`, `apply_states`, `commands`, `requires_pet` |
| A job and the skills it gives | Database > Game Data > Classes / Jobs | `granted_abilities` |
| What a weapon gives | Database > Game Data > Equipment | `granted_abilities` and the `equip.*` tag |
| Concoctions (ingredient mixes) | Database > Game Data > Crafting / Alchemy | recipes of station `concoct`; the item's `battle_ability` |
| A pet species (stats, growth, experience) | Database > Game Systems > Pet Species | `stats`, `growth`, `exp_base`, `exp_per_battle` |
| Which enemy can be captured as a pet | Database > Game Systems > Capture Rules | `Becomes Owned Pet`, `Pet Starts At Level` |
| Where enemies stand and wander | Scene workspace | entities with Visible Encounter + Field AI |
| The party, bag and pets you start with | Database > Game Start | scene, facing, position, party, bag, currencies, pets |
| What a tag or a stat means, and who reads it | Database > Game Systems > Tags / Stats | a definition per tag or stat |
| The pause menu and its pages | Database > Game Systems > Pause Menu | the order, the pages' blocks, event entries |
| Where a menu's parts sit on screen | Presentation > Menu Screens | one layout per screen |

## Try these first

1. Give a skill one more hit: Game Data > Abilities > `grand_inferno` > `hits` (add one more
   `{"tags": ["damage.fire"]}`).
2. Make the boss weaker to spears: Enemies / Bosses > `astral_tyrant` tags (add `weak.spear`).
3. Add a new pet: Game Systems > Pet Species > New, then a Capture Rule on an enemy, then an
   ability with `requires_pet` set to the species id and a damage formula reading `pet_power`.
4. Change how fast pets level: Pet Species > `exp_base` (experience to level up = this x level).

The README next to this file lists every mechanic the project shows and how it is tested.
