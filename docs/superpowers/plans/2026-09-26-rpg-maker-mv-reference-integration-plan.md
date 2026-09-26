# RPG Maker MV Reference Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Copy the complete local RPG Maker MV `NewData` and `dlc` trees into a Git-ignored Asteria reference library, then make Asteria load and exercise MV maps, actors, skills, items, icons, and character/battle artwork through explicit adapters.

**Architecture:** Licensed files live only under a repository-local ignored root. Small resolver, inventory, database, map, visual-catalog, and project-import adapters translate MV-specific structures at the boundary into generic Asteria models. Unsupported fields remain available as immutable source metadata, while audio is indexed and reference-resolved without claiming playback support.

**Tech Stack:** Python 3.13, pathlib/json/hashlib/shutil, Pillow, pygame-ce, pytest, existing Asteria canonical assets/RPG/project/tilemap/runtime APIs.

**Spec:** `docs/superpowers/specs/2026-09-26-local-rpg-maker-mv-reference-library-design.md`

## Global Constraints

- Copy both `RPG Maker MV.app/Contents/MacOS/NewData` and `dlc` completely, preserving relative paths.
- Keep `/local_reference/rpg_maker_mv/` ignored by Git before copying any licensed file.
- Never commit, push, package, or redistribute copied MV files.
- The source installation is read-only; synchronization is additive and must not delete destination files.
- Derived reports may contain relative paths, sizes, hashes, and aggregate counts, but never source file contents.
- Future Asteria starter data must use independently authored names, records, images, audio, and text.
- Audio scope in this plan is discovery, indexing, reference validation, and metadata only; playback remains a later phase.
- Tests requiring licensed fixtures skip explicitly only when neither the local reference library nor Steam installation is available.

## Review Focus

- Interrupted or partial copies must be detected by source/destination count and byte mismatches and safely resumable.
- MV JSON arrays contain a `null` element at index zero; loaders must preserve numeric IDs without creating phantom records.
- DLC sample projects vary in encoding, plugin content, and database completeness; discovery must isolate malformed projects instead of aborting the entire inventory.
- MV map tile data is a flattened six-layer array and uses MV tile IDs; layer dimensions and unsupported IDs must fail clearly rather than render shifted geometry.
- Visual records may refer to empty filenames, missing sheets, or out-of-range icon indices; imports must report unresolved references without crashing unrelated records.

---

### Task 1: Local reference synchronization and deterministic inventory

**Files:**
- Modify: `.gitignore`
- Create: `src/asteria/assets/local_reference.py`
- Create: `scripts/sync_rpg_maker_mv_reference.py`
- Create: `tests/test_local_reference.py`
- Create: `audit/rpg_maker_mv_local_inventory.json`

**Interfaces:**
- Produces: `LocalReferenceLayout`, `resolve_rpg_maker_mv_root(repo_root: Path, steam_root: Path | None = None) -> Path | None`, `inventory_tree(root: Path) -> ReferenceInventory`, and CLI `scripts/sync_rpg_maker_mv_reference.py SOURCE DESTINATION --inventory OUTPUT`.
- Consumes: no earlier task interfaces.

- [ ] **Step 1: Write failing synchronization and inventory tests**

Add tests named `test_local_reference_prefers_repo_copy`, `test_inventory_is_deterministic`, `test_partial_copy_is_reported`, and `test_reference_root_is_git_ignored`. Use tiny temporary `NewData`/`dlc` trees and assert relative paths, byte totals, SHA-256 values, mismatch records, and ignore coverage.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_local_reference.py -v`

Expected: FAIL because `asteria.assets.local_reference` and the sync CLI do not exist.

- [ ] **Step 3: Implement resolver, inventory, and additive synchronization**

Add `LocalReferenceLayout(repo_root: Path, root: Path, new_data: Path, dlc: Path)`, immutable `ReferenceFile`, `ReferenceInventory`, and `ReferenceMismatch` values. The CLI must copy with `shutil.copy2`, create parents, skip equal-size/equal-mtime files, never unlink destination entries, and atomically replace the derived JSON inventory file.

- [ ] **Step 4: Add Git exclusion before copying**

Append `/local_reference/rpg_maker_mv/` to `.gitignore`, then verify:

Run: `git check-ignore -v local_reference/rpg_maker_mv/probe`

Expected: output identifies the new `.gitignore` rule.

- [ ] **Step 5: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_local_reference.py -v`

Expected: PASS.

- [ ] **Step 6: Synchronize the complete local source trees**

