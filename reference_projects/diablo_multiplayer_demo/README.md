# Asteria Diablo Multiplayer Demo

This is a separate copy of `../diablo_demo`; the offline source and its assets are preserved.
The server runs the copied project's original ECS scenes, monsters, collisions, skills,
projectiles, NPC events, shops and crafting. Each guest has an independent character save.

## Load and play

1. Open this folder's `project.asteria.json` through **File > Open**.
2. In **Multiplayer**, keep `asteria.multiplayer.project_demo:build_project_adapter` and
   **Connect Run Project** enabled, then choose **Start Local Server** once.
3. Choose **Run Project** and start the game. Use the original movement bindings,
   **J** to attack, **F** to pick up nearby loot (**G** also works), and **B** for the original bag.
   Skill, equipment, NPC, vendor and crafting menus submit commands to the server.
4. For each additional client, load this project in another editor, choose **New ID**,
   **Save Profile**, and **Run Project**, connecting to the same server. Use four distinct IDs.
5. **F5** and the original save/load menus use the server character save while connected.
   **F3** reconnects after a disconnection; gameplay freezes until connected again.

The copied profile selects the actual loaded project through the server's `--project` option.
For LAN tests choose the host's LAN address on clients and `0.0.0.0` as the host listen address.

## Editable defaults

Every player who deals accepted positive damage to a Boss gets the full **100 XP**.
Four contributors therefore each get 100 XP. Each item rolled from the Boss's original loot
table is reserved for a randomly selected contributor, who must pick it up in range.
The server records hit order, final-hit attribution, contribution, reward ownership and claims.
A successful claim and its full RPG inventory update commit together in SQLite.

Edit `.asteria/multiplayer-rules.json` or **Game Rules Template**, save and restart the server.
These are sample policies; custom adapters can implement other game rules.
See [gameplay template](../../docs/audits/MULTIPLAYER_GAMEPLAY_TEMPLATE.md).

## Save and session behavior

`.asteria/multiplayer.sqlite3` preserves character progression, equipment instances, inventory,
resources, skills, contributions and claimed rewards. Restarting the server starts a fresh
scene simulation: AI, spawn timers and unclaimed ground loot belong to the running session.
Guest IDs are development save keys for local/trusted-LAN testing, not verified accounts.

Four independent Cocoa game processes have exercised the original 900 HP Cyclops fight,
100 XP for all four contributors, assigned loot pickup, equipment and SQLite reopening.
Run `scripts/validate_multiplayer_project.py` from the repository's VS Code terminal to repeat it.
