# CB15_RETIREMENT_REVIEW

**Status:** EXECUTED 2026-10-11 under the CB15 conditional approval — see **Part D (execution record)** at the end. Part A below is the original proposal, kept for reference. Fields follow D14 #6: Module / Feature, Source Paths, Current Dependencies, Original SPEC Requirement, Replacement Availability, Regression Risk, Proposed Action, Rollback Plan.
**Evidence date:** 2026-10-10, `main` @ `2f14a7e`. Reference counts come from `grep` over `src/`, `tests/` and `scripts/` (the build-generated `src/asteria.egg-info/SOURCES.txt` is excluded).
**Scope basis:** `SCOPE_DECISIONS.md` cancels the Character Generator (status E). `ASTERIA_SPEC.md` §"Character Generator" (line 822) calls it *optional*. D2 lists generic capabilities that must survive. CB14 (generic sprite-sheet placement, actor appearance, actor link, thumbnails) is complete, so no generic capability now depends only on the Generator UI.

---

## Part A — Items still in the repository (decision needed)

### A1. Layered Character Generator compositor

| Field | Content |
|---|---|
| Module / Feature | Layered character compositor (`CharacterGeneratorPreset`, `CharacterPart`, `CharacterGeneratorCatalog`, layer order) — purpose: Composite body, hair, outfit and other part layers into a 48×48 walking sheet |
| Source Paths | `src/asteria/assets/character_generator.py` (109 lines) |
| Current Dependencies | Imported by `character_generator_topology.py`, `rpg_maker_mv_generator.py`, `character_bundle.py`, `editor/character_generator_widget.py`, `editor/character_generator_workspace.py`, `editor/shell.py:146` (Character Creator tab), `scripts/validate_mv_character_creator.py`; tests `test_character_generator.py` (5), `test_character_bundle_generator.py` (10), `test_character_generator_topology.py` (3) |
| Original SPEC Requirement | Optional feature, formally cancelled (E). No other SPEC section requires it. |
| Replacement Availability | **Available.** Any free-licensed sprite sheet → `CharacterVisualSet.from_walking_sheet` → `CreateCharacterCommand` ("Place Character from Sprite Sheet…", CB14). |
| Regression Risk | Removes the Character Creator tab; projects that rely on in-editor layered composition lose it. Runtime is unaffected (0 runtime imports). |
| Proposed Action | **RETIRE** (together with A2–A5, one change) |
| Rollback Plan | Existing generated sheets remain normal PNG assets and keep working through `CharacterVisualSet`. Rollback: `git revert` of the retirement commit. Back up the files to a dated zip outside the repo before deleting (as in D7). |

### A2. Generator part topology

| Field | Content |
|---|---|
| Module / Feature | Part slot/topology description for the compositor — purpose: Define which part slots exist and how they stack |
| Source Paths | `src/asteria/assets/character_generator_topology.py` (65 lines) |
| Current Dependencies | Only `tests/test_character_generator_topology.py` (3 tests) |
| Original SPEC Requirement | None beyond the cancelled Generator |
| Replacement Availability | Not needed without A1 |
| Regression Risk | None outside the Generator |
| Proposed Action | **RETIRE** with A1 |
| Rollback Plan | Same as A1 |

### A3. RPG Maker MV generator-part catalog

| Field | Content |
|---|---|
| Module / Feature | `RPGMakerMVGeneratorCatalog`: indexes RPG Maker MV `Generator/` parts as compositor parts — purpose: Feed MV generator parts from a local, git-ignored MV install into the compositor |
| Source Paths | `src/asteria/assets/rpg_maker_mv_generator.py` (163 lines); star-imported by `src/asteria/assets/__init__.py:43` |
| Current Dependencies | `editor/shell.py:113` (`_discover_mv_generator_catalog`), `editor/character_generator_workspace.py`, `assets/character_bundle.py`, `scripts/validate_mv_character_creator.py`; tests `test_rpg_maker_mv_generator_catalog.py` (8), `test_create_character_command.py`, `test_editor_mv_character_creator.py`, `test_character_bundle_generator.py` |
| Original SPEC Requirement | None. AST-13 confines MV material to the asset boundary. The **MV import adapters** (`assets/rpg_maker_mv*.py` other than this file) are a separate, kept capability. |
| Replacement Availability | Not needed. MV database/map/sprite import stays in the other `rpg_maker_mv_*` modules. |
| Regression Risk | Removes the `assets` package star-export. Check that no project code uses `from asteria.assets import RPGMakerMVGenerator…` (none in the repo). |
| Proposed Action | **RETIRE** with A1 |
| Rollback Plan | Same as A1. Drop the `__init__` import in the same commit. |

