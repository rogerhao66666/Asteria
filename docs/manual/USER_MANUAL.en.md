# Asteria User Manual

**For game authors.** This manual explains how to make a game with the Asteria editor and
engine: start the editor, build maps and events, fill the database, set up battles, menus,
dialogue, controls and translations, then play-test and export. The last chapter lists the
Python API you can use from scripts.

- Version: engine and editor as of 2026-10-29 (decision log D100, plus record notes).
- The same manual in Traditional Chinese: [USER_MANUAL.zh-TW.md](USER_MANUAL.zh-TW.md).
- Every picture is a real screen: editor pictures come from the editor window on macOS (Cocoa)
  with the Full Verification demo open; game pictures are real frames of the game window.
- Engine developers should read [`docs/ENGINE_HANDBOOK.md`](../ENGINE_HANDBOOK.md) instead.

## Contents

1. [What Asteria is](#1-what-asteria-is)
2. [Installing and starting the editor](#2-installing-and-starting-the-editor)
3. [Projects: new, open, save](#3-projects-new-open-save)
4. [The editor window](#4-the-editor-window)
5. [Maps and the field](#5-maps-and-the-field)
6. [Events and event programs](#6-events-and-event-programs)
7. [The database](#7-the-database)
8. [Battles](#8-battles)
9. [Menus and screens](#9-menus-and-screens)
10. [Dialogue and choices](#10-dialogue-and-choices)
11. [Input and controls](#11-input-and-controls)
12. [Translations](#12-translations)
13. [Play-testing, saving and exporting](#13-play-testing-saving-and-exporting)
14. [The reference projects](#14-the-reference-projects)
15. [Python API for authors](#15-python-api-for-authors)

---

## 1. What Asteria is

Asteria is a 2D RPG engine written in Python (pygame-ce) with an editor written in PySide6.
Everything a game is made of is **data in the project file**, edited in the editor: maps,
characters, skills, items, enemies, battle rules, screen layouts and translations. The engine has
no game of its own built in; the demos are only example data. You can make:

- turn-based party battles (side view, weaknesses, shields and boosts),
- creature battles (catch, party of creatures, the Pokémon-style screen),
- real-time action RPGs (top-down or side-scrolling, with loot and skill trees),
- anything in between, because rules are options, not code.

When the editor does not offer something, a Python script in the **Code** workspace can do it
(chapter 15 lists the API).

Three words used throughout:

| Word | Meaning |
| --- | --- |
| **Project** | One `project.asteria.json` and its folder (art, music, `playable_test_manifest.json`, `saves/`). |
| **Record** | One entry in the database: an actor, a skill, an item, an enemy, an encounter… Every record has a fixed internal ID and a name. |
| **Event program** | A list of commands (dialogue, choices, switches, world commands) that runs when the player talks to someone, steps somewhere, or a battle moment comes. |

---

## 2. Installing and starting the editor

> **No Python?** Download the standalone app instead: it carries the editor, playtesting and
> export, and games exported from it run without Python too. See
> [STANDALONE_APP.md](../STANDALONE_APP.md). The steps below are for a source install.

You need Python 3.12 or newer (3.13 works). From the Asteria folder:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[pygame,editor,mv,dev]"
```

Start the editor:

```bash
.venv/bin/asteria-editor
```

The first start opens your own copy of the **Full Verification** demo (a whole small game to
learn from). The copy lives in your user data folder, so the reference project is never changed.

Other commands you will use:

```bash
.venv/bin/asteria-preview path/to/project.asteria.json
.venv/bin/asteria-export path/to/project.asteria.json OUTPUT_FOLDER --pyz
.venv/bin/asteria-export-web path/to/project.asteria.json OUTPUT_FOLDER --serve
```

`asteria-preview` plays a project without the editor; the two export commands are explained in
chapter 13. Optional: `.venv/bin/python -m asteria.kernels.build_native` compiles the C++ speed-ups
once (the engine also runs without them).

> Quiet runs: set `ASTERIA_MUTE=1` to play without sound (for automated checks), or add
> `?mute=1` to a web build's address.

---

## 3. Projects: new, open, save

### 3.1 A new project

**File ▸ New Project…** (Ctrl+N) copies a template into a new folder and opens it. The
dialog asks for the template, then the project name, then the folder.

![File menu](images/editor_en_menu_file.png)

![New project: choose a template](images/editor_en_dialog_new_project.png)

| Template | What you get |
| --- | --- |
| Full Verification (Recommended) | A whole game to learn from: four maps, a town with shops, a party of four with jobs and skill trees, elements, shields and Breaks, bosses, quests, crafting and every editor page filled in. |
| Basic RPG (Small) | One hero, two enemies, Attack, Fire and Heal; a playable field and basic battles. |
| Party RPG (break and boost battles) | Weaknesses and shields, boost points, jobs, a pet, concoction, statuses and four enemy types. |
| Action RPG (real-time loot and skill trees) | Real-time combat with classes and skill trees, loot with rarities and affixes, potions, a grid bag, an action bar with cooldowns. |
| Completely Empty | No sample data. |

The whole template folder is copied, including its art and licence files. If the project has a
`START_HERE.md`, the **Console** panel shows it (it says where each rule lives in the editor).

### 3.2 Open, save, import

| Menu item | Shortcut | Does |
| --- | --- | --- |
| File ▸ Open Project… | Ctrl+O | Open a `*.asteria.json` file. |
| File ▸ Save | Ctrl+S | Save the project. |
| File ▸ Save As… | Ctrl+Shift+S | Save under a new file name. |
| File ▸ Import RPG Maker MV Project… | | Convert an RPG Maker MV project folder into a new Asteria project. |
| File ▸ Import from Asset Library… | | Copy art from the bundled CC0 `asset_library/` into the project (shows each pack's licence; one undo step). |
| File ▸ Export Game… | | Chapter 13. |

On macOS the shortcuts use ⌘ instead of Ctrl.

### 3.3 What is in a project folder

| Path | Contents |
| --- | --- |
| `project.asteria.json` | The project: scenes, database, rules, layouts, events, translations. |
| `playable_assets/` (or other folders) | Art, music, fonts the project uses. |
| `playable_test_manifest.json` | Game-folder settings (title, field and battle look). Edit it with **Run ▸ Game Folder Settings…**, not by hand. |
| `saves/` | The player's saves (`slot1.asteria-save.json`…, `playtest_autosave.asteria-save.json`). |
| `scripts/` | Your Code workspace scripts. |

---

## 4. The editor window

![The editor with the Scene workspace](images/editor_en_scene.png)

- **Menu bar**: File, Edit, View, Prefab, Run, Help.
- **Workspace bar**: Scene, Database, Battle, Presentation, Events, Code, Multiplayer
  (Ctrl+1 … Ctrl+7, also under View ▸ Workspace), then **Run Project**, **Stop** and
  **Reset View**.
- **Panels** (docks): Project, Tiles, Layers on the left; Inspector on the right; Assets,
  Console, Debugger, Profiler, Problems at the bottom. View ▸ Panels reopens a closed panel and
  View ▸ Reset Layout puts them all back.

| Workspace | What you edit there |
| --- | --- |
| Scene | Maps: tiles, entities, prefabs (chapter 5). |
| Database | Game Data, Game Systems, Enemy AI, Behavior Trees, Real-Time Combat, Game Start (chapter 7). |
| Battle | Battle rules: resources, statuses, turn order, escape, victory… (chapter 8). |
| Presentation | Battle Screen, Menu Screens, animations, effects, Controls (chapters 8, 9, 11). |
| Events | Entity Events, Interaction Overview, Common & Battle Events (chapter 6). |
| Code | Python scripts that edit the project (chapter 6.6, 15). |
| Multiplayer | A local server and guest testing for network games. |

![View menu](images/editor_en_menu_view.png)
![Edit menu](images/editor_en_menu_edit.png)
![Help menu](images/editor_en_menu_help.png)

**How editing works everywhere**

- Every change can be undone: Edit ▸ Undo (Ctrl+Z) and Redo (Ctrl+Shift+Z), or the Undo / Redo
  buttons at the bottom of each page.
- Record forms apply a change by themselves a moment after you stop typing (about a third of a
  second); a value the engine refuses is shown in red and not applied.
- Help text is in tooltips: hover the **ⓘ** mark next to a field or section.
- View ▸ Theme switches the colour palette; View ▸ Language switches the editor's language
  (chapter 12).
- Help ▸ Controls and Shortcuts lists the viewport and play shortcuts.

---

## 5. Maps and the field

### 5.1 Scenes

Each map is a **scene**. The **Project** panel lists the scenes, prefabs and assets. Use Edit ▸
Add Scene…, Delete Scene, Set as Startup Scene and Rename… (F2) on the selected scene. A new
game starts where **Database ▸ Game Start** says (7.5); the startup scene is used when Game
Start names no scene.

### 5.2 Painting tiles

Open the **Tiles** panel. It shows the whole tile set; click one tile or drag over a block of
tiles, then paint on the map. While you hold the button the tiles appear on the map; letting go
is one undo step.

| Tool | Key |
| --- | --- |
| Select | S |
| Paint | B |
| Fill | G |
| Rectangle | R |
| Erase | E |
| Pick a tile from the map | right click |
| Brush size smaller / bigger | `[` / `]` |

**Terrain**, **Region** and **Doodad** in the same panel paint auto-tiling terrain, map regions
and decorations. The **Layers** panel chooses the layer you paint on (ground, walls, collision…).

Viewport: the mouse wheel zooms round the cursor; arrow keys pan (or move the selected entity,
Shift for bigger steps); a trackpad pans with two fingers and zooms by pinching; Ctrl+0 resets
the view. View ▸ Show Hit & Hurt Boxes draws real-time combat boxes.

### 5.3 Entities, components and prefabs

Everything placed on a map (the player, people, doors, chests, the camera) is an **entity** made
of **components**. Select it in the map or in the Project panel; the **Inspector** shows every
component as its own section (rename it and turn it on or off at the top).

| Edit menu | Does |
| --- | --- |
| Add Entity… | A new empty entity. |
| Place Character from Sprite Sheet… | A walking character from a sprite sheet. |
| Set Actor Appearance… | Use an actor's look for the selected entity. |
| Add Component… | Add a component (collision, interaction, encounter, light…). |
| Copy / Cut / Paste / Duplicate Entity (Ctrl+D) | |
| Enable / Disable Entity (Ctrl+E) | |
| Delete Selected (Delete) | |

The **Prefab** menu turns an entity into a reusable prefab (Create Prefab from Selected
Entity…), places it (Place Prefab…), and pushes or reverts instance changes.

### 5.4 Map areas

**Database ▸ Game Systems ▸ Map Areas (regions, hazards)** gives regions of a map their own
rules: music, an area name sign, random encounters per step, floor damage, slippery floors,
footstep sounds, restricted passage and an event when the player enters.

---

## 6. Events and event programs

### 6.1 Entity events

Select a person or object in the Scene workspace, then open **Events ▸ Entity Events**.

![Entity Events](images/editor_en_events_entity.png)

- The top list holds the entity's events; **+ Event** adds one.
- **Trigger**: when it runs. `Action` (the player faces it and presses the interact key),
  `Autorun` (runs by itself, blocking the player) or `Parallel` (runs alongside play). Touch and
  click triggers are set on the entity's interaction component.
- **Program**: which event program runs. Several events can share one program.
- **Conditions**: when the event is available (**+ Condition**: a switch, a variable, an NPC
  state, a party fact…). "Conditions: Always" means none.
- **Commands**: the program's commands. The buttons below add **Dialogue**, **Choice**,
  **Wait**, **If**, **Switch**, **Variable**, **World** and **Sequence…**; the arrows move the
  selected command and **Delete** removes it. Double-click a command to edit it.

### 6.2 What commands do

| Command | Does |
| --- | --- |
| Dialogue | A message with a speaker and an optional portrait (chapter 10). |
| Choice | A question with options; the answer goes into a variable (chapter 10). |
| Wait | Wait some seconds, or until a condition holds (a switch, a variable, a battle, a sound…). |
| If | Run the next commands only when a condition holds. |
| Switch | Turn a switch (an on/off flag saved with the game) on or off. |
| Variable | Set, add to or copy a variable (a number or text saved with the game). |
| World | One of the engine's world commands: start a battle, give an item, move to another map, open a shop, play music, move the camera, join the party, walk somewhere… The full list with arguments is in 15.16. |
| Sequence… | A cutscene: parallel tracks of moves, facing, animations, lines and world commands; can be skippable. |

Switches and variables are shared by all events and are saved with the game.

### 6.3 Interaction Overview

**Events ▸ Interaction Overview** lists, map by map, everything the player can interact with;
pick one to see its binding, the program it starts and its interaction (range, facing), so you
can check a whole town at once.

![Interaction Overview](images/editor_en_events_overview.png)

### 6.4 Common and battle events

**Events ▸ Common & Battle Events** holds programs that do not belong to one entity
(**New Program…** makes one):

- **Common events**: reusable programs with a trigger: `call` (only when another program calls
  it), `autorun` or `parallel` (run while their switch is on).
- **Battle events**: **When** (the battle starts, a new round starts, the battle ends…),
  **Program** and **Only if** conditions (for example `battle hp_ratio:<enemy> <= 0.5` for a
  wounded boss).

![Common and battle events](images/editor_en_events_common.png)

### 6.5 Example

The Full Verification demo's guildmaster (Hearthfold ▸ *Guildmaster Orla*) shows a typical
program: a **Choice** ("Companions wait here until you hire them. Anything else?"), **If**
branches for each answer, a **World** `LEAVE_PARTY`, a **Switch** and a **Dialogue** line.

### 6.6 Scripts (Code workspace)

![Code workspace](images/editor_en_code.png)

**Code** runs Python against the open project. Write in `scripts/main.py` (or **New
Script…**), then **Run** (Ctrl+Enter). The script sees `project`, `selected`, `scene` and
`entity`; the Authoring API box on the right is a short reminder. All changes of one run are a
single undo step, and a failing script is rolled back with its error in **Traceback**.

```python
town = project.scene("Hearthfold")
lina = town.create_entity("Lina", x=160, y=96)
lina.event("Greeting").dialogue("Lina", "Hello!").set_switch("met_lina").end()
```

---

## 7. The database

**Database** has six tabs: Game Data, Game Systems, Enemy AI, Behavior Trees, Real-Time Combat
and Game Start.

### 7.1 Record pages

![Game Data: Actors](images/editor_en_gamedata_actors.png)

Every record page works the same way:

- The drop-down at the top right chooses the category (Actors, Abilities, Items…).
- The list on the left shows names and icons; **Filter records…** searches names and IDs; the
  sort box orders by ID or name. Hover a row to see its internal ID.
- The form on the right: name and icon at the top, the internal ID below it (it never changes;
  use **Duplicate…** to make a copy with a new ID). Numbers, switches, drop-downs that pick other
  records (with icons), tag chips and cards for lists. Empty optional fields are folded under
  "Show N more fields"; internal fields are under **Advanced**.
- **Duplicate…** and **Delete** at the bottom; edits apply by themselves.
- **Note** is the last box of every form: write anything for yourself or your team there. Notes
  stay in the project file and never reach the game.
- **Players See It** sits next to a description. Untick it and the description stays in the
  editor only; a description the game never shows is labelled "(editor only)". The game shows
  the descriptions of skills, items, equipment, jobs, enemies (in the bestiary), quests,
  achievements, quest boards, gacha banners, stats, tags and equipment slots.

### 7.2 Game Data categories

| Category | What it holds |
| --- | --- |
| Actors | Playable characters: base stats, tags, abilities, classes, equipment, look. |
| Classes / Jobs | Jobs: growth per level, abilities, points per level. |
| Abilities | Skills: targeting, costs, conditions, hits, effects, states, cooldowns, menu group. |
| Status Definitions | Statuses (poison, sleep, buffs…): duration, stacking, ticks, icon. |
| Passives | Always-on effects. |
| Progression Tracks, Skill Trees, Ability Evolutions | Levels, skill trees (with a graph view) and skills that turn into stronger ones. |
| Items, Equipment, Attachments, Equipment Growth | Consumables, gear, gems / cards, gear growth paths. |
| Crafting / Alchemy | Recipes. |
| Party Setups, Formations, Party Menu Rules | Party size and rows. |
| Enemies / Bosses, Encounters, Enemy AI / Boss Phases | Foes, the groups you fight, how they act. |
| Field Action Timelines, Attacks, Projectiles | Real-time combat moves. |
| Loot Rarities, Loot Affixes | Random loot (action RPGs). |

![Classes / Jobs](images/editor_en_gamedata_classes.png)
![Abilities](images/editor_en_gamedata_abilities.png)
![Items](images/editor_en_gamedata_items.png)
![Enemies / Bosses](images/editor_en_gamedata_enemies.png)
![Encounters](images/editor_en_gamedata_encounters.png)

**Encounters** are what a battle starts: the enemy members, their rows, rewards and tags (for
example `rules:<id>` to use other battle rules). A field enemy, a map area or a `START_ENCOUNTER`
world command names the encounter.

**Skill Trees** open as a graph: icon cards with arrows. Drag cards and press **Save Graph
Layout**; **List / Data View** shows the form.

![Skill tree graph](images/editor_en_gamedata_skilltree.png)

### 7.3 Game Systems

**Game Systems** holds the project-wide rules, one kind at a time (drop-down at the top left):
Stats, Stat Formulas (derived stats), Tags, Job Points, Ability Slots, Pause Menu, Equipment
Slots, Equipment Sets, Weapon Refine (+N), Equipment Durability, Disassembly, Battle Options,
Battle Extras (taunt, steal, TP...), Enemy Levels, Capture Rules, Drop Tables, Pet Species, Pet
Rules (creature party), Recruiting Offices, Shops, Quests, Quest Boards, Factions, Achievements,
World Interactions, Map Areas (regions, hazards), Workstations (crafting), Gacha Banners,
Inventory Rules, Message Settings, Music Room, Credits, Translations, Doodads and New Game Plus.

![Game Systems: Shops](images/editor_en_systems_shops.png)

**Stats and Tags say what every number and tag means.** Each stat has a short name (STR), how it
is written (a number, a percentage…), where its base value is set and what it means; each tag
(or a whole family such as `weak.*`) has a name and a meaning. The card under the form lists who
carries the tag or gives the stat, step by step in the order the game adds them up, and every
rule or formula that reads it, with the page where each one is edited. Once a project defines
its stats and tags, the **Problems** panel lists any tag or stat used without a definition.

![Game Systems: Tags](images/editor_en_systems_tags.png)

**Formulas.** Fields that take a formula (a stat formula, a chance check, an escape chance, the
turn order, the final damage, a skill's value) only accept names declared under Stats. Type the
formula, or insert names with the `source ▾`, `target ▾` or `self ▾` buttons, the functions
menu and the operator buttons. The line below says which names it reads, or what is wrong; a
wrong formula is not applied, and an empty one falls back to the page's other fields.

**Equipment Slots** names every slot and sets its order and description. A slot can hold more
than one piece (two rings), take gear tagged for another slot (a sub-weapon slot that takes any
`weapon`), be **Carried, Not Worn** (its pieces give nothing until swapped in during battle) or
be **Only for Heroes With** a capability a job grants. A two-handed weapon names the slots it
**Also takes (two-handed)** on its equipment record; **Inventory Rules** decides what happens
when such a slot is taken and whether swapping a carried weapon in battle costs a turn.

![Game Systems: Equipment Slots](images/editor_en_systems_equipment_slots.png)

### 7.4 Enemy AI, Behavior Trees, Real-Time Combat

- **Enemy AI**: rule tables per enemy (condition → action → target) and boss phases.
- **Behavior Trees**: AI for field and real-time enemies.
- **Real-Time Combat**: attacks, projectiles, rarities and affixes with a live preview and the
  hit boxes drawn over it.

### 7.5 Game Start

**Game Start** decides what a new game is: the start scene, the player's facing and position, the
party, starting items, money and starting pets.

![Game Start](images/editor_en_game_start.png)

---

## 8. Battles

### 8.1 Classic turn-based battles

The **Battle** workspace holds the battle rules, one category at a time: Battle Resources,
Status Effects, Damage Interactions, Chance Checks, Targeting, Turn Order, Cast & Recovery
Timing, Action Sequences, Break Gauges, Counters & Follow-ups, Victory & Defeat Conditions, Escape
Rules, Action Costs and General Battle Rules.

![Battle rules](images/editor_en_battle_rules.png)

Heroes with carried weapons get a **Swap** command in battle: it lists the carried weapons and
the slot each one goes into; the weapon taken off goes back to the carried slots.

**General Battle Rules** ties them together: the knockout resource (HP), the boost resource and
its cost per level, the shield resource for weakness Breaks, what happens on defeat, action
timing and the weakness tag. **Status Effects** sets how each status behaves in battle (turns,
prevent action, chance, removal).

![Status effects in battle](images/editor_en_battle_states.png)

A battle in play (Full Verification): the turn order at the top, the party card on the right, the
command menu next to the acting hero, shields and hidden weaknesses under the enemies.

![A turn-based battle](images/game_en_battle.png)

The party RPG demo with a full party, boost points and the timeline:

![Party RPG battle with breaks and boosts](images/game_break_battle.png)

### 8.2 The battle screen

**Presentation ▸ Battle Screen** sets how a battle looks: Combatant Sprites, Damage Numbers &
Labels, Battle HUD, Battle UI Layout, Battle UI Spacing, Side-View Positions, Portrait Party
Layout, Animation Timing, Camera & Choreography, Effect & Sound Channels, Action Menu, Command Menu
Pages, Result Screen, Party Layout, Battle UI Theme, Motion Sequences and Command Input Steps (the
same page also holds Menu Layout, Menu Theme, Bitmap Font, Dialogue Window and Creature Screen
records, chapter 9).

![Battle UI Layout](images/editor_en_battle_screen.png)

**Battle UI Layout** places the party HUD, the command menu (`Action Menu Placement`), the
overhead names and HP, portraits and the stage. **Command Menu Pages** names the commands (Fight,
Skills, Bag, Run…).

### 8.3 Creature battles

A creature game (catch creatures, fight with a party of them) uses the same rules plus:

- **Game Systems ▸ Pet Species** (base stats, growth, moves, evolutions), **Pet Rules
  (creature party)** (party size, storage, formulas, genes, experience) and **Capture Rules**
  (catch rates, balls, shakes).
- The creature battle screen: turn it on with **Presentation ▸ Menu Screens ▸ Shared
  Settings ▸ Creature Screens…** (the `battle.creature_screen` record; or `battle.style: "creature"` in the
  game folder settings). Its pictures, font, sounds and positions are edited in the same dialog.

These frames come from the Full Verification demo with stand-in Foozle creatures:

![Creature battle: commands](images/game_creature_03_commands.png)
![Creature battle: moves](images/game_creature_04_moves.png)
![Creature battle: a ball shaking](images/game_creature_11_ball_shaking.png)
![Creature battle: party screen](images/game_creature_16_party_screen.png)

### 8.4 Real-time battles

Action RPGs fight on the map. Attacks, projectiles, loot rarities and affixes are in **Database
▸ Real-Time Combat**; enemy behaviour in **Behavior Trees**; the bottom HUD (orbs, action bar,
cooldowns) is the **Action RPG HUD** menu screen (chapter 9).

![Action RPG town with the action HUD](images/game_arpg_town.png)

---

## 9. Menus and screens

### 9.1 The layout canvas

**Presentation ▸ Menu Screens ▸ Layout** lets you rearrange every screen the game draws.

![Menu Screens ▸ Layout](images/editor_en_menu_layout.png)

- **The screen list** (left): Title, Pause menu, Settings, Controls, Save / load, Game over,
  Status pages, Equipment bag, Equipment (paper doll), Enhance (refine, sockets, cards, growth),
  Skill tree, Shop, Crafting (a workstation), Quest board, Recruiting office, Gacha banner, Quest
  log, Pets, Achievements, Bestiary, Message log, Music room, Credits, Skill slots, Wear new gear?,
  Map hints line, and the in-play screens Dialogue window, Dialogue choice, Action RPG HUD and
  Battle screen. "(modified)" marks screens this project has changed; a workstation, board or
  banner can have its own layout (the indented rows).
- **The canvas** (middle): the screen drawn with sample data, as the game draws it. Hover an
  element to see its dashed outline and name; click to select it, drag it to move, drag its
  corner to resize. **Show All Outlines** draws every outline at once.
- **The properties** (right): Engine's place (untick to place it yourself), Anchor, Place, Size,
  Shown, Layer, Frame (nine-patch), Picture and more.
- **Buttons**, in two rows: the element list, **Add Element** (your own Picture, Panel, Text,
  Gauge or Portrait) and **Remove Element**; then **This Screen** (reset to the engine's layout,
  copy the layout from another screen, background), **Shared Settings** (Menu Theme, Bitmap
  Fonts, Picture Message Window, Creature Screens, Game Folder Settings), **Show All Outlines**
  and **Open in Game** (runs the project opened on this screen). **Preview language** draws the
  canvas in another locale. On the status pages, a button jumps to the pages' blocks in Game
  Systems ▸ Pause Menu.

A screen without a layout is drawn exactly as the engine always drew it.

### 9.2 The pause menu and its pages

**Database ▸ Game Systems ▸ Pause Menu** is the whole pause menu on one page.

![Game Systems: Pause Menu](images/editor_en_systems_pause_menu.png)

- **The list** (left) is the menu in the game's order: tick to show an entry, drag to move it.
  **Show All** ticks every entry and **Engine Order** puts them back in the engine's order; **New Page** and **New Event Entry** add your
  own. An entry the game has nothing to open for yet is greyed out, and its tooltip says what it
  needs.
- **The settings** (right) belong to the selected row. A built-in entry says what it opens. A
  **page** (Status, Items, or one of your own) has a name, an icon and **blocks** from top to
  bottom: Profile, Stat Points, Stat Details or Item List, each placed Left, Right or Full (the
  whole width), with its own settings (which stat columns, which item tabs…). **Back to the
  Engine's Page** undoes your changes to Status or Items; **Move It on the Screen (Layout)** opens
  the page in Menu Screens. An **event entry** runs an event program.

The names of stats come from Game Systems ▸ Stats and the names of equipment slots from Game
Systems ▸ Equipment Slots.

### 9.3 The game's screens

Pictures of the Full Verification demo:

![Title](images/game_en_title.png)
![Pause menu](images/game_en_pause.png)
![Status](images/game_en_status.png)
![Status: skills](images/game_en_status_skills.png)
![Equipment (paper doll)](images/game_en_equipment.png)
![Equipment bag](images/game_en_bag.png)
![Skill tree](images/game_en_skill_tree.png)
![Shop](images/game_en_shop_buy.png)
![Crafting](images/game_en_crafting.png)
![Quest log](images/game_en_quests.png)
![Pets](images/game_en_pets.png)
![Save slots](images/game_en_save_slots.png)
![Game over](images/game_en_game_over.png)

The pause menu's order, pages and entries come from **Game Systems ▸ Pause Menu**; screens such
as Pets, Crafting or Enhance appear only when the project has that content.

---

## 10. Dialogue and choices

### 10.1 A dialogue line

In the event's **Commands**, press **Dialogue**:

![Dialogue command](images/editor_en_dialog_dialogue.png)

- **Speaker** and **Text**; the preview on the right shows the message box.
- **Portrait**: a picture (Browse… or the list), and **Portrait side** (left or right).
- Text codes: `\V[name]` a variable, `\S[name]` a switch, `\N[id]` an actor's name, `\P[n]` the
  n-th party member, `\G` the currency name, `\$` the money, `\M[name]` a macro from Message
  Settings, `\T[key]` a translated text, `\C[n]` a colour, `\I[n]` an icon, `\{` / `\}` bigger /
  smaller, `\.` and `\|` pauses, `\!` wait for a key.

![A dialogue line in play](images/game_en_dialogue.png)

### 10.2 A choice

Press **Choice**: a prompt and the options, each with the value that goes into the variable.
Options can run commands when the pointer is on them (hover), the cancel key can give a value,
and options can be laid out in columns.

![Choice command](images/editor_en_dialog_choice.png)

![A choice in play](images/game_en_choice.png)

### 10.3 Message settings and the message window

- **Game Systems ▸ Message Settings**: macros (`\M[name]`), the currency shown by `\G` and `\$`,
  the message log size, the **Default Locale**, the portrait style (face inside the box or bust
  standing on it) and the portrait size.
- **Menu Screens ▸ Layout ▸ Picture message window…**: your own message window picture, bitmap
  font, typing speed and page arrow; the Dialogue window and Dialogue choice screens can be laid
  out like any other screen.
- The world commands `NAME_INPUT` (enter a name) and `PICTURE_CHOICE` (pick a picture) open their
  own screens.

![Message Settings](images/editor_en_systems_message.png)

---

## 11. Input and controls

### 11.1 Actions and bindings

**Presentation ▸ Controls** holds the project's default controls. An **action** (Confirm,
Cancel, Interact, Menu, Move Up…) has **bindings**: keys, gamepad buttons, axes or hats.

![Controls](images/editor_en_controls.png)

- **Add Action…** / **Remove Action** on the left; **Add Binding** / **Remove Binding** on the
  right, with **Device**, **Code** (a key name such as `a`, `left`, `space`, or a pad button /
  axis number) and **Direction (axes / hats)**.
- Players can rebind in the game: Settings ▸ Controls.

![Rebinding keys in the game](images/game_en_controls.png)

Default keys of a new input map:

| Action | Keys | Gamepad |
| --- | --- | --- |
| Move | arrows, WASD | left stick, d-pad |
| Interact | E, Enter, Space | A (button 0) |
| Confirm | Enter, Space | A |
| Cancel | Escape, Backspace | B (button 1) |
| Menu | C | Start (button 7) |
| Run | Shift | B |

### 11.2 Mouse control

The **Mouse control** switch (on by default) lets players use the mouse in every menu, dialogue
and battle:

- pointing at a row or an option selects it,
- a left click confirms, a right click goes back (Cancel), the wheel moves up and down,
- long menus scroll,
- after the mouse is used a hint appears at the bottom right ("Click: choose  Right click:
  back").

![Pause menu picked with the mouse](images/game_en_mouse_02_pause_hover_settings.png)
![A long menu scrolled to its end, with the mouse hint](images/game_en_mouse_07_pause_scrolled_quit_hint.png)
![Battle command under the pointer](images/game_en_mouse_04_battle_hover.png)

Turn it off for keyboard-only games; the project then stores `"mouse": false`.

### 11.3 Click to move

The **Click to move** switch (off by default): a left click on the map walks the player there
along a path around obstacles; clicking a person walks up to them and talks. Any key press takes
over again. It works on top-down maps, top-down action scenes and network games, not in
side-scrolling platform scenes.

![Click to move](images/game_en_mouse_09_click_to_move_walking.png)
![Click a figure to walk up and talk (action RPG)](images/game_en_mouse_12_arpg_click_figure_talks.png)

### 11.4 In-game keys of the demos

The field shows a hint line, for example in Full Verification: Move WASD / Arrows, C Build,
Q Quests, E Interact, F5 Save, Esc Pause. The action RPG demo: J attack, K dodge, 1–6 skills,
L lock on, F pick up, B bag, C skill tree, Esc pause.

---

## 12. Translations

### 12.1 The editor's language

**View ▸ Language** switches the editor between English (the default) and 繁體中文 at once,
without a restart; the choice is remembered. Only the editor's own words change; your names,
IDs and descriptions stay as you wrote them.

![View ▸ Language](images/editor_en_menu_view_language.png)

### 12.2 The game's language

Everything the game draws can be translated, and renamed:

- **Game Systems ▸ Translations** has one table per locale (`en`, `zh-TW`, `fr`…). The page lists
  every built-in word with its English next to it, then the project's own keys and the project
  data (actors, items, maps, speakers, dialogue lines…). Search, show only untranslated rows,
  **Fill empty rows** (fills zh-TW from the engine's own Traditional Chinese), **Add key**,
  **Remove key** and **Give dialogue lines keys** (gives every line and option a `dlg.*` key).
- An empty text keeps the English; a single space hides the word.
- Writing in the default locale's table renames a word: for example `battle.command.attack` =
  `Fight` in the `en` table.
- The table is used when it is the **Default Locale** (Message Settings) or the player picks it
  in **Settings ▸ Language** (shown when there are two or more locales).

![Translations](images/editor_en_systems_translations.png)

Keys you will meet:

| Key | Text |
| --- | --- |
| `battle.command.attack`, `pause.save`… | The engine's built-in words; the whole list is in [`docs/BUILT_IN_TEXT_KEYS.md`](../BUILT_IN_TEXT_KEYS.md). |
| `data.<kind>.<id>.name` / `.description` | A record's name and description (`data.actor.hero_01.name`). |
| `data.map.<scene id>.name`, `data.speaker.<name>.name`, `data.currency.<id>.name` | Map names, speakers, currencies. |
| `battle.layer.<command id>`, `pause.entry.<id>`, `controls.action.<action id>` | Your command pages, pause entries and control names. |
| `dlg.*` | Dialogue lines and options (their `text_key`). |

In scripts and your own screens, draw text with `game.tr("key", "English")` (15.5). The world
command `SET_LOCALE` switches the language from an event.

The same screens in English and Traditional Chinese:

![Settings in English](images/game_en_settings.png)
![The field in Traditional Chinese](images/game_zh_field.png)
![A dialogue line in Traditional Chinese](images/game_zh_dialogue.png)

---

## 13. Play-testing, saving and exporting

### 13.1 Play-testing

![Run menu](images/editor_en_menu_run.png)

| Run menu | Shortcut | Does |
| --- | --- | --- |
| Run Project | F6 | Play from Game Start (title screen, new game). |
| Run Current Scene | Ctrl+F6 | Play the scene open in the editor. |
| Play from Selection | Shift+F5 | Play the current scene with the player at the selected entity. |
| Restart Play | Ctrl+Shift+F5 | Stop and start again the same way. |
| Stop | Shift+F6 | Close the game window. |
| Game Folder Settings… | | Edit `playable_test_manifest.json` in a settings tree (undoable). |

The game opens in its own window. The **Debugger**, **Profiler** and **Problems** panels show
the running game's state, frame times and project errors.

Without the editor: `.venv/bin/asteria-preview PROJECT.json` (options `--scene`, `--width`,
`--height`, `--save`, `--spawn X Y`, `--fps`).

### 13.2 Saving in the game

Players save with the pause menu (Save Game / Load Game) or F5 on the field; saves go to the
project's `saves/` folder as numbered slots (`slot1.asteria-save.json`…). The editor never edits a player's save; play-test
saves stay out of the project file.

![Save slots](images/game_en_save_slots.png)

### 13.3 Export a desktop game

**File ▸ Export Game…** asks for the game name and whether to also build a single-file game
(.pyz) and a macOS app (.app), then the folder.

![Export Game](images/editor_en_dialog_export.png)

The game folder always carries the engine (`run_game.py`); players need Python 3.12+ with
pygame-ce. The same from a terminal:

```bash
.venv/bin/asteria-export PROJECT.json OUTPUT --pyz --app --name "My Game"
```

From the **standalone Asteria app** (no Python installed), the macOS app it exports carries a
small player of its own, so players do not need Python either; its saves go to
`~/Library/Application Support/Asteria Games/<game name>/saves`. The .pyz and the game folder
still need Python. See [STANDALONE_APP.md](../STANDALONE_APP.md).

### 13.4 Export a web game

```bash
.venv/bin/python -m pip install pygbag
.venv/bin/asteria-export-web PROJECT.json OUTPUT --serve
```

This builds `OUTPUT/build/web/` (`index.html` and the game package) with pygbag and serves it on
`http://127.0.0.1:8000` (open it with `127.0.0.1`, not `localhost`). Options: `--title`,
`--width`, `--height`, `--icon`, `--cjk-font` (Noto Sans TC by default, `none` for no font),
`--cdn`, `--no-build`, `--port`. Copy `index.html` and the package to any static web host.

In the browser: saves are kept in the browser's local storage; audio must be ogg or wav; the
editor, multiplayer, the GPU renderer and the C++ speed-ups are not part of a web build; the page
loads the Python runtime from pygame-web's CDN unless you pass `--cdn`. Add `?mute=1` to the
address for a silent run.

---

## 14. The reference projects

Open any of them with File ▸ Open Project… or play them with `asteria-preview`.

| Project | Shows |
| --- | --- |
| `reference_projects/full_verification_demo` | The recommended template: a whole turn-based game. Hearthfold (town) → Whispering Woods → Catacombs → Ember Throne, the hero Roger hiring Mira, Vesper and Cael, jobs and skill trees, STR / DEX / INT / LUK, elements, weaknesses / shields / Breaks, refine and sockets, crafting, quests, pets, map areas, New Game Plus, full Traditional Chinese, music room. Every editor page has data. |
| `reference_projects/arpg_demo` | A real-time action RPG: a town, fields, a side-scrolling mine with platforms and ladders, three classes with skill trees, loot with rarities, affixes and sets, potions, bosses. |
| `reference_projects/party_rpg_demo` | Party battles with breaks and boosts: four travellers with two jobs each, weaknesses and shields, boost points, divine skills, multi-weapon attacks, a Pokémon-style pet, concoction, five encounters. |
| `reference_projects/complex_reference_rpg` | A dense generic RPG: 12 actors, 8 jobs, 24 abilities, 16 passives, eight skill trees, equipment growth, a 12-person roster, a three-phase boss with adds, custom battle resources. See its `PLAYTEST.md`. |

To see how a system is described in data, find it in the Full Verification demo: its
[`README.md`](../../reference_projects/full_verification_demo/README.md) has a table of every
system and where it lives in the editor.

The Full Verification game in play (Traditional Chinese):

![Title](images/game_zh_title.png)
![Pause menu](images/game_zh_pause.png)
![Battle](images/game_zh_battle.png)

---

## 15. Python API for authors

This chapter is generated from the engine's source by `scripts/manual_api_list.py`; the
signatures are the real ones (type hints left out). Run the script after an engine change, and
`--check` to see whether the chapter is still up to date.

<!-- BEGIN API (generated by scripts/manual_api_list.py; do not edit by hand) -->

### 15.1 Loading, saving and running a project

A project is one `project.asteria.json`; its folder holds the art, the `playable_test_manifest.json` and `saves/`. The registry tells the loader which components exist: use `EditorDocument().component_registry` (as the editor and the reference scripts do) or `build_preview_registry()`.

| Signature | Description |
| --- | --- |
| `Project.load_json(path, registry)` | Load a project file (classmethod). |
| `Project.save_json(path)` | Write the project to a file. |
| `Project.validate(*, validate_gameplay_refs=True)` | Check the project's data; raises on the first problem. |
| `Project.ability_reference_errors()` | Every record that grants an ability the gameplay library does not define. |
| `Project.scenes()` | All scenes (maps) in order. |
| `Project.scene(scene_id)` | One scene by id, or `None`. |
| `Project.add_scene(scene)` | Add a scene to the project. |
| `Project.game_start` *(attribute)* | The Database ▸ Game Start settings. |
| `GameStartDefinition.instantiate(project)` | A new game's save (`GameRuntimeSave`) built from Game Start. |
| `GameRuntimeSave.load_json(path, project)` | Read a save file for a project (static method). |
| `GameRuntimeSave.save_json(path)` | Write a save file. |
| `asteria.runtime.save_slots.SaveSlots(folder, project, *, count=3, lookup=None)` | The numbered save slots in a folder (the game uses `<project>/saves`). |
| `SaveSlots.save(slot, game)` | Save `game` into a slot. |
| `SaveSlots.load(slot)` | Read the save in a slot. |
| `SaveSlots.info(slot)` | A slot's summary (map, leader, level) for a save screen. |
| `SaveSlots.delete(slot)` | Delete the save in a slot. |
| `asteria.runtime.preview.build_preview_registry()` | The component registry the game player uses. |
| `asteria.runtime.preview.run_preview(project_path, scene_id=None, *, resource_root=None, backend=None, width=None, height=None, target_fps=60, save_path=None, playtest_profile=None, backend_kind='pygame', max_frames=None, profile_path=None, battle_presentation=None, debug_port=None, debug_token=None, spawn=None)` | Play a project in a window (what `asteria-preview` runs). |

### 15.2 PlayableTestRuntime (the game window)

Opens a pygame window over a project and its save, draws every screen and turns keys and the mouse into game actions. `rt.game` is the `GameSessionRuntime` below. Example: `rt = PlayableTestRuntime(project, project.game_start.instantiate(project), folder, width=1280, height=720); rt.open(); rt.run()`.

| Signature | Description |
| --- | --- |
| `asteria.runtime.playable_test_runtime.PlayableTestRuntime(project, runtime_save, resource_root, *, width=960, height=540, backend=None)` | Make the game host (nothing is shown until `open`). |
| `rt.open()` | Open the window, audio and input. |
| `rt.run(target_fps=60, max_frames=None, *, profile_path=None)` | The game loop until the player quits (or `max_frames`). |
| `rt.step(dt, events=None)` | One whole frame: events, game update, drawing and the flip (for your own loop and the web build). |
| `rt.tick(target_fps=60)` | Wait for the next frame of a steady frame rate; returns dt. |
| `rt.capture()` | The frame as the player sees it (a pygame Surface). |
| `rt.close()` | Close the window. |
| `rt.save_playtest()` | Write the play-test autosave into `saves/`. |
| `rt.open_status_menu(back='field', page=None)` | Open the status menu. |
| `rt.open_equipment_screen(back='field')` | Open the equipment (paper doll) screen. |
| `rt.open_enhance_screen(back='field')` | Open the enhance screen (refine, sockets…). |
| `rt.open_slots(mode, back='pause')` | Open the save / load slots (`mode` is `save` or `load`). |
| `rt.menu_layout(screen_id)` | The project's layout of a menu screen, or `None`. |
| `rt.text(value, x, y, *, size=20, color=(245, 245, 250), center=False, anchor=None, font=None)` | Draw text on the screen (menus written in Python). |
| `rt.menu_row(label, x, y, *, selected, size=20, color=(245, 245, 250), pick=None, width=0)` | Draw one menu row with its cursor (and its mouse spot). |
| `rt.hotspot(rect, pick=None, *, key='return')` | Mark a place the mouse can point at this frame; a click sends `key`. |
| `rt.enable_profiling(profiler=None, *, target_fps=60.0)` | Attach a frame-time profiler. |
| `rt.enable_debugger(*, port=0, token=None)` | Open the editor's debug channel. |
| `rt.game` *(attribute)* | The `GameSessionRuntime`. |
| `rt.settings` *(attribute)* | The player's settings (language, volume, key overrides). |

### 15.3 GameSessionRuntime: field, maps and movement

`game = rt.game`. The game's rules without any drawing: everything an event's world command does is also a method here. Entity keys are `"player"`, an entity name or id.

| Signature | Description |
| --- | --- |
| `game.project` *(attribute)* | The loaded `Project`. |
| `game.save` *(attribute)* | The running `GameRuntimeSave`. |
| `game.player` *(attribute)* | The player entity. |
| `game.transfer_player(scene_id, x=None, y=None, *, facing=None)` | Move the player to another scene or position. |
| `game.set_player_position(x, y)` | Put the player at `(x, y)`. |
| `game.set_player_facing(facing)` | Turn the player (`up`, `down`, `left`, `right`). |
| `game.find_path(start, goal, *, walker=None, cell_size=16.0, margin=0.0)` | Waypoints from `start` to `goal` around walls, or `None`. |
| `game.walk_to(entity_key, x, y, *, speed=60.0)` | Send an entity walking to `(x, y)` around obstacles; switch `walk.<id>.done` turns on on arrival. |
| `game.navigation_grid(*, cell_size=16.0, margin=0.0, walker=None)` | The walkable grid of the current field. |
| `game.move_route(entity_key, route, *, step=32.0, speed=60.0)` | Walk an entity along a route such as `"up 3, left 2"`. |
| `game.grid_route(entity_key, steps)` | Walk a grid character along steps (`GRID_ROUTE`). |
| `game.set_entity_position(entity_key, x, y, *, facing=None, permanent=False)` | Put an entity at `(x, y)`; `permanent` keeps it there in the save. |
| `game.show_entity(entity_key, shown=True)` | Show or hide an entity. |
| `game.set_entity_movement(entity_key, behaviour='', facing='')` | Change how a grid character moves and faces. |
| `game.spawn_prefab(prefab_id, x, y, *, name=None)` | Create an entity from a prefab at `(x, y)`. |
| `game.copy_entity(entity_key, x, y, *, name=None)` | Copy a scene entity to `(x, y)`. |
| `game.morph_entity(entity_key, prefab_id)` | Replace an entity by a prefab where it stands. |
| `game.click_entity(world_x, world_y)` | A mouse click in the field: start the clicked entity's click-triggered event. |
| `game.show_balloon(entity_key, balloon='exclamation', *, duration_ms=1000.0)` | A balloon (`exclamation`…) over an entity. |
| `game.set_entity_icon(entity_key, icon_id='')` | Keep an icon (quest marker…) over an entity. |
| `game.play_action(entity_key, timeline_id)` | Start an action timeline on a field entity. |
| `game.set_tile(layer, x, y, tile, *, permanent=False)` | Change one tile of a layer (a door opens); `permanent` saves it. |
| `game.tile_changes(scene_id=None)` | The tiles changed in a scene. |
| `game.set_light(radius=None, *, speed=0.0)` | Darken the field except a circle round the player (`None`: lights on). |
| `game.set_npc(npc_id, key, value)` | Change an NPC's saved state (visible, alive, mood…). |
| `game.move_npc(npc_id, scene_id, x, y)` | Move an NPC, also to another scene. |
| `game.notify(text, *, entity=None, duration_ms=1100.0, kind='info')` | A short floating message above an entity. |
| `game.damage_party(resource_id, amount, *, can_kill=False)` | Floor-style damage to every active hero. |

### 15.4 GameSessionRuntime: events, dialogue and choices

`game.events` is the foreground event runner: `game.events.start("program.id")` runs an event program, then the host calls `update_events` every frame.

| Signature | Description |
| --- | --- |
| `game.events` *(attribute)* | The foreground `EventRunner`. |
| `game.events.start(program_id, *, source_entity_id='', local_scope_id='', replace=False)` | Run an event program. |
| `game.events.stop()` | Stop the running event. |
| `game.update_events(dt=0.0)` | Advance running event programs by `dt` seconds. |
| `game.pending_dialogue` *(property)* | The dialogue line or choice waiting for the player. |
| `game.acknowledge_dialogue()` | Close the waiting line (the confirm key). |
| `game.choose(index)` | Pick option `index` of the waiting choice. |
| `game.hover_choice(index)` | The pointer is on option `index` (runs its hover commands). |
| `game.cancel_choice()` | The cancel key on the waiting choice. |
| `game.held_dialogue` *(property)* | A line shown without waiting (`DIALOGUE wait: false`). |
| `game.event_busy` *(property)* | True while an event blocks player control. |
| `game.cutscene_active` *(property)* | True while a cutscene sequence runs. |
| `game.skip_cutscene()` | Fast-forward a skippable cutscene. |
| `game.expand_message(text, *, plain=False)` | A message with its codes (`\V[..]`, `\N[..]`, `\G`…) filled in. |
| `game.request_name_input(target, *, max_length=7, title='', default='', initial='')` | Open the name entry screen (`NAME_INPUT`). |
| `game.finish_name_input(name)` | Give the name screen's answer. |
| `game.request_picture_choice(layout, variable)` | Show a layout of pictured options (`PICTURE_CHOICE`). |
| `game.finish_picture_choice(value)` | Give the picture choice's answer. |
| `game.actor_variable(actor_id, name, default=0)` | A per-actor variable (saved). |
| `game.set_actor_variable(actor_id, name, value)` | Set a per-actor variable. |

### 15.5 GameSessionRuntime: translation

Every word a screen draws goes through `game.tr(key, english)`; the keys are listed in `docs/BUILT_IN_TEXT_KEYS.md`. Project data uses `data.<kind>.<id>.name`.

| Signature | Description |
| --- | --- |
| `game.tr(key, default=None, **params)` | A built-in word in the player's language (`default` when no table has it). |
| `game.set_locale(locale)` | Switch the game's language (a locale table must exist, e.g. `zh-TW`). |
| `game.localizer` *(property)* | The project's translations at the player's locale. |
| `game.name_of(record, fallback=None)` | A record's name in the player's language. |
| `game.description_of(record, fallback='')` | A record's description in the player's language. |
| `game.line_text(line)` | A dialogue line's or choice's text, translated. |
| `game.speaker_of(line)` | Who speaks a line, translated. |
| `game.map_name(scene_id, own)` | A map's name, translated. |
| `game.stat_name(stat_id, *, short=False)` | A stat's or resource's name, translated. |
| `game.slot_name(slot_id)` | An equipment slot's name, translated. |
| `game.tag_name(tag)` | A tag's name, translated. |

### 15.6 GameSessionRuntime: party, growth and skills

| Signature | Description |
| --- | --- |
| `game.join_party(actor_id, *, active=True)` | An actor joins the roster (and the active party if room). |
| `game.leave_party(actor_id)` | An actor leaves the party. |
| `game.set_active_party(actor_ids, placements=None)` | Choose the active party from the roster. |
| `game.rest_party()` | An inn: every member back to full. |
| `game.set_classes(actor_id, class_ids, *, unlock=True)` | Make classes an actor's active classes. |
| `game.set_secondary_class(actor_id, class_id)` | Set an actor's secondary class. |
| `game.learn_ability(actor_id, ability_id)` | An actor learns an ability. |
| `game.grant_actor_experience(actor_id, amount, *, level_threshold=1000.0, ap_per_level=2.0, ability_points_per_level=1.0, points_per_level=None, level_track='')` | Give experience (levels and points follow). |
| `game.allocate_progression(actor_id, graph_id, node_id, count=1)` | Spend points on a skill tree node. |
| `game.reset_progression(actor_id, graph_id=None, *, cost=None)` | Refund skill tree points. |
| `game.equip_passive(actor_id, passive_id, *, capacity=None)` | Equip a passive. |
| `game.ability_slots(actor_id)` | Equipped abilities and slot capacity of an actor. |
| `game.equip_ability(actor_id, ability_id)` | Put an ability in a skill slot. |
| `game.unequip_ability(actor_id, ability_id)` | Take an ability out of its slot. |
| `game.party_gauge(gauge_id)` | A party-wide gauge's value. |
| `game.change_party_gauge(gauge_id, amount)` | Add to or spend a party gauge. |

### 15.7 GameSessionRuntime: items, equipment, shops and crafting

| Signature | Description |
| --- | --- |
| `game.use_item(actor_id, item_id)` | Use a consumable on a member outside battle. |
| `game.equip_from_inventory(actor_id, equipment_id, slot_id=None)` | Equip an item from the bag. |
| `game.unequip_to_inventory(actor_id, slot_id)` | Take a slot's item off into the bag. |
| `game.gain_equipment(equipment_id, quantity=1)` | New gear into the equipment bag (may ask to wear it). |
| `game.wear_from_bag(actor_id, instance_id, slot_id, index=None)` | Wear a bag piece in a slot. |
| `game.unequip_to_bag(actor_id, slot_id, index=0)` | Take a worn piece off into the bag. |
| `game.refine_equipment(actor_id, instance_id, *, protect=False)` | One refine (+N) attempt on an equipped item. |
| `game.socket_item(actor_id, instance_id, socket_id, item_id)` | Put a gem or card into a socket. |
| `game.unsocket_item(actor_id, instance_id, socket_id)` | Take a socket's attachment out. |
| `game.disassemble(item_id)` | Break an item down by its recipe. |
| `game.open_shop(shop_id)` | Open a shop. |
| `game.close_shop()` | Close the shop. |
| `game.buy(item_id, quantity=1, *, shop_id=None)` | Buy from the open shop. |
| `game.sell(item_id, quantity=1, *, shop_id=None)` | Sell to the open shop. |
| `game.craft(payload, *, station='', quality_bonus=0.0, rng=None)` | Craft with the project's recipes. |
| `game.learn_recipe(recipe_id)` | Learn a recipe. |
| `game.known_recipes(station=None)` | The recipes the player can see. |

### 15.8 GameSessionRuntime: quests and the world

| Signature | Description |
| --- | --- |
| `game.start_quest(quest_id)` | Start a quest. |
| `game.advance_quest(quest_id, objective_id, amount=1)` | Add progress to a quest objective. |
| `game.complete_quest(quest_id)` | Complete a quest. |
| `game.fail_quest(quest_id)` | Fail a quest. |
| `game.change_reputation(faction_id, amount)` | Change a faction's reputation. |
| `game.change_relationship(subject_id, amount)` | Change a relationship value. |
| `game.add_counter(counter_id, amount=1)` | Add to a world counter. |
| `game.perform_interaction(interaction_id)` | Run a world interaction (check, cost, outcome). |
| `game.set_difficulty(difficulty_id)` | Choose a difficulty of the enemy level rules. |
| `game.new_game_plus(rules_id=None)` | A New Game Plus save carried over from this game. |
| `game.request_new_game_plus(rules_id=None)` | Ask the game to start over in New Game Plus. |

### 15.9 GameSessionRuntime: battles

| Signature | Description |
| --- | --- |
| `game.start_encounter(encounter_id, *, opening=None)` | Begin a turn-based fight; `opening` is `preemptive`, `normal` or `surprise`. |
| `game.current_turn_actor()` | Whose turn it is. |
| `game.ability_unavailable(actor_id, ability_id)` | Why an actor cannot use an ability now (`''`: can). |
| `game.default_targets(actor_id, ability_id)` | The targets a selection would default to. |
| `game.preview(actor_id, ability_id, target_ids)` | Predicted results of an action (nothing changes). |
| `game.use_ability(actor_id, ability_id, target_ids=None, *, boost_level=0, form=None, choices=None)` | One player action through the project's rules. |
| `game.use_battle_item(actor_id, item_id, target_ids=None)` | Use an item in battle. |
| `game.end_turn()` | End the current turn. |
| `game.run_enemy_turns(*, limit=1000)` | Play enemy turns until a hero must act. |
| `game.plan_round(choices=None)` | Everyone chooses before the round (creature style). |
| `game.escape_unavailable()` | Why the party cannot run now (`''`: can). |
| `game.attempt_escape(actor_id, *, rng=None)` | Try to run. |
| `game.capture_chance(target_id, item_id=None)` | Chance (0–1) that a capture succeeds now. |
| `game.attempt_capture(actor_id, target_id, *, rng=None, item_id=None)` | Try to capture an enemy. |
| `game.summon(*, enemy_id=None, actor_id=None, count=1, owner_id=None, join_current_round=True)` | Bring combatants into the running battle. |
| `game.steal(actor_id, target_id, *, chance_bonus=0.0)` | Try to steal from an enemy. |
| `game.auto_battle_act(actor_id, **options)` | Let a hero take its turn automatically. |
| `game.drain_battle_log()` | Return and clear the battle facts so far. |
| `game.set_battle_weather(kind, intensity=0.6, wind=0.0)` | The weather of the next battles. |

### 15.10 GameSessionRuntime: pets and creatures

| Signature | Description |
| --- | --- |
| `game.add_pet(species_id, *, level=1, nickname='', record=None, rng=None)` | Own a new creature of a species. |
| `game.pets()` | The owned pets. |
| `game.active_pet()` | The pet abilities send out. |
| `game.set_active_pet(instance_id)` | Choose the active pet. |
| `game.rename_pet(instance_id, nickname)` | Give a pet a nickname. |
| `game.party_pets()` | The pets travelling with the player. |
| `game.stored_pets()` | The pets in storage. |
| `game.move_pet_to_party(instance_id)` | Move a pet from storage to the party. |
| `game.move_pet_to_storage(instance_id)` | Move a pet to storage. |
| `game.heal_pets(*, party_only=False)` | Every pet back to full. |
| `game.use_item_on_pet(pet, item_id)` | Use an item on a creature outside battle. |
| `game.learn_pet_move(instance_id, ability_id, forget_ability_id='')` | Teach a pet a move. |
| `game.pet_evolution(instance_id, *, item_id='')` | The evolution a pet qualifies for now, or `None`. |
| `game.evolve_pet(instance_id, *, item_id='')` | Evolve a pet now. |
| `game.pet_stats_at(pet, level=None)` | A pet's stats at a level. |
| `game.switch_pet(out_member_id, in_member_id)` | Swap a creature on stage for a benched one. |

### 15.11 Input and controls

`project.input_map` is the project's `InputActionMap` (Presentation ▸ Controls). An `InputBinding` is one key, pad button or axis.

| Signature | Description |
| --- | --- |
| `asteria.runtime.input_map.InputActionMap(actions=None, *, mouse=True, click_move=False)` | Actions and their bindings, plus the two mouse switches. |
| `InputActionMap.mouse` *(attribute)* | Menus, dialogue and battles answer the mouse (default on). |
| `InputActionMap.click_move` *(attribute)* | A left click on the map walks the player there (default off). |
| `InputActionMap.default()` | Keyboard (arrows / WASD) plus a standard gamepad (classmethod). |
| `InputActionMap.actions()` | The action ids. |
| `InputActionMap.bindings(action_id)` | The bindings of an action. |
| `InputActionMap.set_bindings(action_id, bindings)` | Replace an action's bindings. |
| `InputActionMap.rebind(action_id, old, new, *, exclusive=False)` | Replace one binding (or add one); `exclusive` frees it elsewhere. |
| `InputActionMap.to_data()` | Serialise to JSON data. |
| `InputActionMap.from_data(data)` | Read from JSON data (classmethod). |
| `asteria.runtime.input_map.InputBinding(device, code, direction=1, threshold=0.5)` | One input: `device` is `key`, `button`, `axis` or `hat`. |

### 15.12 The Code workspace (authoring scripts)

Scripts in the Code workspace get the globals `project` (an `AuthoringSession`), `selected`, `scene`, `entity` and the helpers `track`, `move`, `face`, `animate`, `say`, `world`, `pause`, `battle_condition`. Every change a script makes is one undo step; a failing script is rolled back.

| Signature | Description |
| --- | --- |
| `AuthoringSession.scenes()` | All scenes, wrapped. |
| `AuthoringSession.scene(name_or_id)` | A scene by name or id. |
| `AuthoringSession.new_event(program_id, name='')` | Create an empty event program. |
| `AuthoringSession.event_program(program_id)` | An existing event program. |
| `AuthoringSession.common_event(program_id, trigger='call', switch='')` | Make a program a common event (`call`, `autorun` or `parallel`). |
| `AuthoringSession.battle_event(hook, program_id, *, conditions=(), once=False)` | Run a program at a battle moment. |
| `AuthoringScene.entities()` | The scene's entities. |
| `AuthoringScene.entity(name_or_id)` | An entity by name or id. |
| `AuthoringScene.create_entity(name, *, x=0.0, y=0.0)` | Add a new entity at `(x, y)`. |
| `AuthoringEntity.name` *(property)* | The entity's name (read / write). |
| `AuthoringEntity.enabled` *(property)* | Whether the entity is on (read / write). |
| `AuthoringEntity.transform` *(property)* | Position, rotation and scale. |
| `AuthoringEntity.gameplay` *(property)* | Stats, resources and tags of the entity. |
| `AuthoringEntity.event(name='Event', *, trigger='action')` | A new event on the entity (`trigger`: `action`, `autorun` or `parallel`). |
| `AuthoringEvent.dialogue(speaker, text=None, *, portrait='', side='left')` | Add a dialogue line. |
| `AuthoringEvent.set_switch(name, value=True)` | Add SET_SWITCH. |
| `AuthoringEvent.set_variable(name, value)` | Add SET_VARIABLE. |
| `AuthoringEvent.wait(seconds)` | Add WAIT. |
| `AuthoringEvent.world(command, **args)` | Add a world command. |
| `AuthoringEvent.transfer(destination, **args)` | Add a TRANSFER to another scene. |
| `AuthoringEvent.sequence(*tracks, cutscene=False, skippable=False, wait='all')` | Add a SEQUENCE of parallel tracks. |
| `AuthoringEvent.append(opcode, **args)` | Add any opcode with its arguments. |
| `AuthoringEvent.end()` | Finish the chain (returns the entity or session). |
| `AuthoringGameplayAttributes.set_stat(name, value)` | Set a base stat. |
| `AuthoringGameplayAttributes.define_resource(name, maximum, *, current=None, minimum=0.0, replace=False)` | Give the entity a resource (HP, MP…). |
| `AuthoringGameplayAttributes.add_tag(tag)` | Add a tag. |
| `asteria.authoring.api.track(name, *steps)` | A parallel track of a sequence. |
| `asteria.authoring.api.move(entity, x, y, duration=1.0, *, relative=False, wait=True)` | A move step for a track. |
| `asteria.authoring.api.face(entity, facing)` | A facing step. |
| `asteria.authoring.api.animate(entity, clip)` | An animation step. |
| `asteria.authoring.api.say(speaker, text, *, portrait='', side='left')` | A dialogue step. |
| `asteria.authoring.api.world(command, *, wait=0.0, **args)` | A world command step. |
| `asteria.authoring.api.pause(seconds)` | A pause step. |
| `asteria.authoring.runner.run_authoring_script(source, project, *, execute=None, filename='<asteria-script>', selection_kind='none', selection_value=None)` | Run a script against a project outside the editor. |

### 15.13 Event programs as data

An event program is a list of instructions. The editor's Events workspace writes them; `project.event_programs` holds them by id.

| Signature | Description |
| --- | --- |
| `asteria.events.program.EventProgram(instructions, *, name='')` | A program: its instructions and a name. |
| `asteria.events.program.EventInstruction(opcode, args=None)` | One instruction: an opcode and its arguments. |
| `EventProgram.label_pc(name)` | The position of a LABEL. |
| `EventProgram.to_data()` | Serialise to JSON data. |
| `EventProgram.from_data(data)` | Read from JSON data (classmethod). |

### 15.14 Export

The same functions run behind File ▸ Export Game… and the command lines `asteria-export` and `asteria-export-web` (also `python -m asteria.export_web`).

| Signature | Description |
| --- | --- |
| `asteria.project_tools.export_game(project_path, output, *, allow_missing=False, bundle_engine=True)` | A game folder: the project, its files and the engine (`run_game.py`). |
| `asteria.project_tools.package_game(project_path, output, *, name=None, pyz=True, app=False, allow_missing=False, player=<bundled player>)` | The game folder plus a single-file `.pyz` and, on macOS, an `.app`. |
| `asteria.project_tools.build_pyz(game_folder, output, *, name)` | Zip a game folder into one `.pyz` file. |
| `asteria.project_tools.build_macos_app(pyz, output_dir, *, name, identifier=None)` | Wrap a `.pyz` in a macOS app. |
| `asteria.project_tools.upgrade_project(path, *, backup=True)` | Upgrade a project file to the current format (keeps a backup). |
| `asteria.project_tools.export_main(argv=None)` | The `asteria-export` command line. |
| `asteria.export_web.export_web(project_path, output, *, title=None, cjk_font='default', cdn=None, icon=None, width=1280, height=720, allow_missing=False, allow_unsupported_audio=False, build=True, serve=False, port=8000, run=run)` | A browser build with pygbag (`build/web/index.html` and the `.apk`). |
| `asteria.export_web.serve_web(web, port=8000, *, bind='127.0.0.1', ready=None)` | Serve a web build on `http://127.0.0.1:PORT`. |
| `asteria.export_web.main(argv=None)` | The `asteria-export-web` command line. |

### 15.15 Event opcodes

Conditions (`JUMP_IF`, `IF_FALSE_SKIP`, `WAIT until`, event pages) are `{source, name, operator, value}`; sources: `switch`, `variable`, `local`, `rpg`, `npc`, `battle`, `audio`; operators `==`, `!=`, `<`, `<=`, `>`, `>=`.

| Opcode | Arguments | Does |
| --- | --- | --- |
| `DIALOGUE` | speaker, text, text_key, portrait_asset_id, portrait_side, wait | Show a line; `wait: false` keeps it on screen while the event goes on. |
| `CHOICE` | prompt, prompt_key, choices [{text, value, text_key, hover}], variable_name, local_name, cursor, cancel, columns, box_at | Ask a question; the picked option's value goes into the variable. |
| `WAIT` | seconds \| until {condition} (+ seconds) | Wait some seconds, or until a condition holds. |
| `SET_SWITCH` | name, value | Turn a switch on or off. |
| `SET_VARIABLE` | name, value \| add \| from_variable | Set, add to or copy a variable. |
| `SET_LOCAL` | name, value (scope_id) | A variable of this event's own entity. |
| `LABEL` | name | A place to jump to. |
| `JUMP` | label | Go to a label. |
| `JUMP_IF` | condition, label | Go to a label when the condition holds. |
| `IF_FALSE_SKIP` | condition, count | Skip the next `count` instructions when false. |
| `CALL` | program_id, scope | Run another program, then come back. |
| `RETURN` |  | Back to the calling program. |
| `EXIT` |  | Stop the whole event, called programs too. |
| `END` |  | End this program. |
| `WORLD` | command, args | Run a world command (table below). |
| `SEQUENCE` | tracks, cutscene, skippable, wait | Parallel tracks of moves, lines and commands (a cutscene). |

### 15.16 World commands

The 83 commands a `WORLD` instruction can run, with the argument names each reads (`asteria.runtime.world_command_handlers.WORLD_COMMAND_ARGUMENTS`). In the editor: Events ▸ World.

| Command | Arguments |
| --- | --- |
| `ADD_COUNTER` | counter_id, amount |
| `ADVANCE_QUEST` | quest_id, objective_id, amount |
| `BATTLE_SEQUENCE` | sequence_id, actor_id, target_id |
| `CAMERA_FOCUS` | entity, x, y, zoom, blend, ease |
| `CAMERA_RELEASE` | blend, ease |
| `CAMERA_SHAKE` | intensity, duration |
| `CHANGE_CURRENCY` | currency_id, amount |
| `CHANGE_RELATIONSHIP` | subject_id, amount |
| `CHANGE_REPUTATION` | faction_id, amount |
| `COMPLETE_QUEST` | quest_id |
| `COPY_ENTITY` | entity, x, y, name |
| `DISASSEMBLE` | item_id |
| `EQUIP_ITEM` | actor_id, equipment_id, slot_id, index |
| `ERASE_PICTURE` | picture_id |
| `FAIL_QUEST` | quest_id |
| `GIVE_EQUIPMENT` | equipment_id, quantity |
| `GIVE_ITEM` | item_id, quantity |
| `GIVE_PET` | species_id, level, nickname, moves |
| `GRANT_EXPERIENCE` | actor_id, amount, threshold, points, level_track |
| `GRID_ROUTE` | entity, steps |
| `HEAL_PETS` | party_only |
| `INTERACT` | interaction_id |
| `JOIN_PARTY` | actor_id, active |
| `LEARN_ABILITY` | actor_id, ability_id |
| `LEARN_RECIPE` | recipe_id |
| `LEAVE_PARTY` | actor_id |
| `MORPH_ENTITY` | entity, prefab_id |
| `MOVE_NPC` | npc, scene_id, x, y |
| `MOVE_PICTURE` | picture_id, x, y, scale, opacity, tint, tint_color, duration, easing, delay |
| `MOVE_ROUTE` | entity, route, step, speed |
| `NAME_INPUT` | target, max_length, title, default, initial |
| `NEW_GAME_PLUS` | rules_id |
| `OPEN_CRAFTING` | station |
| `OPEN_GACHA` | banner_id |
| `OPEN_QUEST_BOARD` | board_id |
| `OPEN_RECRUIT` | office_id |
| `OPEN_SHOP` | shop_id |
| `PARTY_RESTORE` | — |
| `PARTY_STASH` | — |
| `PET_STORAGE` | — |
| `PICTURE_CHOICE` | layout, variable |
| `PLAY_ACTION` | entity, timeline_id |
| `PLAY_BGM` | asset_id, fade, volume, temporary |
| `PLAY_ME` | asset_id, volume |
| `PLAY_SE` | asset_id, volume |
| `PLAY_VFX` | asset_id, entity, x, y, scale, anchor |
| `REFINE_EQUIPMENT` | actor_id, instance_id, protect |
| `RESTORE_BGM` | — |
| `REST_PARTY` | — |
| `SCREEN_FADE` | to, duration, color |
| `SET_BATTLE_WEATHER` | kind, intensity, wind |
| `SET_CLASSES` | actor_id, class_ids, unlock |
| `SET_ENTITY_ICON` | entity, icon_id |
| `SET_LIGHT` | radius, speed, off |
| `SET_LOCALE` | locale |
| `SET_LOOK` | entity, sprite_sheet_asset_id, clip_set_id |
| `SET_MOVEMENT` | entity, behaviour, facing |
| `SET_NPC` | npc, key, value |
| `SET_PICTURE_FRAME` | picture_id, frame |
| `SET_POSITION` | entity, x, y, facing, permanent |
| `SET_RESPAWN` | scene_id, x, y, facing |
| `SET_TILE` | layer, x, y, tile, permanent |
| `SHOW_BALLOON` | entity, balloon, duration_ms |
| `SHOW_ENTITY` | entity, shown |
| `SHOW_PICTURE` | picture_id, asset_id, x, y, scale, opacity, frame, columns, rows, layer, click_event, tint, tint_color, frame_rate, frame_loop, scroll_x, scroll_y, wave_amplitude, wave_length, wave_speed, blend, text, font, text_color, shadow_color, text_align |
| `SHOW_POPUP` | text, entity, duration_ms, kind |
| `SOCKET_ITEM` | actor_id, instance_id, socket_id, item_id |
| `SPAWN_ENTITY` | prefab_id, x, y, name |
| `START_ENCOUNTER` | encounter_id |
| `START_QUEST` | quest_id |
| `STOP_BGM` | fade |
| `SUMMON` | enemy_id, actor_id, count, owner_id |
| `TAKE_ITEM` | item_id, quantity |
| `TIMER_ADD` | timer_id, seconds |
| `TIMER_PAUSE` | timer_id |
| `TIMER_RESUME` | timer_id |
| `TIMER_START` | timer_id, seconds, on_expire, count_up, show |
| `TIMER_STOP` | timer_id |
| `TITLE_COMMAND` | action, screen |
| `TRANSFER` | scene_id, x, y, facing |
| `UNSOCKET_ITEM` | actor_id, instance_id, socket_id |
| `UPGRADE_EQUIPMENT` | actor_id, instance_id, node_id |
| `WALK_TO` | entity, x, y, speed |

<!-- END API -->