Run the CLI with the approved Steam root and destination `local_reference/rpg_maker_mv`, emitting `audit/rpg_maker_mv_local_inventory.json`. Record source and destination file counts and bytes for `NewData` and `dlc`.

Expected: both trees match; rerunning reports zero files requiring copy.

- [ ] **Step 7: Verify licensed files remain invisible to Git and commit derived work**

Run: `git status --short --ignored local_reference/rpg_maker_mv audit/rpg_maker_mv_local_inventory.json`

Expected: the reference root is ignored and only the inventory/code/tests are commit candidates.

Commit: `feat: add local MV reference library tooling`

### Task 2: Portable fixture resolution and complete content discovery

**Files:**
- Modify: `src/asteria/assets/local_reference.py`
- Modify: `tests/test_rpg_maker_mv_adapter.py`
- Create: `tests/test_rpg_maker_mv_reference_inventory.py`

**Interfaces:**
- Consumes: `resolve_rpg_maker_mv_root(...) -> Path | None` from Task 1.
- Produces: `discover_mv_projects(root: Path) -> tuple[RPGMakerMVProjectLayout, ...]` and `RPGMakerMVProjectLayout` paths for `data`, `img`, `audio`, `fonts`, and `js`.

- [ ] **Step 1: Write failing discovery tests**

Assert that the repository-local `NewData` is preferred, all DLC projects containing `data/System.json` are discovered deterministically, missing optional directories are represented as `None`, and a malformed DLC directory does not hide valid siblings.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_rpg_maker_mv_reference_inventory.py tests/test_rpg_maker_mv_adapter.py -v`

Expected: FAIL because discovery and local preference are absent.

- [ ] **Step 3: Implement layout discovery and switch existing real-fixture tests**

Use the local resolver first and the Steam root only as fallback. Preserve the current explicit skip message when neither exists.

- [ ] **Step 4: Run focused tests and commit**

Run: `.venv/bin/python -m pytest tests/test_rpg_maker_mv_reference_inventory.py tests/test_rpg_maker_mv_adapter.py -v`

Expected: PASS against `local_reference/rpg_maker_mv`.

Commit: `test: use portable MV reference fixtures`

### Task 3: MV database reader for actors, skills, items, equipment, and system metadata

**Files:**
- Create: `src/asteria/assets/rpg_maker_mv_database.py`
- Modify: `src/asteria/assets/__init__.py`
- Create: `tests/test_rpg_maker_mv_database.py`

**Interfaces:**
- Consumes: `RPGMakerMVProjectLayout` from Task 2.
- Produces: `RPGMakerMVDatabase.load(layout: RPGMakerMVProjectLayout) -> RPGMakerMVDatabase`, `MVRecord`, `MVActorRecord`, `MVSkillRecord`, `MVItemRecord`, `MVEquipmentRecord`, `MVSystemRecord`, and `MVReferenceIssue`.

- [ ] **Step 1: Write failing real-database tests**

Using local `NewData`, assert exact non-null record counts from `Actors.json`, `Classes.json`, `Skills.json`, `Items.json`, `Weapons.json`, and `Armors.json`; verify ID 1 remains ID 1; verify actor character/face/battler names, skill/item icon indices, and `System.json` tileset/start-map metadata. Add a temporary fixture proving index-zero `null`, missing files, invalid JSON, and unknown fields are handled as specified.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_rpg_maker_mv_database.py -v`

Expected: FAIL because the database reader does not exist.

- [ ] **Step 3: Implement immutable typed records plus raw metadata retention**

Use `load_json_array(name: str) -> tuple[Mapping[str, Any], ...]` internally. Typed records expose stable fields required by Asteria and store untouched unknown keys in a sorted metadata tuple. Return issues for missing cross-references; reject malformed top-level structures with `ValueError` naming the file.

- [ ] **Step 4: Run focused tests and commit**

Run: `.venv/bin/python -m pytest tests/test_rpg_maker_mv_database.py -v`

Expected: PASS.

Commit: `feat: read RPG Maker MV database records`

### Task 4: MV visual and audio reference catalog

**Files:**
- Create: `src/asteria/assets/rpg_maker_mv_catalog.py`
- Modify: `src/asteria/assets/rpg_maker_mv.py`
- Modify: `src/asteria/assets/__init__.py`
- Create: `tests/test_rpg_maker_mv_catalog.py`