### A4. Generated character bundle

| Field | Content |
|---|---|
| Module / Feature | `GeneratedCharacterBundle`, `CharacterBundleGenerator` — purpose: Write the compositor output (sheets, metadata, canonical asset records) to disk as a bundle |
| Source Paths | `src/asteria/assets/character_bundle.py` (227 lines) |
| Current Dependencies | `editor/create_character_command.py` (accepts a bundle as well as `CharacterVisualSet`), `assets/character_visual.py` `CharacterVisualSet.from_bundle`, `editor/character_generator_workspace.py`; tests `test_character_bundle_generator.py` (10), `test_create_character_command.py` (5) |
| Original SPEC Requirement | None |
| Replacement Availability | **Available:** `CharacterVisualSet` (CB14) carries the same canonical asset records for any sprite sheet |
| Regression Risk | `CreateCharacterCommand` must drop its bundle branch and the `generated.` id prefix and tags. Existing projects with `actor.generated.*` ids keep loading because the ids are plain data. |
| Proposed Action | **RETIRE** with A1, keeping `CreateCharacterCommand` (see A6) |
| Rollback Plan | Keep `CharacterVisualSet.from_bundle` reading existing bundle **metadata files** if any user project has them; otherwise remove. Rollback by revert. |

### A5. Character Creator editor UI

| Field | Content |
|---|---|
| Module / Feature | `CharacterGeneratorWidget`, `CharacterGeneratorWorkspace`, "Character Creator" tab and its click-to-place flow — purpose: In-editor UI for the compositor |
| Source Paths | `src/asteria/editor/character_generator_widget.py` (328 lines), `src/asteria/editor/character_generator_workspace.py` (163 lines), wiring in `src/asteria/editor/shell.py` (lines ~110–160, ~469) |
| Current Dependencies | `shell.py`; tests `test_editor_mv_character_creator.py` (11), `test_mv_character_creator_e2e.py` (1, also runs the script in A7), `test_character_generator.py` |
| Original SPEC Requirement | None (cancelled) |
| Replacement Availability | **Available:** shell actions "Place Character from Sprite Sheet…" and "Set Actor Appearance…" plus Inspector pickers (CB14, `tests/test_generic_character_inspector.py`) |
| Regression Risk | The RPG workspace loses the "Character Creator" tab. `viewport.characterCellClicked` placement must stay because the generic placement uses it, so verify before removing `_place_generated_character_at`. |
| Proposed Action | **RETIRE**. Keep the generic click-to-place and route it only through `CharacterVisualSet`. |
| Rollback Plan | Revert restores the tab. Run the GUI smoke tests (`test_editor_shell_surface.py`, `test_generic_character_inspector.py`) before and after. |

### A6. `CreateCharacterCommand` (keep)

| Field | Content |
|---|---|
| Module / Feature | Reversible "visual → Entity + Actor + assets" command — purpose: Generator output placement, generalized in CB14 |
| Source Paths | `src/asteria/editor/create_character_command.py` (204 lines) |
| Current Dependencies | `shell.py:51`; `tests/test_generic_character_inspector.py`, `test_create_character_command.py`, `test_editor_mv_character_creator.py` |
| Original SPEC Requirement | **Yes:** generic Character/Entity presentation (D2, EDT-16) |
| Replacement Availability | It *is* the replacement |
| Regression Risk | Removing it would break CB14 |
| Proposed Action | **KEEP.** If A4 is approved, only remove the `GeneratedCharacterBundle` branch. |
| Rollback Plan | None needed |

