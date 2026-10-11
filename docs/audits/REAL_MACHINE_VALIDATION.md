# REAL_MACHINE_VALIDATION

D14 #4. Run on a real macOS machine with real windows and devices: no dummy SDL drivers and no offscreen Qt. Each item is **PASS**, **FAIL**, **BLOCKED** (a required device or permission is missing) or **NOT EXECUTED** (needs a person). Nothing is marked PASS without a measurement.

- **Machine:** macOS 27.0.1 arm64, Apple M5 GPU (OpenGL 4.1 Metal), Python 3.13.15, pygame-ce 2.5.8 (SDL 2.32.10), PySide6.
- **Run:** 2026-10-11 (re-run after D16; items 11–19 added in D17 Phase 6).
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
| 25 | Weather load | **PASS** | 2000 rain particles + full chain: 59.5–60.1 fps. |
| 26 | Gameplay systems (STR-01) | **PASS** | JRPG stress playthrough presented in the real window: 13/13 items, victory. [break](evidence/real_machine/gameplay_broken.png) |
| 27 | More menus (UI-01/02) | **PASS** | Quest log, shop buy, item use, equip cycle, settings, game over → title by real key events. |
| 28 | Editor workflows | **PASS** | Thumbnails, record search/copy/paste/cut shortcuts, batch edit, hierarchy drop, prefab apply/propagate/revert, pivot, editor event in the live game, Play from Selection + Restart. |

**Full re-run 2026-10-11 (D18):** 29 PASS, 3 NOT EXECUTED (M1, M3, M4), 1 BLOCKED (controller, M2). An earlier commit message said "34 PASS"; that was a miscount — the results file is authoritative.

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
- **M10 — VFX visual review.** Run the reference game with `--backend moderngl` after adding an Environment2D (lighting, a light, rain, bloom) to the field in the editor (do not save), then compare with `--backend pygame`. PASS if lights, shadows and bloom look right on the GPU, nothing flickers, and the pygame fallback stays playable.
- **M11 — MV import by a person.** File → Import RPG Maker MV Project… with your own MV project; play it. Record which MV commands the Console lists as not converted.

## Rerunning

Run `python scripts/real_machine_validation.py OUTPUT_DIR [--only CHECK ...]` (checks: gpu_window input audio battle field_camera editor editor_tools editor_d17 runtime cutscene battle_features menus follow_camera packaged_app). `--only` merges into the existing results. The script restores `saves/playtest_autosave.asteria-save.json`, the slot 1 save and `settings.json` after the checks that write them.