**Interfaces:**
- Consumes: `RPGMakerMVDatabase` from Task 3 and existing `RPGMakerMVImporter`.
- Produces: `RPGMakerMVCatalog.build(layout, database) -> RPGMakerMVCatalog`, canonical assets for image sheets/textures/tilesets, `MVIconReference(index: int, source: Path, box: tuple[int, int, int, int])`, and `MVAudioReference(kind: str, name: str, candidates: tuple[Path, ...])`.

- [ ] **Step 1: Write failing catalog tests**

Assert character sheets, face sheets, side-view battlers, enemies, tilesets, battlebacks, pictures, parallaxes, animations, titles, and `img/system/IconSet.png` resolve. Assert MV icon index 1 produces its correct 32×32 source box. Assert database BGM/BGS/ME/SE names resolve to available `.ogg`/`.m4a` candidates. Test empty filenames, missing files, and an out-of-range icon index as non-fatal `MVReferenceIssue` values.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_rpg_maker_mv_catalog.py -v`

Expected: FAIL because the catalog does not exist.

- [ ] **Step 3: Implement cataloging and canonical registration**

Keep MV filename/category/icon-grid rules inside this adapter. Register canonical assets with `provider="rpg_maker_mv"`, local source URIs, provenance identifying local development fixtures, and metadata linking source MV IDs without copying content.

- [ ] **Step 4: Run focused tests and commit**

Run: `.venv/bin/python -m pytest tests/test_rpg_maker_mv_catalog.py -v`

Expected: PASS.

Commit: `feat: catalog MV visual and audio references`

### Task 5: MV map parsing, scene conversion, and tile drawing

**Files:**
- Create: `src/asteria/assets/rpg_maker_mv_map.py`
- Create: `src/asteria/runtime/rpg_maker_mv_map_render.py`
- Modify: `src/asteria/assets/__init__.py`
- Create: `tests/test_rpg_maker_mv_map.py`
- Create: `tests/test_rpg_maker_mv_map_render.py`

**Interfaces:**
- Consumes: project layout/catalog from Tasks 2 and 4.
- Produces: `RPGMakerMVMap.load(path: Path) -> RPGMakerMVMap`, `to_asteria_scene(mv_map, catalog) -> Scene`, `MVTileResolver.resolve(tile_id: int) -> MVTileRegion | None`, and `compose_mv_map_draws(mv_map, catalog, viewport) -> tuple[TextureDraw, ...]`.

- [ ] **Step 1: Write failing parser tests**

Assert `MapInfos.json` entries resolve to map files, width/height and six flattened layers are validated, display name/parallax/encounter/event placement is retained, and event character page image references resolve. Add temporary malformed maps for wrong data length and invalid tile IDs.

- [ ] **Step 2: Run parser tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_rpg_maker_mv_map.py -v`

Expected: FAIL because map support does not exist.

- [ ] **Step 3: Implement map records and Asteria scene conversion**

Create one generic `Scene` per map, a `TileMap2DComponent` host entity, and entities for event placements with retained MV event/page metadata. Keep MV-specific tile IDs and autotile rules in `MVTileResolver`; do not leak them into `asteria.graphics.TileMap`.

- [ ] **Step 4: Write failing tile-render tests**

Assert representative A/B/C/D/E tiles resolve to the correct source texture and region, draw order follows MV lower/upper layers, empty tile zero emits no draw, and viewport culling removes off-screen tiles.

- [ ] **Step 5: Implement draw composition and run tests**

Run: `.venv/bin/python -m pytest tests/test_rpg_maker_mv_map.py tests/test_rpg_maker_mv_map_render.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

Commit: `feat: import and render RPG Maker MV maps`

### Task 6: Convert MV gameplay records into an Asteria project

**Files:**
- Create: `src/asteria/assets/rpg_maker_mv_project.py`
- Modify: `src/asteria/assets/__init__.py`
- Create: `tests/test_rpg_maker_mv_project.py`

**Interfaces:**
- Consumes: database, catalog, and map adapters from Tasks 3–5.
- Produces: `RPGMakerMVProjectImporter.import_project(layout: RPGMakerMVProjectLayout, *, map_ids: Iterable[int] | None = None) -> RPGMakerMVProjectImport`, where the result contains `project: Project`, `issues: tuple[MVReferenceIssue, ...]`, and source-ID maps.

- [ ] **Step 1: Write failing conversion tests**

Assert actors become `ActorDefinition`, skills become `AbilityDefinition`, items become `ItemDefinition`, weapons/armors become `EquipmentDefinition`, images become canonical assets, selected maps become scenes, and icon references are attached as source metadata. Verify the generated project serializes, reloads, validates, and preserves counts and cross-reference maps.

- [ ] **Step 2: Add edge-case tests from Review Focus**

Test a missing character sheet, empty actor image name, dangling skill ID, unknown effect code, and out-of-range icon index. Expected behavior: import all unaffected records, retain unsupported raw metadata, and return deterministic issues.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_rpg_maker_mv_project.py -v`

