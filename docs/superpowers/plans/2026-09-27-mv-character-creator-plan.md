# MV-Backed Character Creator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an RPG Maker-style Asteria character creator that composes local MV walking, face, and side-view parts and places generated characters naturally on 48×48 map cells using a shared feet anchor.

**Architecture:** MV-specific generator topology is isolated in an adapter that produces generic character parts and representation bundles. A shared placement contract drives Editor previews, imported map events, scene entities, and runtime sprite draws. A command creates the generated files, canonical assets, actor record, animator metadata, and scene entity atomically.

**Tech Stack:** Python 3.13, Pillow, PySide6, pygame-ce, pytest, existing Asteria asset/RPG/project/editor/runtime APIs.

**Spec:** `docs/superpowers/specs/2026-09-26-mv-character-creator-design.md`

## Global Constraints

- Read licensed inputs only from Git-ignored `local_reference/rpg_maker_mv`.
- Write MV-derived generated pixels only beneath Git-ignored `local_reference/rpg_maker_mv/generated` by default.
- Standard map cells are exactly 48×48 pixels and character world coordinates represent the bottom-center standing point.
- Preserve native dimensions for taller and `$` large characters; never shrink them merely to fit one cell.
- Use nearest-neighbor integer scaling for pixel-art previews.
- Keep MV filename, layer, mask, variation, body, and representation rules inside MV adapters.
- Missing representations are explicit unavailable states, never unrelated substitutes.
- Create/undo/redo must use stable IDs and atomically affect files, canonical assets, actor records, animator metadata, and scene entities.

## Review Focus

- A 96×96 `$` character must share the same standing point as a 48×48 actor without being scaled or clipped.
- `!` object-character alignment must remain explicit and must not accidentally receive normal-character vertical correction.
- Generator roots contain incomplete and differently named DLC packs; one malformed part must not hide valid siblings.
- Palette/mask and representation layers can have incompatible canvases; generation must reject the selection before writing partial output.
- Undo after a mid-command file or registry failure must remove every artifact created by that command and preserve pre-existing files.

---

### Task 1: Shared feet-anchor and 48×48 placement contract

**Files:**
- Create: `src/asteria/graphics/character_placement.py`
- Modify: `src/asteria/runtime/draw.py`
- Modify: `src/asteria/assets/scene_placement.py`
- Modify: `src/asteria/editor/character_generator_widget.py`
- Create: `tests/test_character_placement.py`

**Interfaces:**
- Consumes: existing sprite frames, `TextureDraw`, scene placement requests, and MV adapter anchor metadata.
- Produces: `CharacterPlacement(frame_size, pivot=(0.5, 1.0), object_character=False)`, `standing_point_for_cell(column: int, row: int, tile_size=(48, 48)) -> tuple[float, float]`, and `frame_rect_at_standing_point(...) -> tuple[float, float, float, float]`.

- [ ] **Step 1: Write failing placement tests**

Add tests proving a 48×48 actor occupies `(0, 0, 48, 48)` at cell `(0, 0)`, a 96×96 `$` actor occupies `(-24, -48, 72, 48)` at the same standing point, `!` semantics remain explicit, and non-integer preview scaling is rejected or rounded down to an integer.

- [ ] **Step 2: Run RED**

Run: `.venv/bin/python -m pytest tests/test_character_placement.py -v`

Expected: FAIL because the placement API does not exist.

- [ ] **Step 3: Implement the placement contract and route generic sprite drawing through it**

Keep `sprite_draw` backward compatible while deriving top-left draw coordinates from bottom-center pivots. Add a placement property identifying character standing points without changing generic non-character asset placement.

- [ ] **Step 4: Run GREEN and commit**

Run: `.venv/bin/python -m pytest tests/test_character_placement.py tests/test_graphics_runtime.py tests/test_rpg_maker_mv_adapter.py -v`

Expected: PASS.

Commit: `fix: align characters to map-cell standing points`

### Task 2: MV generator-part discovery and topology adapter

