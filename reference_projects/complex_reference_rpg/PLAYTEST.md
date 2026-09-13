# Complex Reference RPG — Human Acceptance Playtest

This reference game is intentionally short, but it exercises a dense RPG feature set from a real New Game start. It does **not** require an Editor-side player save or midgame profile.

## Main path

1. Open Asteria and open `project.asteria.json`.
2. Run Project.
3. At the in-game title screen use `Up/Down` and `Enter`, or click **New Game**. Select **Load Game** to load an existing Player Save.
4. In the field press `C` to open Character / Build.
5. In Character / Build, use `Left/Right` to change actor, `Up/Down` to select a row, and `Enter` to apply it. Every row, actor arrow, and skill-tree node can also be clicked with the mouse. The menu covers Secondary Class, Skill Tree allocation, Passive loadout, Weapon, Weapon Upgrade/Growth, Accessories, and Party/Formation.
6. Close the menu with `C`, walk to the Astral Tyrant, face it and press `E`.
7. During battle use the arrow keys to select a skill and `Enter` to use it, or click a skill directly. Press `B` to spend the generic `Momentum` combat resource as a boost-like mechanic.
8. Verify elemental weakness reduces the Boss `Shield` (`stagger` internally) and reaches a Break-like state, while boss phases/adds and buffs/debuffs/status tags continue to use generic engine mechanisms.
9. Win and verify Rewards + EXP + AP + Ability Points are applied.
10. Return to Character / Build and spend newly earned points / learn another node.
11. Press `F5` **inside the game** to create the Player Save.
12. Quit, Run Project again, press `L` on the in-game title screen, and confirm class, progression, passives, equipment, weapon growth, party, rewards and progression persisted.

## Boundary

`Player Save` is runtime/player data. The Editor does not expose New/Open/Save Player Save authoring actions. The title/load/save controls above exist in the game runtime only.