Expected: FAIL because the importer does not exist.

- [ ] **Step 4: Implement conservative conversion**

Map stable shared concepts only. Prefix generated IDs with `mv.` plus source category and numeric ID. Preserve MV-only formulas/effects/traits as metadata or issues rather than guessing Asteria semantics. Register placeholder-safe references so one unsupported record does not invalidate the entire imported project.

- [ ] **Step 5: Run focused tests and commit**

Run: `.venv/bin/python -m pytest tests/test_rpg_maker_mv_project.py -v`

Expected: PASS.

Commit: `feat: convert MV data into Asteria projects`

### Task 7: Real renderer validation for maps, characters, faces, battlers, and icons

**Files:**
- Create: `scripts/validate_rpg_maker_mv_runtime.py`
- Create: `tests/test_rpg_maker_mv_runtime_validation.py`
- Modify: `audit/REAL_VALIDATION_ACCEPTANCE_REPORT_2026-09-26.md`

**Interfaces:**
- Consumes: `RPGMakerMVProjectImporter` and runtime draw adapters.
- Produces: bounded validation CLI with `--reference-root`, `--map-id`, `--frames`, and `--output-dir`; JSON summary and PNG captures outside Git.

- [ ] **Step 1: Write failing bounded-runner test**

Use a fake backend to assert the runner imports one real map and renders map tiles, an event character, a face region, a side-view battler frame, an enemy image, and several item/skill icons; assert it stops after the requested frame count.

- [ ] **Step 2: Run test and verify failure**

Run: `.venv/bin/python -m pytest tests/test_rpg_maker_mv_runtime_validation.py -v`

Expected: FAIL because the runner does not exist.

- [ ] **Step 3: Implement bounded validation CLI**

Use `PygameRuntimeBackend`; never wait indefinitely for input. Render labels and a diagnostic panel listing source IDs and unresolved references. Save framebuffer captures and a machine-readable summary under `/private/tmp/asteria-mv-runtime-validation` by default.

- [ ] **Step 4: Run real pygame validation**

Run the CLI against `local_reference/rpg_maker_mv/NewData` with a bounded frame count.

Expected: process exits zero, captures are non-empty, and summary reports successful map/character/face/battler/enemy/icon draws.

- [ ] **Step 5: Visually inspect captures and update acceptance report**

Confirm tile alignment, transparency, frame clipping, icon clipping, z-order, and absence of stale/overlapping UI. Record actual PASS/PARTIAL results and do not promote audio playback.

- [ ] **Step 6: Run focused tests and commit**

Run: `.venv/bin/python -m pytest tests/test_rpg_maker_mv_runtime_validation.py tests/test_rpg_maker_mv_project.py tests/test_rpg_maker_mv_map_render.py -v`

Expected: PASS.

Commit: `test: validate imported MV content in real runtime`

### Task 8: Full verification and repository hygiene

**Files:**
- Modify: `audit/REAL_VALIDATION_ACCEPTANCE_REPORT_2026-09-26.md`

**Interfaces:**
- Consumes: all earlier tasks.
- Produces: final verified report and clean Git state with licensed data ignored.

- [ ] **Step 1: Verify copy integrity and ignored state**

Compare source/destination counts and byte totals, validate the inventory, run `git check-ignore`, and search staged/tracked files for paths under `local_reference/rpg_maker_mv`.

Expected: exact source/destination match and zero licensed files tracked or staged.

- [ ] **Step 2: Run the complete regression suite**

Run: `.venv/bin/python -m pytest -q`

Expected: 0 failures and no unexpected skips in local-MV tests.

- [ ] **Step 3: Run build and dependency checks**

Run: `.venv/bin/python -m compileall -q src tests scripts`

Run: `.venv/bin/python -m pip check`

Run: `git diff --check`

Expected: all exit zero; pip reports no broken requirements.

- [ ] **Step 4: Update evidence with exact results and commit**

Record test counts, inventory totals, runtime captures, unresolved feature boundaries, and audio-index-only status.

Commit: `docs: record complete MV integration validation`
