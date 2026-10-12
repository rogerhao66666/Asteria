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
| Frost Lynx | (Sera's pet, in reserve) | — |

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
- **Pet**: Sera's *Call Frost Lynx* brings the lynx into the battle.
- **Concoct**: Bram picks a base and a catalyst from the bag — herb + fire dust is a Fire Bomb on every enemy,
  herb + ice crystal a Frost Bomb, herb + herb a Healing Salve, fire dust + ice crystal a Storm Flask.
- **Give boost points**: Garrick's *Donate BP* gives 1 boost point to an ally.
- **Statuses**: poison that hurts more every turn (*Venom Strike*, the boss's *Meteor*, the hound's bite), sleep
  (*Sleepy Waltz*, the Sporecap's spores — the turn is skipped), silence (the boss's roar blocks magic), attack
  up (*Abide*, *Peacock Strut*), defence down (*Armor Corrosive*); *Cleanse* removes poison, sleep and silence.

Controls in battle: Up / Down choose, Tab switches Skills / Items, Left / Right boost, Enter confirms, Esc goes
back. Keys 1–4 still use the first four skills directly.

## Where it lives in the data

| Rule | Record |
|---|---|
| Weakness multipliers, Break x2, boost power | Database › Damage Interactions |
| Shields per enemy | enemy `resources.shield` + Battle Resources › `shield` (`subject_maximum`) |
| Break | Break Gauges › `break` (`reset_to_maximum`) + Status Definitions › `broken` |
| Divine cost, hits, states, commands, concoct | each ability's `battle_costs`, `hits`, `apply_states`, `commands`, `concoct_station` |
| Concoctions | Crafting recipes of station `concoct`; their items' `battle_ability` |
| Status rules | Status Effects (battle policies) + Status Definitions |
