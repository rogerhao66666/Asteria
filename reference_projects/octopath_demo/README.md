# Octopath-style Battle Demo

A playable Asteria project whose battle works like Octopath Traveler — built only from project data on top of
the Complex Reference RPG's CC0 art (see `playable_assets/CREDITS.md`). The engine has no Octopath code; every
rule below is an authored record you can open and change in the editor.

```bash
.venv/bin/python -m asteria.runtime.preview reference_projects/octopath_demo/project.asteria.json
```

Rebuild it after changing the script: `python reference_projects/octopath_demo/build_project.py`.

## The party

| Traveller | Main job / secondary job | Weapons |
|---|---|---|
| Garrick | Warrior / Merchant | sword + spear |
| Sera | Hunter / Thief | bow + dagger |
| Bram | Apothecary / Cleric | axe + staff |
| Ione | Scholar / Dancer | staff + dagger |
| (pets) | Sera starts with a tamed Frost Lynx in the bag; an Ember Hound can be captured | — |

## What to try

- **Weaknesses and shields.** Under each enemy: its shield count and its weaknesses (`?` until you hit one). A
  weakness hit takes a shield point; at 0 the enemy is **BROKEN** — it loses its turn and takes double damage,
  then its shields come back.
- **Boost.** Left / Right raise the boost level (boost points are the pips under each traveller; +1 per turn).
  Attacks hit once more per level; spells (`boost.power`) grow stronger instead.
- **Divine skills** — *Brand of Valor*, *Arrowstorm*, *Last Stand*, *Elemental Storm* — cost **3 boost points**.
  The menu shows why they wait ("Needs 3 bp").
- **Twin Fang** (Garrick) needs a sword *and* a spear equipped.
- **Several hits, several damage types**: *Brand of Valor* (sword, spear, sword, spear, lightning),
  *Elemental Barrage* (fire, ice, lightning), *Thousand Spears* (4 spear hits), *Amputation* (2 axe hits).
- **Pets (Pokemon-style, not units)**: Sera starts with a Frost Lynx called "Frosty" (level 3). A pet has
  a species (stats and growth per level), a level, experience and a nickname. *Send Frost Lynx* (three
  ice hits) needs the matching pet (`requires_pet`) and hits for the pet's `pet_power`, so a higher
  level hits harder; without a pet the row is greyed out ("Needs Frost Lynx"). A pet sent out in a
  won battle gains experience and levels up. Capturing the Ember Hound in the boss fight gives an
  owned Ember Hound (level 2) and unlocks *Send Ember Hound*. Pause menu > **Pets**: choose the
  active pet (Enter), rename it (R).
- **Weapons**: each equipped weapon gives its own attack (take the sword off and *Attack (Sword)*
  is gone); skills strike with several weapons or several elements in one action - *Brand of
  Valor* (sword, spear, sword, spear, lightning), *Arrowstorm* (five arrows and an ice finisher),
  *Grand Inferno* (one fire spell, three hits), *Elemental Barrage* (fire, ice, lightning).
- **Concoct**: Bram picks a base and a catalyst from the bag — herb + fire dust is a Fire Bomb on every enemy,
  herb + ice crystal a Frost Bomb, herb + herb a Healing Salve, fire dust + ice crystal a Storm Flask.
- **Give boost points**: Garrick's *Donate BP* gives 1 boost point to an ally.
- **Statuses**: poison that hurts more every turn (*Venom Strike*, the boss's *Meteor*, the hound's bite), sleep
  (*Sleepy Waltz*, the Sporecap's spores — the turn is skipped), silence (the boss's roar blocks magic), attack
  up (*Abide*, *Peacock Strut*), defence down (*Armor Corrosive*); *Cleanse* removes poison, sleep and silence.

Controls in battle: Up / Down choose, Tab switches Skills / Items, Left / Right boost, Enter confirms, Esc goes
back. Keys 1–4 still use the first four skills directly.

## Enemies — each asks for a different answer

Four of them wander the field (touch one to fight); Grimgarde waits by the path.

| Enemy | Where | What makes it different | Weak to |
|---|---|---|---|
| Grimgarde (boss) + Sporecap + Venom Hound | the boss by the path | 6 shields; silencing roar, poisoning meteor, summons adds; spores put you to sleep | sword, axe, ice, lightning |
| Gel Slime ×2 + Web Spinner | **Gel Slime** (slime pit) | fire *heals* the slime (absorb); it splits into another slime; the spider lowers your defence | lightning, staff, dagger |
| Bone Wraith + Skeleton Knight | **Bone Wraith** (old crypt) | undead: immune to poison; drains life, chills and silences; the knight resists daggers and bows | light, axe, fire / staff |
| Mirror Gazer + Pit Viper ×2 | **Mirror Gazer** (gazer nest) | spells bounce back to the caster (reflect); immune to sleep, puts the whole party to sleep; the vipers are very fast and poison | dagger, spear, bow |
| Iron Samurai + Bone Wraith | **Iron Samurai** (duel) | 8 shields; resists swords, axes and bows (half damage, no shield lost); war cry, two-hit whirlwind | spear, lightning, dagger |

## Where it lives in the data

| Rule | Record |
|---|---|
| Weakness / resistance multipliers, absorb, reflect, Break x2, boost power | Database › Damage Interactions |
| Immunities (poison, sleep) | Status Effects › `immune_target_tags` + the enemy's tags |
| Enemy moves | Enemy AI (one per enemy) + enemy behaviour bindings |
| Field enemies | entities with Visible Encounter + Field AI (wander) |
| Shields per enemy | enemy `resources.shield` + Battle Resources › `shield` (`subject_maximum`) |
| Break | Break Gauges › `break` (`reset_to_maximum`) + Status Definitions › `broken` |
| Divine cost, hits, states, commands, concoct | each ability's `battle_costs`, `hits`, `apply_states`, `commands`, `concoct_station` |
| Concoctions | Crafting recipes of station `concoct`; their items' `battle_ability` |
| Status rules | Status Effects (battle policies) + Status Definitions |
