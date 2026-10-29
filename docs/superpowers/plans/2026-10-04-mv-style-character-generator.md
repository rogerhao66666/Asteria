# MV-Style Character Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The user explicitly requested no commits, so omit the skill's usual commit steps.

**Goal:** Build an MV-style, four-representation character generator with complete sheet previews and compatible body families, then connect equipped weapon type to separate battle weapon animation.

**Architecture:** Extend the existing catalog/workspace/bundle pipeline rather than replacing it. A saved `CharacterRecipe` selects a single body family and aligned parts; the compositor produces complete transparent TV/FG/TVD/SV sheets. The Editor previews those sheets and restores recipes, while a separate weapon-animation adapter reads equipment state without changing armor visuals.

**Tech Stack:** Python 3, Pillow, PySide6, pytest; local ignored RPG Maker MV reference tree.

**Spec:** `docs/superpowers/specs/2026-10-04-mv-style-character-generator-design.md`

## Global Constraints

- Work in the original `~/Documents/Vscode/Asteria` repo. Preserve existing uncommitted changes. Do not commit.
- Do not copy or mutate `local_reference/rpg_maker_mv`; use it read-only, and do not add MV files to Git.
- Output grids: walking 144×192 (3×4 at 48px), damaged 144×48 (3×1 at 48px), side-view 576×384 (9×6 at 64px), face 144×144.
- Body families are Male, Female, and Kid. Never silently composite parts across families or resize a source to disguise mismatched dimensions.
- Armor equipment does not change appearance. Weapon visuals remain separate from generated character sheets.
- Native macOS Editor validation, including save/reopen and battle, is required before declaring completion.

## Review Focus

- A part with only FG or TVD art contributes to that sheet without blocking unrelated sheets; test in Task 2.
- Family switching with selected DLC parts cannot retain cross-family IDs or stale palette keys; test in Task 1.
- Two parts mapped to one collapsed category (e.g. eyes/eyebrows) must remain independently selectable; test in Task 1.
- A preexisting three-image bundle must still load as a fixed character; test in Task 2.
- A weapon with missing image mapping must fall back to empty-hand animation without crashing; test in Task 4.

---

### Task 1: Catalog and recipe family compatibility

**Files:** Modify `src/asteria/assets/rpg_maker_mv_generator.py`, `src/asteria/assets/character_generator.py`, `src/asteria/editor/character_generator_workspace.py`; test `tests/test_rpg_maker_mv_generator_catalog.py`, `tests/test_editor_mv_character_creator.py`.

**Interfaces:** `CharacterRecipe` persists `body_family: str`; `CharacterGeneratorWorkspace.set_body_family(family: str) -> tuple[str, ...]` returns cleared category names; `choices(category, ..., gender=...)` exposes only compatible parts. Preserve existing recipe construction and `ordered_part_ids()` callers.

- [ ] Add failing tests for Male/Female/Kid discovery, independent eyebrows/eyes and cloak/clothing/accessory choices, mandatory body, cross-family rejection, and family-switch cleanup (including palette).
- [ ] Run those tests with `PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_rpg_maker_mv_generator_catalog.py tests/test_editor_mv_character_creator.py`; confirm the new cases fail for the intended reason.
- [ ] Implement distinct logical categories and family-aware workspace selection, with one canonical base body for each family and compatible source-set filtering.
- [ ] Re-run the focused tests; confirm all pass.

### Task 2: Four-sheet composition and recipe round-trip

**Files:** Modify `src/asteria/assets/character_bundle.py`, `src/asteria/editor/character_generator_workspace.py`; test `tests/test_character_bundle_generator.py`, `tests/test_editor_mv_character_creator.py`, `tests/test_starter_character_native_pipeline.py`.

**Interfaces:** `GeneratedCharacterBundle.damaged_path: Path | None`; `CharacterBundleGenerator.compose(name: str, recipe: CharacterRecipe) -> Image.Image` for `walking`, `face`, `damaged`, `side_view`; `CharacterGeneratorWorkspace.load_bundle(metadata_path: Path) -> None`. Existing `visual_paths` remains its current three-path contract; add a separate four-path accessor.

