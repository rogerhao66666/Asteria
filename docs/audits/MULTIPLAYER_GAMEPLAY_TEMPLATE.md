# Loadable multiplayer gameplay template

Open `reference_projects/diablo_multiplayer_demo/project.asteria.json`, start one server from
Multiplayer, then Run Project. Use distinct Guest IDs for four clients. The copied profile
selects `asteria.multiplayer.project_demo:build_project_adapter`; the server receives the
selected document through `--project`. The original offline project remains unchanged.

## Authoritative original gameplay

The server simulates each occupied authored scene once: player controllers, AI/behavior,
collisions, action timelines, hitboxes, projectiles, combat, statuses, loot and spawn systems.
Clients render bounded scene snapshots and submit individual input/command intents.
The original bag, equipment, attributes, classes, skill bindings, item use, dialogue,
merchant and crafting interfaces route through the server. Original gates preserve scene
entry positions and topdown/side controller modes; death respawns at the scene entry.
J attacks, F picks up nearby loot, G is a pickup alias, B opens the original bag.
Server character saves also back F5 and the original save/load menus. F3 reconnects;
disconnected connected-project gameplay freezes instead of resolving local combat.

## Defaults and ownership

Input sequences reject stale/repeated frames. The server ECS update order determines accepted
hits; it does not reconstruct simultaneous physical button presses across computers.
The accepted lethal hit supplies `kill_credit`. Ordered combat records and positive-damage
contributions are saved with encounter results; final-hit credit is separate from eligibility.

Every positive-damage Boss contributor gets the full configured 100 XP, including a player
who did not land the final hit. Joining alone grants no Boss XP. Original Boss loot tables roll
actual RPG item instances; each rolled item is reserved for one random eligible contributor.
That owner must pick it up in range. Duplicate operations cannot grant a second item.
Ordinary monster XP follows authored rewards; ordinary world loot uses the selected pickup policy.

## Editable project rules

Edit `.asteria/multiplayer-rules.json` or the Game Rules Template card, save and restart.

- `project_runtime.project_file`: fallback project path, resolved relative to the rules folder's
  project root. The explicitly selected editor document takes precedence.
- `rewards.boss.eligibility`: `positive_damage` or `any_session_participant`.
- `rewards.boss.experience.amount`: full XP for each eligible character.
- `rewards.boss.drops.source`: `authored` uses original loot tables; `configured` uses `items`.
- `rewards.boss.drops.assignment`: `random_eligible_player`, `highest_damage_player`,
  or `every_eligible_player`.
- `world_pickup.policy`: `first_valid_claim`, `owner_only`, `personal`, `round_robin`,
  or `random_eligible_player` for ordinary ground loot.

The server validates configured item IDs against the loaded RPG database. Ground drop eligibility
and ownership are established on the server; pickup validates health, scene, range and ownership.
For arbitrary rules choose `your_package.module:build_adapter` and implement adapter
join/input/command/tick methods returning `AdapterUpdate`. Adapter-specific JSON sections are
retained. Built-in policies are editable examples, not an arbitrary rule programming language.

## SQLite persistence

The project's `.asteria/multiplayer.sqlite3` stores players, namespaced full RPG character saves,
XP, inventory, encounters, contributions, grants, world-drop claims and processed operations.
A ground claim, reward ledger entry, inventory credit and updated full character save commit
in one transaction; failed writes roll back both the claim and in-memory RPG bag mutation.
Clients never write SQLite directly. Rejoining with the same Guest ID restores that character;
a fresh adapter and reopened database preserve equipment instances and progression.

Scene AI, spawn timers and unclaimed ground drops are transient. A server restart creates a
fresh session world while preserving characters and completed claims. Guest IDs are trusted-LAN
development identities. Internet authentication, TLS, relay and WAN quality qualification remain
separate deployment work.

## Repeat native acceptance

Run from the repository's VS Code integrated terminal on macOS:

```sh
PYTHONPATH=src .venv/bin/python scripts/validate_multiplayer_project.py
```

It opens four separate Cocoa game processes, uses actual game input against the original 900 HP
Cyclops, asserts 100 XP for each contributor, walks owners to their rolled loot, picks it up,
equips gear through the original command route, captures renders and reopens SQLite.
`FOUR_PROJECT_NATIVE_PASS` is printed only after all checks pass. Input is automated;
this evidence does not claim human keyboard/mouse playtesting.