### A7. MV Character Creator validation script

| Field | Content |
|---|---|
| Module / Feature | End-to-end validation of the MV-backed Character Creator — purpose: Manual and CI evidence for the Generator workflow |
| Source Paths | `scripts/validate_mv_character_creator.py` (246 lines) |
| Current Dependencies | `tests/test_mv_character_creator_e2e.py` (1) |
| Original SPEC Requirement | None |
| Replacement Availability | Generic placement is covered by `test_generic_character_inspector.py` |
| Regression Risk | None outside the Generator |
| Proposed Action | **RETIRE** with A5 |
| Rollback Plan | Same as A1 |

### A8. Generator-specific tests

| Field | Content |
|---|---|
| Module / Feature | Tests that only exercise A1–A5 and A7 — purpose: Verify the Generator |
| Source Paths | `tests/test_character_generator.py` (5), `test_character_generator_topology.py` (3), `test_character_bundle_generator.py` (10), `test_rpg_maker_mv_generator_catalog.py` (8), `test_editor_mv_character_creator.py` (11), `test_mv_character_creator_e2e.py` (1); the bundle cases in `test_create_character_command.py` (5) |
| Current Dependencies | n/a |
| Original SPEC Requirement | None. **Generic validation (D4 class A) is not on this list and stays unchanged.** |
| Replacement Availability | Generic tests: `test_generic_character_inspector.py`, asset pipeline gates |
| Regression Risk | About 43 fewer tests. The total test count will drop; that is expected and must not be read as a regression. |
| Proposed Action | **RETIRE** with their modules. Port any assertion that covers generic behavior (for example `CreateCharacterCommand` undo/redo and rollback) to bundle-free tests **before** deleting. |
| Rollback Plan | Same as A1 |

### A9. Legacy pygame battle presentation (keep)

