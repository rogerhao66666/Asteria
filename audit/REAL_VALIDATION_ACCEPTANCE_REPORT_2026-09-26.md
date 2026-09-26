# Asteria Real Validation Acceptance Report — 2026-09-26

## Evidence summary

- Final full regression: **1762 passed, 0 failed**.
- `python -m compileall -q src tests`: **PASS**.
- Imports and `pip check`: **PASS**.
- Targeted integration group: **663 passed**.
- Real RPG Maker MV adapter tests: **15 passed**, using files from the local Steam RPG Maker MV installation without copying or modifying them.
- Fresh environment install with `editor,pygame,mv,dev` extras: **PASS**; selected startup/editor/runtime/MV tests: **25 passed**.
- Actual Cocoa Editor process: **PASS** for application launch, six workspace renders, three UI tabs, canonical command/undo/redo, save, reopen, and canonical-data equality. Nine screenshots were captured and inspected. Mouse/keyboard-driven desktop automation remains PARTIAL because its provider could not bind to the Python window within a bounded timeout.
- Actual pygame runtime process: **PASS** for a bounded real-window launch, 640×360 rendering, three displayed frames, framebuffer capture, and clean shutdown.
- Real MV walking render: **PASS** for loading the installed `Actor1.png`, extracting Down/Left/Right/Up with three frames each, and rendering 12 consecutive frames through the pygame texture backend.
- Repository asset hygiene: no tracked PNG/JPG/WebP files and no copied MV assets.

## Acceptance matrix

| Subsystem | CODE | UNIT TEST | INTEGRATION TEST | REAL EDITOR | REAL RUNTIME | REAL MV ASSET | VISUAL CHECK | PERFORMANCE |
|---|---|---|---|---|---|---|---|---|
| Core/project/scene | PASS | PASS | PASS | PASS for scripted Cocoa E2E; PARTIAL for mouse/keyboard automation | PASS | NOT APPLICABLE | PASS for captured Editor/runtime frames | PARTIAL |
| Editor workspaces and canonical model | PASS | PASS | PASS | PASS for scripted Cocoa E2E; PARTIAL for mouse/keyboard automation | NOT APPLICABLE | NOT APPLICABLE | PASS for nine captures | NOT APPLICABLE |
| Asset pipeline/Registry/serialization | PASS | PASS | PASS | PASS for scripted load/save/reopen | PASS | PASS | PASS for tested paths | PARTIAL |
| RPG Maker MV adapter | PASS | PASS | PASS | NOT APPLICABLE | PASS for texture load/draw | PASS | PASS for source sheets and walking playback | PARTIAL |
| Character walking vertical slice | PASS for import/clip mapping | PASS | PASS through canonical registration | PARTIAL | PASS for bounded four-direction frame playback; PARTIAL for live input | PASS | PASS for four-direction frame grid | PARTIAL |
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

The Cocoa Editor screenshots exposed a real lifecycle defect: a replaced workspace child remained visible until Qt processed deferred deletion, causing the initial placeholder to overlap the RPG and Battle editors. `FamilyHostWidget.rebuild()` now hides the outgoing child before detaching it; a visible Cocoa regression test and a second full Editor capture pass confirm the overlap is gone.

The bounded runtime capture shows the real pygame/SDL renderer drawing the Asteria grid and scene markers. A second real-window pass loads the installed MV `Actor1.png` through `PygameRuntimeBackend`, extracts all four walking directions with `RPGMakerMVImporter`, and renders 12 consecutive frames. Live keyboard/controller movement, camera-follow playback, GPU sampling seams, audio-device timing, and final composite occlusion remain PARTIAL rather than being promoted from non-interactive evidence.

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

An additional Editor E2E finding was fixed:

- hide the old `FamilyHostWidget` child synchronously before `removeWidget()` and `deleteLater()`;
- add a Cocoa-visible regression test proving the replaced placeholder is hidden immediately;
- rerun the complete Editor E2E capture and visually confirm the workspace no longer overlaps.

## Remaining external gates

- Mouse/keyboard-driven Editor automation on macOS (scripted in-process Cocoa operations and visual panel inspection pass).
- Real windowed runtime keyboard/controller and camera-follow verification (window, renderer, texture loading, frame extraction, playback, capture, and shutdown pass).
- Real GPU shader/material/lighting/VFX visual output and frame pacing.
- Real audio-device event timing.
- Full visual tilemap, battle, side-view transition, and attachment occlusion playback; four-direction MV walking frame playback passes.

These limitations are environmental/interactive gates and were not converted into false PASS results.

## MV Character Creator validation addendum — 2026-09-27

- Final regression after the character-creator integration: **1820 passed, 0 failed**.
- The local ignored MV reference now includes the previously omitted built-in app `Generator`: **5 Generator roots, 3422 source files**. The synchronization inventory and script include `Generator`, `NewData`, and `dlc`.
- Actual desktop operation: **PASS**. A visible Cocoa Asteria Editor was launched, `RPG → Character Creator` was opened through accessibility-driven desktop interaction, a real MV Body part was selected, and its walking art visibly aligned to the 48×48 ground line. The Character Creator is now mounted in the real Editor shell beside the RPG Database page.
- Full recipe: **PASS**. The bounded validator selected nine real core parts: body, face shape, eyes, eyebrows, nose, mouth, rear hair, clothing, and front hair. Representation-specific face-only layers no longer invalidate walking or side-view composition.
- Cocoa captures: **PASS after visual inspection**:
  - `/private/tmp/asteria-mv-character-creator/editor-walking.png`
  - `/private/tmp/asteria-mv-character-creator/editor-face.png`
  - `/private/tmp/asteria-mv-character-creator/editor-side-view.png`
- pygame capture: **PASS after visual inspection**: `/private/tmp/asteria-mv-character-creator/runtime-map.png`. It contains a generated 48×48 actor and a native 96×96 `$BigMonster1` at the same `standing_y=240`; both rectangles end at y=240, and the large sprite is neither shrunk nor clipped.
- Bounded runtime: **PASS**, exactly 3 displayed frames followed by clean shutdown. Machine-readable evidence is `/private/tmp/asteria-mv-character-creator/results.json`.
- Generated actor integration: **PASS** for three canonical visual assets, RPG ActorDefinition, eight idle/walk directional clips, Animator2D metadata, map-cell entity placement, stable undo/redo IDs, and rollback at files/assets/actor/entity boundaries.
- Repository hygiene: **PASS**. `local_reference/rpg_maker_mv` remains Git-ignored; no MV source or generated PNG/JPG/WebP is tracked.
- `compileall`, `pip check`, and `git diff --check`: **PASS**.

The face capture initially exposed an incomplete recipe with only body and clothing layers. That evidence was rejected rather than promoted to PASS. Independent generic categories were added for face shape, eyebrows, nose, mouth, and facial marks; the final captures were regenerated and visually re-inspected.

Audio-device timing remains **PARTIAL** and outside this character-creator phase. Live keyboard/controller movement, real GPU frame pacing, and final game-specific occlusion also remain **PARTIAL**; they are not implied by the bounded three-frame pygame evidence.