- [ ] Add failing tests for 144×48 damaged output, transparency and exact cell positions in all sheets, FG/TVD-only contributions, atomic rollback, legacy three-image bundle, and saved-recipe reloading.
- [ ] Run `PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_character_bundle_generator.py tests/test_starter_character_native_pipeline.py`; confirm the new cases fail.
- [ ] Implement four-sheet validation/composition and metadata, preserving the existing three-image placement contract. Reject bad source dimensions before publishing any directory.
- [ ] Re-run the focused tests; confirm all pass.

### Task 3: Complete-sheet Editor preview

**Files:** Modify `src/asteria/editor/character_generator_widget.py`, `src/asteria/editor/character_generator_workspace.py`; test `tests/test_editor_mv_character_creator.py`.

**Interfaces:** `preview_representation(name: str)` accepts four names; the widget exposes `damaged_canvas`, four preview tabs, and a full-sheet walking canvas while keeping `preview_frame()` for single-frame inspection. Switching body family calls `set_body_family` and refreshes all previews.

- [ ] Add failing Qt tests for Kid selection, all four full-sheet tabs, full image sizes, selection-driven refresh, accessible frame inspection, and a clear message when one representation is unavailable.
- [ ] Run focused Editor tests with `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_editor_mv_character_creator.py`; confirm the new cases fail.
- [ ] Implement checkerboard full-sheet previews, family/variation/color controls, and a scroll container so 576×384 remains inspectable without clipping. Keep the map-placement signal unchanged.
- [ ] Re-run the focused Qt tests; confirm all pass.

### Task 4: Weapon-type battle animation

**Files:** Add `src/asteria/graphics/mv_weapon_visual.py`; modify `src/asteria/presentation/battle_runtime.py` (battle draw assembly), `src/asteria/presentation/battle_screen.py` (equipped-weapon visual input), and `src/asteria/assets/rpg_maker_mv_project.py` (MV weapon-type metadata); test `tests/test_battle_combatant_visual_system.py` plus a new `tests/test_mv_weapon_visual.py`.

**Interfaces:** `weapon_visual_for_type(weapon_type: str, system_data: dict) -> WeaponVisual` returns motion (`thrust`, `swing`, `missile`, or unarmed) and optional source rectangle from `Weapons1–3.png`; battle rendering overlays those frames only during an attack. The weapon definition's type must be explicit or mapped from imported MV weapon metadata; do not infer it from display name.

- [ ] Add failing tests for sword/bow/unarmed mapping, three successive weapon frames, missing image fallback, weapon swap changing attack visual, and armor swap leaving appearance unchanged.
- [ ] Run the new and relevant existing battle tests; confirm intended failures.
- [ ] Implement the adapter and connect it to equipped weapon state without baking weapon pixels into the character bundle.
- [ ] Re-run battle tests; confirm all pass.

### Task 5: Integration and native validation

**Files:** Extend `tests/test_editor_mv_character_creator.py` and `tests/test_starter_character_native_pipeline.py`; add an evidence note under `docs/superpowers/validation/` if the repo already uses that pattern, otherwise report evidence in the final answer only.

**Interfaces:** No new product API; verifies Tasks 1–4 together.

- [ ] Add an integration test that selects one distinct appearance per Male/Female/Kid, generates all four sheets, places a character on a map, saves/reopens, and restores the recipe.
- [ ] Run the focused tests, then the full pytest suite. Use a temporary `PYTHONPYCACHEPREFIX` if compilation checks are needed; do not overwrite user assets.
- [ ] Launch the real macOS Editor (not only `QT_QPA_PLATFORM=offscreen`) and inspect the three families, full sheet cells, colors, placement, save/reopen, and battle weapon change. Record exact pass/fail evidence and any renderer limitation.
- [ ] Confirm `git status --short` contains only expected changes; leave all changes uncommitted.
