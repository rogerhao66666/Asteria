# REAL_MACHINE_VALIDATION

D14 #4. Run on a real macOS machine with real windows and devices: no dummy SDL drivers and no offscreen Qt. Each item is **PASS**, **FAIL**, **BLOCKED** (a required device or permission is missing) or **NOT EXECUTED** (needs a person). Nothing is marked PASS without a measurement.

- **Machine:** macOS 27.0.1 arm64, Apple M5 GPU (OpenGL 4.1 Metal), Python 3.13.15, pygame-ce 2.5.8 (SDL 2.32.10), PySide6.
- **Run:** 2026-10-12 (full re-run in D20; items 11–19 added in D17 Phase 6, 20–28 in D18, 29–35 in D19, 36–44 in D20). macOS Low Power Mode was on during this run (`pmset -g`: `lowpowermode 1`); see item 25.
- **Command:** `python scripts/real_machine_validation.py docs/audits/evidence/real_machine`
- **Raw results:** [`evidence/real_machine/results.json`](evidence/real_machine/results.json). Profile: [`battle_profile.json`](evidence/real_machine/battle_profile.json).

## Results

| # | Item (D14 #4) | Status | Evidence |
|---|---|---|---|
| 1 | GPU window | **PASS** | ModernGL window on 'Apple M5': 400 sprites/frame for 240 frames, 60.737 fps, read-back framebuffer has 8 sampled colours ([gpu_window.png](evidence/real_machine/gpu_window.png)). |
| 2a | Input: keyboard through the OS event queue | **PASS** | Key events posted to the real Cocoa window's SDL queue reached `InputActionMap` (`move_right`, `confirm`, `cancel`). These are synthetic events, not physical presses. |
| 2b | Input: physical keyboard | **NOT EXECUTED** | Needs a person. See M1. |
| 2c | Input: controller | **BLOCKED** | No game controller connected (`pygame.joystick.get_count() == 0`). See M2. |
| 3a | Audio playback (device) | **PASS** | CoreAudio opened at 44100 Hz, 16-bit, stereo. `hit.wav` (0.340 s) kept its channel busy for 0.351 s, and `battle_theme.ogg` streamed. |
| 3b | Audio playback (audible) | **NOT EXECUTED** | Needs a listener. See M3. |
| 4 | Audio latency | **NOT EXECUTED** | Needs an acoustic or loopback measurement. See M4. No number is reported because pygame does not expose output latency. |
| 5 | Animation smoothness | **PASS** (measured) | New battle screen in a real Cocoa window: sprites drawn, the boss animation advanced 88 frames in 10.0 s, 7 skills used through the key-event queue, VFX played ([battle_window_0.png](evidence/real_machine/battle_window_0.png)). Perceived smoothness is M5. |
| 6 | Frame pacing | **PASS** | 588 frames: 58.86 fps (target 60), jitter 1.0696 ms, p99 interval 19.5462 ms, 2 frames over 1.5x budget. Pass criteria: ≥ 55 fps, p99 ≤ 25 ms, ≤ 1 % over budget. |
| 7 | Editor → runtime playtest | **PASS** | Qt `cocoa`: Run Project started the runtime process, it was still running after 4 s, Stop Play ended it, and the process exited. |
| 8a | Runtime exit | **PASS** | The real-window runtime ran 90 frames and exited with code 0 in 2.4 s. |
| 8b | Runtime recovery | **PASS** | The runtime wrote a player save and was killed with SIGKILL (exit −9). The save reloaded with the saved player position (7.0, 3.0). |
| 9 | Boss camera (CAM-02) | **PASS** | Boss event camera in a real cocoa window: zoom 1.60 (authored 1.6), map image covers the screen=True, boss moved from x=624 to x=480 (screen centre 480). Before / after: [field_camera_home.png](evidence/real_machine/field_camera_home.png), [field_camera_boss_focus.png](evidence/real_machine/field_camera_boss_focus.png). Whether it feels right is M5. |
| 10 | Editor tools (CB10) | **PASS** | Qt platform 'cocoa': animation_editor=ok, action_timeline=ok, vfx_tool=ok, vfx_preview=ok, enemy_ai_preview=ok, multi_select_batch_fields=ok, problems_panel=ok, problems_clear_again=ok, script_completion=ok, debugger_live_game=ok. Screenshots reviewed: [animation](evidence/real_machine/editor_animation.png), [action timeline](evidence/real_machine/editor_action_timeline.png), [VFX](evidence/real_machine/editor_vfx.png), [enemy AI](evidence/real_machine/editor_enemy_ai.png), [records](evidence/real_machine/editor_records_multiselect.png), [problems](evidence/real_machine/editor_problems.png), [script](evidence/real_machine/editor_script.png), [debugger](evidence/real_machine/editor_debugger.png). Hands-on use by a person is not part of this check. |
| 11 | Cutscene (EVT-03/04) | **PASS** | Tween moved the player to x=7.8 of 20 after 0.6 s with the arrow key held (input locked); camera zoom 1.40; letterbox; parallel VFX track; a real Esc event skipped to the end state. [mid](evidence/real_machine/cutscene_mid.png), [skipped](evidence/real_machine/cutscene_skipped.png) |
| 12 | Boss intro camera (CAM-02) | **PASS** | Zoom peaked at 1.35 and settled at 1.00; commands blocked during the intro. [screenshot](evidence/real_machine/battle_boss_intro.png) |
| 13 | Layered characters (CMP-01/02) | **PASS** | 6 heroes with an authored socket attachment and back layer, 12 part draws; the charm is visible and mirrored with the body. [screenshot](evidence/real_machine/battle_layered_characters.png) |
| 14 | Status screen (UI-01) | **PASS** | The I key opened the status screen. [screenshot](evidence/real_machine/menu_status.png) |
| 15 | Save slots (ENG-21) | **PASS** | Saved to slot 1 (overwrite confirmed), loaded it back: player x=11.0 restored. [screenshot](evidence/real_machine/menu_save_slots.png) |
| 16 | Rebinding (ENG-15) | **PASS** (keyboard) | move_right rebound to D on the Controls screen; holding D moved the player. Gamepad rebinding is BLOCKED (no controller, M2). [screenshot](evidence/real_machine/menu_controls.png) |
| 17 | Follow camera (CAM-02) | **PASS** | Follow zoom 1.80; the camera centre moved 48.9 units with the walking player. [start](evidence/real_machine/follow_camera_start.png), [end](evidence/real_machine/follow_camera_end.png) |
| 18 | Packaged .app (AST-06) | **PASS** | The .app (2.4 MB .pyz) ran 120 frames in a real window from a temporary folder outside the repo, exit 0. Double-click in Finder is M6. |
| 19 | D17 editor surfaces | **PASS** | Cocoa: export_game, animation_states, character_composition, input_map, behavior_trees, profiler_dock (live game), project file untouched. [states](evidence/real_machine/editor_animation_states.png), [composition](evidence/real_machine/editor_character_composition.png), [input map](evidence/real_machine/editor_input_map.png), [trees](evidence/real_machine/editor_behavior_trees.png), [profiler](evidence/real_machine/editor_profiler.png) |
| 20 | MV import (W-18) | **PASS** | Parallax sample imported, saved, reloaded in a fresh process and played by real key events: blocked by the NPC, Japanese dialogue, NPC gone, door to map 2 (8, 23); no MV module loaded. [dialogue](evidence/real_machine/mv_import_dialogue.png), [after transfer](evidence/real_machine/mv_import_after_transfer.png) |
| 21 | MV import on the GPU, night environment | **PASS** | Same flow on the ModernGL backend with an authored Environment2D (ambient, player light, rain, bloom). [screenshot](evidence/real_machine/mv_import_gpu_dialogue.png) |
| 22 | GPU playable runtime (ENG-12) | **PASS** | GPU frame == composed frame pixel for pixel (field, battle); 56.1 fps, p99 18.8 ms, upload 0.41 ms, GPU 0.58 ms, 1 draw call. [battle](evidence/real_machine/gpu_battle.png) |
| 23 | VFX on the GPU / on pygame | **PASS** | Lights, shadow, water, rain, bloom, grading, vignette: 56 fps on both; pygame reports bloom / grade / vignette / shadows unsupported. [GPU](evidence/real_machine/vfx_moderngl_field.png), [pygame](evidence/real_machine/vfx_pygame_field.png) |
| 24 | Battle afterimages (VFX-03) | **PASS** | motion_fx beat: up to 4 copies. [screenshot](evidence/real_machine/vfx_gpu_battle_afterimage.png) |
| 25 | Weather load | **FAIL** (D20 run, environment) | 2000 rain particles + full chain: 31.8 fps in the full run, 34.2 fps rerun alone (limit 55). Low Power Mode was on. The same check at `06a5577`, which measured 59.5 fps in D19, measured 34.7 fps under the same conditions, so the code did not regress; the CPU-side particle update and draw take about twice as long (vfx section 4.4 → 8.9 ms). Stays FAIL until rerun with Low Power Mode off (`--only vfx`). D19 result: 59.5–60.1 fps. |
| 26 | Gameplay systems (STR-01) | **PASS** | JRPG stress playthrough presented in the real window: 13/13 items, victory. [break](evidence/real_machine/gameplay_broken.png) |
| 27 | More menus (UI-01/02) | **PASS** | Quest log, shop buy, item use, equip cycle, settings, game over → title by real key events. |
| 28 | Editor workflows | **PASS** (D20: rerun after other window checks; see note) | Thumbnails, record search/copy/paste/cut shortcuts, batch edit, hierarchy drop, prefab apply/propagate/revert, pivot, editor event in the live game, Play from Selection + Restart. |
| 29 | Battle without art (A9 replacement) | **PASS** | No combatant visuals and no motion sequences. On both pygame and ModernGL: generated combatants, manifest fx played as canonical VFX, victory by real key events, back to the field, F5 save. pygame 55.5 fps / p99 22.7 ms; ModernGL 56.5 fps / p99 24.6 ms. [pygame](evidence/real_machine/no_art_pygame_battle.png), [ModernGL](evidence/real_machine/no_art_moderngl_battle.png) |
| 30 | Session tests replayed in the real window (`b_items_replay`) | **PASS** (14 items) | 79 session-level integration tests from 13 files run unchanged inside the real playable cocoa window. After each session call the current state is drawn and flipped; nothing advances and nothing is loaded. Items: RPG-02/04/05/06/07/09/10, WLD-01/02, EVT-01/02/03, ANI-05, CMP-01. Tests that never drove the window are not counted. Per-test frames: [`b_items_replay.json`](evidence/real_machine/b_items_replay.json); screenshots in `evidence/real_machine/replay/`. These are session-API scenarios, not key-driven play. |
| 31 | Engine systems in `Application.run` | **PASS** | The engine's own main loop with the pygame backend, real clock, 8 s. Fixed step: 400 steps at 50 Hz for 8.00 s. Trigger: enter / stay / exit. Layer / mask: Hero–Wall pairs, Ghost filtered out. Action-timeline hitbox hit. Frame events. Camera look-ahead 50–58 px. Persistent entity carried through a fade. Movement is scripted. [town](evidence/real_machine/engine_systems_town.png), [cave](evidence/real_machine/engine_systems_cave.png) |
| 32 | Battle memory (ENG-10) | **PASS** | 12 boss battles: 0 battle-scoped images left after each, 108 released. RSS per battle settles at about 173 MB (battle 2 → 12: −90.8 MB, limit +25 MB). |
| 33 | M10 automatable comparison | **PASS** | Same field frame on both backends. Without effects: identical. With effects: 10.1 % of pixels differ; pygame reports bloom / grade / shadows / vignette unsupported. 30 s soak with 800 rain particles, 0 errors on both: ModernGL 57.5 fps, p99 23.4 ms; pygame 55.8 fps, p99 19.1 ms. A separate 90 s ModernGL run held RSS flat (175.2–175.7 MB). [side by side + diff](evidence/real_machine/m10_moderngl_pygame_diff.png), [`m10_compare.json`](evidence/real_machine/m10_compare.json). Whether it looks right is M10. |
| 34 | Editor dock tabs (D19) | **PASS** | Cocoa: one tab strip per dock group (the stale "Assets / Console" bar is gone); layout saved and restored; Reset Layout. `tests/test_editor_dock_tabs.py` also passes in Cocoa. |
| 35 | Editor UI audit (D19) | **PASS** | `scripts/editor_ui_audit.py` in real Cocoa windows, 19 workspace surfaces at 1280×800 and 1440×900, all three palettes: 0 clipped / overflow / tiny-control defects. Minimum window 763×435 (was 1721×1772, larger than the 1470×840 screen). [before / after](evidence/ui_audit/before_after_theme.png), [palettes](evidence/ui_audit/themes_graphite_twilight_daylight.png) |
| 36 | Session tests replayed, D20 additions (`b_items_replay`) | **PASS** (21 items) | 115 tests in 20 files, 2736 frames, cocoa. New: EVT-04 (dialogue + music tracks), RPG-01 (inventory rules in events and shops), RPG-08 (summons, reserve companion called in, growth, storage, summoned combatant drawn), GP-02 (cost, targeting, cooldown, timeline cast / recovery), BTL-02 (DOT fixed or scaled, two weapons with weakness / resistance, break ×2, boost repeat / power, secondary job, a poison that worsens every turn), ANI-02 (authored state machine picks the battle clip), CMP-03 (field popups). A test that closes its own runtime now leaves a screenshot of its last frame. These are session-API scenarios, not key-driven play. |
| 37 | Engine systems: parallax and target group | **PASS** | Added to item 31: a parallax 0.5 layer moved 0.500× the play layer; the target-group camera centre is 0.5 px from the hero–foe midpoint at zoom 2.00. |
| 38 | Migrated project plays (ENG-20) | **PASS** | The reference project in its stored format (project v8) is copied, upgraded by the `asteria-upgrade` CLI in its own process to v11, then played in a real window: walk by key events, E at the boss starts the event, F5 save written and loaded. [screenshot](evidence/real_machine/migrated_project_playing.png) |
| 39 | Asset categories (AST-07 / AST-08) | **PASS** | 11 golden assets (character, icon, monster, NPC, projectile, prop, scene, skill, tileset, UI, VFX) loaded through the canonical asset store and drawn; monster, projectile, tileset and VFX animate. Item and Equipment have no runtime image (menus show no item icons), so AST-07 stays B. [screenshot](evidence/real_machine/asset_categories.png) |
| 40 | Editor characters and image tools (EDT-16 / AST-11) | **PASS** | Cocoa editor on a copy of the reference project: a walking sheet is copied into the project, placed as a character linked to a new Actor, shown with a thumbnail, given to another Actor as its appearance, and found in the live game (Play from Selection). Auto-fix Image: preview 96×96 → 42×45, applied with a `.bak.png` backup; a fix that loses pixels is refused without confirmation. Pack into Atlas: PNG + JSON with 3 regions. [placed](evidence/real_machine/characters_placed.png), [auto-fix preview](evidence/real_machine/autofix_preview.png). This run found and fixed two defects: the new sheet showed as "Missing sprite sheet" and did not draw in Scene until reload, and Inspector combo / checkbox cells showed the value text through the widget. |
| 41 | Menu icons (AST-07) | **PASS** | Real cocoa window, real key events (Esc, Tab): the shop, the Items tab and the Equipment tab draw the item / equipment icons (36 CC0 icons in one atlas, each an `icon` asset with a region). Equipment carried in the bag shows its name and icon. [shop](evidence/real_machine/icons_shop.png), [items](evidence/real_machine/icons_items.png), [equipment](evidence/real_machine/icons_equipment.png) |
| 42 | Particle effects in the field and in battle (VFX-01) | **PASS** | Two entity emitters (fire on the boss, sparkle following the player) plus a `PLAY_VFX` heal one-shot for 3 s: about 63 particles per frame, 58.8–59.2 fps on pygame and on the ModernGL presenter (Low Power Mode on). Battle: every action timeline's VFX beat cues a particle burst; 80 particles drawn on the target. This run found and fixed a defect: the battle cue is replaced every frame as it ages, so the burst restarted every frame and stayed a dot; cues are now keyed by sequence, cue and member, with a regression test. [field](evidence/real_machine/particles_field_moderngl.png), [battle](evidence/real_machine/particles_battle.png). Whether it looks good is M10. |
| 43 | Particle Effects editor (VFX-01) | **PASS** | Cocoa editor: new effect from a preset, values changed in the form, the live preview running on its own timer (59 live particles), Apply / Undo, the emitter's Inspector choice, usage list; the project file is untouched. [editor](evidence/real_machine/editor_particles.png) |
| 44 | Octopath-style demo (BTL-02 / BTL-03 / GP-02) | **PASS** | `reference_projects/octopath_demo` in a real cocoa window, real key events through the new battle command menu: Boost x2 by Right and a chosen target (the attack landed twice), a divine skill spending 3 boost points with a 120-particle burst, concocting healing herb + fire dust into a Fire Bomb on every enemy, then the battle won by Enter presses (enemies worn down in memory to keep it short). D20-7: the four new encounters (slime pit, old crypt, gazer nest, samurai duel) each open in the window with their own battle art, shields and weaknesses ([samurai](evidence/real_machine/octo_samurai_duel.png), [gazer](evidence/real_machine/octo_gazer_nest.png)). The demo's 7 session tests also run in the real-window replay (`replay_BTL-03`). [menu](evidence/real_machine/octo_menu.png), [target](evidence/real_machine/octo_target.png), [divine](evidence/real_machine/octo_divine.png), [concoct](evidence/real_machine/octo_concoct.png). Whether it plays well is for a person. |

