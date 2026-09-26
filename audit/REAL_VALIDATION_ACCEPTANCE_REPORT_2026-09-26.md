# Asteria Real Validation Acceptance Report — 2026-09-26

## Evidence summary

- Final full regression: **1761 passed, 0 failed**.
- `python -m compileall -q src tests`: **PASS**.
- Imports and `pip check`: **PASS**.
- Targeted integration group: **663 passed**.
- Real RPG Maker MV adapter tests: **15 passed**, using files from the local Steam RPG Maker MV installation without copying or modifying them.
- Fresh environment install with `editor,pygame,mv,dev` extras: **PASS**; selected startup/editor/runtime/MV tests: **25 passed**.
- Actual Cocoa Editor process: launched successfully. Desktop automation could not bind to the Python application window within a bounded 10.6-second timeout, so interactive Editor validation remains PARTIAL.
- Repository asset hygiene: no tracked PNG/JPG/WebP files and no copied MV assets.

## Acceptance matrix

| Subsystem | CODE | UNIT TEST | INTEGRATION TEST | REAL EDITOR | REAL RUNTIME | REAL MV ASSET | VISUAL CHECK | PERFORMANCE |
|---|---|---|---|---|---|---|---|---|
| Core/project/scene | PASS | PASS | PASS | PARTIAL | PASS | NOT APPLICABLE | PARTIAL | PARTIAL |
| Editor workspaces and canonical model | PASS | PASS | PASS | PARTIAL | NOT APPLICABLE | NOT APPLICABLE | PARTIAL | NOT APPLICABLE |
| Asset pipeline/Registry/serialization | PASS | PASS | PASS | PARTIAL | PASS | PASS | PARTIAL | PARTIAL |
| RPG Maker MV adapter | PASS | PASS | PASS | NOT APPLICABLE | PARTIAL | PASS | PASS for source sheets; PARTIAL for playback | PARTIAL |
| Character walking vertical slice | PASS for import/clip mapping | PASS | PASS through canonical registration | PARTIAL | PARTIAL | PASS | PARTIAL | PARTIAL |
| Tilemap | PASS | PASS | PASS | PARTIAL | PASS headlessly | PASS for source detection/metadata | PARTIAL | PARTIAL |
| Battle Core | PASS | PASS | PASS | PARTIAL | PASS headlessly | PARTIAL | PARTIAL | PARTIAL |
| Presentation/animation/VFX/camera/audio/text | PASS | PASS | PASS | PARTIAL | PASS headlessly | PARTIAL | PARTIAL | PARTIAL |
| Attachments/weapons | PASS | PASS | PASS | PARTIAL | PASS headlessly | NOT APPLICABLE | PARTIAL | PARTIAL |
| Side-view actor adapter | PASS | PASS | PASS | NOT APPLICABLE | PARTIAL | PASS | PASS for sheet/motion layout; PARTIAL for playback | PARTIAL |
| Save/load round trip | PASS | PASS | PASS | PARTIAL | PASS | PASS for adapter metadata | NOT APPLICABLE | NOT APPLICABLE |
| GUI ↔ script parity | PASS | PASS | PASS | PARTIAL | NOT APPLICABLE | NOT APPLICABLE | PARTIAL | NOT APPLICABLE |
| Invalid/missing asset handling | PASS | PASS | PASS | PARTIAL | PASS | PASS | NOT APPLICABLE | NOT APPLICABLE |
| Clean-machine/package | PASS | PASS | PASS | PARTIAL | PASS headlessly | PASS | NOT APPLICABLE | NOT APPLICABLE |

## RPG Maker MV real-fixture coverage

The adapter inspected real local files from all required categories:

- `img/characters`, including normal sheets and `$` / `!` filename semantics;
- `img/faces`;
- `img/sv_actors`;
- `img/enemies` and `img/sv_enemies`;
- `img/tilesets`;
- `img/animations`;
- `img/pictures`;
- `img/parallaxes`.

It verifies PNG readability, dimensions, alpha presence, source category, MV layout, generic frame size, direction order, idle frame, anchor, canonical conversion, AssetRegistry registration, serialization round trip, walking clip boxes, side-view motion boxes, and malformed/unsupported inputs. MV layout constants remain confined to `asteria.assets.rpg_maker_mv`.

## Visual findings

`Actor1.png` and `sv_actors/Actor1_1.png` were inspected at original resolution. The source sheets have transparent backgrounds, complete silhouettes, no source cropping, consistent per-frame bounds, and the expected MV row/grid topology. The adapter's walking boxes map Down/Left/Right/Up to rows 0/1/2/3 and preserve the middle idle frame.

Interactive keyboard/controller movement, camera rendering, animation playback, GPU sampling seams, audio-device timing, and final composite occlusion could not be visually completed because the desktop automation provider timed out while binding to the running Python/Cocoa Editor window. These are PARTIAL, not PASS.

## Performance findings

The reference presentation workload completed with 1,494 total draws, 1,194 visible draws, 300 culled draws, 11 batches, largest batch 167, and all 512 transient resources released. Its synthetic frame workload averaged 13.43 ms with two dropped frames. The command used approximately 39.9 MB maximum resident memory and 0.18 seconds wall time on this run.

This is headless/synthetic evidence. Actual GPU update/render split, asset-upload stalls, audio latency, hardware frame spikes, and final-art memory behavior remain PARTIAL.

## Fix made during validation

Root cause: the integrated canonical repository had no RPG Maker MV adapter despite the handoff requiring real MV compatibility at the import boundary.

Fix:

- added `asteria.assets.rpg_maker_mv.RPGMakerMVImporter`;
- kept MV-specific topology inside the adapter;
- added canonical asset conversion and registry-compatible metadata;
- added real-fixture regression tests for all required MV image categories;
- added walking and side-view motion extraction boundaries;
- declared the `mv` optional dependency (`Pillow>=10`).

## Remaining external gates

- Interactive Editor operations and visual panel inspection on macOS.
- Real windowed runtime keyboard/controller and camera verification.
- Real GPU shader/material/lighting/VFX visual output and frame pacing.
- Real audio-device event timing.
- Full visual walking, tilemap, battle, side-view transition, and attachment occlusion playback.

These limitations are environmental/interactive gates and were not converted into false PASS results.
