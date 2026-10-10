# CB15_RETIREMENT_REVIEW

**Status:** PROPOSAL — **nothing below has been removed.** Per D12 #5, each item needs your explicit approval (approve / reject / defer) before any change.
**Evidence date:** 2026-10-10, `main` @ `2f14a7e`. Reference counts come from `grep` over `src/`, `tests/` and `scripts/` (the build-generated `src/asteria.egg-info/SOURCES.txt` is excluded).
**Scope basis:** `SCOPE_DECISIONS.md` cancels the Character Generator (status E). `ASTERIA_SPEC.md` §"Character Generator" (line 822) calls it *optional*. D2 lists generic capabilities that must survive. CB14 (generic sprite-sheet placement, actor appearance, actor link, thumbnails) is complete, so no generic capability now depends only on the Generator UI.

---

## Part A — Items still in the repository (decision needed)

### A1. Layered Character Generator compositor

| Field | Content |
|---|---|
| Feature / Module | Layered character compositor (`CharacterGeneratorPreset`, `CharacterPart`, `CharacterGeneratorCatalog`, layer order) |
| Source Paths | `src/asteria/assets/character_generator.py` (109 lines) |
| Original Purpose | Composite body, hair, outfit and other part layers into a 48×48 walking sheet |
| Current Dependencies | Imported by `character_generator_topology.py`, `rpg_maker_mv_generator.py`, `character_bundle.py`, `editor/character_generator_widget.py`, `editor/character_generator_workspace.py`, `editor/shell.py:146` (Character Creator tab), `scripts/validate_mv_character_creator.py`; tests `test_character_generator.py` (5), `test_character_bundle_generator.py` (10), `test_character_generator_topology.py` (3) |
| Canonical SPEC Requirement | Optional feature, formally cancelled (E). No other SPEC section requires it. |
| Replacement Availability | **Available.** Any free-licensed sprite sheet → `CharacterVisualSet.from_walking_sheet` → `CreateCharacterCommand` ("Place Character from Sprite Sheet…", CB14). |
| Removal Impact | Removes the Character Creator tab; projects that rely on in-editor layered composition lose it. Runtime is unaffected (0 runtime imports). |
| Recommendation | **RETIRE** (together with A2–A5, one change) |
| Migration / Rollback | Existing generated sheets remain normal PNG assets and keep working through `CharacterVisualSet`. Rollback: `git revert` of the retirement commit. Back up the files to a dated zip outside the repo before deleting (as in D7). |

### A2. Generator part topology

| Field | Content |
|---|---|
| Feature / Module | Part slot/topology description for the compositor |
| Source Paths | `src/asteria/assets/character_generator_topology.py` (65 lines) |
| Original Purpose | Define which part slots exist and how they stack |
| Current Dependencies | Only `tests/test_character_generator_topology.py` (3 tests) |
| Canonical SPEC Requirement | None beyond the cancelled Generator |
| Replacement Availability | Not needed without A1 |
| Removal Impact | None outside the Generator |
| Recommendation | **RETIRE** with A1 |
| Migration / Rollback | Same as A1 |

### A3. RPG Maker MV generator-part catalog

| Field | Content |
|---|---|
| Feature / Module | `RPGMakerMVGeneratorCatalog`: indexes RPG Maker MV `Generator/` parts as compositor parts |
| Source Paths | `src/asteria/assets/rpg_maker_mv_generator.py` (163 lines); star-imported by `src/asteria/assets/__init__.py:43` |
| Original Purpose | Feed MV generator parts from a local, git-ignored MV install into the compositor |
| Current Dependencies | `editor/shell.py:113` (`_discover_mv_generator_catalog`), `editor/character_generator_workspace.py`, `assets/character_bundle.py`, `scripts/validate_mv_character_creator.py`; tests `test_rpg_maker_mv_generator_catalog.py` (8), `test_create_character_command.py`, `test_editor_mv_character_creator.py`, `test_character_bundle_generator.py` |
| Canonical SPEC Requirement | None. AST-13 confines MV material to the asset boundary. The **MV import adapters** (`assets/rpg_maker_mv*.py` other than this file) are a separate, kept capability. |
| Replacement Availability | Not needed. MV database/map/sprite import stays in the other `rpg_maker_mv_*` modules. |
| Removal Impact | Removes the `assets` package star-export. Check that no project code uses `from asteria.assets import RPGMakerMVGenerator…` (none in the repo). |
| Recommendation | **RETIRE** with A1 |
| Migration / Rollback | Same as A1. Drop the `__init__` import in the same commit. |