**Files:**
- Create: `src/asteria/assets/rpg_maker_mv_generator.py`
- Modify: `src/asteria/assets/__init__.py`
- Create: `tests/test_rpg_maker_mv_generator_catalog.py`

**Interfaces:**
- Consumes: local reference resolver and project layout from the current MV integration.
- Produces: `RPGMakerMVGeneratorCatalog.discover(reference_root: Path) -> RPGMakerMVGeneratorCatalog`, `MVGeneratorPart`, `MVGeneratorRepresentation`, `MVGeneratorIssue`, and `to_character_parts() -> tuple[CharacterPart, ...]`.

- [ ] **Step 1: Write failing real-part discovery tests**

Assert deterministic discovery of the available generator roots and parts; verify category, body/gender, variation, layer order, walking/face/side-view relationships, thumbnails, and masks for representative real files. Add malformed/incomplete temporary roots proving one bad part yields an issue without hiding valid siblings.

- [ ] **Step 2: Run RED**

Run: `.venv/bin/python -m pytest tests/test_rpg_maker_mv_generator_catalog.py -v`

Expected: FAIL because the adapter does not exist.

- [ ] **Step 3: Implement discovery and generic-category translation**

Normalize only stable shared categories; retain source category and filename tokens as metadata. Represent unavailable walking/face/SV variants with `None` and an issue rather than substitution.

- [ ] **Step 4: Run GREEN and commit**

Run: `.venv/bin/python -m pytest tests/test_rpg_maker_mv_generator_catalog.py -v`

Expected: PASS against repo-local MV parts.

Commit: `feat: discover MV generator parts`

### Task 3: Coordinated walking, face, and side-view composition

**Files:**
- Create: `src/asteria/assets/character_bundle.py`
- Modify: `src/asteria/assets/character_generator.py`
- Create: `tests/test_character_bundle_generator.py`

**Interfaces:**
- Consumes: `RPGMakerMVGeneratorCatalog`, generic `CharacterRecipe`, and `CharacterPlacement`.
- Produces: `GeneratedCharacterBundle`, `CharacterBundleGenerator.generate(recipe, output_root) -> GeneratedCharacterBundle`, and canonical assets for walking, face, and side-view outputs.

- [ ] **Step 1: Write failing composition tests**

Use representative real local parts to assert deterministic layer order and output dimensions for all three representations, transparent backgrounds, feet anchor metadata, source identities, and nearest-neighbor-safe pixels. Test incompatible canvas/body, missing mask, missing representation, and failure before partial file output.

- [ ] **Step 2: Run RED**

Run: `.venv/bin/python -m pytest tests/test_character_bundle_generator.py -v`

Expected: FAIL because bundle generation does not exist.

- [ ] **Step 3: Implement atomic bundle generation**

Compose into a temporary sibling directory, validate every representation, then rename into the ignored generated root. Existing single-sheet `CharacterGenerator.generate` remains supported through a compatibility path.

- [ ] **Step 4: Run GREEN and commit**

Run: `.venv/bin/python -m pytest tests/test_character_bundle_generator.py tests/test_character_generator.py -v`

Expected: PASS.

Commit: `feat: generate coordinated character visual bundles`

### Task 4: RPG Maker-style Editor character creator

**Files:**
- Modify: `src/asteria/editor/character_generator_workspace.py`
- Rewrite: `src/asteria/editor/character_generator_widget.py`
- Modify: `src/asteria/editor/theme.py`
- Create: `tests/test_editor_mv_character_creator.py`

**Interfaces:**
- Consumes: generator catalog and bundle generator from Tasks 2–3.
- Produces: filter/search/selection workspace API plus walking, face, and side-view preview models; widget exposes selected category, part grid, representation tabs, direction, animation frame, and unavailable states.

- [ ] **Step 1: Write failing workspace and visible-widget tests**

Assert category filtering, thumbnail selection, synchronized preview refresh, Down/Left/Right/Up animation, explicit unavailable representations, and a visible 48×48 grid with ground line. Assert preview pixmaps use integer nearest-neighbor scale and tall art is not clipped.

