# Boss Trial - coverage checklist

The Boss Trial demo (`reference_projects/boss_trial_demo`) is a stress test of the turn-based part of
the engine. This file lists every system on the "not covered yet" list the user asked for, and
where each one is exercised. Out of scope by decision: real-time (action) combat, multiplayer, new
game plus, localization, music room, map rules, loose loot on the ground.

How it is verified:

* `tests/test_boss_trial_campaign.py` plays the whole game through the host
  (`run_campaign.py`: four maps, three bosses, four party members, 8 fights) and asserts on it.
* `scripts/boss_trial_campaign_live_check.py` plays the same campaign in a real Cocoa window,
  starting with real key presses; pictures in `docs/audits/evidence/boss_trial_campaign/`.
* The earlier batches keep their own tests (`test_boss_trial_b11.py`, `_b12.py`, `_editable.py`,
  `_workshop.py`) and real-window scripts (`boss_trial_b11/b12/b13_live_check.py`).

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
| Quests, shops, story events | Warden chain (4 quests), bounty clerk, shop, inn, recruits Vesper and Cael |
| Save and load in the middle | `save_and_reload` in the woods; party, level, quests, pets must be unchanged |

## The empty database categories

| Category | Used by |
|---|---|
| Factions | Hearthfold Wardens (rank Ally at the end), Bonewalker Court (goes negative); reputation rewards, achievement |
| Inventory rules | `trial_bag`: 40 kinds, overflow reported (`test_the_bag_has_a_limit...`) |
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

## World commands (54)

Used in the campaign or by Showman Pip's menu: TRANSFER, GIVE_ITEM, TAKE_ITEM, START_QUEST,
ADVANCE_QUEST, COMPLETE_QUEST, FAIL_QUEST, CHANGE_REPUTATION, CHANGE_RELATIONSHIP, ADD_COUNTER,
LEARN_RECIPE, PLAY_BGM, STOP_BGM, PLAY_SE, SCREEN_FADE, CAMERA_FOCUS / RELEASE / SHAKE, PLAY_VFX,
PLAY_ACTION, INTERACT, SET_NPC, MOVE_NPC, SHOW_POPUP, UNSOCKET_ITEM, WALK_TO, MOVE_ROUTE,
SHOW_BALLOON, SET_ENTITY_ICON, SPAWN_ENTITY, COPY_ENTITY, MORPH_ENTITY, SET_BATTLE_WEATHER,
SHOW_PICTURE, MOVE_PICTURE, SET_PICTURE_FRAME, ERASE_PICTURE, TIMER_START / STOP / PAUSE /
RESUME / ADD, plus the earlier ones (OPEN_SHOP, OPEN_CRAFTING, SET_CLASSES, GRANT_EXPERIENCE,
REFINE / SOCKET / UPGRADE_EQUIPMENT, EQUIP_ITEM, DISASSEMBLE, SUMMON) and the new JOIN_PARTY,
LEAVE_PARTY, REST_PARTY.

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
