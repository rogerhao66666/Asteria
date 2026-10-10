# REAL_MACHINE_VALIDATION

D14 #4. Run on a real macOS machine with real windows and devices: no dummy SDL drivers and no offscreen Qt. Each item is **PASS**, **FAIL**, **BLOCKED** (a required device or permission is missing) or **NOT EXECUTED** (needs a person). Nothing is marked PASS without a measurement.

- **Machine:** macOS 27.0.1 arm64, Apple M5 GPU (OpenGL 4.1 Metal), Python 3.13.15, pygame-ce 2.5.8 (SDL 2.32.10), PySide6.
- **Run:** 2026-10-10 (re-run after the D15 staging changes; same results).
- **Command:** `python scripts/real_machine_validation.py docs/audits/evidence/real_machine`
- **Raw results:** [`evidence/real_machine/results.json`](evidence/real_machine/results.json). Profile: [`battle_profile.json`](evidence/real_machine/battle_profile.json).

## Results

| # | Item (D14 #4) | Status | Evidence |
|---|---|---|---|
| 1 | GPU window | **PASS** | ModernGL window on Apple M5: 400 sprites per frame for 240 frames at 61.9 fps. The read-back framebuffer has rendered content ([gpu_window.png](evidence/real_machine/gpu_window.png)). |
| 2a | Input: keyboard through the OS event queue | **PASS** | Key events posted to the real Cocoa window's SDL queue reached `InputActionMap` (`move_right`, `confirm`, `cancel`). These are synthetic events, not physical presses. |
| 2b | Input: physical keyboard | **NOT EXECUTED** | Needs a person. See M1. |
| 2c | Input: controller | **BLOCKED** | No game controller connected (`pygame.joystick.get_count() == 0`). See M2. |
| 3a | Audio playback (device) | **PASS** | CoreAudio opened at 44100 Hz, 16-bit, stereo. `hit.wav` (0.340 s) kept its channel busy for 0.351 s, and `battle_theme.ogg` streamed. |
| 3b | Audio playback (audible) | **NOT EXECUTED** | Needs a listener. See M3. |
| 4 | Audio latency | **NOT EXECUTED** | Needs an acoustic or loopback measurement. See M4. No number is reported because pygame does not expose output latency. |
| 5 | Animation smoothness | **PASS** (measured) | New battle screen in a real Cocoa window: sprites drawn, the boss animation advanced 88 frames in 10.0 s, 7 skills used through the key-event queue, VFX played ([battle_window_0.png](evidence/real_machine/battle_window_0.png)). Perceived smoothness is M5. |
| 6 | Frame pacing | **PASS** | 590 frames at 58.9 fps (target 60). Jitter 1.2 ms, p99 frame interval 18.0 ms, 1 frame over 1.5× budget. Pass criteria: ≥ 55 fps, p99 ≤ 25 ms, ≤ 1 % over budget. |
| 7 | Editor → runtime playtest | **PASS** | Qt `cocoa`: Run Project started the runtime process, it was still running after 4 s, Stop Play ended it, and the process exited. |
| 8a | Runtime exit | **PASS** | The real-window runtime ran 90 frames and exited with code 0 in 2.4 s. |
| 8b | Runtime recovery | **PASS** | The runtime wrote a player save and was killed with SIGKILL (exit −9). The save reloaded with the saved player position (7.0, 3.0). |

## Defect found and fixed by this run

The **first run FAILED frame pacing**: 43.7 fps, p99 frame interval 441 ms. cProfile found the cause: the legacy `_play_fx` effect loop blocks the main loop for about 430 ms per skill, and the new battle screen was still calling it. Headless tests had replaced `_play_fx` with a no-op, so they missed it.

- **Fix:** the legacy loop now runs only under the legacy screen; the new screen plays the ability's motion sequence.
- **Regression test:** `test_canonical_screen_never_runs_the_blocking_legacy_effect_loop`.
- **Result:** the re-run above.

Fixed at the same time: the canonical screen also played each skill's manifest sound immediately, so every hit sound was heard twice, and the victory jingle could play before the final hit sound. Now the motion sequence is the only audio source under the canonical screen, and the jingle waits until the presentation is idle and its pending sounds have played (`tests/test_audio_mixer.py`).

The legacy screen itself still blocks the same way. That is existing behavior and is recorded as a gap; legacy is not being changed (D14 #6).

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
