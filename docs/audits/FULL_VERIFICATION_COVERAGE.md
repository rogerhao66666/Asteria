# Full Verification - coverage checklist

The Full Verification demo (`reference_projects/full_verification_demo`) is a stress test of the turn-based part of
the engine. This file lists every system on the "not covered yet" list the user asked for, and
where each one is exercised. Out of scope by decision: real-time (action) combat, multiplayer, loose
loot on the ground. (New Game Plus, translations, the music room and map areas were out of scope at
first; the user asked for them on 2026-10-18 and they are covered below.)

How it is verified:

* `tests/test_full_verification_campaign.py` plays the whole game through the host
  (`run_campaign.py`: four maps, three bosses, four party members, 8 fights) and asserts on it.
* `scripts/full_verification_campaign_live_check.py` plays the same campaign in a real Cocoa window,
  starting with real key presses; pictures in `docs/audits/evidence/full_verification_campaign/`.
* The earlier batches keep their own tests (`test_full_verification_b11.py`, `_b12.py`, `_editable.py`,
  `_workshop.py`) and real-window scripts (`full_verification_b11/b12/b13_live_check.py`).

## Cast (2026-10-18)

The hero (Roger, Lucifer Warrior; called Aldric until 2026-10-24, D65) sets out alone. Three companions are hired at the adventurers'
guild in Hearthfold, each with art no one else wears: Mira (Sorceress) waits there from the start,
Vesper (Necromancer) and Cael (Cultist) walk there once met after the woods and catacomb bosses.
Guildmaster Orla sends a companion back to wait (LEAVE_PARTY) and they can be hired again.
Townsfolk wear the same figures in plain sepia colours, so none looks like a party member. The
summon (Spirit Rider) is the Lucifer Goblin Rider. Foes: three bosses (Goblin Beast, Skeleton
Ancient, Vaelor the Skeleton King) plus three kinds of minion (Goblin Slinger, which can be tamed;
Skeleton Hunter; Vaelor's Skeleton Acolyte), three foes in the woods and two in the catacombs.

## Jobs (phase 1, 2026-10-18)

Every party member has a main job and a sub job. The companions walk three-tier lines
(MapleStory style), advanced and trained at the Job Master in Hearthfold: Mira Cleric -> Priest
(Lv 5) -> Bishop (Lv 10), sub Mystic; Vesper Necromancer -> Lich -> Death Lord, sub Knight; Cael
Cultist -> Zealot -> Heretic, sub Duelist. Roger keeps Knight -> Guardian -> Hero, Duelist ->
Weapon Master / Rogue, Mystic -> Sage. 19 jobs, a skill tree per job (212 nodes), job points per
job. The campaign makes all six advances; the smoke fights every companion in every tier (18 of
18 jobs use their skills).

## Skill trees (phase 2, 2026-10-18)

554 tree nodes in four styles. **Atlas of Fate** (Path of Exile): a shared passive web every
member walks with ability points (2 a level): six sectors (Might, Arcana, Bulwark, Swiftness,
Precision, Vigor), each a gate, small nodes, two notables and a keystone that trades one strength
for another; bridges join neighbours; drawn as a web (authored positions). **Specializations**
(World of Warcraft): every job tree has three exclusive specs (Priest: Holy / Discipline /
Shadow ...), each with two ranked talents and a capstone passive (54 spec passives). **Runes**
(Diablo III): each job's rune skill takes Ember (fire + burn), Echo (twice the hits) or Siphon
(heals the user); the rune node grants a tag and an evolution that needs the tag swaps the skill
(54 rune skills; engine: `AbilityEvolutionRule.required_tags`). **Skill books** (MapleStory): a
ten-rank book per job paid with skill points from levels (shrine, Job Master training). The
campaign spends every member's points across all four; runes show up as the skills used.

## Gear and crafting (phase 3, 2026-10-18)

40 pieces of equipment: a second tier of every weapon (two gem sockets, a card socket), heavy /
light / cloth armour in two tiers (a card socket), six accessories (a gem socket) and a set per
companion (Vestments of Dawn, Regalia of the Grave, Raiment of the Zealot: 2- and 3-piece
bonuses) whose weapon enchants (Kindle opens a card socket, three Stars, a Light / Shadow path,
Masterwork). Seven gems, each fused into a flawless one at the alchemy station; ten cards, one
per foe (bosses always drop theirs, minions rarely). Refining +N for weapons and armour uses
ores and a Blessed Scroll keeps the level on a failure (engine: `RefineRules.materials`,
`protect_item`; gear commands take `slot:<slot>`). Six more affixes, three more concoctions,
gem recipes and disassembly. Every record has an icon (Lucifer equipment and pickups, tinted
when reused; cards show their monster). The campaign dresses all three companions, fuses three
gems, sockets two boss cards, enchants three weapons and refines armour nine times (three
protected).

## Battle screen

Party HP down the right edge; the command menu always at the acting member's lower right, drawn
over anything else; foes show a name over the head (never covering another combatant or name) and
no health bar. The bestiary (pause menu) unlocks a foe's weaknesses and health after the first kill
and lists only the drops that really fell.

## Whole-game flow (not one fight)

| What | Where it happens in the campaign |
|---|---|
| Level ups | Shrine (gold for experience on a drawn level curve), battle experience, pet and party levels |
| Skill tree, job points, ability points, attribute points | `Campaign.allocate` after the shrine; points come from levels and fights |
| Job change and job unlock rules | Job teachers (levels 1-8, jobs they need), `set_classes` at the rogue and hero steps |
| Weapon growth, refine, sockets (and taking gems out) | Smith, Jeweler, Card Dealer menus |
| Equipment (off-hand weapon, rolled drops in the bag) | Armory menu; boss drop tables roll rarity and affixes |
| Alchemy and concoction | Alchemist station; concoct skill in battle |
| Capture, pet unit, pet evolution | Goblin Slinger tamed in the woods; evolves to War Slinger; fights beside the party |
| Quests, shops, story events | Warden chain (4 quests), bounty clerk, shop, inn, the guild (hire Mira, Vesper, Cael; send one back and hire again) |
| Save and load in the middle | `save_and_reload` in the woods; party, level, quests, pets must be unchanged |

## The empty database categories

| Category | Used by |
|---|---|
| Factions | Hearthfold Wardens (rank Ally at the end), Bonewalker Court (goes negative); reputation rewards, achievement |
| Inventory rules | `trial_bag`: 64 kinds, overflow reported (`test_the_bag_has_a_limit...`) |
| Behaviour trees | `foe_patrol` drives the goblins and skeletons in view (they roam and chase; `foes_roamed`) |
| World interactions | Search the old cache, persuade the scout, pick the sealed vault |

## Battle rules

| System | Where |
|---|---|
| Other battle objectives | `beast_down`, `ancient_down`: a fight ends when its leader falls; absent leaders do not end other fights |
| Weather | Doors set rain / none / dust; rain feeds lightning and drowns fire, dust dims light |
| Shared (party) gauge and taunt | `unity` gauge fills as the party hits and is hurt, `Unity Strike` (Limit group) spends it; `Taunting Roar` |
| Other turn scheduler | `classic_rounds` (round mode) picked by the `scheduler:` tag of two encounters |
| Escape | Woods fights can be fled, boss halls carry `no_escape` |
| Ability fields | `requires_items` (Grave Whisper), `requires_pet` (Beast Command), `menu_category` (Limit, Beast, Rites), `gauge_costs`, forms, follow tags, item / currency / battle costs |

## Battle categories (phase 4, 2026-10-18)

| Battle-tab category | Where the campaign uses it |
|---|---|
| Battle Resources | `momentum` (+1 a turn, max 10) pays Momentum Strike and Party Rush; `soul` (+1 a round, max 6) pays Soul Burst |
| Outcome Checks | `block` on every foe blow; a blocked hit takes half (`blocked_half`), 10 blocks in the run |
| Turn Schedulers | `swift_timeline` (continuous) in the crypt patrol, `classic_rounds` for the vigil |
| Action Timing / Transactions | Long casts (Holy Judgment, Mass Cure, Death Coil, Soul Harvest, Forbidden Rite, Frost Nova) |
| Sequences | `party_rush`: the actor leads, the party follows with Rush Blow (world command `BATTLE_SEQUENCE`) |
| Gauge Compositions | `overdrive`: crits add momentum; at 10 the striker gains Attack Up and it resets |
| Reactions | `cover` (Roger intercepts a blow at an ally), `follow_up` (Cael's Chase Strike) |
| Objectives / Escape / Session Rules | Acolyte Vigil at the throne: survive 8 rounds (`objective:vigil_survive`), its own `rules:vigil_gauntlet`; `escape:woods_escape` / `crypt_escape` rates |

Engine gaps this phase found and fixed: objectives never ended a fight (the session now settles
them each turn), sequences could not be reached from an ability, only the first escape / session
rule was ever used (encounters now pick one by tag), and a follow-up aimed at a foe the first blow
already felled crashed the battle (the reaction is now skipped as `no_target`).

Balance note: by the throne Roger (Lv 22) has power 3147 and one-shots about 98k HP; the web,
specs, books, gear and refining stack. The vigil foes are warded so the 8 rounds really happen.

## Presentation, slots and field strikes (phase 5, 2026-10-18)

| Category | Where the campaign uses it |
|---|---|
| Side-View Positions | `crypt_ranks`: the catacomb guards stand in a staggered rank against the party's (`stage:crypt_ranks` on `crypt_guard`) |
| Portrait Party Layout | `vigil_portrait`: the Acolytes' Vigil keeps the party in its HUD (bodies hidden), the acolytes in one line |
| Command Menu Pages | `trial_commands` (named by the layout's `command_pages`): five commands, then a More page with the rest (Fight, Skills, Arts, Limit, Combos, Rites, Beast, Bag, Run in that order); six rows a page |
| Command Input Steps | `elemental_weave`: Vesper picks an element, then up to two focuses (Overcharge x1.5 for 12 SP, Echo x1.25 for 1 Soul) through the real command menu |
| Ability Slots | `trial_slots`: the Old Master teaches four arts (`LEARN_ABILITY`); two slots, three from level 10, four from level 18; a full slot refuses, an unset art is not usable |
| Attacks / Projectiles | `field_slash` (J) and `sling_throw` (1, the `sling_stone` projectile): hitting a foe in view first opens its fight preemptive |

Engine gaps this phase found and fixed: the four presentation categories had no runtime reader
(the layout now names `stage_template` / `command_pages`, encounters pick staging with
`stage:<id>`, abilities name `input_workflow`, workflow steps carry their `options`, combatant
visuals can hide their body); staging zones gained `x_step`; turn-based maps could not use field
attacks (a player with ActionCombat bindings now strikes there, shots are drawn, and
`VisibleEncounter.struck_opening` starts the fight); `start_encounter(opening=)`; no world
command taught a skill (`LEARN_ABILITY`). Skill effects drifted off their target: a swipe sheet
draws its picture in one side of each frame and the battle centred the frame, so a slash landed
up to ~20 world pixels beside the foe. VFX now centre the clip's drawn picture on the member
(placement `align`: `content`, or `frame` for the old rule; editable in the VFX tool, the
preview follows it).

## Map areas, New Game Plus, translations, music room (2026-10-18)

| Category | Where the campaign uses it |
|---|---|
| Map Areas | `trial_areas` on a hidden Regions layer: the woods' poison bog (40 HP/s, a bog battle backdrop; the escape fight happens there), the warden's glade (foes cannot enter, the party rests), the catacombs' shadowed halls (foes see half as far; the crypt guards fight on a crypt backdrop), the throne's ember floor (burns while `vaelor.awake`, out after the win) |
| New Game Plus | `trial_again`: the Victory Banner offers it; levels (cap 40), skills, gear, bag, pets and bestiary carry, gold halves, `ngplus.` and `music.heard.` switches stay; the Hall of Heroes plaque then names Roger |
| Translations | `en` and `zh-TW` tables; Scholar Lin (`SET_LOCALE`) or Settings > Language switches; area lines, the plaque, the banner and the scholar speak through `\T[key]` |
| Music Room | five themes with pictures, opened by hearing them (`PLAY_BGM`) or by beating the Goblin Beast |

Engine gaps found and fixed: the game host's tile view never applied map areas (only the old
preview did); behaviour-tree foes ignored area stealth (`sight_scale` now scales `player_within`,
`player_beyond` and a chase's `lose_radius`); no command switched the language or started New
Game Plus (`SET_LOCALE`, `NEW_GAME_PLUS`, the host adopts the carried save); Settings had no
Language row; the Music Room did not draw track icons; doors can turn switches on.

Editor fixes: opening a second project with the same id left Game Data, Battle Rules and Battle
Presentation showing the first project (the hosts now compare the project itself); the skill
tree graph drew black text on the dark theme and no icons (it now draws a card per node with
its icon, name, ranks and gift, coloured by kind, with arrows, and opens as the graph); a node
without an icon shows its skill's or passive's.

## Townsfolk and Roger's house (2026-10-19)

Every person on the maps wears a look of their own (`trial_people.CAST`): the hero and the three
companions keep their Lucifer characters, the 28 others are distinct Ninja Adventure characters
(CC0) at 1.5x, the shrines, plaque and banner are spirits and statues, the cache a bag, the vault
a chest (`tests/test_town_people_and_home.py` fails if two share a picture). Roger's house stands
in Hearthfold's north-east corner; the game starts at its door. Inside, the bed's Sleep fades out,
rests the party (`REST_PARTY`) and fades in; the campaign hurts the hero, sleeps and checks full
health (`home_sleeps`).

## Roger the Brave and Archmage, the Demon Ring, stronger foes (2026-10-19)

`trial_brave.py`. Roger starts as a **Brave** (main) with an **Archmage** sub job; the job
teachers and the vault let him try others, and he returns to the pair.

| What | Design |
|---|---|
| Brave | Every weapon (`capability.weapon.*`: sword, axe, spear, dagger, bow, staff, ring); power and magic grow together; nine skills: Valiant Slash, Aegis of Courage, Heroic Lance, Gigaslash, Rallying Cry, Lightbringer, Dragon Slayer, Arsenal Storm (one blow with each weapon, so any weapon weakness lands), Final Hope (divine, 3 BP) |
| Archmage | Every element: fire, ice, lightning, light, dark and the new wind and earth (weak / resist rules, foes tagged); a Bolt and a Storm each, Prismatic Cataclysm (seven elements), Mana Shield, Arcane Surge |
| Brave tree (38 nodes) | 10-rank core, the skills, a 5-rank mastery per weapon (its blows x1.25), Weapon Saint (all seven at rank 3), three exclusive Oaths, Hero's Resolve, three specs with talents and capstones, three runes on Valiant Slash, a skill book; Final Hope needs Dragon Slayer, Lightbringer and an Oath |
| Archmage tree (52 nodes) | 10-rank core, seven schools (school, Bolt, Storm, Attunement: that element x1.25), Mana Shield, Arcane Surge, three exclusive Paths, Archmage's Insight, three specs, runes on Fire Bolt, a book; Prismatic Cataclysm needs fire / ice / lightning attunement and one more |
| Demon Ring | A ring weapon (power +45, magic +45, crit, speed); seven sockets - three cards, two gems, two charms (six new charm attachments); its attack strikes five times; in the Family Chest in Roger's house: it goes to the bag and the game asks whether to wear it in his free second hand |
| Foes | See the next two sections |

The campaign opens the chest, sockets two charms, and uses the ring's five-strike attack,
Valiant Slash, Arsenal Storm and the wind and earth bolts against the stronger foes; it still
wins every fight. The bag holds 64 kinds now (the charms did not fit in 40).

## New gear asks before it is worn (2026-10-19)

Engine: `InventoryRules.equip_offer` - `never` (the default: new gear waits in the bag),
`empty_slot` (asks only when a party member has a free place for it) or `always` (also offers a
swap; the worn piece goes to the bag). The bag rules form in the editor has the field ("Ask to
Wear New Gear"). `GIVE_EQUIPMENT` gives gear to the bag; chests, drops and loot all ask through
the same offer. The playtest host shows "New: <name> / <who> has a free <place>. Wear it now?"
(1 / Enter: wear it, 2 / Esc: keep it in the bag).

Demo: `empty_slot`. Roger starts with only Sunbrand, so the chest's Demon Ring is offered for
his free hand (the campaign says yes); the Armory's pick is offered too (the campaign keeps it
in the bag). Fact `equip_offers` = 2.

## Battle mechanics that are felt, and foes that are truly strong (2026-10-19)

`trial_brave.mechanics`, all project data (Battle Rules: Interactions, Chance Checks, Gauges;
States; Enemies; Jobs; Battle Presentation > Feedback):

| What | Design |
|---|---|
| Weakness / resistance | x1.8 / x0.4 (were x1.3 / x0.5); every weakness hit chips the shield |
| Critical blows | see the stats section below (5% + 0.3% x crit, x(2 + 1% x critical damage)) |
| Evasion | see the stats section below (accuracy against evasion) |
| Bosses | Many weaknesses behind thick shields: Goblin Beast 16 (seven weaknesses), Ancient Skeleton 24 (nine), Crimson Warlord 36 (ten) - a weak *critical* blow chips two. Broken: x2.5 damage taken and three turns lost |
| Guard / dodge | Foes with `trait.guard` guard 30% of the party's blows (x0.3); `trait.dodge` foes dodge 20-35% (by speed). Neither while broken, stunned, asleep or frozen (the new blocked tags on Chance Checks) |
| Foe states | Their blows leave bleed, blind, burn, poison + silence, magic down, stun, defence down, power down |
| Damage over time | Poison 3% / burn 4% / bleed 5% of the holder's maximum health a turn; regen gives 4% back (state ticks can use formulas now) |
| Foes | Retuned in the stats section below, after the compounding-stats fix |
| Party health | Every job gains maximum health per level (Brave 160, Guardian 150, Knight 130, Archmage 70, most 80) - before, health never grew with level |
| On screen | WEAK, CRITICAL, GUARD, MISS, BLOCK, BREAK!, OVERDRIVE, ABSORB, REFLECT labels on the hits (the feedback profile was empty) |

Measured on the scripted campaign (rounds, the lowest any hero fell to) - before the stats
rework below found that hero stats compounded after every fight; see there for today's numbers:

| Fight | Before | Now |
|---|---|---|
| Woods boss | 4 rounds, party untouched (every foe blow missed) | 4 rounds, party at 95% |
| Crypt guard | 2 rounds, untouched | 5 rounds, down to 79% |
| Crypt boss | 1 round | 4 rounds, down to 83% |
| Ember vigil | 8 rounds (held), 85% | 8 rounds (held), 99% |
| Crimson Warlord | 2 rounds, down to 5% | 7 rounds, down to 43% |

New campaign facts: `guarded_blows` 15, `dodged_blows` 51, `critical_blows` 51, `breaks` 4
(`boss_breaks` 2), `status_ticks` 31. The scripted player now heals when it is low or (half the
time) when an ally is. The smoke covers the boss's mechanics on Normal (the campaign plays
Legend).

Engine fixes found on the way: `ClassDefinition.resource_growth` (health per level, in the job
form); state ticks and apply / remove / expire effects get a formula context (the holder);
`OutcomeCheckDefinition.blocked_source_tags` / `blocked_target_tags`; `Battle.apply_state` and
`Battle.resolve_targets` use the battle's seeded dice (they used Python's unseeded global
random, so status hits differed on every run).

## Stats with written formulas: STR / DEX / INT / LUK, accuracy, elements (2026-10-19)

`trial_stats.py`. Every number is project data the editor shows.

| What | Design | In the editor |
|---|---|---|
| Attributes | STR, DEX, INT, LUK (and VIT for health) from stat points in the Attributes tree, which every hero's tree screen now shows; each actor starts with its own, every job grows them (the jobs' old attack growth became attribute growth) | Game Data > Skill Trees, Jobs |
| Formulas | power += 2 STR + 0.5 DEX; magic += 2 INT + 0.5 LUK; defense += 1 STR + 0.5 DEX; magic_defense += 1 INT + 0.5 LUK + 0.5 defense; accuracy += 1 DEX + 0.5 LUK; evade += 0.5 DEX + 1 LUK; crit += 0.5 LUK + 0.2 DEX; crit_damage += 0.3 LUK + 0.1 STR; speed += 0.3 DEX | Game Systems > Stat Formulas |
| Hit | 95% + 0.3% x attacker accuracy - 0.3% x target evasion, 30% to 100%; Blind: half the blows miss | Battle > Chance Checks |
| Critical | 5% + 0.3% x crit, at most 65%; damage x(2 + 1% x crit_damage) | Chance Checks, Damage Interactions |
| Block | defence-based, x0.5, physical blows only (spells are not blocked) | Chance Checks |
| Physical / magic | a blow's user stat picks the defence: power against defense, magic against magic_defense | Abilities |
| Elements | `<element>_attack` / `<element>_resist` for all seven: x(1 + 1% x attack - 1% x the target's resistance), on top of weakness x1.8 / resistance x0.4 | Damage Interactions (`element_*`) |
| Gear | element attack on weapons, rings, gems; resistances and magic defence on robes, armour, amulets, cards; accuracy and critical damage on accessories and cards; the Lion / Owl / Falcon / Viper / Serpent charms give STR / INT / DEX / LUK | Equipment, Attachments |
| Foes | magic defence (0.5 to 1.5 x their defence), accuracy, element attack and resistance (negative = takes more) | Enemies |
| Skill text | every skill says Physical, Magic or Physical + Magic, its element or Non-elemental, then hits, targets, states, drains (for example "Physical + Magic / Light: 2 hits, inflicts Defence Down"); shown in a help box over the battle menu | Abilities > Description |
| More effects | Defence Down, Bleed, Power Down, Slow, Freeze, Stun, Blind, Silence on the party's skills; Armour Up, Regen, Haste, Mirror, Focus on the user; SP drain on the dark spells | Abilities |
| Status screen | the stats named and ordered: attributes, attack and defence, accuracy, evasion, criticals, speed, element attack / resistance | Presentation > Character Screen (`stat_order`) |

Engine changes on the way: `DerivedStatRule` (rpg_database.derived_stats, run last in every
build; enemies too when set to); `InteractionRule.multiplier_source_terms` /
`multiplier_target_terms`; `AbilityDefinition.description`; hit checks see the skill's and the
hit's tags (a check can refuse `magic`); `CharacterScreenProfile.stat_order`; the tree screen
names stats as the status screen does.

Bugs found and fixed: a battle saved the heroes' *finished* stats and health as their base, so
every build added level growth, trees, gear and passives again - stats compounded after every
fight (Roger's power had climbed to 5,431 at the end; 770 honestly). Snapshots now keep the
base, and health is stored without the build's bonus. A round where nobody can act (all
stunned, the boss broken) no longer stalls the battle, and a foe that dies on its own turn
(poison, burn) now ends the fight in victory. The escape chance weighs the foes' speed too.

Balance on the honest numbers (scripted campaign, rounds, the lowest any hero fell to): woods
boss 9 rounds, 66%; crypt boss 11 rounds, 53%; the vigil (held) 8 rounds, 19%; the Crimson
Warlord 16 rounds, two heroes knocked out. Facts: `guarded_blows` 40, `dodged_blows` 70,
`critical_blows` 39, `breaks` 3, `status_ticks` 78, `blocked_blows` 47.

## Weapons: whole Lucifer pictures and their rarity (2026-10-19)

Every weapon wears a whole picture from the Lucifer Equipment pack (`Weapons/Png`, 32 x 16);
before, eight were cut to their left half (the icon step read any wide picture as an animation
strip). Each weapon carries the rarity its picture names - the new optional
`EquipmentDefinition.rarity`, shown as the cell colour and the name in the bag:

| Rarity | Weapons (picture) |
|---|---|
| Common | Iron Sword (Arming Sword), Steel Sword (Greatsword), Stiletto (Shamshir), Hand Axe (Bearded Axe), Wyrm Lance (Spear), Oak Staff (Wizards Pole), Hunter's Bow |
| Rare | **Sunbrand, Roger's sword (Rare Greatsword)**, Ritual Kris (Explorers Hook), Dragoon Lance, Ash Staff (Mages Spire), Saint's Staff, Longbow |
| Legendary | Kris (Rapier), War Axe (Dane Axe), Dawnbreaker (Shamshir) |
| Mythic (new, never rolled as loot) | Bone Scepter (Godhammer), Demon Ring, **Titan Cleaver (Mythic Battleaxe)** - a new axe (power 75, crit 10, STR 10, earth +25, two gem and one card sockets) the crypt's Ancient Skeleton always leaves (campaign fact `titan_cleaver`) |

The bows: the Lucifer pack has none, so the Hunter's Bow and the Longbow wear HomoHikka's CC0
bow (OpenGameArt) with the Lucifer outline of their rarity, and the bow attack shows it. The
art comes from the engine's asset library (`asset_library/`, see THIRD_PARTY_ASSETS.md), not
from `~/Downloads`.

## World commands (58)

Used in the campaign or by Showman Pip's menu: TRANSFER, GIVE_ITEM, TAKE_ITEM, START_QUEST,
ADVANCE_QUEST, COMPLETE_QUEST, FAIL_QUEST, CHANGE_REPUTATION, CHANGE_RELATIONSHIP, ADD_COUNTER,
LEARN_RECIPE, PLAY_BGM, STOP_BGM, PLAY_SE, SCREEN_FADE, CAMERA_FOCUS / RELEASE / SHAKE, PLAY_VFX,
PLAY_ACTION, INTERACT, SET_NPC, MOVE_NPC, SHOW_POPUP, UNSOCKET_ITEM, WALK_TO, MOVE_ROUTE,
SHOW_BALLOON, SET_ENTITY_ICON, SPAWN_ENTITY, COPY_ENTITY, MORPH_ENTITY, SET_BATTLE_WEATHER,
SHOW_PICTURE, MOVE_PICTURE, SET_PICTURE_FRAME, ERASE_PICTURE, TIMER_START / STOP / PAUSE /
RESUME / ADD, plus the earlier ones (OPEN_SHOP, OPEN_CRAFTING, SET_CLASSES, GRANT_EXPERIENCE,
REFINE / SOCKET / UPGRADE_EQUIPMENT, EQUIP_ITEM, DISASSEMBLE, SUMMON) and the new JOIN_PARTY,
LEAVE_PARTY, REST_PARTY, BATTLE_SEQUENCE, LEARN_ABILITY, SET_LOCALE, NEW_GAME_PLUS.

## Scenes and events

Four tile scenes (Hearthfold, Whispering Woods, Catacombs, Ember Throne) with doors both ways, 30+
event programs (menus with CHOICE, branches on switches and on the new `rpg` condition source),
cinematic moments (fade, camera focus, shake, popups, pictures, music per area).

## Engine gaps this found and fixed on the way

JOIN_PARTY / LEAVE_PARTY / REST_PARTY, `rpg` event conditions (level, items, gold, jobs, party,
reputation, quest status), party-gauge costs on abilities, `scheduler:` encounter tag, named
COPY_ENTITY / SPAWN_ENTITY, pet units no longer break saves, objective conditions ignore absent
members, move beats skip combatants that left, the playtest host walks tile maps (walls, doors,
bounds), keeps PLAY_BGM, and redraws the right map after a load; UI skin (nine-patch panels, row
buttons, font), `column_size` and `front_large_zones` stage layout, three attack animations per
Lucifer character.