- [ ] **Step 2: Run RED**

Run: `.venv/bin/python -m pytest tests/test_editor_mv_character_creator.py -v`

Expected: FAIL on missing workspace/widget capabilities.

- [ ] **Step 3: Implement the three-area Editor surface**

Use body/profile controls on the left, a scrollable thumbnail grid in the center, and walking/face/SV previews on the right. Avoid loading full-resolution images for every thumbnail; cache bounded thumbnail pixmaps by source path and mtime.

- [ ] **Step 4: Run GREEN and commit**

Run: `.venv/bin/python -m pytest tests/test_editor_mv_character_creator.py tests/test_character_generator.py -v`

Expected: PASS.

Commit: `feat: redesign MV-backed character creator UI`

### Task 5: Atomic Actor, asset, animator, and scene creation command

**Files:**
- Create: `src/asteria/editor/create_character_command.py`
- Modify: `src/asteria/editor/character_generator_workspace.py`
- Create: `tests/test_create_character_command.py`

**Interfaces:**
- Consumes: `GeneratedCharacterBundle`, `Project`, target `Scene`, and selected map cell.
- Produces: `CreateCharacterCommand.execute() -> CreatedCharacter`, `undo()`, and `redo()` with stable actor/asset/entity IDs.

- [ ] **Step 1: Write failing command tests**

Assert execute registers three canonical assets, creates `ActorDefinition`, directional walking clips, animator metadata, and a scene entity at the cell standing point. Assert undo removes only created records/files and redo restores identical IDs. Inject failure after each mutation boundary and assert complete rollback while pre-existing files remain.

- [ ] **Step 2: Run RED**

Run: `.venv/bin/python -m pytest tests/test_create_character_command.py -v`

Expected: FAIL because the command does not exist.

- [ ] **Step 3: Implement transactional command behavior**

Stage generated files first, snapshot only touched registries, and apply mutations in deterministic order. Roll back in reverse order on any exception.

- [ ] **Step 4: Run GREEN and commit**

Run: `.venv/bin/python -m pytest tests/test_create_character_command.py tests/test_editor_commands.py -v`

Expected: PASS.

Commit: `feat: create playable characters from generated bundles`

### Task 6: Cocoa and pygame end-to-end validation

**Files:**
- Create: `scripts/validate_mv_character_creator.py`
- Create: `tests/test_mv_character_creator_e2e.py`
- Modify: `audit/REAL_VALIDATION_ACCEPTANCE_REPORT_2026-09-26.md`

**Interfaces:**
- Consumes: every prior task plus imported MV map support from the main MV integration plan.
- Produces: bounded Editor/runtime validation, PNG captures under `/private/tmp/asteria-mv-character-creator`, and machine-readable results.

- [ ] **Step 1: Write failing bounded E2E test**

Assert a real MV-backed recipe creates a bundle and actor, is placed on an imported map cell, renders walking frames with feet aligned to the ground line, and stops after the requested frame count.

- [ ] **Step 2: Run RED**

Run: `.venv/bin/python -m pytest tests/test_mv_character_creator_e2e.py -v`

Expected: FAIL because the validation path does not exist.

- [ ] **Step 3: Implement bounded Cocoa and pygame validators**

Capture the creator's three preview modes and a runtime map view containing a standard and a `$` large character at known cells. Never wait indefinitely for UI automation or input.

- [ ] **Step 4: Inspect captures and run complete verification**

Run focused E2E, complete pytest, compileall, pip check, `git diff --check`, and Git ignored/tracked checks for source and generated licensed pixels.

Expected: all automated checks pass; captures show exact standing-point alignment, crisp integer-scaled pixels, and no clipping or overlap.

- [ ] **Step 5: Update evidence and commit**

Record exact counts, captures, remaining audio boundary, and any PARTIAL items without promoting them to PASS.

Commit: `test: validate MV-backed character creation end to end`