| Field | Content |
|---|---|
| Module / Feature | `LegacyPygameBattleAdapter` and the legacy HUD/world drawing in the playable runtime — purpose: the default battle presentation since before CB2 |
| Source Paths | `src/asteria/runtime/battle_presentation_adapters.py` (`LegacyPygameBattleAdapter`), `src/asteria/runtime/playable_test_runtime.py` (`_draw_battle_world`, `_draw_battle_hud`, `_play_fx`) |
| Current Dependencies | Default adapter of `PlayableTestRuntime`; `tests/test_playable_battle_loop.py` (parity test against the canonical adapter), `tests/test_audio_mixer.py` |
| Original SPEC Requirement | S§19/§29 battle presentation (BTL-04, UI-01); the canonical replacement is `CanonicalBattleAdapter` |
| Replacement Availability | **Partial:** the canonical adapter is still being completed (CB2, D14 #1) and has no real-machine validation |
| Regression Risk | High: removing it now leaves the playable game without a verified battle screen |
| Proposed Action | **KEEP** (D14 #6) until the canonical presentation passes real-machine validation; then submit a separate retirement proposal |
| Rollback Plan | n/a (no change proposed) |

### A10. Legacy playable runtime host (keep)

| Field | Content |
|---|---|
| Module / Feature | `PlayableTestRuntime` — purpose: the pygame game host for Run Project and exported games |
| Source Paths | `src/asteria/runtime/playable_test_runtime.py`, `src/asteria/runtime/preview.py` |
| Current Dependencies | Run Project, `asteria-preview`, `asteria-export` launcher, all runtime integration tests |
| Original SPEC Requirement | S§8 runtime loop / platform layer |
| Replacement Availability | None. It is the only runtime host. |
| Regression Risk | Critical |
| Proposed Action | **KEEP** (D14 #6) |
| Rollback Plan | n/a |

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


---

## Part D — Execution record (2026-10-11, conditional approval)

Conditions applied to every item: unused or migrated first; a complete replacement exists and passes tests; the canonical SPEC is unaffected; no generic engine capability is lost. Uncertain → kept and marked BLOCKED.

**Backup:** `/Users/roger/Documents/Vscode/Asteria_backup_2026-10-11_cb15_generator.zip` (18 files, outside the repo).
**Rollback reference:** `git revert 71e76c1` (the single retirement commit); the parent `3c6dd57` is the last state with the Generator.

| Item | Decision | Removed Files | Replacement | Dependency Check | Regression Tests |
|---|---|---|---|---|---|
| A1 compositor | **RETIRED** | `assets/character_generator.py` | `CharacterVisualSet.from_walking_sheet` + `CreateCharacterCommand` (CB14) | no import left in `src/`, `scripts/`, `tests/` (grep); `compileall` clean | full suite 2165 passed; `test_generic_character_inspector.py` (real shell placement from a sprite sheet) |
| A2 topology | **RETIRED** | `assets/character_generator_topology.py` | not needed | only its own test used it | as above |
| A3 MV generator catalog | **RETIRED** | `assets/rpg_maker_mv_generator.py`; lazy export removed from `assets/__init__.py` | MV import stays in the other `rpg_maker_mv_*` adapters | no import left; the remaining `mv_reference` tests pass (23; the other 16 lived in the removed generator test files) | `test_architecture_boundaries.py`, `test_mv_import_playable.py` |
| A4 bundle | **RETIRED** | `assets/character_bundle.py`; `CharacterVisualSet.from_bundle`; the bundle branch of `CreateCharacterCommand` | `CharacterVisualSet` (owned files supported) | existing projects: generated characters are plain canonical assets / actor ids — load unchanged | ported `test_create_character_command.py` (execute, undo/redo identical ids, owned files only, extra owned sheet, rollback at files / assets / actor / entity) |
| A5 Character Creator UI | **RETIRED** | `editor/character_generator_widget.py`, `editor/character_generator_workspace.py`, the RPG "Character Creator" tab, its styles | shell "Place Character from Sprite Sheet…", "Set Actor Appearance…", Inspector pickers; click-to-place kept (`_place_character_at`, `CharacterVisualSet` only) | `test_editor_shell_integration_154a.py` updated (Game Systems is now the second RPG tab) | GUI smoke in the full suite; real Cocoa editor checks re-run in WS7 |
| A6 `CreateCharacterCommand` | **KEPT** (bundle branch removed) | — | it is the replacement | — | ported tests above |
| A7 validation script | **RETIRED** | `scripts/validate_mv_character_creator.py`, `tests/test_mv_character_creator_e2e.py` | W-18 real-window check `mv_import_real_window` covers MV content end to end | no other user | — |
| A8 generator tests | **RETIRED** | `test_character_generator.py`, `test_character_generator_topology.py`, `test_character_bundle_generator.py`, `test_rpg_maker_mv_generator_catalog.py`, `test_editor_mv_character_creator.py` | generic assertions ported first (A4 row) | — | 2206 → 2165 tests: the 41 removed tests covered only removed code |
| A9 legacy battle presentation | **BLOCKED (kept)** | — | `CanonicalBattleAdapter` is real-machine validated, but it still falls back to the legacy world layer (`_draw_battle_world`) for projects without combatant visuals, and `legacy` stays the default adapter for manifests that do not choose one | replacement not complete for those projects | — |
| A10 runtime host | **KEPT** | — | none (only host) | — | — |

**Other candidates reviewed in WS6 (kept):**

| Candidate | Why kept |
|---|---|
| `editor/attachment_authoring.py` (`AttachmentAuthoringModel`) | Generic attachment authoring model (protected: "generic Animation/Attachment"); Character Composition uses the persisted path but the model has its own tests and users |
| `assets/rpg_maker_mv_map_render.py` (`compose_mv_map_draws`) | MV import adapter (Part C, AST-13); `MVTileResolver` is used by the W-18 baker |
| `runtime/reference_runtime.py` | Still the runtime for tile-map projects without a game-start player (e.g. the Reference World); `TileMapField` covers the others |
| `runtime/preview.build_preview_registry` | Public API; now delegates to the single `default_component_registry()` |
