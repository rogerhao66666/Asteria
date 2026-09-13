# Asteria Complex Reference RPG

This is a real Asteria Project, not a validation harness.

Open `project.asteria.json` in Asteria Editor.

The project intentionally exercises a dense but generic RPG configuration:

- 12 playable actors
- 8 jobs/classes
- 24 abilities
- 16 passives
- 8 progression tracks
- 8 six-node skill trees
- 20 equipment definitions
- 6 attachments/runes
- equipment growth
- crafting/alchemy recipes
- 12-person roster with active/reserve formation
- enemies plus a three-phase boss with adds
- arbitrary battle resources (`stagger`, `rage`)
- weakness-style interactions
- break-like state generated from generic gauge composition
- timeline scheduling
- reactions
- objectives / escape / transaction policies
- project-owned battle presentation
- project-owned runtime RPG UI policies
- a field scene with an interactable Boss that dispatches `START_ENCOUNTER`

All names/content are original reference material. The project does not contain or
copy Octopath Traveler assets, characters, story, maps, music, or proprietary game
data. Commercial JRPGs are used only as a system-density benchmark.

`build_project.py` reproduces the project entirely through canonical Asteria APIs.
Do not manually edit the generated JSON as part of normal validation.


## Visual playable test content

The project now includes `playable_assets/` and `playable_test_manifest.json`.
When launched through Asteria Editor **Run**, the runtime preview automatically
uses the playable test adapter and displays a real field and battle screen.

See `PLAYTEST.md` for controls and the Codex/real-machine validation path.
