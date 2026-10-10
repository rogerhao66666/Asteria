# REAL_MACHINE_VALIDATION

D14 #4. Run on a real macOS machine with real windows and devices: no dummy SDL drivers and no offscreen Qt. Each item is **PASS**, **FAIL**, **BLOCKED** (a required device or permission is missing) or **NOT EXECUTED** (needs a person). Nothing is marked PASS without a measurement.

- **Machine:** macOS 27.0.1 arm64, Apple M5 GPU (OpenGL 4.1 Metal), Python 3.13.15, pygame-ce 2.5.8 (SDL 2.32.10), PySide6.
- **Run:** 2026-10-11 (re-run after D16: CB10 editors, VFX placement, CAM-02 camera; two checks added).
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

## Rerunning

Run `python scripts/real_machine_validation.py OUTPUT_DIR [--only gpu_window input audio battle editor runtime]`. The script restores `saves/playtest_autosave.asteria-save.json` after the recovery check.