**Full re-run 2026-10-11 (D18):** 29 PASS, 3 NOT EXECUTED (M1, M3, M4), 1 BLOCKED (controller, M2). An earlier commit message said "34 PASS"; that was a miscount — the results file is authoritative.

**Update 2026-10-12 (D20-6, Octopath demo):** `octopath_demo` (item 44) and `b_items_replay` were run again after the demo; the other results are from the full re-run below. `results.json` now holds 70 results: **65 PASS, 3 NOT EXECUTED, 1 BLOCKED, 1 FAIL** (item 25, deferred by the user). The replay covers 23 items, all PASS in cocoa.

**Full re-run 2026-10-12 (D20, after AST-07 and VFX-01):** `results.json` holds 68 results: **63 PASS, 3 NOT EXECUTED (M1, M3, M4), 1 BLOCKED (controller, M2), 1 FAIL (item 25, weather load, Low Power Mode still on: 35.5 fps).** `editor_workflows_gui` lost keyboard focus to an earlier check's window again; the check now re-activates the editor and waits up to 2 s for focus, and passed when rerun after `menus_more` and `battle_no_art`. The results file records that rerun with a note.

**Full re-run 2026-10-12 (D20):** `results.json` holds 63 results: **58 PASS, 3 NOT EXECUTED (M1, M3, M4), 1 BLOCKED (controller, M2), 1 FAIL (item 25, weather load, under Low Power Mode; see the item).** In the full run `editor_workflows_gui` also failed its copy / paste shortcut step (the shortcut needs the editor to hold keyboard focus); it passed when rerun alone right after, and the results file records the rerun with that note.