### A4. Generated character bundle

| Field | Content |
|---|---|
| Feature / Module | `GeneratedCharacterBundle`, `CharacterBundleGenerator` |
| Source Paths | `src/asteria/assets/character_bundle.py` (227 lines) |
| Original Purpose | Write the compositor output (sheets, metadata, canonical asset records) to disk as a bundle |
| Current Dependencies | `editor/create_character_command.py` (accepts a bundle as well as `CharacterVisualSet`), `assets/character_visual.py` `CharacterVisualSet.from_bundle`, `editor/character_generator_workspace.py`; tests `test_character_bundle_generator.py` (10), `test_create_character_command.py` (5) |
| Canonical SPEC Requirement | None |
| Replacement Availability | **Available:** `CharacterVisualSet` (CB14) carries the same canonical asset records for any sprite sheet |
| Removal Impact | `CreateCharacterCommand` must drop its bundle branch and the `generated.` id prefix and tags. Existing projects with `actor.generated.*` ids keep loading because the ids are plain data. |
| Recommendation | **RETIRE** with A1, keeping `CreateCharacterCommand` (see A6) |
| Migration / Rollback | Keep `CharacterVisualSet.from_bundle` reading existing bundle **metadata files** if any user project has them; otherwise remove. Rollback by revert. |

### A5. Character Creator editor UI

| Field | Content |
|---|---|
| Feature / Module | `CharacterGeneratorWidget`, `CharacterGeneratorWorkspace`, "Character Creator" tab and its click-to-place flow |
| Source Paths | `src/asteria/editor/character_generator_widget.py` (328 lines), `src/asteria/editor/character_generator_workspace.py` (163 lines), wiring in `src/asteria/editor/shell.py` (lines ~110–160, ~469) |
| Original Purpose | In-editor UI for the compositor |
| Current Dependencies | `shell.py`; tests `test_editor_mv_character_creator.py` (11), `test_mv_character_creator_e2e.py` (1, also runs the script in A7), `test_character_generator.py` |
| Canonical SPEC Requirement | None (cancelled) |
| Replacement Availability | **Available:** shell actions "Place Character from Sprite Sheet…" and "Set Actor Appearance…" plus Inspector pickers (CB14, `tests/test_generic_character_inspector.py`) |
| Removal Impact | The RPG workspace loses the "Character Creator" tab. `viewport.characterCellClicked` placement must stay because the generic placement uses it, so verify before removing `_place_generated_character_at`. |
| Recommendation | **RETIRE**. Keep the generic click-to-place and route it only through `CharacterVisualSet`. |
| Migration / Rollback | Revert restores the tab. Run the GUI smoke tests (`test_editor_shell_surface.py`, `test_generic_character_inspector.py`) before and after. |

### A6. `CreateCharacterCommand` (keep)

| Field | Content |
|---|---|
| Feature / Module | Reversible "visual → Entity + Actor + assets" command |
| Source Paths | `src/asteria/editor/create_character_command.py` (204 lines) |
| Original Purpose | Generator output placement, generalized in CB14 |
| Current Dependencies | `shell.py:51`; `tests/test_generic_character_inspector.py`, `test_create_character_command.py`, `test_editor_mv_character_creator.py` |
| Canonical SPEC Requirement | **Yes:** generic Character/Entity presentation (D2, EDT-16) |
| Replacement Availability | It *is* the replacement |
| Removal Impact | Removing it would break CB14 |
| Recommendation | **KEEP.** If A4 is approved, only remove the `GeneratedCharacterBundle` branch. |
| Migration / Rollback | None needed |

### A7. MV Character Creator validation script

| Field | Content |
|---|---|
| Feature / Module | End-to-end validation of the MV-backed Character Creator |
| Source Paths | `scripts/validate_mv_character_creator.py` (246 lines) |
| Original Purpose | Manual and CI evidence for the Generator workflow |
| Current Dependencies | `tests/test_mv_character_creator_e2e.py` (1) |
| Canonical SPEC Requirement | None |
| Replacement Availability | Generic placement is covered by `test_generic_character_inspector.py` |
| Removal Impact | None outside the Generator |
| Recommendation | **RETIRE** with A5 |
| Migration / Rollback | Same as A1 |

### A8. Generator-specific tests

| Field | Content |
|---|---|
| Feature / Module | Tests that only exercise A1–A5 and A7 |
| Source Paths | `tests/test_character_generator.py` (5), `test_character_generator_topology.py` (3), `test_character_bundle_generator.py` (10), `test_rpg_maker_mv_generator_catalog.py` (8), `test_editor_mv_character_creator.py` (11), `test_mv_character_creator_e2e.py` (1); the bundle cases in `test_create_character_command.py` (5) |
| Original Purpose | Verify the Generator |
| Current Dependencies | n/a |
| Canonical SPEC Requirement | None. **Generic validation (D4 class A) is not on this list and stays unchanged.** |
| Replacement Availability | Generic tests: `test_generic_character_inspector.py`, asset pipeline gates |
| Removal Impact | About 43 fewer tests. The total test count will drop; that is expected and must not be read as a regression. |
| Recommendation | **RETIRE** with their modules. Port any assertion that covers generic behavior (for example `CreateCharacterCommand` undo/redo and rollback) to bundle-free tests **before** deleting. |
| Migration / Rollback | Same as A1 |

---

## Part B — Already removed in D7 (for the record; no action requested)

These were removed on 2026-10-09 under your D7 authorization ("先備份後處理") and are backed up at `/Users/roger/Documents/Vscode/Asteria_backup_2026-10-09_generated_art.zip` (outside the repo):

| Item | Paths |
|---|---|
| Generated / AI art | entire `assets/` tree (including `ready_user_hero`, `asteria_hero`, `template_*`, `asteria_boss`) |
| Starter character code | `assets/starter_character.py`, `starter_character_packs.py`, `starter_sprite.py`, `character_content_pack.py`, `editor/ready_character_library_widget.py` |
| Art scripts | `scripts/build_starter_template_art.py`, `rebuild_asteria_boss_aura.py`, `rebuild_starter_side_views.py` |
| Class-B art tests (D4) | `test_asteria_boss_pack.py`, `test_starter_character_art.py`, `test_starter_sprite.py`, `test_character_content_packs.py`, `test_starter_character_native_pipeline.py` (the original failure record is kept in D4) |

**Note:** D7 also recorded commit `773d072` on branch `cleanup/remove-generated-art` (not pushed). Whether that branch should be deleted is your call; it is not part of this proposal.

---

## Part C — Explicitly **not** proposed for retirement

- MV **import** adapters (`assets/rpg_maker_mv_*.py` other than A3): AST-13 keeps them at the asset boundary.
- `assets/character_visual.py` `CharacterVisualSet`, `runtime/actor_link.py`, `editor/actor_appearance.py`, `editor/asset_thumbnails.py`: these are the generic CB14 path.
- Legacy battle presentation (`LegacyPygameBattleAdapter`): retiring it is a separate CB2 proposal that depends on canonical combatant visuals and real-window verification. It is not covered here.
- All D4 class-A generic asset validation.

## Proposed execution after approval

1. Back up A1–A5, A7 and A8 to a dated zip outside the repo.
2. Port any generic assertions out of the A8 tests.
3. Remove the approved items in one commit, plus the `shell.py` and `assets/__init__.py` wiring.
4. Run the full suite, `compileall`, the lint gate, and the GUI smoke tests. Record the before and after test counts.
5. Update the traceability matrix (CG rows) and the decision log.