**Full re-run 2026-10-11 23:24 (D19):** `results.json` holds 53 results: **49 PASS, 3 NOT EXECUTED (M1, M3, M4), 1 BLOCKED (controller, M2), 0 FAIL.** Items 34–35 are editor GUI runs outside that script (dock test in Cocoa, `editor_ui_audit.py`).

## Defect found and fixed by this run

The **first run FAILED frame pacing**: 43.7 fps, p99 frame interval 441 ms. cProfile found the cause: the legacy `_play_fx` effect loop blocks the main loop for about 430 ms per skill, and the new battle screen was still calling it. Headless tests had replaced `_play_fx` with a no-op, so they missed it.

- **Fix:** the legacy loop now runs only under the legacy screen; the new screen plays the ability's motion sequence.
- **Regression test:** `test_canonical_screen_never_runs_the_blocking_legacy_effect_loop`.
- **Result:** the re-run above.

Fixed at the same time: the canonical screen also played each skill's manifest sound immediately, so every hit sound was heard twice, and the victory jingle could play before the final hit sound. Now the motion sequence is the only audio source under the canonical screen, and the jingle waits until the presentation is idle and its pending sounds have played (`tests/test_audio_mixer.py`).

The legacy screen itself still blocks the same way. That is existing behavior and is recorded as a gap; legacy is not being changed (D14 #6).

## Defects found by the D16 review of the editor screenshots

All three were fixed in the same batch, and the check was re-run:

- The Enemy AI rule and phase tables showed about one row. They now sit in a splitter with a minimum height.
- The Problems panel listed one database error twice: once under Game Start without a location, and once with its location. Repeats are now folded into the located copy.
- The record editor truncated field names ("def…", "resour…"). The field column now fits its contents.

Still open: a stray "Assets | Console" tab strip is drawn inside the bottom dock when the Debugger or Problems dock is raised. It looks like a Qt rendering artifact of tabified docks; it needs a person to check whether it is visible in normal use.

## Defects found by the D17 Phase 6 review of the screenshots

Fixed in `c8b7616` and re-run:
- Boss intro: zooming onto a boss near the edge left screen areas without background, showing smeared earlier frames. The battle camera is now clamped to the battlefield.
- The default font has no arrow glyphs: the rebinding message showed a box and the status hint showed "??". Game text now uses ASCII fallbacks.

## Manual procedures (macOS) for the items that need a person or a device

Each item stays NOT EXECUTED or BLOCKED until someone runs its procedure and records the result here.

- **M1 — Physical keyboard.**
  1. Run `asteria-preview reference_projects/complex_reference_rpg/project.asteria.json --battle-presentation canonical`.
  2. Press `N` (new game), move with arrows or WASD, press `E` at the boss, then use `1`–`4`, `B` and `X` in battle.
  3. Press `Esc` to pause, navigate the menu with the arrows and `Enter`, and press `Q` for the quest log.
  4. PASS if every key acts as described.
- **M2 — Controller.**
  1. Connect a standard gamepad and start the same command.
  2. Move with the left stick and the d-pad; check that A confirms or interacts, B cancels or pauses, and Start opens the build menu.
  3. PASS if every mapping in `InputActionMap.default()` works.
- **M3 — Audible playback.** During M1 you should hear:
  - field music on the title and field screens;
  - battle music after `E` at the boss;
  - a hit sound on each damaging skill, timed with the target's hit pose and damage number;
  - a heal sound on Heal;
  - a victory jingle.

  PASS if all are heard and in time.
- **M4 — Audio latency.**
  1. Record the speaker with a phone or a loopback (for example BlackHole) while pressing `1` repeatedly in battle.
  2. Measure the delay from the key click in the recording to the hit sound, then subtract the authored impact beat (0.24 s for Strike).
  3. Report the median of 10 presses. Target: under 100 ms.
- **M5 — Perceived smoothness.** Watch 2 minutes of battle (M1). PASS if there are no visible hitches, sprites animate continuously, and effects play without stutter.

- **M6 — Packaged app in Finder.** Export with File → Export Game… (macOS app ticked). Double-click the `.app` in Finder. Note what Gatekeeper shows for an unsigned app (Open from the context menu if needed). PASS if the game window opens and plays; record the Gatekeeper behaviour either way.
- **M7 — Editor hands-on (D17 tabs).** A person uses Animation States (drag nodes, add a transition, preview), Character Composition (socket, key at frame, attach, layer), Behavior Trees, Input Map, Event Flow (sequence editor) and the Profiler dock while playing. PASS if every action works with the mouse and keyboard without errors.
- **M8 — Gamepad rebinding.** With a controller (M2), open Settings → Controls, rebind confirm to another pad button and use it. PASS if the new button works and the old one no longer does.
- **M9 — D17 visual review.** Watch the boss intro, a cutscene with Esc skip, layered characters in battle and the follow camera (enable `field.camera.follow`). PASS if nothing looks wrong (popping, smearing, misplaced parts).
- **M10 — VFX visual review.** The automatable part is done (item 33: pixel diff, unsupported list, soak). What is left is the visual judgement. Run the reference game with `--backend moderngl` after adding an Environment2D (lighting, a light, rain, bloom) to the field in the editor (do not save), then compare with `--backend pygame`. PASS if lights, shadows and bloom look right on the GPU, nothing flickers, and the pygame fallback stays playable.
- **M11 — MV import by a person.** File → Import RPG Maker MV Project… with your own MV project; play it. Record which MV commands the Console lists as not converted.

## Rerunning

Run `python scripts/real_machine_validation.py OUTPUT_DIR [--only CHECK ...]` (checks: gpu_window input audio battle field_camera editor editor_tools editor_d17 runtime cutscene battle_features menus follow_camera packaged_app). `--only` merges into the existing results. The script restores `saves/playtest_autosave.asteria-save.json`, the slot 1 save and `settings.json` after the checks that write them.
